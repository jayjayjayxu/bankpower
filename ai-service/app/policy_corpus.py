"""V0.3-A policy-corpus metadata, extraction and article-aware chunking.

The corpus deliberately keeps source files outside Git.  A versioned manifest
points at an operator-mounted corpus root, and every extracted chunk carries
the metadata that must be filtered *before* it can become RAG evidence.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import unicodedata
import zipfile
from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


METADATA_FIELDS = (
    "document_id", "title", "file_name", "authority_code", "policy_level",
    "issuing_authority", "document_number", "issue_date", "effective_date",
    "expiry_date", "status", "region", "topic", "subtopic", "beneficiary_side",
    "confidentiality", "source_url", "local_file", "version", "supersedes",
    "superseded_by",
)
AUTHORITY_CODES = {
    "LAW", "REGULATION", "GOV_POLICY", "IMPLEMENTATION_RULE", "APPLICATION_GUIDE",
    "BANK_INTERNAL", "BANK_PUBLIC", "COMPANY_DISCLOSURE", "INDUSTRY_REPORT", "MEDIA",
}
STATUSES = {"EFFECTIVE", "EXPIRED", "REPEALED", "DRAFT", "UNKNOWN"}
CONFIDENTIALITIES = {"PUBLIC", "INTERNAL", "RESTRICTED"}
SUPPORTED_SUFFIXES = {".pdf", ".html", ".htm", ".docx"}
CHAPTER_PATTERN = re.compile(r"^(?:第[一二三四五六七八九十百千〇零两]+[编章节])")
ARTICLE_PATTERN = re.compile(
    r"^(?:(?:第[一二三四五六七八九十百千〇零两]+条)|"
    r"(?:[一二三四五六七八九十]+、)|(?:（[一二三四五六七八九十]+）))"
)


class PolicyCorpusError(ValueError):
    """A manifest or source file violates the V0.3 corpus contract."""


@dataclass(frozen=True)
class PolicyDocument:
    document_id: str
    title: str
    file_name: str
    authority_code: str
    policy_level: str
    issuing_authority: str
    document_number: str
    issue_date: str
    effective_date: str
    expiry_date: str
    status: str
    region: str
    topic: str
    subtopic: str
    beneficiary_side: str
    confidentiality: str
    source_url: str
    local_file: str
    version: str
    supersedes: str
    superseded_by: str

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "PolicyDocument":
        missing = [field for field in METADATA_FIELDS if field not in row]
        if missing:
            raise PolicyCorpusError("metadata 缺少字段：" + "、".join(missing))
        values = {field: str(row[field] or "").strip() for field in METADATA_FIELDS}
        for field in ("document_id", "title", "file_name", "authority_code", "policy_level", "status",
                      "region", "topic", "confidentiality", "local_file"):
            if not values[field]:
                raise PolicyCorpusError(f"metadata {field} 不能为空。")
        if values["authority_code"] not in AUTHORITY_CODES:
            raise PolicyCorpusError(f"{values['document_id']}: 未知 authority_code。")
        if values["status"] not in STATUSES:
            raise PolicyCorpusError(f"{values['document_id']}: status 必须是 {sorted(STATUSES)} 之一。")
        if values["confidentiality"] not in CONFIDENTIALITIES:
            raise PolicyCorpusError(f"{values['document_id']}: 未知 confidentiality。")
        for field in ("issue_date", "effective_date", "expiry_date"):
            if values[field]:
                try:
                    date.fromisoformat(values[field])
                except ValueError as exc:
                    raise PolicyCorpusError(f"{values['document_id']}: {field} 必须为 YYYY-MM-DD。") from exc
        if values["effective_date"] and values["expiry_date"]:
            if values["effective_date"] > values["expiry_date"]:
                raise PolicyCorpusError(f"{values['document_id']}: effective_date 晚于 expiry_date。")
        relative = Path(values["local_file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise PolicyCorpusError(f"{values['document_id']}: local_file 必须是语料根目录内的相对路径。")
        return cls(**values)

    def is_current_on(self, as_of: date) -> bool:
        if self.status != "EFFECTIVE":
            return False
        return not (
            (self.effective_date and date.fromisoformat(self.effective_date) > as_of)
            or (self.expiry_date and date.fromisoformat(self.expiry_date) < as_of)
        )


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int | None
    text: str


def load_policy_metadata(path: Path) -> list[PolicyDocument]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise PolicyCorpusError("policy_metadata.csv 不能为空。")
    documents = [PolicyDocument.from_row(row) for row in rows]
    ids = [document.document_id for document in documents]
    file_names = [document.file_name for document in documents]
    if len(set(ids)) != len(ids):
        raise PolicyCorpusError("document_id 必须唯一。")
    if len(set(file_names)) != len(file_names):
        raise PolicyCorpusError("file_name 必须唯一；不同版本应使用独立 document_id。")
    return documents


def retrieval_documents(
    documents: Iterable[PolicyDocument],
    *,
    allowed_confidentiality: set[str],
    as_of: date,
    include_non_current: bool = False,
    region: str | None = None,
    topic: str | None = None,
) -> list[PolicyDocument]:
    """Apply access and status filters before indexing or retrieval.

    This function is intentionally shared by the index build and RAG runtime.
    An INTERNAL/RESTRICTED document cannot be embedded in the public index, so
    it never enters a public user's retrieval candidates or LLM prompt.
    """

    selected = []
    for document in documents:
        if document.confidentiality not in allowed_confidentiality:
            continue
        if not include_non_current and not document.is_current_on(as_of):
            continue
        if region and document.region != region:
            continue
        if topic and document.topic != topic:
            continue
        selected.append(document)
    return selected


def resolve_source_path(corpus_root: Path, document: PolicyDocument) -> Path:
    root = corpus_root.resolve()
    path = (root / document.local_file).resolve()
    if root != path and root not in path.parents:
        raise PolicyCorpusError(f"{document.document_id}: local_file 越过了 POLICY_CORPUS_ROOT。")
    if not path.is_file():
        raise PolicyCorpusError(f"{document.document_id}: 找不到源文件 {path}。")
    if path.suffix.casefold() not in SUPPORTED_SUFFIXES:
        raise PolicyCorpusError(
            f"{document.document_id}: 不支持 {path.suffix or '无扩展名'}；请先转换为 PDF、HTML 或 DOCX。"
        )
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    text = html.unescape(unicodedata.normalize("NFC", text))
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\u00ad", "")
    text = text.replace("\r", "\n")
    lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in text.splitlines()]
    merged: list[str] = []
    for line in lines:
        if not line:
            if merged and merged[-1]:
                merged.append("")
            continue
        if not merged or not merged[-1]:
            merged.append(line)
            continue
        previous = merged[-1]
        separator = " " if previous[-1:].isascii() and line[:1].isascii() else ""
        merged[-1] = previous + separator + line
    value = "\n".join(merged).strip()
    value = re.sub(r"(?<=[\u3400-\u9fff])[ \t]+(?=[\u3400-\u9fff])", "", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


class _HTMLTextExtractor(HTMLParser):
    _BLOCK_TAGS = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "br", "section", "article"}
    _IGNORED_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        lowered = tag.casefold()
        if lowered in self._IGNORED_TAGS:
            self._ignored_depth += 1
        elif lowered in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
        elif lowered in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _read_pdf(path: Path) -> list[ExtractedPage]:
    """Use the legacy corpus' layout-aware extractor, then pypdf as fallback."""

    try:
        import pymupdf

        with pymupdf.open(path) as reader:
            pages = [
                ExtractedPage(index, normalize_text(page.get_text("text", sort=True) or ""))
                for index, page in enumerate(reader, 1)
            ]
    except ImportError:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise PolicyCorpusError("缺少 PyMuPDF/pypdf；请安装 ai-service/requirements.txt。") from exc
        try:
            reader = PdfReader(str(path))
            pages = [
                ExtractedPage(index, normalize_text(page.extract_text() or ""))
                for index, page in enumerate(reader.pages, 1)
            ]
        except Exception as exc:  # parser errors must be visible in the extraction audit
            raise PolicyCorpusError(f"无法打开 PDF：{exc}") from exc
    except Exception as exc:
        raise PolicyCorpusError(f"无法打开 PDF：{exc}") from exc
    if not any(page.text for page in pages):
        raise PolicyCorpusError("PDF 没有可提取文本，需 OCR 后再入库。")
    return pages


