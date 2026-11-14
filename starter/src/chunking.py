from __future__ import annotations

"""Implement fixed-size and structure-aware chunking."""
import re
from typing import List

from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Split text into overlapping fixed-size windows and retain page metadata."""
    text = (page.text or "").strip()
    if not text:
        return []

    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")
    if overlap < 0 or overlap >= size:
        raise ValueError(f"overlap must be in range [0, {size}), got {overlap}")

    step = size - overlap
    chunks: list[Chunk] = []
    start = 0
    chunk_idx = 0

    while start < len(text):
        end = min(start + size, len(text))
        chunk_text = text[start:end].strip()

        if chunk_text:
            meta = dict(page.metadata)
            meta.update(
                {
                    "chunk_index": chunk_idx,
                    "strategy": "fixed_size",
                    "char_count": len(chunk_text),
                    "start_offset": start,
                    "end_offset": end,
                }
            )
            chunk_id = f"{page.document_id}_p{page.page}_c{chunk_idx:03d}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=chunk_text,
                    metadata=meta,
                )
            )
            chunk_idx += 1

        if end >= len(text):
            break
        start += step

    return chunks


def _split_oversized_block(block: str, max_size: int) -> list[str]:
    """Recursively split a block exceeding max_size down to lines, sentences, or words."""
    block = block.strip()
    if not block:
        return []
    if len(block) <= max_size:
        return [block]

    # 1. Try splitting by line breaks (e.g., table rows or list items)
    lines = [line.strip() for line in block.split("\n") if line.strip()]
    if len(lines) > 1:
        sub_blocks: list[str] = []
        curr = ""
        for line in lines:
            candidate = f"{curr}\n{line}" if curr else line
            if len(candidate) <= max_size:
                curr = candidate
            else:
                if curr:
                    sub_blocks.extend(_split_oversized_block(curr, max_size))
                curr = line
        if curr:
            sub_blocks.extend(_split_oversized_block(curr, max_size))
        if sub_blocks:
            return sub_blocks

    # 2. Try splitting by sentence endings (. , ! , ? followed by whitespace)
    sentence_delims = re.split(r"(?<=[.!?])\s+", block)
    if len(sentence_delims) > 1:
        sub_blocks: list[str] = []
        curr = ""
        for s in sentence_delims:
            candidate = f"{curr} {s}" if curr else s
            if len(candidate) <= max_size:
                curr = candidate
            else:
                if curr:
                    sub_blocks.append(curr.strip())
                curr = s
        if curr:
            sub_blocks.append(curr.strip())
        return sub_blocks

    # 3. Fallback: split by word boundary
    words = block.split()
    sub_blocks: list[str] = []
    curr = ""
    for w in words:
        candidate = f"{curr} {w}" if curr else w
        if len(candidate) <= max_size:
            curr = candidate
        else:
            if curr:
                sub_blocks.append(curr.strip())
            curr = w
    if curr:
        sub_blocks.append(curr.strip())

    return sub_blocks


def by_paragraph(page: DocumentPage, max_size: int = 800) -> list[Chunk]:
    """Group paragraphs / structure blocks, split oversized ones, and retain metadata."""
    raw_text = (page.text or "").strip()
    if not raw_text:
        return []

    if max_size <= 0:
        raise ValueError(f"max_size must be positive, got {max_size}")

    # 1. Structure-aware splitting:
    # Separate by double or more newlines to identify paragraphs, tables, or sections
    raw_paragraphs = re.split(r"\n{2,}", raw_text)

    # Clean and split any individual oversized blocks
    atomic_blocks: list[str] = []
    for para in raw_paragraphs:
        cleaned = para.strip()
        if not cleaned:
            continue
        if len(cleaned) <= max_size:
            atomic_blocks.append(cleaned)
        else:
            atomic_blocks.extend(_split_oversized_block(cleaned, max_size))

    if not atomic_blocks:
        return []

    # 2. Greedy grouping of small consecutive paragraphs / blocks
    grouped_chunks: list[str] = []
    current_acc: list[str] = []
    current_len = 0

    for block in atomic_blocks:
        # Projected length if we append this block
        added_len = len(block) + (2 if current_acc else 0)

        # If adding would exceed max_size (and we already have accumulated content):
        if current_acc and (current_len + added_len > max_size):
            grouped_chunks.append("\n\n".join(current_acc))
            current_acc = [block]
            current_len = len(block)
        else:
            current_acc.append(block)
            current_len += added_len

    if current_acc:
        grouped_chunks.append("\n\n".join(current_acc))

    # 3. Build Chunk objects with full metadata and traceability
    chunks: list[Chunk] = []
    for idx, chunk_text in enumerate(grouped_chunks):
        chunk_text = chunk_text.strip()
        if not chunk_text:
            continue

        meta = dict(page.metadata)
        meta.update(
            {
                "chunk_index": idx,
                "strategy": "by_paragraph",
                "char_count": len(chunk_text),
                "is_multiline": "\n" in chunk_text,
            }
        )

        chunk_id = f"{page.document_id}_p{page.page}_c{idx:03d}"
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                document_id=page.document_id,
                source=page.source,
                page=page.page,
                text=chunk_text,
                metadata=meta,
            )
        )

    return chunks

