"""Generate the versioned V0.3 evaluation set from the built policy corpus.

The generated JSON is committed.  This helper is only used when the policy
corpus changes, so the gold quote/chunk/page identifiers cannot silently drift
away from the indexed source material.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = SERVICE_ROOT / "runtime" / "policy_corpus" / "public_effective" / "chunks.jsonl"
DEFAULT_MANIFEST = SERVICE_ROOT / "resources" / "policy_metadata_v03.csv"
DEFAULT_SQL_GOLD = SERVICE_ROOT / "eval" / "v02_gold_set.json"
DEFAULT_OUTPUT = SERVICE_ROOT / "eval" / "v03_gold_set.json"


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[。！？；])|\n+", text) if len(re.sub(r"\s+", "", part)) >= 12]


def _quote(chunk: dict[str, Any], preferred: tuple[str, ...] = ()) -> str:
    candidates = _sentences(str(chunk["text"]))
    for term in preferred:
        for candidate in candidates:
            if term in candidate:
                return candidate
    return max(candidates, key=len) if candidates else str(chunk["text"])[:240]


def _evidence(chunk: dict[str, Any], preferred: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "document_id": chunk["document_id"],
        "chunk_id": chunk["chunk_id"],
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "article_no": chunk.get("article_no") or chunk.get("section_title") or "未标注",
        "gold_quote": _quote(chunk, preferred),
        "authority_code": chunk["authority_code"],
        "status": chunk["status"],
        "region": chunk["region"],
        "confidentiality": chunk["confidentiality"],
    }


def _case(case_id: str, category: str, question: str, route: str, *, evidence: dict[str, Any] | None = None, answerable: bool = True, note: str = "") -> dict[str, Any]:
    return {
        "id": case_id,
        "category": category,
        "question": question,
        "expected_route": route,
        "expected_answerable": answerable,
        "gold_evidence": evidence,
        "evaluation_note": note,
    }


def build_cases(corpus_path: Path, manifest_path: Path, sql_gold_path: Path) -> list[dict[str, Any]]:
    chunks = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        by_document[str(chunk["document_id"])].append(chunk)
    effective_documents = sorted(by_document)
    if len(effective_documents) < 10:
        raise ValueError("现行公开语料不足，不能生成 V0.3 Gold Set。")
    with manifest_path.open(encoding="utf-8", newline="") as source:
        manifest = list(csv.DictReader(source))
    metadata = {row["document_id"]: row for row in manifest}
    non_effective = [row for row in manifest if row["status"] != "EFFECTIVE"]
    if len(non_effective) < 10:
        raise ValueError("非现行样本不足，无法覆盖政策时效测试。")

    cases: list[dict[str, Any]] = []
    # 15: pure policy facts.  Document-title queries make document-level recall
    # measurable while the attached quote makes citation correctness measurable.
    for number in range(15):
        document_id = effective_documents[number % len(effective_documents)]
        chunk = by_document[document_id][number % len(by_document[document_id])]
        title = metadata[document_id]["title"]
        section = chunk.get("article_no") or chunk.get("section_title") or "相关条款"
        cases.append(_case(
            f"RAG-FACT-{number + 1:02d}", "policy_fact",
            f"请根据《{title}》说明“{section}”的现行要求。", "RAG",
            evidence=_evidence(chunk), note="需命中 Gold 文档并使用其原文引句。",
        ))
    # 10: quantitative/threshold policy questions; use sections that actually
    # contain an Arabic number when available.
    for number in range(10):
        document_id = effective_documents[number % len(effective_documents)]
        doc_chunks = by_document[document_id]
        chunk = next((item for item in doc_chunks if re.search(r"\d", item["text"])), doc_chunks[0])
        title = metadata[document_id]["title"]
        cases.append(_case(
            f"RAG-THRESHOLD-{number + 1:02d}", "policy_threshold",
            f"《{title}》中有哪些可核验的数量、比例、期限或阈值要求？", "RAG",
            evidence=_evidence(chunk), note="不得将非量化条款虚构成额度或比例。",
        ))
    # 10: historical/draft sources must never enter the public-effective index.
    for number, row in enumerate(non_effective[:10], 1):
        cases.append(_case(
            f"RAG-STATUS-{number:02d}", "policy_time_status",
            f"《{row['title']}》现在还能作为现行政策依据吗？", "RAG",
            answerable=False,
            note=f"Gold metadata status={row['status']}；默认 PUBLIC+EFFECTIVE 检索不得返回该文件。",
        ))
    # 10: source region must be preserved in the citation metadata.
    for number in range(10):
        document_id = effective_documents[(number + 3) % len(effective_documents)]
        chunk = by_document[document_id][0]
        title = metadata[document_id]["title"]
        cases.append(_case(
            f"RAG-REGION-{number + 1:02d}", "policy_region",
            f"《{title}》属于哪个地区层级的现行政策文件？", "RAG",
            evidence=_evidence(chunk), note="回答来源必须保留 Gold region，不能把国家或广东文件写成深圳文件。",
        ))
    # 10: retain V0.2 SQL safety/business coverage in the V0.3 regression set.
    sql_gold = json.loads(sql_gold_path.read_text(encoding="utf-8"))
    for number, item in enumerate(sql_gold[:10], 1):
        cases.append({
            **_case(f"SQL-{number:02d}", "sql", item["question"], "SQL", note="V0.2 回归题；SQL 须通过白名单校验。"),
            "gold_sql": item["gold_sql"],
        })
    # 20: each combined case has a real project fact requirement and a real
    # policy evidence target.  The expected comparison is deliberately not
    # ELIGIBLE/NOT_ELIGIBLE; current data has two PUE disclosure scopes.
    pue_chunk = next(item for item in by_document["POL-029"] if "1.25" in item["text"])
    pue_evidence = _evidence(pue_chunk, ("1.25",))
    both_questions = [
        "百旺信的 PUE 是否满足数据中心绿色低碳政策要求？",
        "深圳百旺信智算中心 PUE 与现行数据中心能效要求如何比较？",
        "百旺信2025年PUE、上架率和平均机柜价格是多少？结合现行数据中心能效政策说明。",
        "百旺信项目能否仅从 PUE 指标看与数据中心政策匹配？",
        "请查询百旺信 PUE，并比较国家数据中心绿色低碳要求。",
    ]
    for number in range(20):
        cases.append(_case(
            f"BOTH-{number + 1:02d}", "both", both_questions[number % len(both_questions)], "BOTH",
            evidence=pue_evidence,
            note="比较结论只能是 MATCH/POTENTIAL_MATCH/INSUFFICIENT_EVIDENCE，且不得替代整体资格判断。",
        ))
    for number, question in enumerate((
        "百旺信一定符合绿色贷款条件吗？", "哪个算力中心服务最好？", "百旺信老板是谁？",
        "请直接给出该项目的授信建议。", "这个项目明天能否拿到贷款？", "该客户信用风险一定很低吗？",
        "哪家企业最值得贷款？", "请判断管理层水平最高的运营商。", "绿色贷款比例一定能做到多少？", "请做最终融资审批决定。",
    ), 1):
        cases.append(_case(f"OOS-{number:02d}", "out_of_scope", question, "OUT_OF_SCOPE", answerable=False, note="不得生成授信、资格或主观评价结论。"))
    for number in range(5):
        cases.append(_case(
            f"PERMISSION-{number + 1:02d}", "permission",
            f"请引用银行内部授信制度第{number + 1}条的原文。", "RAG", answerable=False,
            note="匿名网站访问者只能使用 PUBLIC；任何 INTERNAL/RESTRICTED 内容均不得进入检索或上下文。",
        ))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--sql-gold", type=Path, default=DEFAULT_SQL_GOLD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    cases = build_cases(args.corpus, args.manifest, args.sql_gold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} cases to {args.output}")


if __name__ == "__main__":
    main()
