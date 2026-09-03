"""Evidence-bounded corporate analysis over registered enterprise records."""

from __future__ import annotations

import re
import json
import os
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from .config import Settings
from .energy_compute import EntityResolver
from .energy_sql import QueryResult, SQLExecutor, SafetyResult, SpdbReadOnlyExecutor, validate_energy_sql
from .value_formatter import format_field, format_percent, label_for


_COMPANY_ID = re.compile(r"^C\d{6}$")
_ANALYSIS_TERMS = (
    "投资优势", "投资风险", "投资建议", "投资价值", "未来几年", "未来", "财务状况",
    "偿债压力", "偿债能力", "融资客户", "项目融资", "授信", "信贷", "债务分析", "负债分析", "值得研究", "经营风险", "优势和风险",
)
_COVERAGE_TERMS = (
    "有哪些数据", "什么数据", "数据存储", "数据有哪些", "已有数据", "目前数据",
    "存了什么", "数据库里有什么", "有哪些资料", "系统里有什么", "数据覆盖",
)
_METRIC_TERMS = {
    "revenue_wanyuan": ("营收", "营业收入", "收入"),
    "total_liabilities_wanyuan": ("总负债", "负债总额", "负债"),
    "total_assets_wanyuan": ("总资产", "资产总额"),
    "net_profit_wanyuan": ("净利润", "利润"),
    "debt_ratio": ("资产负债率", "负债率"),
    "operating_cashflow_wanyuan": ("经营现金流", "经营活动现金流"),
    "passenger_volume": ("客运量", "客流", "客运"),
}
_ENERGY_METRIC_TERMS = {
    "annual_power_kwh": ("年度用电", "年用电", "年度耗电", "年耗电", "年度用电量", "年用电量", "用电量"),
    "annual_electricity_cost_yuan": ("年度电费", "年电费", "用电成本", "电费"),
    "avg_cost_yuan_kwh": ("平均电价", "平均用电价格", "度电价格"),
    "annual_max_demand_kw": ("最大需量", "最大负荷", "最大需求"),
}
_METRIC_LABELS = {
    "revenue_wanyuan": "营业收入", "total_liabilities_wanyuan": "总负债",
    "total_assets_wanyuan": "总资产", "net_profit_wanyuan": "净利润",
    "debt_ratio": "资产负债率", "operating_cashflow_wanyuan": "经营现金流",
    "passenger_volume": "客运量",
    "annual_power_kwh": "年度用电量", "annual_electricity_cost_yuan": "年度电费",
    "avg_cost_yuan_kwh": "平均电价", "annual_max_demand_kw": "年度最大需量",
}


class CorporateNarrator(Protocol):
    """Turns only supplied, already-verified enterprise evidence into prose."""

    def narrate(self, question: str, mode: str, evidence: dict[str, Any], fallback: str) -> tuple[str, dict[str, Any]]: ...


class DeepSeekCorporateNarrator:
    """Evidence-bounded DeepSeek narration with a deterministic safe fallback."""

    _SYSTEM_PROMPT = """你是银行内部 EnergyComputeAI 的企业分析表达层。
只能使用用户消息中给出的“已核验数据”。不得补充外部知识、未给出的数字、客运量、财务数据、债务情况或政策结论。
直接回答用户问题；如果模式是 DATA_COVERAGE，清晰区分“当前已存储的数据”和“当前未存储的数据”。
如果模式是 CORPORATE_ANALYSIS，可以给出系统基于情景数据的研究看法，但必须把模拟/研究情景与真实经营财务分开，并说明不构成最终授信、证券或投资决定。
不要编造来源、页码、数据库字段或具体项目进度。只输出 JSON：{"answer":"简洁中文回答"}。"""

    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

    def narrate(self, question: str, mode: str, evidence: dict[str, Any], fallback: str) -> tuple[str, dict[str, Any]]:
        if not self.api_key:
            return fallback, {"used": False, "reason": "DEEPSEEK_API_KEY_UNAVAILABLE"}
        try:
            from openai import OpenAI

            response = OpenAI(api_key=self.api_key, base_url=self.base_url).chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps({"question": question, "mode": mode, "verified_data": evidence}, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"}, temperature=0, max_tokens=1_200, stream=False,
                extra_body={"thinking": {"type": "disabled"}},
            )
            raw = (response.choices[0].message.content or "").strip()
            payload = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I))
            answer = str(payload.get("answer") or "").strip() if isinstance(payload, dict) else ""
            if not answer or len(answer) > 3_000:
                raise ValueError("企业分析表达层返回了空答案或超长答案。")
            return answer, {
                "used": True, "model": response.model or self.model,
                "usage": response.usage.model_dump() if response.usage else {},
            }
        except Exception as exc:
            return fallback, {"used": False, "reason": type(exc).__name__}


