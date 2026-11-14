"""Read and normalize source data with Docling, keeping page-level provenance."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .models import DocumentPage

# Docling labels that only repeat running headers/footers: drop them from the text.
_SKIP_LABELS = {"page_header", "page_footer"}

# Markdown prefix per Docling label, so later chunking can keep the structure.
_PREFIX = {
    "title": "# ",
    "section_header": "## ",
    "list_item": "- ",
}

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"), None)
_SPACES = re.compile(r"[ \t\u00a0\u2007\u202f]+")
_BLANK_LINES = re.compile(r"\n{3,}")
# "1. Nhận dạng xe" / "0. Bảng tổng quan": the document's numbered sections.
_SECTION = re.compile(r"^\s*(\d+)\.\s+\S")

# Bump when the parsing output changes so old caches are not reused silently.
_CACHE_VERSION = 2
# Decorative icons (warning triangles, logo) are smaller than this on the short side.
_MIN_IMAGE_SIDE = 150


def load_pdf(
    path: Path,
    document_id: str,
    source: str,
    *,
    images_dir: Path | None = None,
    cache_path: Path | None = None,
    force: bool = False,
    do_ocr: bool = False,
    page_range: tuple[int, int] | None = None,
) -> list[DocumentPage]:
    """Extract each physical page; keep its page number and source.

    Uses Docling for layout-aware parsing (reading order, headings, tables, pictures).
    Pages with no text are kept with ``metadata["has_text"] = False`` so the caller
    can apply OCR separately, per the lab rules.

    Docling cannot see text that sits inside a figure; when a page's plain text
    layer is clearly longer, that text is used instead and
    ``metadata["text_source"]`` says so.

    Args:
        path: PDF file to read.
        document_id: stable ID stored on every page and chunk.
        source: human-readable source (path or URL) kept for traceability.
        images_dir: where extracted pictures are written. Defaults to
            ``data/processed/<document_id>/images`` relative to the working dir.
        cache_path: JSON cache of the parsed pages. Defaults to
            ``data/processed/<document_id>/pages.json``.
        force: ignore an existing cache and re-run Docling.
        do_ocr: enable Docling OCR for scanned pages (slower; not needed when the
            PDF already has a text layer).
        page_range: optional 1-based ``(first, last)`` range for a quick smoke test.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    if page_range is not None:
        # A partial parse must never be reused as the full corpus.
        force, cache_path = True, None

    processed_dir = Path("data") / "processed" / document_id
    images_dir = Path(images_dir) if images_dir else processed_dir / "images"
    cache_path = Path(cache_path) if cache_path else processed_dir / "pages.json"

    if cache_path is not None and cache_path.exists() and not force:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        same_file = (
            cached.get("version") == _CACHE_VERSION
            and cached.get("source_file") == path.name
            and cached.get("file_size") == path.stat().st_size
        )
        if same_file:
            return [DocumentPage(**page) for page in cached["pages"]]

    doc = _convert(path, do_ocr=do_ocr, page_range=page_range)
    pages = _pages_from_document(
        doc, document_id, source, images_dir, raw_texts=_raw_page_texts(path)
    )

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _CACHE_VERSION,
            "docling_version": _docling_version(),
            "source_file": path.name,
            "file_size": path.stat().st_size,
            "document_id": document_id,
            "images": str(images_dir.as_posix()),
            "pages": [page.__dict__ for page in pages],
        }
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return pages


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace without discarding useful structure.

    - NFC so Vietnamese diacritics compare as one code point.
    - Drop zero-width/soft-hyphen characters and non-printable controls.
    - Unify newlines and collapse runs of blank lines to one blank line.
    - Keep single newlines and bullet markers (structure survives chunking).
    """
    text = unicodedata.normalize("NFC", text or "")
    text = text.translate(_ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        ch
        if ch in "\n\t" or unicodedata.category(ch)[0] != "C"
        else " "
        for ch in text
    )
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def _convert(
    path: Path,
    *,
    do_ocr: bool,
    page_range: tuple[int, int] | None,
):
    """Run Docling once and return its DoclingDocument."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = do_ocr
    options.do_table_structure = True  # TableFormer; harmless when no tables exist
    options.generate_picture_images = True
    options.images_scale = 2.0

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    kwargs = {"page_range": page_range} if page_range else {}
    result = converter.convert(str(path), **kwargs)

    status = getattr(result.status, "name", str(result.status))
    if status != "SUCCESS":
        raise RuntimeError(f"Docling failed on {path}: {result.status}")

    return result.document


