#!/usr/bin/env python3
"""Generate the versioned V0.3 seed manifest from the audited ETL registry.

The ETL registry has already been manually assessed for file identity and
policy status.  This generator maps its legacy status vocabulary to the strict
V0.3 values and adds two compute-policy sources needed by the AI layer.
"""

from __future__ import annotations

import ast
import csv
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.policy_corpus import METADATA_FIELDS


ROOT = SERVICE_ROOT.parents[1]
ETL_REGISTRY = ROOT / "etl" / "11_policy_layer_v1.py"
OUTPUT = SERVICE_ROOT / "resources" / "policy_metadata_v03.csv"
SKIP_FILES = {
    "新型电力系统建设“十五五”规划.pdf",  # parsed text is known unreliable
    "深圳市峰谷分电价比价关系表.wps",  # WPS requires a controlled conversion first
}
STATUS_MAP = {
    "EFFECTIVE": "EFFECTIVE",
    "DRAFT": "DRAFT",
    "REFERENCE": "UNKNOWN",
    "NEEDS_OFFICIAL_CHECK": "UNKNOWN",
    "NEEDS_PARSE": "UNKNOWN",
}


def read_docs() -> list[dict[str, object]]:
    tree = ast.parse(ETL_REGISTRY.read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "DOCS" for target in node.targets)
    )
    return ast.literal_eval(assignment.value)


def authority(document: dict[str, object]) -> str:
    if document["type"] == "IMPLEMENTATION_RULE":
        return "IMPLEMENTATION_RULE"
    return "GOV_POLICY"


def base_row(document: dict[str, object], index: int) -> dict[str, str]:
    file_name = str(document["file"])
    return {
        "document_id": f"POL-{index:03d}",
        "title": str(document["title"]),
        "file_name": file_name,
        "authority_code": authority(document),
        "policy_level": str(document["level"]),
        "issuing_authority": str(document["org"]),
        "document_number": str(document.get("number") or ""),
        "issue_date": str(document.get("issue") or ""),
        "effective_date": str(document.get("effective") or ""),
        "expiry_date": str(document.get("expiry") or ""),
        "status": STATUS_MAP[str(document["status"])],
        "region": str(document["region"]),
        "topic": str(document["category"]),
        "subtopic": str(document["type"]),
        "beneficiary_side": "政策适用主体见原文",
        "confidentiality": "PUBLIC",
        "source_url": str(document.get("url") or ""),
        "local_file": f"政策文件/{file_name}",
        "version": "V0.3-A seed",
        "supersedes": "",
        "superseded_by": "",
    }


def compute_rows(start_index: int) -> list[dict[str, str]]:
    return [
        {
            "document_id": f"POL-{start_index:03d}",
            "title": "数据中心绿色低碳发展专项行动计划",
            "file_name": "数据中心绿色低碳发展专项行动计划.pdf",
            "authority_code": "GOV_POLICY",
            "policy_level": "NATIONAL",
            "issuing_authority": "国家发展改革委、工业和信息化部、国家能源局、国家数据局",
            "document_number": "发改环资〔2024〕970号",
            "issue_date": "2024-07-03",
            "effective_date": "2024-07-03",
            "expiry_date": "",
            "status": "EFFECTIVE",
            "region": "全国",
            "topic": "DATA_CENTER",
            "subtopic": "GREEN_LOW_CARBON",
            "beneficiary_side": "新建及改扩建数据中心",
            "confidentiality": "PUBLIC",
            "source_url": "https://zfxxgk.ndrc.gov.cn/web/iteminfo.jsp?id=20410",
            "local_file": "算力政策文件/数据中心绿色低碳发展专项行动计划.pdf",
            "version": "发改环资〔2024〕970号",
            "supersedes": "",
            "superseded_by": "",
        },
        {
            "document_id": f"POL-{start_index + 1:03d}",
            "title": "2026年度深圳市训力券申请指南",
            "file_name": "2026年度深圳市训力券申请指南.docx",
            "authority_code": "APPLICATION_GUIDE",
            "policy_level": "MUNICIPAL",
            "issuing_authority": "深圳市科技创新局",
            "document_number": "",
            "issue_date": "",
            "effective_date": "2026-05-06",
            "expiry_date": "2026-06-05",
            "status": "EXPIRED",
            "region": "深圳市",
            "topic": "COMPUTE_SUBSIDY",
            "subtopic": "TRAINING_VOUCHER",
            "beneficiary_side": "深圳市企业、高等院校、科研机构等需求方",
            "confidentiality": "PUBLIC",
            "source_url": "",
            "local_file": "算力政策文件/2026年度深圳市训力券申请指南.docx",
            "version": "2026年度",
            "supersedes": "",
            "superseded_by": "",
        },
    ]


def main() -> int:
    rows = []
    for item in read_docs():
        if item["file"] in SKIP_FILES:
            continue
        rows.append(base_row(item, len(rows) + 1))
    rows.extend(compute_rows(len(rows) + 1))
    if len(rows) != 30:
        raise ValueError(f"预期 30 份首批文件，实际 {len(rows)} 份。")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=METADATA_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"已生成 {OUTPUT}：{len(rows)} 份首批文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
