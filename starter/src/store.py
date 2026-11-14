"""Store and search vectors using PostgreSQL + pgvector."""
from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        """Retain connection settings; validate model dimensions."""
        if not database_url:
            raise ValueError("database_url must not be empty")
        if dimensions <= 0:
            raise ValueError(f"dimensions must be positive, got {dimensions}")

        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        """Create table with vector column and source/page/filter metadata."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                # Create document_chunks table
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id TEXT PRIMARY KEY,
                        strategy TEXT NOT NULL,
                        chunk_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        page INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        section TEXT,
                        section_no INTEGER,
                        embedding vector({self.dimensions}) NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    """
                )

                # Indexes for fast filtering and retrieval
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chunks_strategy ON document_chunks (strategy);
                    CREATE INDEX IF NOT EXISTS idx_chunks_doc_strat ON document_chunks (document_id, strategy);
                    CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON document_chunks USING gin (metadata);
                    CREATE INDEX IF NOT EXISTS idx_chunks_section ON document_chunks (strategy, section);
                    CREATE INDEX IF NOT EXISTS idx_chunks_section_no ON document_chunks (strategy, section_no);
                    """
                )
            conn.commit()

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Validate lengths/dimensions and write stable IDs without duplicates.

        When re-ingesting changed source documents, remove obsolete chunks too.
        """
        if len(chunks) != len(vectors):
            raise ValueError(
                f"Mismatch: got {len(chunks)} chunks and {len(vectors)} vectors"
            )

        if not chunks:
            return

        for idx, vec in enumerate(vectors):
            if len(vec) != self.dimensions:
                raise ValueError(
                    f"Vector at index {idx} has dimension {len(vec)}, expected {self.dimensions}"
                )

        new_ids = [f"{strategy}_{chunk.chunk_id}" for chunk in chunks]
        doc_ids = list({chunk.document_id for chunk in chunks})

        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # Remove obsolete chunks for this document and strategy that are not in the new set
                cur.execute(
                    """
                    DELETE FROM document_chunks
                    WHERE strategy = %s
                      AND document_id = ANY(%s)
                      AND NOT (id = ANY(%s));
                    """,
                    (strategy, doc_ids, new_ids),
                )

                # Prepare upsert query
                sql = """
                    INSERT INTO document_chunks (
                        id, strategy, chunk_id, document_id, source, page, text,
                        metadata, section, section_no, embedding
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        source = EXCLUDED.source,
                        page = EXCLUDED.page,
                        text = EXCLUDED.text,
                        metadata = EXCLUDED.metadata,
                        section = EXCLUDED.section,
                        section_no = EXCLUDED.section_no,
                        embedding = EXCLUDED.embedding;
                """

                rows = []
                for chunk, vec in zip(chunks, vectors):
                    row_id = f"{strategy}_{chunk.chunk_id}"
                    meta = chunk.metadata or {}
                    section = meta.get("section")
                    section_no = meta.get("section_no")
                    # Format vector as string "[0.1, 0.2, ...]" for pgvector casting
                    vec_str = f"[{','.join(f'{x:.8f}' for x in vec)}]"

                    rows.append(
                        (
                            row_id,
                            strategy,
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.source,
                            chunk.page,
                            chunk.text,
                            Jsonb(meta),
                            section,
                            section_no,
                            vec_str,
                        )
                    )

                cur.executemany(sql, rows)
            conn.commit()

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Filter permitted metadata in SQL, rank by cosine distance, return top-k.

        Return chunk ID, text, score and metadata. Parameterize user-supplied values.
        """
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"Query vector dimension {len(query_vector)} != store dimensions {self.dimensions}"
            )

        vec_str = f"[{','.join(f'{x:.8f}' for x in query_vector)}]"

        where_clauses = ["strategy = %s"]
        params: list[Any] = [strategy]

        if filters:
            for key, val in filters.items():
                if val is None:
                    continue
                if key == "section":
                    # Support partial/exact matching on section name
                    where_clauses.append("section ILIKE %s")
                    params.append(f"%{val}%")
                elif key == "section_no":
                    where_clauses.append("section_no = %s")
                    params.append(int(val))
                elif key == "page":
                    where_clauses.append("page = %s")
                    params.append(int(val))
                else:
                    # Generic JSONB filter
                    where_clauses.append("metadata->>%s = %s")
                    params.extend([str(key), str(val)])

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT
                chunk_id,
                document_id,
                source,
                page,
                text,
                metadata,
                1 - (embedding <=> %s::vector) AS cosine_similarity,
                embedding <=> %s::vector AS distance
            FROM document_chunks
            WHERE {where_sql}
            ORDER BY embedding <=> %s::vector ASC
            LIMIT %s;
        """
        # params order: vec_str (similarity), vec_str (distance), where params..., vec_str (order by), top_k
        full_params = [vec_str, vec_str] + params + [vec_str, top_k]

        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, full_params)
                rows = cur.fetchall()

        results = []
        for r in rows:
            results.append(
                {
                    "chunk_id": r[0],
                    "document_id": r[1],
                    "source": r[2],
                    "page": r[3],
                    "text": r[4],
                    "metadata": r[5] if isinstance(r[5], dict) else json.loads(r[5]),
                    "score": round(float(r[6]), 5),
                    "distance": round(float(r[7]), 5),
                }
            )
        return results