class CorporateAnalysisAgent:
    """Program-owned CORPORATE router, planner and renderer.

    It intentionally uses static, allow-listed SQL rather than LLM-generated
    queries.  Financial facts, scenario outputs and evidence gaps therefore
    remain separately traceable and a scenario can never become a credit view.
    """

    def __init__(
        self,
        settings: Settings,
        executor: SQLExecutor | None = None,
        resolver: EntityResolver | None = None,
        narrator: CorporateNarrator | None = None,
    ) -> None:
        self.executor = executor or SpdbReadOnlyExecutor(settings)
        self.resolver = resolver or EntityResolver()
        self.narrator = narrator or DeepSeekCorporateNarrator()

    def supports(self, question: str) -> bool:
        _, entities = self.resolver.resolve(question)
        return any(item.get("entity_type") == "COMPANY" for item in entities)

    def run(self, question: str) -> dict[str, Any]:
        _, entities = self.resolver.resolve(question)
        companies = [item for item in entities if item.get("entity_type") == "COMPANY"]
        if len(companies) != 1:
            return self._missing_entity(question, entities)
        company = companies[0]
        if not _COMPANY_ID.fullmatch(str(company["entity_id"])):
            raise ValueError("企业实体标识不符合受控查询格式。")
        if any(term in question.casefold() for term in _COVERAGE_TERMS):
            return self._data_coverage(question, company, entities)
        if any(term in question.casefold() for term in _ANALYSIS_TERMS):
            return self._analysis(question, company, entities)
        if self._requested_energy_metrics(question):
            return self._energy_facts(question, company, entities)
        return self._facts(question, company, entities)

    def _data_coverage(self, question: str, company: dict[str, str], entities: list[dict[str, str]]) -> dict[str, Any]:
        company_id = company["entity_id"]
        profile_safety, profile = self._query(self._profile_sql(company_id))
        financial_safety, financial = self._query(self._financial_sql(company_id))
        annual_safety, annual = self._query(self._annual_energy_sql(company_id))
        feature_safety, features = self._query(self._energy_features_sql(company_id))
        observation_safety, observations = self._query(self._bank_observation_sql(company_id))
        opportunity_safety, opportunities = self._query(self._finance_opportunity_sql(company_id))
        assessment_safety, assessments = self._query(self._policy_assessment_sql(company_id))
        snapshot_safety, snapshots = self._query(self._snapshot_sql(company_id))
        passenger_safety, passengers = self._query(self._passenger_sql(company_id))
        inventory = [
            self._inventory_item("企业主数据", "enterprise_profile", profile, "企业名称、属地、所有制、行业、用能/业务标签与核验状态"),
            self._inventory_item("年度财务", "enterprise_financial", financial, "营业收入、利润、资产负债和经营现金流"),
            self._inventory_item("客运运营数据", "enterprise_operational_statistic_v1", passengers, "年度客运量、客流和运营指标"),
            self._inventory_item("年度用电", "v_enterprise_annual_energy_summary", annual, "年度用电量、电费、平均电价、最大需量与数据类型"),
            self._inventory_item("用电特征", "enterprise_energy_features", features, "负荷、峰谷结构、用电量及数据情景/可信度"),
            self._inventory_item("银行观察", "enterprise_bank_observation", observations, "业务机会标签、潜在产品和营销初筛说明"),
            self._inventory_item("项目融资机会", "enterprise_finance_opportunity_v1", opportunities, "储能项目规模、NPV、IRR、DSCR、风险和机会标签"),
            self._inventory_item("政策评估", "enterprise_policy_assessment_v1", assessments, "项目政策适用性、证据状态、待补证据和后续动作"),
            self._inventory_item("分析快照", "analysis_result_snapshot", snapshots, "已保存的储能及融资研究情景输出"),
        ]
        available = [item["category"] for item in inventory if item["status"] == "AVAILABLE"]
        unavailable = [item["category"] for item in inventory if item["status"] != "AVAILABLE"]
        fallback = (
            f"系统当前已为{company['canonical_name']}保存：" + "、".join(available) + "。"
            + (f"当前尚未保存：{'、'.join(unavailable)}。" if unavailable else "")
            + "其中项目融资机会、政策评估和分析快照均属于研究/情景资料，应与经审计财务和实际运营数据区分使用。"
        )
        evidence = {"company": company["canonical_name"], "inventory": inventory}
        answer, narration = self.narrator.narrate(question, "DATA_COVERAGE", evidence, fallback)
        primary_safety, primary_result = profile_safety, profile
        facts = [self._fact("company_name", company["canonical_name"])]
        return self._result(
            question, "CORPORATE_DATA_COVERAGE", "CORPORATE_PROFILE", entities, primary_safety, primary_result,
            answer, facts, [], ["研究/情景数据不能替代经审计财务或实际运营数据。"],
            {"status": "ANSWERED", "data_inventory": inventory, "available_categories": available,
             "unavailable_categories": unavailable},
            extra_sources=[financial_safety, annual_safety, feature_safety, observation_safety, opportunity_safety,
                           assessment_safety, snapshot_safety, passenger_safety], narration=narration,
        )

    def _energy_facts(self, question: str, company: dict[str, str], entities: list[dict[str, str]]) -> dict[str, Any]:
        requested = self._requested_energy_metrics(question)
        year = self._requested_year(question)
        safety, annual = self._query(self._annual_energy_sql(company["entity_id"], year))
        row = self._row(annual)
        if not row:
            suffix = f"{year}年" if year else ""
            answer = f"当前数据库未查询到{company['canonical_name']}{suffix}的年度用电汇总记录。"
            return self._result(
                question, "IN_SCOPE_DATA_MISSING", "CORPORATE_OPERATION", entities, safety, annual, answer, [],
                ["缺少与问题匹配的年度用电汇总记录。"], ["该结果只表示本地受控数据不存在或尚未导入，不代表企业没有用电。"],
                {"status": "IN_SCOPE_DATA_MISSING", "missing_metrics": requested},
            )
        missing = [metric for metric in requested if not row.get(metric)]
        facts = [self._fact(metric, row[metric]) for metric in requested if metric not in missing]
        period = f"{row.get('year')}年"
        available_text = "，".join(f"{item['label']}为{item['value']}" for item in facts)
        answer = f"{company['canonical_name']}{period}{available_text}。"
        if row.get("data_type"):
            answer += f" 数据类型：{row['data_type']}。"
        warnings: list[str] = []
        boundaries: list[str] = []
        if missing:
            labels = "、".join(_METRIC_LABELS[item] for item in missing)
            answer += f" 当前年度汇总记录未提供{labels}。"
            warnings.append(f"当前年度汇总记录未提供 {labels}。")
        if row.get("data_type") != "PUBLIC":
            boundaries.append("该年度数据不是 PUBLIC 口径，使用前应核验其数据类型与统计范围。")
        return self._result(
            question, "CORPORATE_ENERGY_FACT", "CORPORATE_OPERATION", entities, safety, annual, answer, facts,
            warnings, boundaries, {"status": "ANSWERED" if not missing else "PARTIAL", "facts": facts,
                                    "year": row.get("year"), "data_type": row.get("data_type"), "missing_metrics": missing},
        )

    def _facts(self, question: str, company: dict[str, str], entities: list[dict[str, str]]) -> dict[str, Any]:
        requested = self._requested_metrics(question)
        year = self._requested_year(question)
        financial_safety, financial = self._query(self._financial_sql(company["entity_id"], year))
        row = self._row(financial)
        financial_metrics = [metric for metric in requested if metric != "passenger_volume"]
        missing = [metric for metric in financial_metrics if not row or not row.get(metric)]
        available = [metric for metric in financial_metrics if metric not in missing]
        facts = [self._fact(metric, row[metric]) for metric in available] if row else []
        extra_sources: list[SafetyResult] = []
        passenger_row: dict[str, str] = {}
        if "passenger_volume" in requested:
            passenger_safety, passenger = self._query(self._passenger_sql(company["entity_id"], year))
            extra_sources.append(passenger_safety)
            passenger_row = self._row(passenger)
            if passenger_row and passenger_row.get("metric_value"):
                facts.append(self._fact("passenger_volume", passenger_row["metric_value"]))
            else:
                missing.append("passenger_volume")
        if missing:
            labels = "、".join(_METRIC_LABELS[item] for item in missing)
            available_text = "；".join(f"{item['label']}为{item['value']}" for item in facts)
            answer = (
                f"已识别企业为{company['canonical_name']}。该问题属于企业经营分析范围，"
                f"但当前数据库缺少该企业的{labels}可核验记录。"
                + (f"当前可核验数据：{available_text}。" if available_text else "")
                + "当前不会以推测值替代缺失记录。"
            )
            return self._result(
                question, "IN_SCOPE_DATA_MISSING", "CORPORATE_FINANCIAL", entities, financial_safety, financial,
                answer, facts, [f"缺少 {labels} 的企业年度披露或已授权数据。"],
                ["该企业已在主数据中确认；数据缺失不等同于数值为零。"],
                {"status": "IN_SCOPE_DATA_MISSING", "missing_metrics": missing, "facts": facts}, extra_sources=extra_sources,
            )
        fact_year = row.get("financial_year") or passenger_row.get("statistic_year") or "当前"
        answer = f"{company['canonical_name']}{fact_year}年的" + "，".join(
            f"{item['label']}为{item['value']}" for item in facts
        ) + "。"
        is_test = any(str(item.get("data_quality") or "").upper().startswith("SIMULATED_TEST_ONLY") for item in (row, passenger_row))
        warnings = ["以下为 SIMULATED / TEST_ONLY 测试数据，不是企业真实披露。"] if is_test else []
        return self._result(
            question, "CORPORATE_FACT", "CORPORATE_FINANCIAL", entities, financial_safety, financial,
            answer, facts, warnings, [], {"status": "SIMULATED_TEST_ONLY" if is_test else "ANSWERED", "facts": facts}, extra_sources=extra_sources,
        )

    def _analysis(self, question: str, company: dict[str, str], entities: list[dict[str, str]]) -> dict[str, Any]:
        profile_safety, profile = self._query(self._profile_sql(company["entity_id"]))
        snapshot_safety, snapshot = self._query(self._snapshot_sql(company["entity_id"]))
        financial_safety, financial = self._query(self._financial_sql(company["entity_id"]))
        observation_safety, observations = self._query(self._bank_observation_sql(company["entity_id"]))
        opportunity_safety, opportunities = self._query(self._finance_opportunity_sql(company["entity_id"]))
        assessment_safety, assessments = self._query(self._policy_assessment_sql(company["entity_id"]))
        profile_row, snapshot_row, financial_row = self._row(profile), self._row(snapshot), self._row(financial)
        observation_row, opportunity_row = self._row(observations), self._row(opportunities)
        positives: list[str] = []
        risks: list[str] = []
        gaps = ["缺少未来资本开支计划、债务期限结构、利息支出和担保信息。"]
        if profile_row:
            ownership = profile_row.get("ownership_type") or ""
            industry = profile_row.get("industry_name") or ""
            verification = profile_row.get("business_verification_status") or ""
            if ownership or industry:
                positives.append(f"企业画像显示为{ownership or '—'}，所属{industry or '—'}。")
            if verification:
                positives.append(f"主数据核验状态为{verification}。")
        if snapshot_row:
            positives.append(
                f"已存在储能项目研究情景：NPV {self._wanyuan(snapshot_row.get('npv_wanyuan'))}，"
                f"最低 DSCR {snapshot_row.get('base_min_dscr')}。"
            )
            risks.append(
                "该结果为 " + str(snapshot_row.get("data_type") or "研究")
                + " 情景；负荷、电价、接入容量和工程条件仍需核验，不能作为集团真实财务或授信结论。"
            )
            risk_summary = str(snapshot_row.get("risk_summary") or "")
            if risk_summary:
                risks.append(risk_summary)
        if observation_row:
            green_potential = observation_row.get("green_finance_potential") or "—"
            products = observation_row.get("potential_bank_product") or "—"
            positives.append(f"银行观察将绿色金融潜力标记为 {green_potential}，可关注产品为{products}。")
            risks.append("银行观察属于营销初筛标签，不构成授信意见。")
        if opportunity_row:
            positives.append(
                "现有项目机会研究标记为机会等级 " + str(opportunity_row.get("opportunity_level") or "—")
                + "、准备度 " + str(opportunity_row.get("readiness_level") or "—") + "。"
            )
            risks.append(
                "项目机会研究的风险等级为 " + str(opportunity_row.get("risk_level") or "—")
                + "，且数据类型为 " + str(opportunity_row.get("data_type") or "研究情景") + "。"
            )
        assessment_rows = [dict(zip(assessments.columns, row, strict=True)) for row in assessments.rows]
        if assessment_rows:
            partial = sum(item.get("evidence_status") == "PARTIAL" for item in assessment_rows)
            not_collected = sum(item.get("evidence_status") == "NOT_COLLECTED" for item in assessment_rows)
            positives.append(f"已保存 {len(assessment_rows)} 条储能项目政策评估，其中 {partial} 条证据状态为 PARTIAL。")
            if not_collected:
                risks.append(f"仍有 {not_collected} 条政策评估处于 NOT_COLLECTED，需补充项目材料后再判断。")
        credit_indicators = self._credit_indicators(financial_row)
        financial_is_test = str(financial_row.get("data_quality") or "").upper().startswith("SIMULATED_TEST_ONLY")
        if financial_row:
            positives.append(
                f"已载入 {financial_row.get('financial_year')} 年{'模拟测试' if financial_is_test else '企业'}财务记录："
                f"营业收入 {format_field('revenue_wanyuan', financial_row.get('revenue_wanyuan'))}，"
                f"总负债 {format_field('total_liabilities_wanyuan', financial_row.get('total_liabilities_wanyuan'))}，"
                f"资产负债率 {format_field('debt_ratio', financial_row.get('debt_ratio'))}。"
            )
            if financial_is_test:
                risks.append("该年度财务为 SIMULATED / TEST_ONLY 测试情景，只能用于演示指标计算与流程验证。")
            if credit_indicators:
                positives.append(
                    f"程序化测试指标：净利率 {credit_indicators['net_profit_margin']}；"
                    f"经营现金流/总负债 {credit_indicators['operating_cashflow_to_liabilities']}。"
                )
        else:
            gaps.append("缺少集团年度营业收入、总负债、资产负债率、净利润和经营现金流记录。")
            risks.append("当前不能评估集团层面的收入趋势、真实杠杆和偿债现金流。")
        overall = "SIMULATED_TEST_ONLY_CREDIT_REVIEW" if financial_is_test else "FURTHER_RESEARCH_REQUIRED"
        fallback = (
            f"综合判断\n{company['canonical_name']}可作为现有储能项目机会的进一步研究对象，"
            "但当前证据不足以形成集团层面的投资结论、证券建议或银行授信决定。\n\n"
            "有利因素\n- " + "\n- ".join(positives or ["当前仅确认企业主数据，尚无足够经营与财务事实。"])
            + "\n\n主要风险与边界\n- " + "\n- ".join(risks)
            + "\n\n证据缺口\n- " + "\n- ".join(gaps)
            + "\n\n下一步\n优先补充经审计年度财务、客运量、债务期限结构、利息支出、未来资本开支、实际电费账单与项目接入资料，再进行项目融资可行性复核。"
        )
        facts = [
            self._fact("company_name", company["canonical_name"]),
            *([self._fact("npv_wanyuan", snapshot_row["npv_wanyuan"]), self._fact("base_min_dscr", snapshot_row["base_min_dscr"], "最低 DSCR")] if snapshot_row else []),
            *([self._fact(metric, financial_row[metric]) for metric in ("revenue_wanyuan", "total_liabilities_wanyuan", "debt_ratio", "operating_cashflow_wanyuan") if financial_row.get(metric)] if financial_row else []),
        ]
        primary_safety, primary_result = snapshot_safety, snapshot
        if not snapshot.rows:
            primary_safety, primary_result = profile_safety, profile
        evidence = {
            "company": company["canonical_name"], "positive_factors": positives, "risk_factors": risks,
            "evidence_gaps": gaps, "bank_observation": observation_row, "project_opportunity": opportunity_row,
            "financial_record": financial_row, "credit_indicators": credit_indicators,
            "policy_assessment_summary": {"record_count": len(assessment_rows), "partial_evidence": sum(item.get("evidence_status") == "PARTIAL" for item in assessment_rows), "not_collected": sum(item.get("evidence_status") == "NOT_COLLECTED" for item in assessment_rows)},
        }
        answer, narration = self.narrator.narrate(question, "CORPORATE_ANALYSIS", evidence, fallback)
        return self._result(
            question, "CORPORATE_ANALYSIS", "CORPORATE_INVESTMENT", entities, primary_safety, primary_result,
            answer, facts, risks, gaps,
            {"status": overall, "positive_factors": positives, "risk_factors": risks, "evidence_gaps": gaps,
             "financial_data_available": bool(financial_row), "financial_data_test_only": financial_is_test,
             "credit_indicators": credit_indicators, "scenario_data_available": bool(snapshot_row)},
            extra_sources=[financial_safety, profile_safety, observation_safety, opportunity_safety, assessment_safety], narration=narration,
        )

    def _result(
        self, question: str, route: str, subdomain: str, entities: list[dict[str, str]], safety: SafetyResult,
        result: QueryResult, answer: str, facts: list[dict[str, str]], warnings: list[str], boundaries: list[str],
        corporate_result: dict[str, Any], extra_sources: list[SafetyResult] | None = None,
        narration: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        all_safety = [safety, *(extra_sources or [])]
        tables = sorted({table for item in all_safety for table in item.tables})
        sources = [
            {"source_filename": f"spdb_power_finance.{table}", "title": f"企业分析受控 SQL：{table}",
             "authority_code": "DATABASE_FACT", "supporting_quote": "本回答仅使用已执行的只读企业数据查询及程序化分析模板。", "source_locator": table}
            for table in tables
        ]
        tool_calls = [{"order": 1, "tool": "CORPORATE_SQL", "tables": tables, "executed": True}]
        if narration is not None:
            tool_calls.append({"order": 2, "tool": "DEEPSEEK_CORPORATE_NARRATION", "executed": bool(narration.get("used")), "model": narration.get("model"), "reason": narration.get("reason")})
        return {
            "agent_version": "EnergyComputeAI-V6.3-CORPORATE", "question": question.strip(), "route": route,
            "router": {"domain": "CORPORATE", "subdomain": subdomain, "route": route,
                       "reason": "命中已注册企业实体，使用企业受控数据与程序化分析模板。", "entity_resolution": entities},
            "tool_calls": tool_calls,
            "sql_result": {"generated_sql": safety.sql, "model": "PROGRAM_OWNED", "usage": {},
                           "safety": asdict(safety), "query_result": {"columns": result.columns, "rows": result.rows}},
            "corporate_result": corporate_result,
            "interpretation": {"response_mode": subdomain, "answer_status": corporate_result["status"],
                               "primary_conclusion": answer.split("\n\n", 1)[0], "facts": facts,
                               "candidates": [], "warnings": warnings, "boundaries": boundaries},
            "sources": sources, "synthesis": {"claims": [], "dropped_claims": []}, "final_answer": answer,
            "warnings": warnings,
        }

    def _query(self, sql: str) -> tuple[SafetyResult, QueryResult]:
        safety = validate_energy_sql(sql)
        if not safety.safe:
            raise RuntimeError("企业受控 SQL 未通过安全校验：" + "；".join(safety.errors))
        return safety, self.executor.execute(safety.sql)

    @staticmethod
    def _inventory_item(category: str, table: str, result: QueryResult, description: str) -> dict[str, Any]:
        return {"category": category, "table": table, "status": "AVAILABLE" if result.rows else "NOT_STORED",
                "record_count": len(result.rows), "description": description}

    @staticmethod
    def _credit_indicators(financial: dict[str, str]) -> dict[str, str]:
        """Deterministic test indicators; never a credit approval result."""
        try:
            revenue = Decimal(str(financial["revenue_wanyuan"]))
            net_profit = Decimal(str(financial["net_profit_wanyuan"]))
            liabilities = Decimal(str(financial["total_liabilities_wanyuan"]))
            operating_cashflow = Decimal(str(financial["operating_cashflow_wanyuan"]))
            if revenue <= 0 or liabilities <= 0:
                return {}
            return {
                "net_profit_margin": format_percent(net_profit / revenue),
                "operating_cashflow_to_liabilities": format_percent(operating_cashflow / liabilities),
                "calculation_note": "净利率=净利润/营业收入；经营现金流/总负债仅为测试性偿债观察指标，不是授信审批指标。",
            }
        except (InvalidOperation, KeyError, ValueError):
            return {}

    @staticmethod
    def _row(result: QueryResult) -> dict[str, str]:
        return dict(zip(result.columns, result.rows[0], strict=True)) if result.rows else {}

    @staticmethod
    def _requested_metrics(question: str) -> list[str]:
        requested = [metric for metric, terms in _METRIC_TERMS.items() if any(term in question.casefold() for term in terms)]
        return requested or ["revenue_wanyuan", "net_profit_wanyuan", "total_assets_wanyuan", "total_liabilities_wanyuan", "debt_ratio"]

    @staticmethod
    def _requested_energy_metrics(question: str) -> list[str]:
        return [metric for metric, terms in _ENERGY_METRIC_TERMS.items() if any(term in question.casefold() for term in terms)]

    @staticmethod
    def _requested_year(question: str) -> int | None:
        matched = re.search(r"(?<!\d)(20\d{2})(?:年)?", question)
        return int(matched.group(1)) if matched else None

    @staticmethod
    def _fact(key: str, value: str, label: str | None = None) -> dict[str, str]:
        return {"key": key, "label": label or _METRIC_LABELS.get(key, label_for(key)), "value": format_field(key, value) or str(value)}

    @staticmethod
    def _wanyuan(value: str | None) -> str:
        return format_field("npv_wanyuan", value) or (f"{value} 万元" if value else "—")

    @staticmethod
    def _profile_sql(company_id: str) -> str:
        return ("SELECT company_id, company_name, ownership_type, industry_name, power_chain_role, energy_customer_type, "
                "business_verification_status, notes FROM enterprise_profile WHERE company_id='" + company_id + "' LIMIT 1;")

    @staticmethod
    def _financial_sql(company_id: str, year: int | None = None) -> str:
        year_filter = f" AND financial_year={year}" if year is not None else ""
        return ("SELECT company_id, financial_year, revenue_wanyuan, revenue_growth, net_profit_wanyuan, total_assets_wanyuan, "
                "total_liabilities_wanyuan, total_equity_wanyuan, debt_ratio, operating_cashflow_wanyuan, currency, data_quality, "
                "statistical_scope FROM enterprise_financial WHERE company_id='" + company_id + "'" + year_filter + " ORDER BY financial_year DESC LIMIT 2;")

    @staticmethod
    def _passenger_sql(company_id: str, year: int | None = None) -> str:
        year_filter = f" AND statistic_year={year}" if year is not None else ""
        return ("SELECT company_id, statistic_year, metric_code, metric_value, metric_unit, data_type, data_quality, statistical_scope "
                "FROM enterprise_operational_statistic_v1 WHERE company_id='" + company_id + "' AND metric_code='PASSENGER_VOLUME'"
                + year_filter + " ORDER BY statistic_year DESC LIMIT 1;")

    @staticmethod
    def _annual_energy_sql(company_id: str, year: int | None = None) -> str:
        year_filter = f" AND year={year}" if year is not None else ""
        return ("SELECT company_id, year, annual_power_kwh, annual_electricity_cost_yuan, avg_cost_yuan_kwh, annual_max_demand_kw, data_type "
                "FROM v_enterprise_annual_energy_summary WHERE company_id='" + company_id + "'" + year_filter + " ORDER BY year DESC LIMIT 2;")

    @staticmethod
    def _energy_features_sql(company_id: str) -> str:
        return ("SELECT company_id, analysis_year, annual_power_kwh, avg_price_yuan_kwh, max_load_kw, peak_plus_critical_ratio, data_type, feature_confidence "
                "FROM enterprise_energy_features WHERE company_id='" + company_id + "' ORDER BY analysis_year DESC LIMIT 2;")

    @staticmethod
    def _bank_observation_sql(company_id: str) -> str:
        return ("SELECT company_id, as_of_date, project_finance_potential, green_finance_potential, bankability_score, potential_bank_product, scenario_basis "
                "FROM enterprise_bank_observation WHERE company_id='" + company_id + "' ORDER BY as_of_date DESC LIMIT 1;")

    @staticmethod
    def _finance_opportunity_sql(company_id: str) -> str:
        return ("SELECT company_id, analysis_year, project_capex_wanyuan, project_npv_wanyuan, project_irr, base_min_dscr, max_feasible_debt_ratio, "
                "opportunity_level, readiness_level, risk_level, opportunity_reason, key_risk_notes, next_action, data_type "
                "FROM enterprise_finance_opportunity_v1 WHERE company_id='" + company_id + "' ORDER BY analysis_year DESC LIMIT 1;")

    @staticmethod
    def _policy_assessment_sql(company_id: str) -> str:
        return ("SELECT company_id, assessment_scope, applicability_status, evidence_status, missing_evidence, model_gate_status, resulting_action, assessment_confidence "
                "FROM enterprise_policy_assessment_v1 WHERE company_id='" + company_id + "' ORDER BY assessed_at DESC LIMIT 20;")

    @staticmethod
    def _snapshot_sql(company_id: str) -> str:
        return ("SELECT company_id, company_name, analysis_date, data_type, storage_power_mw, storage_capacity_mwh, capex_wanyuan, "
                "npv_wanyuan, irr, base_min_dscr, max_debt_ratio, financing_status, overall_risk, recommended_product, "
                "recommendation_text, risk_summary FROM analysis_result_snapshot WHERE company_id='" + company_id + "' "
                "ORDER BY analysis_date DESC, snapshot_id DESC LIMIT 1;")

    @staticmethod
    def _missing_entity(question: str, entities: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "question": question.strip(), "route": "IN_SCOPE_DATA_MISSING",
            "router": {"domain": "CORPORATE", "subdomain": "CORPORATE_PROFILE", "route": "IN_SCOPE_DATA_MISSING",
                       "reason": "企业分析问题未匹配到已注册、可核验的企业实体。", "entity_resolution": entities},
            "sql_result": None, "interpretation": {"response_mode": "CORPORATE_PROFILE", "answer_status": "IN_SCOPE_DATA_MISSING",
                "primary_conclusion": "该问题属于企业分析范围，但未找到可核验的企业实体。", "facts": [], "candidates": [], "warnings": [],
                "boundaries": ["请提供企业全称、统一社会信用代码或将该企业录入受控主数据。"]},
            "corporate_result": {"status": "IN_SCOPE_DATA_MISSING", "missing_metrics": ["company_identity"]},
            "sources": [], "synthesis": {"claims": [], "dropped_claims": []},
            "final_answer": "该问题属于企业分析范围，但当前数据库未找到可核验的企业实体。请提供企业全称、统一社会信用代码或补充受控主数据。",
            "warnings": [],
        }
