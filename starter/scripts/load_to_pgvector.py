"""Load embedded chunks into PostgreSQL + pgvector and verify search.

Run from the ``starter/`` directory:
    python scripts/load_to_pgvector.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from src.embeddings import OllamaEmbedder
from src.models import Chunk
from src.store import PgVectorStore


def load_embedded_file(path: Path) -> tuple[list[Chunk], list[list[float]]]:
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}. Run `python scripts/embed_corpus.py` first."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    chunks: list[Chunk] = []
    vectors: list[list[float]] = []

    for item in data:
        vec = item["embedding"]
        chunk = Chunk(
            chunk_id=item["chunk_id"],
            document_id=item["document_id"],
            source=item["source"],
            page=item["page"],
            text=item["text"],
            metadata=item["metadata"],
        )
        chunks.append(chunk)
        vectors.append(vec)

    return chunks, vectors


def find_data_file(filename: str) -> Path:
    candidates = [
        Path("data") / "processed" / filename,
        Path("starter") / "data" / "processed" / filename,
        Path(__file__).resolve().parents[1] / "data" / "processed" / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Cannot find {filename} in any of: {[str(c) for c in candidates]}")


def main() -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL is missing in .env")

    print(f"Connecting to database...")
    dimensions = 768  # nomic-embed-text dimensions
    store = PgVectorStore(database_url=db_url, dimensions=dimensions)

    print("Creating schema and pgvector table...")
    store.create_schema()
    print(" Schema ready (table: document_chunks, vector dim: 768).")

    # 1. Load & upsert Strategy A (fixed_size)
    path_fixed = find_data_file("embedded_fixed.json")
    chunks_a, vecs_a = load_embedded_file(path_fixed)
    print(f"\nUpserting {len(chunks_a)} chunks for strategy 'fixed_size'...")
    t0 = time.perf_counter()
    store.upsert("fixed_size", chunks_a, vecs_a)
    print(f" Strategy 'fixed_size' indexed in {time.perf_counter() - t0:.2f}s")

    # 2. Load & upsert Strategy B / C (by_paragraph)
    path_para = find_data_file("embedded_paragraph.json")
    chunks_b, vecs_b = load_embedded_file(path_para)
    print(f"\nUpserting {len(chunks_b)} chunks for strategy 'by_paragraph'...")
    t0 = time.perf_counter()
    store.upsert("by_paragraph", chunks_b, vecs_b)
    print(f" Strategy 'by_paragraph' indexed in {time.perf_counter() - t0:.2f}s")

    # 3. Test search query
    print("\n--- Verifying Retrieval from Database ---")
    embedder = OllamaEmbedder()
    test_query = "Ngắt cầu chì cứu hộ và ắc quy 12V xe VinFast VF 8 như thế nào?"
    print(f"Test query: '{test_query}'")
    q_vec = embedder.embed_query(test_query)

    print("\n[Strategy: fixed_size] Top-3 results:")
    hits_a = store.search("fixed_size", q_vec, top_k=3)
    for i, hit in enumerate(hits_a, 1):
        print(f"  {i}. [Page {hit['page']}] (Score: {hit['score']:.4f}) ID: {hit['chunk_id']}")
        print(f"     Preview: {hit['text'][:120]}...\n")

    print("[Strategy: by_paragraph] Top-3 results:")
    hits_b = store.search("by_paragraph", q_vec, top_k=3)
    for i, hit in enumerate(hits_b, 1):
        print(f"  {i}. [Page {hit['page']}] (Score: {hit['score']:.4f}) ID: {hit['chunk_id']}")
        print(f"     Preview: {hit['text'][:120]}...\n")

    print("[Strategy: by_paragraph WITH FILTER (section_no=5: Năng lượng)] Top-3 results:")
    hits_c = store.search("by_paragraph", q_vec, top_k=3, filters={"section_no": 5})
    for i, hit in enumerate(hits_c, 1):
        print(f"  {i}. [Page {hit['page']}] (Score: {hit['score']:.4f}) ID: {hit['chunk_id']}")
        print(f"     Section: {hit['metadata'].get('section')} | Preview: {hit['text'][:120]}...\n")

    print(" Database setup and vector retrieval verified successfully!")


if __name__ == "__main__":
    main()
