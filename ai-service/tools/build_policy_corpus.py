#!/usr/bin/env python3
"""Build the public, current-effective V0.3 policy corpus from its manifest."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.policy_corpus import (  # noqa: E402
    PolicyCorpusError,
    build_policy_chunks,
    load_policy_metadata,
    retrieval_documents,
    write_audit,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建 EnergyComputeAI V0.3 政策语料。")
    parser.add_argument(
        "--metadata",
        type=Path,
        default=SERVICE_ROOT / "resources" / "policy_metadata_v03.csv",
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=Path(os.getenv("POLICY_CORPUS_ROOT", "")),
        help="政策源文件根目录；必须与 metadata.local_file 对应。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SERVICE_ROOT / "runtime" / "policy_corpus" / "public_effective",
    )
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--include-non-current", action="store_true")
    parser.add_argument("--max-chars", type=int, default=1800)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not str(args.corpus_root):
        print("POLICY_CORPUS_ROOT 或 --corpus-root 必须指定。", file=sys.stderr)
        return 2
    try:
        all_documents = load_policy_metadata(args.metadata)
        documents = retrieval_documents(
            all_documents,
            allowed_confidentiality={"PUBLIC"},
            as_of=args.as_of,
            include_non_current=args.include_non_current,
        )
        if not documents:
            raise PolicyCorpusError("筛选后没有可索引的 PUBLIC 政策文件。")
        chunks, audit = build_policy_chunks(
            documents, args.corpus_root, maximum_chars=args.max_chars
        )
        failures = [row for row in audit if row["status"] != "PASS"]
        if failures:
            details = "；".join(f"{row['document_id']}: {row['error']}" for row in failures)
            raise PolicyCorpusError("解析质量检查失败，未建立部分索引：" + details)
        write_jsonl(args.output_dir / "chunks.jsonl", chunks)
        write_audit(args.output_dir / "extraction_audit.json", audit)
        manifest = {
            "schema_version": "EnergyComputeAI-V0.3-A",
            "as_of": args.as_of.isoformat(),
            "allowed_confidentiality": ["PUBLIC"],
            "include_non_current": args.include_non_current,
            "document_count": len(documents),
            "chunk_count": len(chunks),
            "metadata": str(args.metadata),
            "corpus_root": str(args.corpus_root.resolve()),
        }
        (args.output_dir / "corpus_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, PolicyCorpusError) as exc:
        print(f"政策语料构建失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
