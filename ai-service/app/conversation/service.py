"""Program-owned multi-turn context resolution for EnergyComputeAI V6-A.

Only verified entity resolutions, explicit user assumptions and completed public
tool results enter state.  Candidate mappings, model guesses and failed calls
are intentionally never promoted into the next turn.
"""
from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Callable

from app.finance import FinanceCalculator, FinanceInput, ProvenancedValue, RepaymentMethod, SourceType


_YEAR = re.compile(r"(?<!\d)(20\d{2})(?:年)?")
_FOLLOW_UP = re.compile(r"^(?:那|那么|再|也)?(?:[，,。？！!？\s]*)?(?:20\d{2}年?(?:呢|怎么样|多少)?)$")
_SOURCE_FOLLOW_UP = re.compile(r"(?:这个|该|这)?(?:数字|数据|数值|结论)?.{0,6}(?:哪来的|哪里来的|来源|依据)(?:是什么|呢)?[？?]?$", re.I)
_METRICS = (
    ("rack_occupancy_rate", ("上架率", "入住率", "机柜利用率"), "上架率"),
    ("rack_price", ("平均机柜价格", "机柜价格", "托管价格"), "平均机柜价格"),
    ("pue", ("pue", "电能利用效率"), "PUE"),
)


@dataclass
class TurnRecord:
    question: str
    effective_question: str
    result: dict[str, Any]
    created_at: str


@dataclass
class ConversationState:
    session_id: str
    active_entities: list[dict[str, str]] = field(default_factory=list)
    active_year: int | None = None
    active_metrics: list[str] = field(default_factory=list)
    active_task: str | None = None
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    turns: list[TurnRecord] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    data_version: str = "spdb_power_finance:runtime"
    policy_index_version: str = "public_effective:runtime"
    finance_context_valid: bool = True

    def public_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "active_entities": list(self.active_entities),
            "active_time_range": {"year": self.active_year} if self.active_year else None,
            "active_metrics": list(self.active_metrics),
            "active_task": self.active_task,
            "assumptions": list(self.assumptions),
            "turn_count": len(self.turns),
            "data_version": self.data_version,
            "policy_index_version": self.policy_index_version,
            "valid_for_followup": bool(self.turns),
            "finance_context_valid": self.finance_context_valid,
        }


