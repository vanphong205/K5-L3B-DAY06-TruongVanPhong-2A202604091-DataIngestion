"""Ingest the corpus PDFs and write a manifest for the lab.

Run from the ``starter/`` directory:

    python scripts/ingest_corpus.py                      # all PDFs in ../docs
    python scripts/ingest_corpus.py ../docs/a.pdf --force
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion import load_pdf  # noqa: E402

MIN_CONTENT_PAGES = 30


def document_id_for(path: Path) -> str:
    """Stable, readable ID: 'VF8_FRG_VI_1690188048.pdf' -> 'vf8-frg-vi-1690188048'."""
    stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    return stem


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pdfs",
        nargs="*",
        type=Path,
        default=sorted(Path("../docs").glob("*.pdf")),
        help="PDF files; defaults to ../docs/*.pdf",
    )
    parser.add_argument("--force", action="store_true", help="ignore the parse cache")
    parser.add_argument("--ocr", action="store_true", help="OCR scanned pages")
    parser.add_argument(
        "--license",
        default="TODO: ghi rõ nguồn và quyền sử dụng",
        help="license/permission note stored in the manifest",
    )
    args = parser.parse_args()

    if not args.pdfs:
        raise SystemExit("No PDF found. Pass paths or put them in ../docs")

    manifest_path = Path("data") / "processed" / "manifest.json"
    manifest: dict = {"generated_at": date.today().isoformat(), "sources": []}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["generated_at"] = date.today().isoformat()

    by_id = {entry["source_id"]: entry for entry in manifest["sources"]}
    total_pages = 0

    for pdf in args.pdfs:
        if not pdf.exists():
            raise SystemExit(f"Missing file: {pdf}")

        source_id = document_id_for(pdf)
        pages = load_pdf(
            pdf,
            document_id=source_id,
            source=pdf.as_posix(),
            force=args.force,
            do_ocr=args.ocr,
        )
        text_pages = [page for page in pages if page.metadata.get("has_text")]
        numbered = [page for page in pages if page.metadata.get("section_no") is not None]
        # Front matter (cover, legal notice) is ingested but not counted as
        # content pages, per RULES.md.
        content_pages = [
            page
            for page in text_pages
            if not numbered or page.page >= numbered[0].page
        ]
        chars = sum(len(page.text) for page in pages)
        images = sum(len(page.metadata.get("images", [])) for page in pages)
        title = pages[0].metadata.get("section") or pdf.stem
        total_pages += len(content_pages)

        by_id[source_id] = {
            "source_id": source_id,
            "title": title,
            "source_path_or_url": pdf.as_posix(),
            "license_or_permission": args.license,
            "accessed_at": date.today().isoformat(),
            "sha256": sha256_of(pdf),
            "pages": [page.page for page in text_pages],
            "page_count": len(pages),
            "content_pages": len(content_pages),
            "char_count": chars,
            "image_count": images,
            "sections": sorted(
                {
                    page.metadata.get("section")
                    for page in pages
                    if page.metadata.get("section")
                }
            ),
        }
        print(
            f"{source_id}: {len(pages)} pages ({len(text_pages)} with text, "
            f"{len(content_pages)} content), {chars} chars, {images} figures, "
            f"cache -> data/processed/{source_id}/"
        )

    manifest["sources"] = sorted(by_id.values(), key=lambda entry: entry["source_id"])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nCorpus: {total_pages} pages with text -> {manifest_path}")
    if total_pages < MIN_CONTENT_PAGES:
        print(
            f"WARNING: {total_pages} < {MIN_CONTENT_PAGES} content pages required. "
            "Add another document (RULES.md allows combining files)."
        )


if __name__ == "__main__":
    main()
