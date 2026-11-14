"""Embed the chunked corpus using the configured Ollama embedding model.

Run from the ``starter/`` directory:
    python scripts/embed_corpus.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from src.chunking import by_paragraph, fixed_size
from src.embeddings import OllamaEmbedder
from src.models import Chunk, DocumentPage


def load_cached_pages(document_id: str) -> list[DocumentPage]:
    cache_file = Path("data") / "processed" / document_id / "pages.json"
    if not cache_file.exists():
        raise FileNotFoundError(
            f"Cached pages not found at {cache_file}. "
            "Please run `python scripts/ingest_corpus.py` first."
        )
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    return [DocumentPage(**p) for p in data["pages"]]


def embed_strategy(
    strategy_name: str,
    chunks: list[Chunk],
    embedder: OllamaEmbedder,
    output_file: Path,
) -> None:
    print(f"\n--- Embedding Strategy: {strategy_name} ({len(chunks)} chunks) ---")
    texts = [c.text for c in chunks]
    
    t0 = time.perf_counter()
    vectors = embedder.embed_documents(texts, batch_size=16)
    elapsed = time.perf_counter() - t0
    
    print(f" Embedded {len(vectors)} chunks in {elapsed:.2f}s "
          f"({len(vectors)/elapsed:.1f} chunks/sec). Dimensions: {len(vectors[0])}")

    # Combine chunk data with embedding vector
    records = []
    for chunk, vec in zip(chunks, vectors):
        chunk_dict = chunk.__dict__.copy()
        chunk_dict["embedding"] = vec
        records.append(chunk_dict)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f" Saved to {output_file}")


def main() -> None:
    doc_id = "vf8-frg-vi-1690188048"
    print(f"Loading parsed pages for '{doc_id}'...")
    pages = load_cached_pages(doc_id)
    print(f"Loaded {len(pages)} pages.")

    print("\nInitializing Ollama Embedder...")
    embedder = OllamaEmbedder()
    print(f" Embedder ready: model={embedder.model_name}, dim={embedder.dimensions}")

    # 1. Strategy A: Fixed-size Chunking (size=500, overlap=50)
    fixed_chunks: list[Chunk] = []
    for page in pages:
        fixed_chunks.extend(fixed_size(page, size=500, overlap=50))
    embed_strategy(
        "fixed_size",
        fixed_chunks,
        embedder,
        Path("data") / "processed" / "embedded_fixed.json",
    )

    # 2. Strategy B: Paragraph / Structure-aware Chunking (max_size=800)
    para_chunks: list[Chunk] = []
    for page in pages:
        para_chunks.extend(by_paragraph(page, max_size=800))
    embed_strategy(
        "by_paragraph",
        para_chunks,
        embedder,
        Path("data") / "processed" / "embedded_paragraph.json",
    )

    print("\n All embedding completed successfully!")


if __name__ == "__main__":
    main()
