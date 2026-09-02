"""Fixed-profile project snapshot builder; it never asks an LLM what to check."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from app.config import Settings
from app.energy_sql import SpdbReadOnlyExecutor

from .models import FieldStatus, ProjectSnapshot, SnapshotEvidence, SnapshotField


_PROFILE_PATH = Path(__file__).resolve().parents[2] / "resources" / "due_diligence_profile_v05.yaml"
_FACILITY_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,63}$")


@dataclass(frozen=True)
class RawProjectData:
    master: dict[str, Any] | None
    metrics: tuple[dict[str, Any], ...]
    operations: tuple[dict[str, Any], ...]


class ProjectSnapshotRepository:
    """Read only the fixed fields defined by the V5 DATA_CENTER profile."""

    def __init__(self, settings: Settings, executor: SpdbReadOnlyExecutor | None = None) -> None:
        self.executor = executor or SpdbReadOnlyExecutor(settings)

    @staticmethod
    def _rows(result: Any) -> list[dict[str, Any]]:
        return [dict(zip(result.columns, row)) for row in result.rows]

    def fetch(self, project_id: str) -> RawProjectData:
        if not _FACILITY_CODE.fullmatch(project_id):
            raise ValueError("project_id 必须是受支持的 facility_code。")
        code = project_id
        master = self._rows(self.executor.execute(
            "SELECT facility_code,official_name,facility_kind,city_name,operator_name,owner_name,"
            "lifecycle_status,operation_start_date,last_verified_date,data_quality "
            "FROM enterprise_data_center_v2 WHERE facility_code='" + code + "' LIMIT 1"
        ))
        metrics = self._rows(self.executor.execute(
            "SELECT m.metric_code,m.metric_scope,m.metric_value,m.metric_text,m.metric_unit,m.as_of_date,"
            "m.source_id,m.source_locator,m.data_quality FROM compute_facility_metric_v1 m "
            "JOIN enterprise_data_center_v2 f ON f.facility_v2_id=m.facility_v2_id "
            "WHERE f.facility_code='" + code + "' ORDER BY m.metric_code,m.metric_scope"
        ))
        operations = self._rows(self.executor.execute(
            "SELECT o.operation_scope_code,o.operation_scope_name,o.fact_year,o.fact_period,"
            "o.rack_capacity_count,o.rack_utilization_ratio,o.average_rack_price_yuan_month,"
            "o.hosting_revenue_wanyuan,o.electricity_consumption_kwh,o.electricity_purchase_price_yuan_kwh,"
            "o.source_id,o.source_locator,o.data_quality FROM compute_facility_operation_fact_v1 o "
            "JOIN enterprise_data_center_v2 f ON f.facility_v2_id=o.facility_v2_id "
            "WHERE f.facility_code='" + code + "' ORDER BY o.fact_year,o.fact_period,o.operation_scope_code"
        ))
        return RawProjectData(master[0] if master else None, tuple(metrics), tuple(operations))


class ProjectSnapshotBuilder:
    def __init__(self, profile_path: Path = _PROFILE_PATH, stale_after_days: int = 730) -> None:
        raw = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
        if raw.get("profile_version") is None or not isinstance(raw.get("fields"), list):
            raise ValueError("尽调 Profile 格式无效。")
        self.profile = raw
        self.stale_after_days = stale_after_days

    def build(self, project_id: str, raw: RawProjectData, today: date | None = None) -> ProjectSnapshot:
        now = today or date.today()
        fields = tuple(self._field(item, raw, now) for item in self.profile["fields"])
        return ProjectSnapshot(
            project_id=project_id,
            project_name=(raw.master or {}).get("official_name"),
            profile_version=str(self.profile["profile_version"]),
            generated_at=datetime.now(UTC).isoformat(), fields=fields,
        )

    def build_project_snapshot(self, project_id: str, repository: ProjectSnapshotRepository) -> ProjectSnapshot:
        return self.build(project_id, repository.fetch(project_id))

    def _field(self, spec: dict[str, Any], raw: RawProjectData, today: date) -> SnapshotField:
        evidence = self._evidence(spec, raw)
        status, reason = self._status(evidence, today)
        return SnapshotField(
            field=str(spec["field"]), domain=str(spec["domain"]), label=str(spec["label"]),
            status=status, required=bool(spec.get("required", True)), weight=int(spec.get("weight", 1)),
            evidence=tuple(evidence), reason=reason,
        )

    def _evidence(self, spec: dict[str, Any], raw: RawProjectData) -> list[SnapshotEvidence]:
        kind = spec["source"]["kind"]
        column = spec["source"].get("column")
        if kind == "MASTER":
            if raw.master is None or raw.master.get(column) in (None, ""):
                return []
            return [SnapshotEvidence(raw.master[column], spec.get("unit"), f"SQL:enterprise_data_center_v2:{raw.master['facility_code']}", f"facility_code={raw.master['facility_code']}", "FACILITY_MASTER", raw.master.get("last_verified_date"), raw.master.get("data_quality"))]
        if kind == "METRIC":
            rows = [row for row in raw.metrics if row.get("metric_code") == spec["source"].get("metric_code") and (row.get("metric_value") is not None or row.get("metric_text"))]
            return [SnapshotEvidence(row.get("metric_value") if row.get("metric_value") is not None else row.get("metric_text"), row.get("metric_unit"), f"SQL:compute_facility_metric_v1:{row.get('source_id')}", row.get("source_locator"), row.get("metric_scope"), row.get("as_of_date"), row.get("data_quality")) for row in rows]
        if kind == "OPERATION":
            rows = [row for row in raw.operations if row.get(column) is not None]
            if rows:
                latest_year = max(int(row["fact_year"]) for row in rows)
                rows = [row for row in rows if int(row["fact_year"]) == latest_year]
            return [SnapshotEvidence(row[column], spec.get("unit"), f"SQL:compute_facility_operation_fact_v1:{row.get('source_id')}", row.get("source_locator"), row.get("operation_scope_name") or row.get("operation_scope_code"), f"{row.get('fact_year')}-{row.get('fact_period')}", row.get("data_quality")) for row in rows]
        raise ValueError(f"未知 Profile source kind: {kind}")

    def _status(self, evidence: list[SnapshotEvidence], today: date) -> tuple[FieldStatus, str]:
        if not evidence:
            return FieldStatus.MISSING, "尽调 Profile 要求该字段，但数据库未返回可追溯事实。"
        distinct_values = {str(item.value) for item in evidence}
        if len(distinct_values) > 1:
            return FieldStatus.CONFLICTING, "数据库返回多个不同值/统计口径；快照保留全部证据，需人工确认适用范围。"
        dated: list[date] = []
        for item in evidence:
            try:
                dated.append(date.fromisoformat(str(item.as_of_date)))
            except (TypeError, ValueError):
                pass
        if dated and max(dated) < today - timedelta(days=self.stale_after_days):
            return FieldStatus.STALE, "最近可识别日期超过资料时效阈值，需取得更新材料。"
        return FieldStatus.AVAILABLE, "已取得单一可追溯事实；仍须结合其统计口径使用。"
