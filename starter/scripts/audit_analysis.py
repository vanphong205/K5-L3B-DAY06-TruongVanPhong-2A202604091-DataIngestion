"""Audit script to perform deep inspection of test traces, chunk coherence, and metadata usefulness."""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    traces = json.loads(Path("results/traces.json").read_text(encoding="utf-8"))
    test_traces = [t for t in traces if t["split"] == "test"]

    print("=" * 80)
    print("DETAILED TEST SPLIT TRACES (5 questions x 3 strategies)")
    print("=" * 80)

    for t in test_traces:
        strat = t["strategy"]
        qid = t["question_id"]
        qtext = t["question"]
        gold_p = t["gold_page"]
        h1 = t["hit_at_1"]
        h3 = t["hit_at_3"]
        print(f"\n--- Strategy: {strat} | QID: {qid} ---")
        print(f"Question: {qtext}")
        print(f"Gold Page: {gold_p} | Hit@1: {h1} | Hit@3: {h3}")
        print(f"Evidence Quote: {t['evidence_quote']}")
        for h in t["hits"]:
            rank = h["rank"]
            p = h["page"]
            score = h["score"]
            cid = h["chunk_id"]
            ehit = h["is_evidence_hit"]
            sec = h["metadata"].get("section", "N/A")
            sec_no = h["metadata"].get("section_no", "N/A")
            print(f"  Rank {rank}: [Page {p}] (Score: {score:.4f}, Hit: {ehit}) Sec: {sec_no} - {sec}")
            print(f"    ID: {cid}")
            print(f"    Text: {h['text'][:140]}...")


if __name__ == "__main__":
    main()