def _read_html(path: Path) -> list[ExtractedPage]:
    parser = _HTMLTextExtractor()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    parser.close()
    text = normalize_text("".join(parser.parts))
    if not text:
        raise PolicyCorpusError("HTML 没有可提取正文。")
    return [ExtractedPage(None, text)]


def _read_docx(path: Path) -> list[ExtractedPage]:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml").decode("utf-8", errors="strict")
    except (KeyError, OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        raise PolicyCorpusError(f"无法解析 DOCX：{exc}") from exc
    paragraphs = re.findall(r"<w:p(?: [^>]*)?>(.*?)</w:p>", xml, flags=re.DOTALL)
    parts = []
    for paragraph in paragraphs:
        pieces = re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", paragraph, flags=re.DOTALL)
        value = html.unescape("".join(re.sub(r"<[^>]+>", "", piece) for piece in pieces))
        if value.strip():
            parts.append(value.strip())
    text = normalize_text("\n\n".join(parts))
    if not text:
        raise PolicyCorpusError("DOCX 没有可提取正文。")
    return [ExtractedPage(None, text)]


def extract_document(path: Path) -> list[ExtractedPage]:
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix in {".html", ".htm"}:
        return _read_html(path)
    if suffix == ".docx":
        return _read_docx(path)
    raise PolicyCorpusError(f"不支持的文档类型：{suffix}")


def _heading(value: str) -> str:
    first_line = value.strip().splitlines()[0] if value.strip() else ""
    return first_line[:120]


def _article_groups(pages: list[ExtractedPage]) -> list[tuple[str, list[int]]]:
    groups: list[tuple[str, list[int]]] = []
    current_lines: list[str] = []
    current_pages: list[int] = []
    pending_headings: list[str] = []
    pending_pages: list[int] = []

    def add_page(target: list[int], page_number: int | None) -> None:
        if page_number is not None and page_number not in target:
            target.append(page_number)

    for page in pages:
        for paragraph in (part.strip() for part in page.text.split("\n\n")):
            if not paragraph:
                continue
            if CHAPTER_PATTERN.match(paragraph):
                if current_lines:
                    groups.append(("\n\n".join(current_lines), current_pages))
                    current_lines, current_pages = [], []
                pending_headings.append(paragraph)
                add_page(pending_pages, page.page_number)
                continue
            if ARTICLE_PATTERN.match(paragraph) and current_lines:
                groups.append(("\n\n".join(current_lines), current_pages))
                current_lines, current_pages = pending_headings, pending_pages
                pending_headings, pending_pages = [], []
            if not current_lines and pending_headings:
                current_lines, current_pages = pending_headings, pending_pages
                pending_headings, pending_pages = [], []
            current_lines.append(paragraph)
            add_page(current_pages, page.page_number)
    if current_lines:
        groups.append(("\n\n".join(current_lines), current_pages))
    elif pending_headings:
        groups.append(("\n\n".join(pending_headings), pending_pages))
    return groups


def _split_long_group(text: str, maximum_chars: int) -> list[str]:
    if len(text) <= maximum_chars:
        return [text]
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > maximum_chars:
            sentences = [
                value.strip()
                for value in re.split(r"(?<=[。！？；])", paragraph)
                if value.strip()
            ]
            if len(sentences) == 1:
                sentences = [
                    paragraph[index : index + maximum_chars]
                    for index in range(0, len(paragraph), maximum_chars)
                ]
            for sentence in sentences:
                separator = "\n\n" if current else ""
                if current and len(current) + len(separator) + len(sentence) > maximum_chars:
                    pieces.append(current)
                    current = ""
                    separator = ""
                current = f"{current}{separator}{sentence}"
            continue
        if current and len(current) + len(paragraph) + 2 > maximum_chars:
            pieces.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        pieces.append(current)
    return pieces


def _pack_article_groups(
    groups: list[tuple[str, list[int]]], minimum_chars: int, maximum_chars: int
) -> list[tuple[str, list[int]]]:
    """Keep a complete article where possible, grouping short neighbours.

    Many rules contain short definition and list articles.  Indexing each as a
    five-character heading is neither semantically useful nor citation-safe;
    this packs neighbouring articles into an Article Group without splitting a
    clause in the middle.
    """

    packed: list[tuple[str, list[int]]] = []
    current_text = ""
    current_pages: list[int] = []

    def flush() -> None:
        nonlocal current_text, current_pages
        if current_text:
            packed.append((current_text, current_pages))
        current_text, current_pages = "", []

    for original_text, pages in groups:
        for text in _split_long_group(original_text, maximum_chars):
            separator = "\n\n" if current_text else ""
            if current_text and len(current_text) + len(separator) + len(text) > maximum_chars:
                flush()
                separator = ""
            current_text = f"{current_text}{separator}{text}"
            for page in pages:
                if page not in current_pages:
                    current_pages.append(page)
            if len(current_text) >= minimum_chars:
                flush()
    flush()
    return packed


def make_article_chunks(
    document: PolicyDocument,
    pages: list[ExtractedPage],
    source_sha256: str,
    *,
    maximum_chars: int = 1_800,
) -> list[dict[str, object]]:
    if maximum_chars < 400:
        raise PolicyCorpusError("maximum_chars 不得小于 400。")
    chunks: list[dict[str, object]] = []
    groups = _pack_article_groups(_article_groups(pages), minimum_chars=400, maximum_chars=maximum_chars)
    for group_text, page_numbers in groups:
        for text in _split_long_group(group_text, maximum_chars):
            section_title = _heading(text)
            article_match = re.search(
                r"(?:第[一二三四五六七八九十百千〇零两]+条|[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）)",
                text,
            )
            chapter_match = re.search(r"第[一二三四五六七八九十百千〇零两]+[编章节]", text)
            chunks.append(
                {
                    "chunk_id": f"{document.document_id}-C{len(chunks) + 1:04d}",
                    "document_id": document.document_id,
                    "source_filename": document.file_name,
                    "title": document.title,
                    "authority_code": document.authority_code,
                    "policy_level": document.policy_level,
                    "issuing_authority": document.issuing_authority,
                    "document_number": document.document_number,
                    "issue_date": document.issue_date,
                    "effective_date": document.effective_date,
                    "expiry_date": document.expiry_date,
                    "status": document.status,
                    "region": document.region,
                    "topic": document.topic,
                    "subtopic": document.subtopic,
                    "beneficiary_side": document.beneficiary_side,
                    "confidentiality": document.confidentiality,
                    "source_url": document.source_url,
                    "local_file": document.local_file,
                    "version": document.version,
                    "supersedes": document.supersedes,
                    "superseded_by": document.superseded_by,
                    "source_sha256": source_sha256,
                    "chapter_title": chapter_match.group(0) if chapter_match else "",
                    "section_title": section_title,
                    "article_no": article_match.group(0) if article_match else "",
                    "page_start": page_numbers[0] if page_numbers else None,
                    "page_end": page_numbers[-1] if page_numbers else None,
                    "page_numbers": page_numbers,
                    "char_count": len(text),
                    "text": text,
                }
            )
    if not chunks:
        raise PolicyCorpusError(f"{document.document_id}: 无法生成有效条款 Chunk。")
    return chunks


def build_policy_chunks(
    documents: Iterable[PolicyDocument],
    corpus_root: Path,
    *,
    maximum_chars: int = 1_800,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    chunks: list[dict[str, object]] = []
    audit: list[dict[str, object]] = []
    for document in documents:
        source_path = resolve_source_path(corpus_root, document)
        try:
            pages = extract_document(source_path)
            text_chars = sum(len(page.text) for page in pages)
            if text_chars < 40:
                raise PolicyCorpusError("可提取文本少于 40 字，需人工核验或 OCR。")
            document_chunks = make_article_chunks(
                document, pages, sha256_file(source_path), maximum_chars=maximum_chars
            )
            chunks.extend(document_chunks)
            audit.append(
                {
                    "document_id": document.document_id,
                    "file_name": document.file_name,
                    "status": "PASS",
                    "page_count": len(pages),
                    "text_chars": text_chars,
                    "chunk_count": len(document_chunks),
                    "pages_without_text": sum(not page.text for page in pages),
                    "error": "",
                }
            )
        except PolicyCorpusError as exc:
            audit.append(
                {
                    "document_id": document.document_id,
                    "file_name": document.file_name,
                    "status": "FAIL",
                    "page_count": 0,
                    "text_chars": 0,
                    "chunk_count": 0,
                    "pages_without_text": 0,
                    "error": str(exc),
                }
            )
    if not chunks:
        raise PolicyCorpusError("没有可供索引的有效政策 Chunk。")
    return chunks, audit


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as destination:
        for row in rows:
            destination.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_audit(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def document_dict(document: PolicyDocument) -> dict[str, str]:
    return asdict(document)
