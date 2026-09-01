#!/usr/bin/env python3
"""Build a physically isolated FAISS index for V0.3 policy evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

# Match the stable legacy build settings on macOS CPU.  They must be set before
# Torch/Transformers are imported through semantic_search.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

from app.policy_corpus import PolicyCorpusError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立 V0.3 政策语料的隔离 FAISS 索引。")
    parser.add_argument(
        "--chunks",
        type=Path,
        default=SERVICE_ROOT / "runtime" / "policy_corpus" / "public_effective" / "chunks.jsonl",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=SERVICE_ROOT / "runtime" / "policy_vector_index" / "public_effective",
    )
    parser.add_argument("--core-dir", type=Path, default=None)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    return parser.parse_args()


def load_chunks(path: Path) -> list[dict[str, object]]:
    chunks = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not chunks:
        raise PolicyCorpusError("chunks.jsonl 不能为空。")
    identifiers = [str(chunk.get("chunk_id") or "") for chunk in chunks]
    if not all(identifiers) or len(set(identifiers)) != len(identifiers):
        raise PolicyCorpusError("chunk_id 必须非空且唯一。")
    invalid = [
        str(chunk.get("chunk_id"))
        for chunk in chunks
        if chunk.get("confidentiality") != "PUBLIC" or chunk.get("status") != "EFFECTIVE"
    ]
    if invalid:
        raise PolicyCorpusError("PUBLIC_EFFECTIVE 索引不得包含非公开或非现行文件：" + "、".join(invalid[:3]))
    return chunks


def main() -> int:
    args = parse_args()
    core_dir = args.core_dir or (Path(os.environ["BANKAI_CORE_DIR"]) if os.environ.get("BANKAI_CORE_DIR") else None)
    if core_dir is None:
        print("--core-dir 或 BANKAI_CORE_DIR 必须指定。", file=sys.stderr)
        return 2
    source_dir = core_dir / "src"
    model_dir = core_dir / "storage" / "models" / "bge-small-zh-v1.5"
    if not source_dir.is_dir() or not model_dir.is_dir():
        print("BankAI 的 BGE 模型或 semantic_search 源码缺失。", file=sys.stderr)
        return 2
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))
    try:
        import faiss
        import numpy as np

        from semantic_search import BGEEmbedder, INDEX_FILENAME, RECORDS_FILENAME, sha256_file, write_jsonl

        chunks = load_chunks(args.chunks)
        embedder = BGEEmbedder(
            model_name_or_path=str(model_dir),
            cache_dir=core_dir / "storage" / "huggingface",
            device=args.device,
            batch_size=1,
            passage_window_tokens=256,
            passage_window_overlap_tokens=64,
            local_files_only=True,
        )
        vectors, mappings = embedder.encode_passage_windows([str(chunk["text"]) for chunk in chunks])
        if not np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5):
            raise PolicyCorpusError("BGE 输出向量未归一化。")
        index = faiss.IndexFlatIP(int(vectors.shape[1]))
        index.add(vectors)
        records = []
        for mapping in mappings:
            record = dict(chunks[int(mapping["chunk_position"])])
            record.update(mapping)
            records.append(record)
        if index.ntotal != len(records):
            raise PolicyCorpusError("FAISS 向量数与索引记录数不一致。")
        args.index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(args.index_dir / INDEX_FILENAME))
        write_jsonl(args.index_dir / RECORDS_FILENAME, records)
        config = {
            "schema_version": "EnergyComputeAI-V0.3-A",
            "created_at": datetime.now(UTC).isoformat(),
            "access_scope": {"confidentiality": ["PUBLIC"], "status": ["EFFECTIVE"]},
            "model_id": str(model_dir),
            "official_model_id": "BAAI/bge-small-zh-v1.5",
            "pooling": "CLS",
            "normalized": True,
            "faiss_index_type": "IndexFlatIP",
            "similarity": "cosine via inner product of L2-normalized vectors",
            "dimension": int(vectors.shape[1]),
            "chunk_count": len(chunks),
            "vector_count": int(index.ntotal),
            "source_chunks": str(args.chunks),
            "source_chunks_sha256": sha256_file(args.chunks),
            "model_max_length": embedder.model_max_length,
            "passage_window_tokens": 256,
            "passage_window_overlap_tokens": 64,
            "device_used_for_build": args.device,
        }
        (args.index_dir / "index_config.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (ImportError, OSError, PolicyCorpusError, RuntimeError, ValueError) as exc:
        print(f"政策 FAISS 索引构建失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(config, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