class ConversationService:
    """In-memory session coordinator; persistence is deliberately a later V6 cut.

    The service keeps no hidden chain-of-thought. It stores user questions,
    final structured tool results and explicit context only.
    """

    def __init__(
        self,
        run_agent: Callable[[str], dict[str, Any]],
        run_due_diligence: Callable[[str], dict[str, Any]] | None = None,
        resolve_entities: Callable[[str], tuple[str, list[dict[str, str]]]] | None = None,
    ) -> None:
        self._run_agent = run_agent
        self._run_due_diligence = run_due_diligence
        self._resolve_entities = resolve_entities
        self._sessions: dict[str, ConversationState] = {}
        self._lock = threading.RLock()

    def run(self, question: str, session_id: str | None = None) -> tuple[ConversationState, dict[str, Any], str]:
        with self._lock:
            state = self._new_state() if session_id is None else self._sessions.get(session_id)
            if state is None:
                raise KeyError("会话不存在或已失效，请重新开始提问。")
            if session_id is None:
                self._sessions[state.session_id] = state
            effective = self._resolve_question(state, question)
            if effective[0] == "LOCAL":
                result = effective[1]
                effective_question = question.strip()
            else:
                effective_question = effective[1]
                result = self._run_agent(effective_question)
            self._update_state(state, question, effective_question, result)
            return state, result, effective_question

    def clear_finance_assumptions(self, session_id: str) -> ConversationState:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                raise KeyError("会话不存在或已失效，请重新开始提问。")
            state.assumptions = []
            # Clearing is an explicit reset: a bare “改成70%” must not revive
            # the former calculation's assumptions from a hidden prior turn.
            state.finance_context_valid = False
            return state

    @staticmethod
    def _new_state() -> ConversationState:
        return ConversationState(session_id=str(uuid.uuid4()))

    def _resolve_question(self, state: ConversationState, question: str) -> tuple[str, Any]:
        clean = question.strip()
        if self._is_due_diligence_request(clean):
            return "LOCAL", self._due_diligence_result(clean, state)
        if state.turns and self._is_due_diligence_follow_up(clean, state.turns[-1].result):
            return "LOCAL", self._due_diligence_follow_up(clean, state.turns[-1].result)
        if state.turns and self._is_finance_modification(clean):
            if state.finance_context_valid:
                return "LOCAL", self._finance_follow_up(clean, state)
            return "LOCAL", self._clarification_result(clean, "融资假设已清除。请重新提供债务比例、利率、期限和逐年 CFADS，再进行测算。")
        if state.turns and _SOURCE_FOLLOW_UP.search(clean):
            return "LOCAL", self._provenance_result(clean, state.turns[-1])
        lowered = clean.casefold()
        if "利用率" in clean and not any(term in lowered for _, terms, _ in _METRICS for term in terms):
            return "LOCAL", self._clarification_result(clean, "“利用率”可能指机柜上架率、GPU 利用率或算力资源利用率。请明确要查询的指标。")
        year_match = _YEAR.search(clean)
        metric = self._metric_for(clean)
        short_year_follow_up = bool(year_match and (_FOLLOW_UP.match(clean) or len(clean) <= 12))
        metric_follow_up = metric is not None and len(clean) <= 14 and not self._has_entity(clean)
        if (short_year_follow_up or metric_follow_up) and state.active_entities:
            name = "、".join(item["name"] for item in state.active_entities)
            inherited_metric = metric or (state.active_metrics[-1] if state.active_metrics else None)
            if inherited_metric is None:
                return "LOCAL", self._clarification_result(clean, "请明确希望延续上一轮的哪项指标。")
            inherited_year = int(year_match.group(1)) if year_match else state.active_year
            label = self._metric_label(inherited_metric)
            year_text = f"{inherited_year}年" if inherited_year else ""
            return "AGENT", f"{name}{year_text}{label}是多少？请仅查询数据库。"
        return "AGENT", clean

    def _update_state(self, state: ConversationState, question: str, effective_question: str, result: dict[str, Any]) -> None:
        if result.get("route") not in {"CLARIFICATION", "PROVENANCE"}:
            router = result.get("router") or {}
            verified = list(router.get("entity_resolution") or [])
            # Resolver output is the only entity source permitted to overwrite state.
            if verified:
                state.active_entities = [
                    {"type": str(item.get("entity_type")), "id": str(item.get("entity_id")), "name": str(item.get("canonical_name"))}
                    for item in verified
                    if item.get("entity_type") and item.get("entity_id") and item.get("canonical_name")
                ]
            year = _YEAR.search(effective_question)
            if year:
                state.active_year = int(year.group(1))
            metrics = self._metrics_for(effective_question)
            if metrics:
                state.active_metrics = metrics
            state.active_task = str(result.get("route") or state.active_task or "UNKNOWN")
            finance = result.get("finance_result") or {}
            if finance.get("inputs"):
                state.assumptions = self._public_assumptions(finance["inputs"])
                state.finance_context_valid = True
            state.turns.append(TurnRecord(question, effective_question, result, datetime.now(UTC).isoformat()))

    @staticmethod
    def _has_entity(question: str) -> bool:
        return any(term in question for term in ("百旺信", "数据中心", "智算中心", "B200", "H800", "项目"))

    @staticmethod
    def _metric_for(question: str) -> str | None:
        lowered = question.casefold()
        for key, terms, _ in _METRICS:
            if any(term in lowered for term in terms):
                return key
        return None

    def _metrics_for(self, question: str) -> list[str]:
        return [key for key, terms, _ in _METRICS if any(term in question.casefold() for term in terms)]

    @staticmethod
    def _metric_label(key: str) -> str:
        return next((label for metric, _, label in _METRICS if metric == key), key)

    @staticmethod
    def _is_finance_modification(question: str) -> bool:
        lowered = question.casefold()
        has_change = any(term in lowered for term in ("改成", "改为", "换成", "调整为"))
        return has_change and ("利率" in lowered or "%" in lowered or "年期" in lowered or "期限" in lowered)

    @staticmethod
    def _is_due_diligence_request(question: str) -> bool:
        lowered = question.casefold()
        return ("初步尽调" in lowered or "做尽调" in lowered or "项目尽调" in lowered) and not any(
            term in lowered for term in ("最大风险", "主要风险", "缺什么资料", "补什么资料")
        )

    @staticmethod
    def _is_due_diligence_follow_up(question: str, previous: dict[str, Any]) -> bool:
        if not previous.get("due_diligence_result"):
            return False
        lowered = question.casefold()
        return any(term in lowered for term in ("最大风险", "主要风险", "风险是什么", "缺什么资料", "缺哪些资料", "补什么资料", "待补材料"))

    def _due_diligence_result(self, question: str, state: ConversationState) -> dict[str, Any]:
        if self._run_due_diligence is None or self._resolve_entities is None:
            return self._clarification_result(question, "当前服务未启用项目初步尽调工具。")
        _, entities = self._resolve_entities(question)
        if len(entities) != 1 or entities[0].get("entity_type") != "FACILITY":
            return self._clarification_result(question, "请明确一个已确认的数据中心项目后再执行初步尽调。")
        due = self._run_due_diligence(str(entities[0]["entity_id"]))
        generated_at = datetime.now(UTC).isoformat()
        due = {
            **due,
            "result_id": f"DD-{uuid.uuid4().hex[:12].upper()}",
            "created_at": generated_at,
            "data_version": state.data_version,
            "policy_index_version": state.policy_index_version,
            "valid_for_followup": True,
        }
        risks = list(due.get("risks") or [])
        high = sum(1 for item in risks if item.get("level") == "HIGH")
        gaps = list(due.get("evidence_gaps") or [])
        answer = (
            f"已为{entities[0]['canonical_name']}生成初步尽调快照：资料完整度为 "
            f"{(due.get('snapshot') or {}).get('data_completeness', {}).get('score', '—')}%；"
            f"确定性风险 {len(risks)} 项（其中高优先级 {high} 项），待补材料 {len(gaps)} 项。"
            "该结果仅供初步尽调辅助，不构成自动授信或最终绿色贷款认定。"
        )
        return {
            "question": question, "route": "DUE_DILIGENCE",
            "router": {"route": "DUE_DILIGENCE", "reason": "已识别单一确认项目，执行 V5 受控初步尽调编排。", "entity_resolution": entities},
            "sql_result": None, "rag_result": None, "interpretation": None,
            "due_diligence_result": due,
            "sources": [{"title": "V5 项目初步尽调快照", "source_filename": "受控 SQL 项目事实与政策规则", "authority_code": "DUE_DILIGENCE", "source_locator": due["result_id"], "supporting_quote": "快照仅使用受控 SQL、固定政策规则和程序化风险/缺口引擎。"}],
            "synthesis": {"claims": list(due.get("claims") or []), "dropped_claims": []},
            "final_answer": answer,
            "warnings": [str(due.get("warning"))] if due.get("warning") else [],
        }

    @staticmethod
    def _due_diligence_follow_up(question: str, previous: dict[str, Any]) -> dict[str, Any]:
        due = previous["due_diligence_result"]
        lowered = question.casefold()
        if any(term in lowered for term in ("最大风险", "主要风险", "风险是什么")):
            priority = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNKNOWN": 3}
            risks = sorted(list(due.get("risks") or []), key=lambda item: priority.get(str(item.get("level")), 4))
            selected = risks[:3]
            if selected:
                text = "；".join(f"{item.get('level')}：{item.get('trigger')}" for item in selected)
                answer = f"基于结果 {due.get('result_id')}，当前优先风险为：{text}。这些是确定性规则提示，仍须结合原始材料人工复核。"
            else:
                answer = f"结果 {due.get('result_id')} 当前未触发风险标记。"
            claim_type = "DUE_DILIGENCE_RISK_REUSE"
        else:
            gaps = list(due.get("evidence_gaps") or [])[:5]
            text = "；".join(str(item.get("required_evidence")) for item in gaps)
            answer = f"基于结果 {due.get('result_id')}，优先待补材料包括：{text or '当前没有待补材料'}。补齐后需重新生成尽调快照。"
            claim_type = "DUE_DILIGENCE_GAP_REUSE"
        return {
            "question": question, "route": "DUE_DILIGENCE_FOLLOW_UP",
            "router": {"route": "DUE_DILIGENCE_FOLLOW_UP", "reason": "复用同一份仍有效的项目尽调结构化结果，未重新执行工具链。"},
            "sql_result": None, "rag_result": None, "interpretation": None, "due_diligence_result": due,
            "sources": list(previous.get("sources") or []),
            "synthesis": {"claims": [{"claim_type": claim_type, "text": answer, "support_ids": [str(due.get("result_id"))]}], "dropped_claims": []},
            "final_answer": answer, "warnings": [str(due.get("warning"))] if due.get("warning") else [],
        }

    @staticmethod
    def _public_assumptions(inputs: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for field in ("debt_ratio", "interest_rate", "loan_term_years", "required_min_dscr"):
            value = inputs.get(field) or {}
            if value.get("source_type") == "ASSUMPTION":
                rows.append({"field": field, "value": value.get("value"), "unit": value.get("unit"), "source_id": value.get("source_id")})
        cfads = inputs.get("annual_cfads") or []
        if cfads and all(item.get("source_type") == "ASSUMPTION" for item in cfads):
            rows.append({"field": "annual_cfads", "value": [item.get("value") for item in cfads], "unit": "CNY", "source_id": "USER:annual_cfads"})
        return rows

    def _finance_follow_up(self, question: str, state: ConversationState) -> dict[str, Any]:
        previous = state.turns[-1].result
        finance = previous.get("finance_result")
        if not finance or not finance.get("inputs"):
            return self._clarification_result(question, "上一轮没有可复用的融资测算。请先提供项目、贷款比例、利率、期限和逐年 CFADS。")
        if "电价" in question:
            return self._clarification_result(question, "当前直接融资测算没有可复用的项目级电价成本输入；请使用项目情景压力测试，并提供或核验能耗与电价口径。")
        try:
            inputs, changed = self._modified_finance_inputs(finance["inputs"], question)
            calculation = FinanceCalculator().calculate(inputs).public_dict()
        except ValueError as exc:
            return self._clarification_result(question, f"无法应用这项融资假设修改：{exc}")
        eligibility = previous.get("eligibility_result") or {}
        result = calculation.get("results") or {}
        changed_text = "、".join(changed)
        answer = (
            f"已在上一轮同一项目、CAPEX 与 CFADS 输入基础上，仅将{changed_text}更新为用户明确值。"
            f"重新计算结果：贷款金额为 {result.get('loan_amount')} CNY；最低 DSCR 为 {result.get('min_dscr')}，"
            f"平均 DSCR 为 {result.get('avg_dscr')}。该结果不构成授信或绿色贷款认定。"
        )
        return {
            "question": question, "route": "FINANCE_FOLLOW_UP",
            "router": {"route": "FINANCE_FOLLOW_UP", "reason": "复用上一轮已核验项目事实与用户明确假设，仅重新执行确定性融资计算。", "entity_resolution": [
                {"entity_type": item["type"], "entity_id": item["id"], "canonical_name": item["name"]} for item in state.active_entities
            ]},
            "sql_result": previous.get("sql_result"), "rag_result": previous.get("rag_result"),
            "interpretation": previous.get("interpretation"), "finance_result": calculation,
            "max_debt_result": None, "eligibility_result": eligibility,
            "sources": list(previous.get("sources") or []),
            "tool_calls": [{"order": 1, "tool": "FINANCE_CALCULATOR", "executed": True, "reused_completed_turn": len(state.turns)}],
            "synthesis": {"claims": [{"claim_type": "CALC_RESULT", "text": answer, "support_ids": [calculation["calculation_id"]]}], "dropped_claims": []},
            "final_answer": answer,
        }

    @staticmethod
    def _modified_finance_inputs(raw: dict[str, Any], question: str) -> tuple[FinanceInput, list[str]]:
        def pv(field: str) -> ProvenancedValue:
            item = raw[field]
            return ProvenancedValue(Decimal(str(item["value"])), str(item["unit"]), SourceType(str(item["source_type"])), str(item["source_id"]))

        debt, rate, term = pv("debt_ratio"), pv("interest_rate"), pv("loan_term_years")
        changed: list[str] = []
        lowered = question.casefold()
        percent = re.search(r"(?:改成|改为|换成|调整为)\s*(\d+(?:\.\d+)?)\s*%", lowered)
        rate_match = re.search(r"利率[^。；，,]{0,12}?(?:改成|改为|换成|调整为)\s*(\d+(?:\.\d+)?)\s*%", lowered)
        term_match = re.search(r"(?:年期|期限)[^。；，,]{0,12}?(?:改成|改为|换成|调整为)\s*(\d+)\s*年", lowered)
        if rate_match:
            rate = ProvenancedValue(Decimal(rate_match.group(1)) / Decimal("100"), "RATIO", SourceType.ASSUMPTION, "USER:interest_rate")
            changed.append(f"年利率（{rate_match.group(1)}%）")
        elif term_match:
            term = ProvenancedValue(Decimal(term_match.group(1)), "YEAR", SourceType.ASSUMPTION, "USER:loan_term_years")
            changed.append(f"贷款期限（{term_match.group(1)}年）")
        elif percent:
            debt = ProvenancedValue(Decimal(percent.group(1)) / Decimal("100"), "RATIO", SourceType.ASSUMPTION, "USER:debt_ratio")
            changed.append(f"债务比例（{percent.group(1)}%）")
        else:
            raise ValueError("请明确“债务比例改成70%”或“利率改成4%”。")
        annual_cfads = tuple(
            ProvenancedValue(Decimal(str(item["value"])), str(item["unit"]), SourceType(str(item["source_type"])), str(item["source_id"]))
            for item in raw.get("annual_cfads") or []
        )
        if len(annual_cfads) != int(term.value):
            raise ValueError("修改期限后，需要同时提供与新期限一致的逐年 CFADS。")
        return FinanceInput(
            project_id=str(raw["project_id"]), capex=pv("capex"), debt_ratio=debt, interest_rate=rate,
            loan_term_years=term, repayment_method=RepaymentMethod(str(raw["repayment_method"])),
            annual_cfads=annual_cfads, required_min_dscr=pv("required_min_dscr"),
        ), changed

    @staticmethod
    def _clarification_result(question: str, message: str) -> dict[str, Any]:
        return {
            "question": question, "route": "CLARIFICATION", "router": {"route": "CLARIFICATION", "reason": "关键指标存在多种会显著改变结果的解释。"},
            "sql_result": None, "rag_result": None, "interpretation": None, "sources": [],
            "synthesis": {"claims": [], "dropped_claims": []}, "final_answer": message,
        }

    @staticmethod
    def _provenance_result(question: str, previous: TurnRecord) -> dict[str, Any]:
        source_result = previous.result
        sql = source_result.get("sql_result")
        sources = list(source_result.get("sources") or [])
        references = list((source_result.get("rag_result") or {}).get("references") or [])
        source_kind = "受控只读 SQL 查询结果" if sql and sql.get("query_result") else "已检索的政策原文"
        answer = f"该结论来自上一轮的{source_kind}。原问题为“{previous.question}”。下方保留同一批来源和结构化结果，未重新执行查询。"
        return {
            "question": question, "route": "PROVENANCE", "router": {"route": "PROVENANCE", "reason": "复用上一轮已完成结果的可追溯证据。"},
            "sql_result": sql, "rag_result": {"references": references} if references else None,
            "interpretation": source_result.get("interpretation"), "sources": sources,
            "synthesis": {"claims": [{"claim_type": "CONVERSATIONAL_PROVENANCE", "text": answer, "support_ids": ["TURN:-1"]}], "dropped_claims": []},
            "final_answer": answer,
        }
