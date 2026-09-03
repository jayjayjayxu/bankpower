"""Evidence-bounded corporate analysis over registered enterprise records."""

from __future__ import annotations

import re
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from typing import Any

from .config import Settings
from .energy_compute import EntityResolver
from .energy_sql import QueryResult, SQLExecutor, SafetyResult, SpdbReadOnlyExecutor, validate_energy_sql
from .value_formatter import format_field


_COMPANY_ID = re.compile(r"^C\d{6}$")
_ANALYSIS_TERMS = (
    "投资优势", "投资风险", "投资建议", "投资价值", "未来几年", "未来", "财务状况",
    "偿债压力", "融资客户", "项目融资", "值得研究", "经营风险", "优势和风险",
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
_METRIC_LABELS = {
    "revenue_wanyuan": "营业收入", "total_liabilities_wanyuan": "总负债",
    "total_assets_wanyuan": "总资产", "net_profit_wanyuan": "净利润",
    "debt_ratio": "资产负债率", "operating_cashflow_wanyuan": "经营现金流",
    "passenger_volume": "客运量",
}


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
    ) -> None:
        self.executor = executor or SpdbReadOnlyExecutor(settings)
        self.resolver = resolver or EntityResolver()

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
        if any(term in question.casefold() for term in _ANALYSIS_TERMS):
            return self._analysis(question, company, entities)
        return self._facts(question, company, entities)

    def _facts(self, question: str, company: dict[str, str], entities: list[dict[str, str]]) -> dict[str, Any]:
        requested = self._requested_metrics(question)
        financial_safety, financial = self._query(self._financial_sql(company["entity_id"]))
        row = self._row(financial)
        missing = [metric for metric in requested if metric == "passenger_volume" or not row or not row.get(metric)]
        available = [metric for metric in requested if metric not in missing]
        facts = [self._fact(metric, row[metric]) for metric in available] if row else []
        if missing:
            labels = "、".join(_METRIC_LABELS[item] for item in missing)
            available_text = "；".join(f"{item['label']}为{item['value']}" for item in facts)
            answer = (
                f"已识别企业为{company['canonical_name']}。该问题属于企业经营分析范围，"
                f"但当前数据库缺少该企业的{labels}可核验记录。"
                + (f"当前可核验数据：{available_text}。" if available_text else "")
                + "客运量也尚未建立受控数据表，不能以推测值替代。"
            )
            return self._result(
                question, "IN_SCOPE_DATA_MISSING", "CORPORATE_FINANCIAL", entities, financial_safety, financial,
                answer, facts, [f"缺少 {labels} 的企业年度披露或已授权数据。"],
                ["该企业已在主数据中确认；数据缺失不等同于数值为零。"],
                {"status": "IN_SCOPE_DATA_MISSING", "missing_metrics": missing, "facts": facts},
            )
        answer = f"{company['canonical_name']}{row['financial_year']}年的" + "，".join(
            f"{item['label']}为{item['value']}" for item in facts
        ) + "。"
        return self._result(
            question, "CORPORATE_FACT", "CORPORATE_FINANCIAL", entities, financial_safety, financial,
            answer, facts, [], [], {"status": "ANSWERED", "facts": facts},
        )

    def _analysis(self, question: str, company: dict[str, str], entities: list[dict[str, str]]) -> dict[str, Any]:
        profile_safety, profile = self._query(self._profile_sql(company["entity_id"]))
        snapshot_safety, snapshot = self._query(self._snapshot_sql(company["entity_id"]))
        financial_safety, financial = self._query(self._financial_sql(company["entity_id"]))
        profile_row, snapshot_row, financial_row = self._row(profile), self._row(snapshot), self._row(financial)
        positives: list[str] = []
        risks: list[str] = []
        gaps = ["缺少集团2024年营业收入、总负债、资产负债率、净利润和经营现金流的可核验记录。", "缺少客运量及未来资本开支计划的受控数据。"]
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
        if financial_row:
            positives.append(f"数据库存在 {financial_row.get('financial_year')} 年企业财务记录，可继续开展年度比较。")
        else:
            risks.append("当前不能评估集团层面的收入趋势、真实杠杆和偿债现金流。")
        overall = "FURTHER_RESEARCH_REQUIRED"
        answer = (
            f"综合判断\n{company['canonical_name']}可作为现有储能项目机会的进一步研究对象，"
            "但当前证据不足以形成集团层面的投资结论、证券建议或银行授信决定。\n\n"
            "有利因素\n- " + "\n- ".join(positives or ["当前仅确认企业主数据，尚无足够经营与财务事实。"])
            + "\n\n主要风险与边界\n- " + "\n- ".join(risks)
            + "\n\n证据缺口\n- " + "\n- ".join(gaps)
            + "\n\n下一步\n优先补充经审计年度财务、客运量、债务期限结构、未来资本开支、实际电费账单与项目接入资料，再进行项目融资可行性复核。"
        )
        facts = [
            self._fact("company_name", company["canonical_name"]),
            *([self._fact("npv_wanyuan", snapshot_row["npv_wanyuan"]), self._fact("base_min_dscr", snapshot_row["base_min_dscr"], "最低 DSCR")] if snapshot_row else []),
        ]
        primary_safety, primary_result = snapshot_safety, snapshot
        if not snapshot.rows:
            primary_safety, primary_result = profile_safety, profile
        return self._result(
            question, "CORPORATE_ANALYSIS", "CORPORATE_INVESTMENT", entities, primary_safety, primary_result,
            answer, facts, risks, gaps,
            {"status": overall, "positive_factors": positives, "risk_factors": risks, "evidence_gaps": gaps,
             "financial_data_available": bool(financial_row), "scenario_data_available": bool(snapshot_row)},
            extra_sources=[financial_safety, profile_safety],
        )

    def _result(
        self, question: str, route: str, subdomain: str, entities: list[dict[str, str]], safety: SafetyResult,
        result: QueryResult, answer: str, facts: list[dict[str, str]], warnings: list[str], boundaries: list[str],
        corporate_result: dict[str, Any], extra_sources: list[SafetyResult] | None = None,
    ) -> dict[str, Any]:
        all_safety = [safety, *(extra_sources or [])]
        tables = sorted({table for item in all_safety for table in item.tables})
        sources = [
            {"source_filename": f"spdb_power_finance.{table}", "title": f"企业分析受控 SQL：{table}",
             "authority_code": "DATABASE_FACT", "supporting_quote": "本回答仅使用已执行的只读企业数据查询及程序化分析模板。", "source_locator": table}
            for table in tables
        ]
        return {
            "agent_version": "EnergyComputeAI-V6.3-CORPORATE", "question": question.strip(), "route": route,
            "router": {"domain": "CORPORATE", "subdomain": subdomain, "route": route,
                       "reason": "命中已注册企业实体，使用企业受控数据与程序化分析模板。", "entity_resolution": entities},
            "tool_calls": [{"order": 1, "tool": "CORPORATE_SQL", "tables": tables, "executed": True}],
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
    def _row(result: QueryResult) -> dict[str, str]:
        return dict(zip(result.columns, result.rows[0], strict=True)) if result.rows else {}

    @staticmethod
    def _requested_metrics(question: str) -> list[str]:
        requested = [metric for metric, terms in _METRIC_TERMS.items() if any(term in question.casefold() for term in terms)]
        return requested or ["revenue_wanyuan", "net_profit_wanyuan", "total_assets_wanyuan", "total_liabilities_wanyuan", "debt_ratio"]

    @staticmethod
    def _fact(key: str, value: str, label: str | None = None) -> dict[str, str]:
        return {"key": key, "label": label or _METRIC_LABELS.get(key, key), "value": format_field(key, value) or str(value)}

    @staticmethod
    def _wanyuan(value: str | None) -> str:
        return format_field("npv_wanyuan", value) or (f"{value} 万元" if value else "—")

    @staticmethod
    def _profile_sql(company_id: str) -> str:
        return ("SELECT company_id, company_name, ownership_type, industry_name, power_chain_role, energy_customer_type, "
                "business_verification_status, notes FROM enterprise_profile WHERE company_id='" + company_id + "' LIMIT 1;")

    @staticmethod
    def _financial_sql(company_id: str) -> str:
        return ("SELECT company_id, financial_year, revenue_wanyuan, revenue_growth, net_profit_wanyuan, total_assets_wanyuan, "
                "total_liabilities_wanyuan, total_equity_wanyuan, debt_ratio, operating_cashflow_wanyuan, currency, data_quality, "
                "statistical_scope FROM enterprise_financial WHERE company_id='" + company_id + "' ORDER BY financial_year DESC LIMIT 2;")

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
