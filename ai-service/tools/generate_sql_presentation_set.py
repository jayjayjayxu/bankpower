"""Generate the deterministic 40-case V0.3.1 SQL presentation regression set."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = SERVICE_ROOT / "eval" / "v031_sql_presentation_set.json"


def case(case_id: str, category: str, question: str, columns: list[str], rows: list[list[str]], mode: str, status: str = "ANSWERED", required: str = "") -> dict[str, Any]:
    return {
        "id": case_id, "category": category, "question": question,
        "columns": columns, "rows": rows, "expected_response_mode": mode,
        "expected_answer_status": status, "required_conclusion_text": required,
    }


def metric_rows(value: str = "1.21000000") -> tuple[list[str], list[list[str]]]:
    return ["official_name", "metric_name", "metric_value", "metric_unit"], [["深圳百旺信智算中心", "PUE", value, "RATIO"]]


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index, question in enumerate((
        "百旺信PUE是多少？", "百旺信2025年PUE是多少？", "深圳百旺信智算中心能效指标是什么？",
        "百旺信上架率和机柜价格是多少？", "百旺信机柜运营指标查询", "查询百旺信PUE披露值",
        "百旺信数据中心指标是什么？", "百旺信最新PUE是多少？",
    ), 1):
        columns, rows = metric_rows()
        cases.append(case(f"FACT-{index:02d}", "FACT_LOOKUP", question, columns, rows, "FACT_LOOKUP", required="PUE为1.21"))
    for index, question in enumerate((
        "哪些中心PUE低于1.3？", "列出深圳已披露PUE的中心", "所有低PUE设施", "哪些设施有上架率数据？", "列出可核验的算力中心",
    ), 1):
        columns, rows = metric_rows("1.22000000")
        cases.append(case(f"LIST-{index:02d}", "LIST", question, columns, rows, "LIST"))
    for index, question in enumerate((
        "PUE最低的3个中心", "PUE最高的设施排名", "TOP 5 数据中心PUE", "按上架率排序", "排名前3的算力中心",
    ), 1):
        columns, rows = metric_rows("1.18000000")
        cases.append(case(f"RANK-{index:02d}", "RANKING", question, columns, rows, "RANKING"))
    for index, question in enumerate((
        "百旺信和A中心PUE比较", "哪个中心PUE更低？", "对比两个机柜价格", "上架率差异是什么？", "PUE指标比较",
    ), 1):
        columns, rows = metric_rows("1.19000000")
        cases.append(case(f"COMPARE-{index:02d}", "COMPARISON", question, columns, rows, "COMPARISON"))
    for index, question in enumerate((
        "深圳设施平均PUE多少？", "数据中心总数量是多少？", "平均机柜价格是多少？", "合计用电量是多少？",
    ), 1):
        cases.append(case(f"AGG-{index:02d}", "AGGREGATION", question, ["average_pue"], [["1.23000000"]], "AGGREGATION"))
    for index, question in enumerate((
        "百旺信2023-2025上架率变化", "百旺信PUE趋势", "历年机柜价格变化", "时间序列上架率", "百旺信运营指标趋势",
    ), 1):
        cases.append(case(f"TIME-{index:02d}", "TIME_SERIES", question, ["fact_year", "rack_utilization_ratio"], [["2023", "0.3762"], ["2025", "0.6542"]], "TIME_SERIES"))
    mapping_rows = {
        "CONFIRMED": ["B200-C4-1", "CONFIRMED", "", "深圳百旺信智算中心", "已完成直接映射。"],
        "CANDIDATE": ["B200-C4-1", "CANDIDATE", "北京超级云计算中心 N61B2B分区", "NULL", "候选关联待核验。"],
        "UNMAPPED": ["B200-C4-1", "UNMAPPED", "北京超级云计算中心 N61B2B分区", "NULL", "未找到直接对应证据。"],
        "CONFLICTING": ["B200-C4-1", "CONFLICTING", "候选A", "NULL", "不同来源存在冲突。"],
        "NO_DATA": ["B200-C4-1", "NO_DATA", "", "NULL", ""],
    }
    for status, row in mapping_rows.items():
        required = "目前无法确认 B200-C4-1 对应具体数据中心。" if status == "UNMAPPED" else ""
        expected_status = "CONFIRMED_MAPPING" if status == "CONFIRMED" else "NO_DATA" if status == "NO_DATA" else "UNCONFIRMED_MAPPING"
        cases.append(case(f"MAP-{status}", "ENTITY_MAPPING", "B200-C4-1对应哪个数据中心？", ["external_product_id", "mapping_status", "candidate_name", "official_name", "boundary_note"], [row], "ENTITY_MAPPING", expected_status, required))
    for index, question in enumerate(("百旺信上架率是多少？", "B200-C4-1对应哪个数据中心？", "深圳设施PUE是多少？"), 1):
        mode = "ENTITY_MAPPING" if "对应哪个数据中心" in question else "FACT_LOOKUP"
        required = "当前数据库中尚无" if mode == "ENTITY_MAPPING" else "没有查询到"
        cases.append(case(f"NODATA-{index:02d}", "NULL_NO_DATA", question, ["metric_value"], [], mode, "NO_DATA", required=required))
    if len(cases) != 40:
        raise AssertionError(f"expected 40 cases, got {len(cases)}")
    return cases


def main() -> None:
    OUTPUT.write_text(json.dumps(build_cases(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
