"""Program-owned display formatting for SQL facts.

No renderer is allowed to decide whether a ratio is a percentage or whether a
database null means zero.  This module keeps raw values separate from their
business display values.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


FIELD_DISPLAY: dict[str, dict[str, str]] = {
    "official_name": {"label": "设施名称"},
    "product_name": {"label": "商品名称"},
    "external_product_id": {"label": "商品编号"},
    "provider_name": {"label": "服务商"},
    "platform_region_label": {"label": "平台地区"},
    "metric_name": {"label": "指标"},
    "metric_scope": {"label": "指标口径"},
    "metric_value": {"label": "指标值"},
    "metric_unit": {"label": "单位"},
    "rack_utilization_ratio": {"label": "上架率", "display": "percent"},
    "average_rack_price_yuan_month": {"label": "平均机柜价格", "display": "rack_price"},
    "fact_year": {"label": "年度", "display": "year"},
    "as_of_date": {"label": "披露日期"},
    "disclosure_status": {"label": "披露状态"},
    "mapping_status": {"label": "映射状态", "display": "mapping_status"},
    "candidate_name": {"label": "候选参照"},
    "company_name": {"label": "企业名称"},
    "financial_year": {"label": "财务年度", "display": "year"},
    "revenue_wanyuan": {"label": "营业收入", "display": "wanyuan"},
    "net_profit_wanyuan": {"label": "净利润", "display": "wanyuan"},
    "total_assets_wanyuan": {"label": "总资产", "display": "wanyuan"},
    "total_liabilities_wanyuan": {"label": "总负债", "display": "wanyuan"},
    "debt_ratio": {"label": "资产负债率", "display": "percent"},
    "operating_cashflow_wanyuan": {"label": "经营现金流", "display": "wanyuan"},
}

MAPPING_STATUS_LABELS = {
    "CONFIRMED": "已确认",
    "CANDIDATE": "候选映射",
    "UNMAPPED": "未映射",
    "CONFLICTING": "映射冲突",
    "NO_DATA": "暂无映射数据",
}

NULL_VALUES = {None, "", "NULL", "null", "None"}


def is_null(value: Any) -> bool:
    return value in NULL_VALUES


def label_for(field: str) -> str:
    return FIELD_DISPLAY.get(field, {}).get("label", field.replace("_", " "))


def _decimal(value: Any) -> Decimal | None:
    if is_null(value):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _plain_decimal(value: Decimal, maximum_fraction: int = 8) -> str:
    text = f"{value:,.{maximum_fraction}f}".rstrip("0").rstrip(".")
    return text or "0"


def format_percent(value: Any) -> str | None:
    number = _decimal(value)
    return None if number is None else f"{_plain_decimal(number * 100, 4)}%"


def format_rack_price(value: Any) -> str | None:
    number = _decimal(value)
    return None if number is None else f"{_plain_decimal(number, 4)} 元/柜/月"


def format_pue(value: Any) -> str | None:
    number = _decimal(value)
    return None if number is None else _plain_decimal(number, 8)


def format_metric_value(metric_name: str | None, value: Any, unit: str | None) -> str | None:
    """Format a metric using its semantic name, never just its raw unit text."""

    metric = (metric_name or "").casefold()
    if metric == "pue" or "电能利用效率" in metric:
        return format_pue(value)
    if metric in {"上架率", "入住率", "机柜利用率"}:
        return format_percent(value)
    if "机柜价格" in metric or "机柜托管价格" in metric:
        return format_rack_price(value)
    number = _decimal(value)
    if number is None:
        return None
    display = _plain_decimal(number, 8)
    unit_text = (unit or "").strip()
    if unit_text == "RATIO":
        return display
    if unit_text == "CNY/RACK/MONTH":
        return f"{display} 元/柜/月"
    return f"{display} {unit_text}".strip()


def format_field(field: str, value: Any) -> str | None:
    """Format a known standalone field; returns None for missing data."""

    if is_null(value):
        return None
    display_type = FIELD_DISPLAY.get(field, {}).get("display")
    if display_type == "percent":
        return format_percent(value)
    if display_type == "rack_price":
        return format_rack_price(value)
    if display_type == "year":
        return f"{value}年"
    if display_type == "wanyuan":
        number = _decimal(value)
        return None if number is None else f"{_plain_decimal(number, 4)} 万元"
    if display_type == "mapping_status":
        return MAPPING_STATUS_LABELS.get(str(value).upper(), str(value))
    return str(value)
