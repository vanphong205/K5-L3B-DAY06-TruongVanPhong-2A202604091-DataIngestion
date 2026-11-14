"""Audit chunk coherence on 10 fixed page positions."""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    fixed_chunks = json.loads(Path("starter/data/processed/embedded_fixed.json").read_text(encoding="utf-8"))
    para_chunks = json.loads(Path("starter/data/processed/embedded_paragraph.json").read_text(encoding="utf-8"))

    sample_pages = [6, 7, 8, 9, 10, 11, 12, 15, 19, 20]

    print("=" * 80)
    print("CHUNK COHERENCE AUDIT: 10 FIXED POSITIONS")
    print("=" * 80)

    for p in sample_pages:
        print(f"\n================ PAGE {p} ================")
        f_hits = [c for c in fixed_chunks if c["page"] == p]
        p_hits = [c for c in para_chunks if c["page"] == p]

        print(f"--- Strategy A: fixed_size ({len(f_hits)} chunks) ---")
        for i, c in enumerate(f_hits):
            print(f"  Chunk {i} (len={len(c['text'])}): {repr(c['text'][:120])} ... {repr(c['text'][-60:])}")

        print(f"--- Strategy B: by_paragraph ({len(p_hits)} chunks) ---")
        for i, c in enumerate(p_hits):
            print(f"  Chunk {i} (len={len(c['text'])}): {repr(c['text'][:120])} ... {repr(c['text'][-60:])}")


if __name__ == "__main__":
    main()