def _pages_from_document(
    doc: Any,
    document_id: str,
    source: str,
    images_dir: Path,
    *,
    raw_texts: dict[int, str] | None = None,
) -> list[DocumentPage]:
    """Group Docling items by page, preserving reading order.

    Two repairs are applied on top of the raw Docling output:

    - Text inside a figure region is dropped by Docling. When the plain-text
      extraction of a page is much longer than Docling's text, the plain text is
      used instead and ``metadata["text_source"]`` is set to ``"pypdf"``.
    - Decorative icons (small logos, warning triangles) are skipped and only
      real figures are written to ``images_dir``.
    """
    from docling_core.types.doc import PictureItem, TableItem, TextItem

    if images_dir.exists():
        for stale in images_dir.glob("p*_fig*.png"):
            stale.unlink()

    pages: dict[int, dict[str, Any]] = {}
    section: str | None = None
    section_no: int | None = None
    figure_no: dict[int, int] = {}

    for entry in doc.iterate_items():
        item, _level = entry if isinstance(entry, tuple) else (entry, 0)
        provenance = getattr(item, "prov", None) or []
        if not provenance:
            continue
        page_no = provenance[0].page_no

        page = pages.setdefault(
            page_no,
            {
                "blocks": [],
                "images": [],
                "n_tables": 0,
                "section": section,
                "section_no": section_no,
            },
        )

        if isinstance(item, TableItem):
            markdown = _table_markdown(item, doc)
            if markdown.strip():
                page["blocks"].append(markdown.strip())
                page["n_tables"] += 1
            continue

        if isinstance(item, PictureItem):
            image = item.get_image(doc)
            if image is None or min(image.size) < _MIN_IMAGE_SIDE:
                continue
            number = figure_no.get(page_no, 0) + 1
            figure_no[page_no] = number
            images_dir.mkdir(parents=True, exist_ok=True)
            name = f"p{page_no:02d}_fig{number:02d}.png"
            image.save(images_dir / name)
            page["images"].append(f"images/{name}")
            continue

        if not isinstance(item, TextItem):
            continue

        label = _label(item)
        if label in _SKIP_LABELS:
            continue
        text = (item.text or "").strip()
        if not text:
            continue

        if label in ("title", "section_header"):
            # Only the numbered sections are stable filters ("5. Năng lượng
            # Lưu trữ"); sub-headings and callout labels ("LƯU Ý", "Bước 2:")
            # stay in the text but must not overwrite the section.
            match = _SECTION.match(text)
            if match:
                section, section_no = text, int(match.group(1))
            elif section is None:
                section = text
            page["section"] = section
            page["section_no"] = section_no
        page["blocks"].append(_PREFIX.get(label, "") + text)

    result: list[DocumentPage] = []
    for page_no in sorted(pages):
        data = pages[page_no]
        text = normalize_text("\n\n".join(data["blocks"]))

        raw = normalize_text((raw_texts or {}).get(page_no, ""))
        text_source = "docling"
        if len(raw) > len(text) * 1.3 + 60:
            # Docling dropped text that sits inside a figure (e.g. the labelled
            # diagram on page 5); the plain text layer still has those labels.
            text, text_source = raw, "pypdf"

        metadata: dict[str, Any] = {
            "section": data["section"],
            "section_no": data["section_no"],
            "images": data["images"],
            "n_tables": data["n_tables"],
            "text_source": text_source,
            "has_text": bool(text),
        }
        page_item = doc.pages.get(page_no)
        if page_item is not None:
            metadata["page_size"] = [
                round(float(page_item.size.width), 1),
                round(float(page_item.size.height), 1),
            ]
        result.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=page_no,
                text=text,
                metadata=metadata,
            )
        )
    return result


def _raw_page_texts(path: Path) -> dict[int, str]:
    """Plain text layer per page, used to detect content Docling dropped."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return {i + 1: page.extract_text() or "" for i, page in enumerate(reader.pages)}


def _docling_version() -> str:
    try:
        from importlib.metadata import version

        return version("docling")
    except Exception:
        return "unknown"


def _label(item: Any) -> str:
    label = getattr(item, "label", None)
    value = getattr(label, "value", label)
    return str(value).lower() if value else ""


def _table_markdown(item: Any, doc: Any) -> str:
    try:
        return item.export_to_markdown(doc)
    except TypeError:  # older Docling signatures take no document
        return item.export_to_markdown()
