"""V0.3-C controlled SQL + policy-RAG comparison workflow.

Models can retrieve policy text and form the protected SQL statement.  The
cross-source comparison is program-owned so this path cannot turn incomplete
evidence into an automated green-loan or credit decision.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .config import Settings
from .energy_compute import EnergyComputeAgent
from .policy_rag import PolicyRAGAgent


_PUE_PATTERNS = (
    re.compile(
        r"(?:PUE|电能利用效率)[^。；\n]{0,80}?"
        r"(?:降至|不得高于|不高于|≤|小于等于|控制在)\s*([0-9]+(?:\.[0-9]+)?)",
        re.I,
    ),
    re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:以内|以下).{0,20}(?:PUE|电能利用效率)", re.I),
)


class EnergyPolicyBothAgent:
    """Run SQL first, policy RAG second, then ground a narrow PUE comparison."""

    def __init__(
        self,
        settings: Settings,
        sql_agent: EnergyComputeAgent | None = None,
        policy_agent: PolicyRAGAgent | None = None,
    ) -> None:
        self.settings = settings
        self.sql_agent = sql_agent or EnergyComputeAgent(settings)
        self.policy_agent = policy_agent or PolicyRAGAgent(settings)

    def supports(self, question: str) -> bool:
        """Require policy intent, a database signal, and a resolved project.

        This makes generic data-centre policy questions stay RAG-only, rather
        than asking SQL to infer an unspecified facility.
        """

        if not (
            self.policy_agent.supports(question)
            and self.sql_agent.has_sql_fact_signal(question)
        ):
            return False
        _, entities = self.sql_agent.resolver.resolve(question)
        return bool(entities)

    def run(self, question: str) -> dict[str, Any]:
        if not question.strip():
            raise ValueError("问题不能为空。")
        sql_question, entities = self._sql_fact_question(question)
        policy_question = self._policy_question(question)
        sql_run = self.sql_agent.run_sql_fact(sql_question)
        rag_run = self.policy_agent.run(policy_question)
        rag = rag_run.get("rag_result") or {}
        comparison = self._compare_pue(sql_run, rag)

        return {
            "agent_version": "EnergyComputeAI-V0.3-C",
            "question": question.strip(),
            "route": "BOTH",
            "router": {
                "route": "BOTH",
                "reason": "已识别项目实体，且同时需要数据库事实与现行公开政策证据。",
                "entity_resolution": entities,
                "rag_scope": (rag_run.get("router") or {}).get("rag_scope") or [],
            },
            "decomposition": [
                {"order": 1, "kind": "SQL_FACT", "question": sql_question},
                {"order": 2, "kind": "POLICY_RAG", "question": policy_question},
                {"order": 3, "kind": "POLICY_COMPARISON", "method": "deterministic_pue_rule"},
            ],
            "tool_calls": [
                {
                    "order": 1,
                    "tool": "ENERGY_TEXT_TO_SQL",
                    "executed": bool((sql_run.get("sql_result") or {}).get("query_result")),
                },
                {"order": 2, "tool": "POLICY_RAG", "top_k": 5, "access_scope": "PUBLIC+EFFECTIVE"},
                {"order": 3, "tool": "POLICY_COMPARISON", "engine": "deterministic_pue_rule"},
            ],
            "sql_result": sql_run.get("sql_result"),
            "rag_result": rag,
            "interpretation": sql_run.get("interpretation"),
            "policy_comparison": comparison,
            "synthesis": {"claims": self._claims(comparison), "dropped_claims": []},
            "sources": list(sql_run.get("sources") or []),
            "final_answer": self._final_answer(sql_run, rag_run, comparison),
        }

    def _sql_fact_question(self, question: str) -> tuple[str, list[dict[str, str]]]:
        _, entities = self.sql_agent.resolver.resolve(question)
        names = "、".join(item["canonical_name"] for item in entities)
        operation_requested = any(
            term in question
            for term in ("上架率", "入住率", "机柜利用率", "机柜价格", "托管价格")
        )
        year = re.search(r"(?<!\d)(20\d{2})(?!\d)", question)
        if operation_requested:
            year_text = f"{year.group(1)}年" if year else "最新披露期"
            return (
                f"{names}{year_text}的 PUE、上架率和平均机柜价格是多少？请仅查询数据库。"
                "每一项都必须返回 metric_name、metric_scope、metric_value、metric_unit、as_of_date 和 disclosure_status。",
                entities,
            )
        # PUE is the only policy-comparison metric in V0.3-C.  Any broader
        # policy/green-finance conclusion remains outside this program rule.
        subtask = (
            f"{names}的 PUE 是多少？请仅查询数据库，并返回设施名称、metric_scope、"
            "metric_value、metric_unit、as_of_date 和 disclosure_status。"
        )
        return subtask, entities

    @staticmethod
    def _policy_question(question: str) -> str:
        """Remove project-specific eligibility wording before policy retrieval.

        A RAG query such as “某项目是否符合” often correctly returns
        insufficient evidence, because the policy corpus cannot contain that
        project's construction documents.  The BOTH path instead retrieves the
        general threshold and its applicability; the deterministic comparison
        then reports whether the project evidence is sufficient to apply it.
        """

        lowered = question.casefold()
        if "pue" in lowered or "数据中心" in question or "智算" in question:
            region = "深圳现行" if "深圳" in question else "广东现行" if "广东" in question else "现行"
            return f"{region}数据中心 PUE 能效阈值、适用范围以及国家枢纽项目要求是什么？"
        return question.strip()

    @staticmethod
    def _query_rows(sql_run: dict[str, Any]) -> list[dict[str, Any]]:
        query_result = (sql_run.get("sql_result") or {}).get("query_result") or {}
        columns = [str(value) for value in query_result.get("columns") or []]
        return [
            dict(zip(columns, row))
            for row in query_result.get("rows") or []
            if isinstance(row, list)
        ]

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @classmethod
    def _pue_thresholds(cls, rag: dict[str, Any]) -> list[dict[str, Any]]:
        thresholds: list[dict[str, Any]] = []
        for reference in rag.get("references") or []:
            quote = str(reference.get("supporting_quote") or "")
            for pattern in _PUE_PATTERNS:
                for match in pattern.finditer(quote):
                    value = cls._decimal(match.group(1))
                    if value is not None:
                        thresholds.append({"value": value, "quote": quote, "reference": reference})
        unique: list[dict[str, Any]] = []
        for item in thresholds:
            key = (item["value"], item["quote"], item["reference"].get("chunk_id"))
            if not any((old["value"], old["quote"], old["reference"].get("chunk_id")) == key for old in unique):
                unique.append(item)
        return unique

    @staticmethod
    def _scope_matches_policy(metric_scope: str, policy_quote: str) -> bool:
        """Use only scope disclosed by the database, never user implication."""

        scope, quote = metric_scope.casefold(), policy_quote.casefold()
        checks = (
            (("国家枢纽", "national_hub", "hub"), "国家枢纽" in quote),
            (("新建", "new_build", "new"), "新建" in quote),
            (("改扩建", "retrofit", "expansion"), "改扩建" in quote),
            (("大型", "large", "超大型", "mega"), "大型" in quote),
        )
        applicable = [terms for terms, required in checks if required]
        return bool(applicable) and all(any(term in scope for term in terms) for terms in applicable)

    def _compare_pue(self, sql_run: dict[str, Any], rag: dict[str, Any]) -> dict[str, Any]:
        pue_rows = []
        for row in self._query_rows(sql_run):
            code = str(row.get("metric_code") or row.get("metric_name") or "PUE").casefold()
            value = self._decimal(row.get("metric_value"))
            if code == "pue" and value is not None:
                pue_rows.append({"value": value, "scope": str(row.get("metric_scope") or "未披露口径")})
        thresholds = self._pue_thresholds(rag)
        sql_support, rag_support = (["SQL1"] if pue_rows else []), (["R1"] if thresholds else [])
        base: dict[str, Any] = {
            "metric": "PUE",
            "status": "INSUFFICIENT_EVIDENCE",
            "sql_support_ids": sql_support,
            "rag_support_ids": rag_support,
            "support_ids": sql_support + rag_support,
            "project_values": [{"value": str(item["value"]), "metric_scope": item["scope"]} for item in pue_rows],
            "policy_thresholds": [
                {"value": str(item["value"]), "quote": item["quote"], "chunk_id": item["reference"].get("chunk_id")}
                for item in thresholds
            ],
        }
        if not pue_rows:
            base["reason"] = "数据库未返回可核验的 PUE 数值，无法与政策要求比较。"
            return base
        if not thresholds:
            base["reason"] = "本次现行公开政策检索未找到可核验的 PUE 阈值，无法比较。"
            return base
        if len(pue_rows) != 1:
            base["reason"] = "数据库返回多个 PUE 披露口径；问题未指定建设期、机房或设施范围，不能选择其中一项作比较。"
            return base
        matching = [item for item in thresholds if self._scope_matches_policy(pue_rows[0]["scope"], item["quote"])]
        if len(matching) != 1:
            base["reason"] = (
                "政策阈值适用于特定的新建/改扩建、规模或国家枢纽范围；"
                "现有数据库 PUE 披露未提供足以证明该适用范围的项目资料。"
            )
            return base
        threshold = matching[0]
        base.update({
            "threshold": str(threshold["value"]),
            "metric_scope": pue_rows[0]["scope"],
            "status": "MATCH" if pue_rows[0]["value"] <= threshold["value"] else "POTENTIAL_MATCH",
            "reason": "在数据库披露口径与政策适用范围一致的前提下，PUE 单项数值与已检索阈值的程序化比较结果。",
        })
        return base

    @staticmethod
    def _claims(comparison: dict[str, Any]) -> list[dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        if comparison.get("sql_support_ids"):
            values = "、".join(item["value"] for item in comparison.get("project_values") or [])
            claims.append({"claim_type": "SQL_FACT", "text": f"数据库返回 PUE：{values}。", "support_ids": ["SQL1"]})
        if comparison.get("rag_support_ids"):
            quote = (comparison.get("policy_thresholds") or [{}])[0].get("quote", "")
            claims.append({"claim_type": "RAG_EVIDENCE", "text": f"现行公开政策引文：{quote}", "support_ids": ["R1"]})
        claims.append({
            "claim_type": "POLICY_COMPARISON",
            "text": f"PUE 匹配状态：{comparison['status']}。{comparison['reason']}",
            "support_ids": comparison.get("support_ids") or [],
        })
        return claims

    @staticmethod
    def _final_answer(sql_run: dict[str, Any], rag_run: dict[str, Any], comparison: dict[str, Any]) -> str:
        sql_answer = str(sql_run.get("final_answer") or "数据库未返回可用事实。")
        rag_answer = str(rag_run.get("final_answer") or "现行公开政策证据不足。")
        status = comparison["status"]
        if status == "MATCH":
            conclusion = "从 PUE 这一单项指标看，数据库披露值未超过已核验政策阈值；这不是项目整体政策资格或绿色贷款资格的结论。"
        elif status == "POTENTIAL_MATCH":
            conclusion = "PUE 单项数值未满足已核验阈值，或需进一步确认披露期间与政策适用口径；不能据此判断项目整体资格。"
        else:
            conclusion = "现有证据不足以完成 PUE 的政策匹配，不能据此判断项目整体政策资格、绿色贷款资格或授信可行性。"
        return (
            f"结论\n{conclusion}\n\n数据库事实\n{sql_answer}\n\n政策依据\n{rag_answer}"
            f"\n\n匹配分析\n状态：{status}。{comparison['reason']}"
            "\n\n仍需人工核验\n项目建设性质、规模/国家枢纽属性、节能审查材料、指标期间与完整融资资料。"
        )
