"""Validate V0.3 Gold Evidence and score captured evaluation observations.

Live calls are intentionally outside this script: callers should capture agent
results (including internal evidence identifiers) to a JSONL file and pass it
through this deterministic scorer.  That makes regression results reproducible
without putting API keys into the evaluation artefact.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from app.energy_sql import validate_energy_sql


SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = SERVICE_ROOT / "eval" / "v03_gold_set.json"
DEFAULT_MANIFEST = SERVICE_ROOT / "resources" / "policy_metadata_v03.csv"
DEFAULT_CORPUS = SERVICE_ROOT / "runtime" / "policy_corpus" / "public_effective" / "chunks.jsonl"
EXPECTED_COUNTS = {
    "policy_fact": 15,
    "policy_threshold": 10,
    "policy_time_status": 10,
    "policy_region": 10,
    "sql": 10,
    "both": 20,
    "out_of_scope": 10,
    "permission": 5,
}


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_gold(gold_path: Path, manifest_path: Path, corpus_path: Path) -> dict[str, Any]:
    cases = json.loads(gold_path.read_text(encoding="utf-8"))
    with manifest_path.open(encoding="utf-8", newline="") as source:
        manifest = {row["document_id"]: row for row in csv.DictReader(source)}
    chunks = {item["chunk_id"]: item for item in load_jsonl(corpus_path)}
    errors: list[str] = []
    if len(cases) != 90:
        errors.append(f"期望 90 题，实际 {len(cases)} 题。")
    if len({item.get('id') for item in cases}) != len(cases):
        errors.append("题目 ID 不唯一。")
    if Counter(item.get("category") for item in cases) != EXPECTED_COUNTS:
        errors.append(f"分类数量不符合约定：{Counter(item.get('category') for item in cases)}")
    for case in cases:
        evidence = case.get("gold_evidence")
        if evidence is None:
            if case["category"] in {"policy_time_status", "sql", "out_of_scope", "permission"}:
                continue
            errors.append(f"{case['id']} 缺少 Gold Evidence。")
            continue
        document_id, chunk_id = evidence.get("document_id"), evidence.get("chunk_id")
        metadata = manifest.get(str(document_id))
        chunk = chunks.get(str(chunk_id))
        if metadata is None or chunk is None:
            errors.append(f"{case['id']} Gold document/chunk 不存在。")
            continue
        if chunk.get("document_id") != document_id:
            errors.append(f"{case['id']} Gold chunk 与 document_id 不一致。")
        if metadata["status"] != "EFFECTIVE" or metadata["confidentiality"] != "PUBLIC":
            errors.append(f"{case['id']} Gold Evidence 不是 PUBLIC+EFFECTIVE。")
        if evidence.get("status") != metadata["status"] or evidence.get("region") != metadata["region"]:
            errors.append(f"{case['id']} Gold metadata 与 manifest 不一致。")
        if _compact(str(evidence.get("gold_quote") or "")) not in _compact(str(chunk.get("text") or "")):
            errors.append(f"{case['id']} Gold quote 不在 Gold chunk 原文中。")
        if case["category"] == "sql":
            safety = validate_energy_sql(str(case.get("gold_sql") or ""))
            if not safety.safe:
                errors.append(f"{case['id']} Gold SQL 不安全：{safety.errors}")
    return {"valid": not errors, "case_count": len(cases), "errors": errors}


def score_observations(gold_path: Path, observations_path: Path) -> dict[str, Any]:
    """Score a JSONL capture with id, route, answerable, source_document_ids and citations."""

    cases = {item["id"]: item for item in json.loads(gold_path.read_text(encoding="utf-8"))}
    observations = {item["id"]: item for item in load_jsonl(observations_path)}
    route_correct = answerability_correct = retrieval_hits = citation_hits = both_correct = permission_leakage = 0
    eligible_for_retrieval = eligible_for_citation = both_total = permission_total = 0
    missing = sorted(set(cases) - set(observations))
    for case_id, case in cases.items():
        observed = observations.get(case_id)
        if observed is None:
            continue
        if observed.get("route") == case["expected_route"]:
            route_correct += 1
        if bool(observed.get("answerable")) == bool(case["expected_answerable"]):
            answerability_correct += 1
        evidence = case.get("gold_evidence")
        if evidence:
            eligible_for_retrieval += 1
            document_ids = set(observed.get("source_document_ids") or [])
            if evidence["document_id"] in document_ids:
                retrieval_hits += 1
            citations = observed.get("citations") or []
            if any(
                citation.get("chunk_id") == evidence["chunk_id"]
                and _compact(str(citation.get("quote") or "")) in _compact(str(evidence["gold_quote"]))
                for citation in citations
            ):
                citation_hits += 1
            eligible_for_citation += 1
        if case["category"] == "both":
            both_total += 1
            if observed.get("route") == "BOTH" and observed.get("comparison_status") in {"MATCH", "POTENTIAL_MATCH", "INSUFFICIENT_EVIDENCE"}:
                both_correct += 1
        if case["category"] == "permission":
            permission_total += 1
            if observed.get("leaked_confidentiality") in {"INTERNAL", "RESTRICTED"}:
                permission_leakage += 1
    total = len(cases)
    ratio = lambda numerator, denominator: None if not denominator else round(numerator / denominator, 4)
    return {
        "observed_cases": len(observations), "missing_case_ids": missing,
        "route_accuracy": ratio(route_correct, total),
        "answerability_accuracy": ratio(answerability_correct, total),
        "gold_document_recall_at_5": ratio(retrieval_hits, eligible_for_retrieval),
        "citation_correctness": ratio(citation_hits, eligible_for_citation),
        "both_e2e": ratio(both_correct, both_total),
        "permission_leakage": permission_leakage,
        "permission_total": permission_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--observations", type=Path)
    args = parser.parse_args()
    validation = validate_gold(args.gold, args.manifest, args.corpus)
    output: dict[str, Any] = {"gold_validation": validation}
    if args.observations:
        output["metrics"] = score_observations(args.gold, args.observations)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if not validation["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
