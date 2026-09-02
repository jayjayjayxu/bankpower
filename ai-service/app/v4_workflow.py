"""V4.0-C fixed orchestration for project finance and policy-rule questions.

This workflow deliberately has no LLM planner.  It preserves the V0.3 public
routes while running the permitted tools in a fixed, auditable order.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .config import Settings
from .eligibility import EligibilityEngine, ProjectFact, load_rule_catalog, validate_evidence_references
from .energy_compute import EnergyComputeAgent
from .finance import FinanceCalculator, FinanceInput, ProvenancedValue, RepaymentMethod, SourceType, calculate_max_debt_ratio
from .policy_rag import PolicyRAGAgent


_RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"
_RULE_CATALOG_PATH = _RESOURCE_DIR / "eligibility_rules_v04.json"
_CORPUS_PATH = Path(__file__).resolve().parents[1] / "runtime" / "policy_corpus" / "public_effective" / "chunks.jsonl"
_FINANCE_TERMS = ("贷款", "融资", "债务", "dscr", "偿债", "利率", "年期", "期限", "cfads")
_ELIGIBILITY_TERMS = ("绿色贷款", "绿色金融", "资格", "符合", "条件", "缺哪些", "还缺")


class V4ProjectWorkflow:
    """Execute SQL → RAG → Finance → Eligibility → program-owned answer."""

    def __init__(
        self,
        settings: Settings,
        sql_agent: EnergyComputeAgent | None = None,
        policy_agent: PolicyRAGAgent | None = None,
    ) -> None:
        self.settings = settings
        self.sql_agent = sql_agent or EnergyComputeAgent(settings)
        self.policy_agent = policy_agent or PolicyRAGAgent(settings)
        self.rule_catalog_version, self.rules = load_rule_catalog(_RULE_CATALOG_PATH)
        validate_evidence_references(self.rules, _CORPUS_PATH)
        self.eligibility_engine = EligibilityEngine()
        self.finance_calculator = FinanceCalculator()
        self._policy_records = self._load_policy_records()

    def supports(self, question: str) -> bool:
        lowered = question.casefold()
        if not (any(term in lowered for term in _FINANCE_TERMS) or any(term in lowered for term in _ELIGIBILITY_TERMS)):
            return False
        # An absolute approval request without scenario inputs stays on the
        # existing safe boundary.  When the user supplies a scenario, V4 can
        # still return its traceable calculation and rule gaps (not approval).
        if any(term in lowered for term in ("一定", "最终", "直接")) and not any(
            term in lowered for term in ("按", "利率", "年期", "期限", "cfads")
        ):
            return False
        _, entities = self.sql_agent.resolver.resolve(question)
        return bool(entities)

    def run(self, question: str) -> dict[str, Any]:
        if not question.strip():
            raise ValueError("问题不能为空。")
        sql_question, entities = self._sql_question(question)
        policy_question = self._policy_question(question)
        sql_run = self.sql_agent.run_sql_fact(sql_question)
        rag_run = self.policy_agent.run(policy_question)
        facts = self._project_facts(sql_run)
        project_id = entities[0]["entity_id"] if len(entities) == 1 else "MULTI_PROJECT"
        finance_result, max_debt_result, finance_boundary = self._finance(question, project_id, facts)
        eligibility = self.eligibility_engine.evaluate(
            project_id=project_id,
            rule_catalog_version=self.rule_catalog_version,
            rules=self.rules,
            facts=facts,
        )
        eligibility_public = eligibility.public_dict()
        sources = list(sql_run.get("sources") or []) + self._rule_sources()
        claims = self._claims(sql_run, rag_run, finance_result, max_debt_result, eligibility_public)
        tool_calls = [
            {"order": 1, "tool": "ENERGY_TEXT_TO_SQL", "executed": bool((sql_run.get("sql_result") or {}).get("query_result"))},
            {"order": 2, "tool": "POLICY_RAG", "top_k": 5, "access_scope": "PUBLIC+EFFECTIVE"},
            {"order": 3, "tool": "FINANCE_CALCULATOR", "executed": finance_result is not None},
            {"order": 4, "tool": "POLICY_ELIGIBILITY_ENGINE", "executed": True, "rule_catalog_version": self.rule_catalog_version},
            {"order": 5, "tool": "CLAIM_GROUNDING", "executed": True},
            {"order": 6, "tool": "ANSWER_RENDERER", "executed": True},
        ]
        return {
            "agent_version": "EnergyComputeAI-V4.0-C",
            "question": question.strip(),
            "route": "BOTH",
            "router": {
                "route": "BOTH",
                "reason": "已识别项目实体，问题同时涉及项目事实、政策资格或融资测算；使用 V4 固定工具链。",
                "entity_resolution": entities,
                "tool_plan": ["SQL", "POLICY_RAG", "FINANCE", "ELIGIBILITY", "CLAIM_GROUNDING", "ANSWER_RENDERER"],
            },
            "decomposition": [
                {"order": 1, "kind": "SQL_FACT", "question": sql_question},
                {"order": 2, "kind": "POLICY_RAG", "question": policy_question},
                {"order": 3, "kind": "FINANCE", "status": "executed" if finance_result else "insufficient_inputs"},
                {"order": 4, "kind": "ELIGIBILITY", "rule_catalog_version": self.rule_catalog_version},
            ],
            "tool_calls": tool_calls,
            "sql_result": sql_run.get("sql_result"),
            "rag_result": rag_run.get("rag_result"),
            "interpretation": sql_run.get("interpretation"),
            "policy_comparison": None,
            "finance_result": finance_result,
            "max_debt_result": max_debt_result,
            "finance_boundary": finance_boundary,
            "eligibility_result": eligibility_public,
            "synthesis": {"claims": claims, "dropped_claims": []},
            "sources": sources,
            "final_answer": self._final_answer(finance_result, max_debt_result, finance_boundary, eligibility_public),
        }

    def _sql_question(self, question: str) -> tuple[str, list[dict[str, str]]]:
        _, entities = self.sql_agent.resolver.resolve(question)
        names = "、".join(item["canonical_name"] for item in entities)
        return (
            f"{names} 的 CAPEX、PUE、GREEN_POWER_RATIO 及其披露口径分别是什么？请仅查询数据库。"
            "每项返回 metric_code、metric_scope、metric_value、metric_unit、source_id、as_of_date 和 disclosure_status。",
            entities,
        )

    @staticmethod
    def _policy_question(question: str) -> str:
        return "现行公开政策中，数据中心项目的节能审查、PUE、服务器能效和可再生能源利用方案有哪些要求？请引用原文并说明适用范围。"

    @staticmethod
    def _rows(sql_run: dict[str, Any]) -> list[dict[str, Any]]:
        query = (sql_run.get("sql_result") or {}).get("query_result") or {}
        columns = [str(item) for item in query.get("columns") or []]
        return [dict(zip(columns, row)) for row in query.get("rows") or [] if isinstance(row, list)]

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _project_facts(self, sql_run: dict[str, Any]) -> dict[str, ProjectFact]:
        facts: dict[str, ProjectFact] = {}
        for row in self._rows(sql_run):
            metric = str(row.get("metric_code") or row.get("metric_name") or "").upper()
            value = self._decimal(row.get("metric_value"))
            unit = str(row.get("metric_unit") or "")
            source_id = str(row.get("source_id") or f"SQL:query_result:{metric}")
            if metric == "CAPEX" and value is not None:
                if unit == "WANYUAN":
                    value, unit = value * Decimal("10000"), "CNY"
                if unit == "CNY":
                    facts["capex"] = ProjectFact(value, "CNY", SourceType.FACT, f"SQL:{source_id}")
            elif metric == "PUE" and value is not None:
                facts["pue"] = ProjectFact(value, "RATIO", SourceType.FACT, f"SQL:{source_id}")
            elif metric == "GREEN_POWER_RATIO" and value is not None:
                facts["green_power_ratio"] = ProjectFact(value, "RATIO", SourceType.FACT, f"SQL:{source_id}")
        return facts

    def _finance(
        self, question: str, project_id: str, facts: dict[str, ProjectFact]
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
        assumptions, missing = self._finance_assumptions(question)
        if "capex" not in facts:
            missing.insert(0, "数据库未返回可核验的 CAPEX")
        if missing:
            return None, None, "未执行融资测算：" + "；".join(dict.fromkeys(missing)) + "。"
        capex = facts["capex"]
        term = int(assumptions["term"])
        inputs = FinanceInput(
            project_id=project_id,
            capex=ProvenancedValue(capex.value, "CNY", capex.source_type, capex.source_id),
            debt_ratio=ProvenancedValue(assumptions["debt_ratio"], "RATIO", SourceType.ASSUMPTION, "USER:debt_ratio"),
            interest_rate=ProvenancedValue(assumptions["interest_rate"], "RATIO", SourceType.ASSUMPTION, "USER:interest_rate"),
            loan_term_years=ProvenancedValue(Decimal(term), "YEAR", SourceType.ASSUMPTION, "USER:loan_term_years"),
            repayment_method=RepaymentMethod.EQUAL_PRINCIPAL,
            annual_cfads=tuple(
                ProvenancedValue(value, "CNY", SourceType.ASSUMPTION, f"USER:annual_cfads:{index}")
                for index, value in enumerate(assumptions["cfads"], 1)
            ),
            required_min_dscr=ProvenancedValue(assumptions["required_min_dscr"], "RATIO", SourceType.ASSUMPTION, assumptions["dscr_source"]),
        )
        result = self.finance_calculator.calculate(inputs)
        maximum = calculate_max_debt_ratio(inputs).public_dict() if any(term in question.casefold() for term in ("最大", "最高", "可承受", "贷款比例")) else None
        return result.public_dict(), maximum, None

    @staticmethod
    def _finance_assumptions(question: str) -> tuple[dict[str, Any], list[str]]:
        text = question.casefold()
        missing: list[str] = []

        def ratio(pattern: str, name: str) -> Decimal | None:
            match = re.search(pattern, text, re.I)
            if not match:
                missing.append(name)
                return None
            return Decimal(match.group(1)) / Decimal("100")

        debt_ratio = ratio(r"(?:按\s*)?(\d+(?:\.\d+)?)\s*%\s*(?:贷款|债务|融资)", "贷款/债务比例")
        interest_rate = ratio(r"(\d+(?:\.\d+)?)\s*%\s*(?:年)?利率", "年利率")
        term_match = re.search(r"(?<!\d)(\d+)\s*年(?:期|期限)?", text)
        if not term_match:
            missing.append("贷款期限")
            term = None
        else:
            term = Decimal(term_match.group(1))
        cfads_match = re.search(r"(?:cfads|现金流)[^。；\n]{0,240}?分别为?\s*([\d、，,\s.]+)\s*万元", text, re.I)
        cfads: list[Decimal] = []
        if cfads_match:
            values = [item for item in re.split(r"[、，,\s]+", cfads_match.group(1).strip()) if item]
            try:
                cfads = [Decimal(item) * Decimal("10000") for item in values]
            except InvalidOperation:
                missing.append("可解析的逐年 CFADS")
        else:
            missing.append("逐年 CFADS（需明确为假设或经核验现金流）")
        if term is not None and cfads and len(cfads) != int(term):
            missing.append("CFADS 年数必须与贷款期限一致")
        dscr_match = re.search(r"(?:最低|门槛)\s*dscr\s*(?:为|=)?\s*(\d+(?:\.\d+)?)", text, re.I)
        required = Decimal(dscr_match.group(1)) if dscr_match else Decimal("1.20")
        return {
            "debt_ratio": debt_ratio,
            "interest_rate": interest_rate,
            "term": term,
            "cfads": cfads,
            "required_min_dscr": required,
            "dscr_source": "USER:required_min_dscr" if dscr_match else "SYSTEM_ASSUMPTION:required_min_dscr_1.20",
        }, missing

    def _rule_sources(self) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rule in self.rules:
            chunk_id = rule.evidence.evidence_chunk_id
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            record = self._policy_records.get(chunk_id, {})
            sources.append({
                "source_filename": record.get("source_filename") or rule.evidence.policy_id,
                "title": record.get("title") or rule.evidence.policy_id,
                "authority_code": record.get("authority_code"),
                "supporting_quote": rule.evidence.source_excerpt,
                "source_locator": chunk_id,
                "page_start": record.get("page_start"), "page_end": record.get("page_end"),
                "issuing_authority": record.get("issuing_authority"), "policy_level": record.get("policy_level"),
                "status": record.get("status"), "region": record.get("region"),
                "effective_date": record.get("effective_date"), "expiry_date": record.get("expiry_date"),
            })
        return sources

    @staticmethod
    def _load_policy_records() -> dict[str, dict[str, Any]]:
        try:
            return {
                str(item["chunk_id"]): item
                for item in (json.loads(line) for line in _CORPUS_PATH.read_text(encoding="utf-8").splitlines() if line.strip())
            }
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("无法加载 V4 资格规则的政策证据索引。") from exc

    @staticmethod
    def _claims(
        sql_run: dict[str, Any], rag_run: dict[str, Any], finance: dict[str, Any] | None,
        maximum: dict[str, Any] | None, eligibility: dict[str, Any],
    ) -> list[dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        if (sql_run.get("sql_result") or {}).get("query_result"):
            claims.append({"claim_type": "SQL_FACT", "text": "项目事实来自受控只读 SQL 查询。", "support_ids": ["SQL1"]})
        if (rag_run.get("rag_result") or {}).get("references"):
            claims.append({"claim_type": "RAG_EVIDENCE", "text": "政策原文来自现行公开政策检索。", "support_ids": ["R1"]})
        if finance:
            claims.append({"claim_type": "CALC_RESULT", "text": f"贷款金额为 {finance['results']['loan_amount']} CNY，最低 DSCR 为 {finance['results']['min_dscr']}。", "support_ids": [finance["calculation_id"]]})
        if maximum:
            claims.append({"claim_type": "CALC_RESULT", "text": f"最大债务比例为 {maximum['max_debt_ratio']}。", "support_ids": [maximum.get("calculation_id") or "CALC:max_debt_ratio"]})
        claims.append({"claim_type": "RULE_EVALUATION", "text": f"已载入规则的总体状态为 {eligibility['overall_status']}。", "support_ids": [f"RULE:{item['rule_id']}" for item in eligibility["evaluations"]]})
        return claims

    @staticmethod
    def _final_answer(
        finance: dict[str, Any] | None, maximum: dict[str, Any] | None,
        finance_boundary: str | None, eligibility: dict[str, Any],
    ) -> str:
        if finance:
            result = finance["results"]
            finance_text = (
                f"按已提供假设，贷款金额为 {result['loan_amount']} CNY；"
                f"最低 DSCR 为 {result['min_dscr']}，平均 DSCR 为 {result['avg_dscr']}。"
            )
            if maximum:
                finance_text += f" 在当前 CFADS 与最低 DSCR 门槛下，程序搜索的最大债务比例为 {maximum['max_debt_ratio']}。"
        else:
            finance_text = finance_boundary or "未请求融资测算。"
        summary = eligibility.get("summary") or {}
        return (
            "结论\n"
            f"{finance_text}\n"
            f"规则核验状态：{eligibility['overall_status']}（MET {summary.get('MET', 0)} 项，"
            f"UNMET {summary.get('UNMET', 0)} 项，UNKNOWN {summary.get('UNKNOWN', 0)} 项，"
            f"NOT_APPLICABLE {summary.get('NOT_APPLICABLE', 0)} 项）。\n\n"
            "依据\n数据库事实、现行公开政策原文、程序计算结果和规则逐项判断均已分别保留来源。\n\n"
            "风险提示\n上述结果不构成绿色贷款认定、银行最终授信审批或融资建议；UNKNOWN 需要以项目资料和人工尽调补齐。"
        )
