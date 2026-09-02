"""V5-D fixed initial due-diligence orchestration."""
from __future__ import annotations
from decimal import Decimal
from typing import Any
from app.config import Settings
from app.eligibility import EligibilityEngine, ProjectFact, load_rule_catalog
from app.finance.models import SourceType
from .risk_engine import EvidenceGapAnalyzer, RiskEngine
from .snapshot import ProjectSnapshotBuilder, ProjectSnapshotRepository


class DueDiligenceOrchestrator:
    def __init__(self, settings: Settings, repository: ProjectSnapshotRepository | None = None) -> None:
        self.snapshot_builder = ProjectSnapshotBuilder()
        self.repository = repository or ProjectSnapshotRepository(settings)
        self.rule_version, self.rules = load_rule_catalog(self._rule_path())

    @staticmethod
    def _rule_path():
        from pathlib import Path
        return Path(__file__).resolve().parents[2] / "resources" / "eligibility_rules_v04.json"

    def run(self, project_id: str) -> dict[str, Any]:
        snapshot = self.snapshot_builder.build_project_snapshot(project_id, self.repository)
        facts: dict[str, ProjectFact] = {}
        for item in snapshot.fields:
            if item.status.value == "AVAILABLE" and item.evidence and item.field == "pue":
                evidence = item.evidence[0]
                facts["pue"] = ProjectFact(Decimal(str(evidence.value)), "RATIO", SourceType.FACT, evidence.source_id)
        eligibility = EligibilityEngine().evaluate(project_id=project_id, rule_catalog_version=self.rule_version, rules=self.rules, facts=facts).public_dict()
        scenarios: list[dict[str, Any]] = []
        scenario_boundary = "未执行压力测试：项目单独 CFADS、贷款比例、利率和期限尚未形成完整可追溯输入。"
        risks = RiskEngine().evaluate(snapshot, scenarios, eligibility)
        gaps = EvidenceGapAnalyzer().analyze(snapshot, eligibility, risks)
        return {
            "result_type": "INITIAL_DUE_DILIGENCE", "project_id": project_id,
            "snapshot": snapshot.public_dict(), "eligibility": eligibility, "scenarios": scenarios,
            "scenario_boundary": scenario_boundary, "risks": [item.public_dict() for item in risks],
            "evidence_gaps": [item.public_dict() for item in gaps],
            "claims": [
                {"claim_type": "SQL_FACT", "text": "项目快照仅由受控只读 SQL 事实构建。", "support_ids": [e.source_id for f in snapshot.fields for e in f.evidence]},
                {"claim_type": "RULE_EVALUATION", "text": f"政策规则状态：{eligibility['overall_status']}。", "support_ids": [f"RULE:{item['rule_id']}" for item in eligibility['evaluations']]},
                {"claim_type": "EVIDENCE_GAP", "text": f"已生成 {len(gaps)} 项待补资料。", "support_ids": [item.code for item in gaps]},
            ],
            "warning": "本结果为初步尽调辅助，不构成自动授信、最终绿色贷款认定或信用评级。",
        }
