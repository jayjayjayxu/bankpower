from __future__ import annotations

import csv
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.policy_corpus import (
    METADATA_FIELDS,
    PolicyCorpusError,
    build_policy_chunks,
    extract_document,
    load_policy_metadata,
    make_article_chunks,
    retrieval_documents,
)


def row(**overrides: str) -> dict[str, str]:
    payload = {field: "" for field in METADATA_FIELDS}
    payload.update(
        {
            "document_id": "DOC-001",
            "title": "测试政策",
            "file_name": "policy.html",
            "authority_code": "GOV_POLICY",
            "policy_level": "MUNICIPAL",
            "issuing_authority": "测试机关",
            "status": "EFFECTIVE",
            "region": "深圳市",
            "topic": "DATA_CENTER",
            "subtopic": "TEST",
            "beneficiary_side": "测试主体",
            "confidentiality": "PUBLIC",
            "local_file": "policy.html",
            "effective_date": "2026-01-01",
            "version": "1",
        }
    )
    payload.update(overrides)
    return payload


class PolicyCorpusTests(unittest.TestCase):
    def write_metadata(self, path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=METADATA_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def test_seed_manifest_has_thirty_unique_documents_and_strict_statuses(self) -> None:
        documents = load_policy_metadata(SERVICE_ROOT / "resources" / "policy_metadata_v03.csv")
        self.assertEqual(len(documents), 30)
        self.assertEqual(len({document.document_id for document in documents}), 30)
        selected = retrieval_documents(
            documents,
            allowed_confidentiality={"PUBLIC"},
            as_of=date(2026, 9, 1),
        )
        self.assertEqual(len(selected), 14)
        self.assertNotIn("POL-030", {document.document_id for document in selected})
        self.assertIn("POL-029", {document.document_id for document in selected})

    def test_status_and_confidentiality_are_filtered_before_chunk_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            metadata = root / "metadata.csv"
            rows = [
                row(),
                row(document_id="DOC-002", file_name="expired.html", local_file="expired.html", status="EXPIRED"),
                row(document_id="DOC-003", file_name="internal.html", local_file="internal.html", confidentiality="INTERNAL"),
            ]
            self.write_metadata(metadata, rows)
            documents = load_policy_metadata(metadata)
            allowed = retrieval_documents(
                documents,
                allowed_confidentiality={"PUBLIC"},
                as_of=date(2026, 9, 1),
            )
            self.assertEqual([document.document_id for document in allowed], ["DOC-001"])

    def test_article_chunking_preserves_metadata_and_groups_short_articles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "policy.html"
            source.write_text(
                "<article><h1>测试办法</h1><p>第一章 总则</p>"
                "<p>第一条 为规范测试，制定本办法。</p>"
                "<p>第二条 本办法适用于测试主体。</p>"
                "<p>第三条 主管部门负责监督实施。</p></article>",
                encoding="utf-8",
            )
            metadata = root / "metadata.csv"
            self.write_metadata(metadata, [row()])
            document = load_policy_metadata(metadata)[0]
            pages = extract_document(source)
            chunks = make_article_chunks(document, pages, "a" * 64, maximum_chars=800)
            self.assertEqual(len(chunks), 1)
            self.assertEqual(chunks[0]["document_id"], "DOC-001")
            self.assertEqual(chunks[0]["authority_code"], "GOV_POLICY")
            self.assertIn("第一条", str(chunks[0]["text"]))
            self.assertIn("第三条", str(chunks[0]["text"]))

    def test_docx_extraction_and_root_escape_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            docx_path = root / "guide.docx"
            with zipfile.ZipFile(docx_path, "w") as archive:
                archive.writestr(
                    "word/document.xml",
                    "<w:document xmlns:w='w'><w:body>"
                    "<w:p><w:r><w:t>第一条 支持标准。</w:t></w:r></w:p>"
                    "<w:p><w:r><w:t>第二条 申请材料。</w:t></w:r></w:p>"
                    "</w:body></w:document>",
                )
            pages = extract_document(docx_path)
            self.assertIn("第一条", pages[0].text)

            metadata = root / "invalid.csv"
            self.write_metadata(metadata, [row(local_file="../outside.html")])
            with self.assertRaises(PolicyCorpusError):
                load_policy_metadata(metadata)

    def test_build_policy_chunks_records_real_source_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "policy.html").write_text("<p>第一条 测试规则。</p>" * 30, encoding="utf-8")
            metadata = root / "metadata.csv"
            self.write_metadata(metadata, [row()])
            chunks, audit = build_policy_chunks(load_policy_metadata(metadata), root)
            self.assertTrue(chunks[0]["source_sha256"])
            self.assertEqual(audit[0]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
