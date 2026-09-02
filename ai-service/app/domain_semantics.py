"""Domain-specific null and mapping semantics used by result interpretation."""

from __future__ import annotations

from typing import Any

from .value_formatter import MAPPING_STATUS_LABELS, is_null


MAPPING_STATUSES = frozenset(MAPPING_STATUS_LABELS)


def normalized_mapping_status(value: Any) -> str:
    status = str(value or "NO_DATA").upper()
    return status if status in MAPPING_STATUSES else "CONFLICTING"


def null_meaning(field: str, value: Any) -> str | None:
    """Business meanings for nulls.  No missing value is ever converted to zero."""

    meanings = {
        "official_name": "尚未建立正式设施映射。",
        "candidate_facility_v2_id": "候选参照尚未形成正式设施映射。",
        "green_power_ratio": "当前数据库没有可靠绿电比例数据。",
        "hosting_revenue_wanyuan": "当前数据库暂无可核验的托管收入数据。",
        "metric_value": "当前数据库未披露该指标的可靠数值。",
    }
    return meanings.get(field) if is_null(value) else None


def mapping_boundaries(status: str, candidate_name: Any, boundary_note: Any) -> list[str]:
    boundaries: list[str] = []
    if not is_null(boundary_note):
        boundaries.append(str(boundary_note))
    if status == "CANDIDATE":
        boundaries.append("候选设施仅表示待核验关联，不构成已确认部署或运营关系。")
    elif status == "UNMAPPED":
        boundaries.append("当前没有该商品与具体数据中心的直接映射证据。")
        if not is_null(candidate_name):
            boundaries.append("同型资源参照不构成该商品的正式设施映射。")
    elif status == "CONFLICTING":
        boundaries.append("不同来源的映射信息存在冲突，暂不能确认具体设施。")
    elif status == "NO_DATA":
        boundaries.append("当前数据库尚无该商品的设施映射信息。")
    return list(dict.fromkeys(boundaries))
