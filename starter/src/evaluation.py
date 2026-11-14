"""Evaluate retrieved evidence and preserve per-query traces."""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def _normalize_text(s: str) -> str:
    """Normalize text for evidence matching."""
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_evidence_hit(gold_quote: str, gold_page: int, chunk: dict[str, Any]) -> bool:
    """Check if the chunk belongs to the gold page and contains the required evidence."""
    chunk_page = chunk.get("page")
    if chunk_page != gold_page:
        return False

    chunk_norm = _normalize_text(chunk.get("text", ""))
    quote_norm = _normalize_text(gold_quote)

    if quote_norm in chunk_norm:
        return True

    # If the quote is multi-sentence, check if significant sub-clauses are matched
    words = quote_norm.split()
    if len(words) <= 5:
        return quote_norm in chunk_norm

    # Check for strong keyword / phrase overlap (>= 70% of tokens match in order or sub-phrase)
    window_size = min(len(words), 8)
    sub_phrases = [" ".join(words[i : i + window_size]) for i in range(0, len(words) - window_size + 1, 3)]
    matched = sum(1 for phrase in sub_phrases if phrase in chunk_norm)
    return matched >= max(1, len(sub_phrases) // 2)


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Check source/page and enough gold evidence; keep hit@1 and hit@3 trace.

    Accept any documented alternative gold evidence.
    """
    gold_quote = question.get("evidence_quote", "")
    gold_page = question.get("gold_page")

    hit_ranks: list[int] = []
    evaluated_hits = []

    for rank, hit in enumerate(hits, 1):
        hit_info = dict(hit)
        matched = is_evidence_hit(gold_quote, gold_page, hit)
        hit_info["is_evidence_hit"] = matched
        hit_info["rank"] = rank
        evaluated_hits.append(hit_info)
        if matched:
            hit_ranks.append(rank)

    hit_at_1 = 1 if (1 in hit_ranks) else 0
    hit_at_3 = 1 if len(hit_ranks) > 0 else 0

    return {
        "question_id": question.get("id"),
        "split": question.get("split"),
        "question": question.get("question"),
        "expected_answer": question.get("expected_answer"),
        "gold_page": gold_page,
        "evidence_quote": gold_quote,
        "filter": question.get("filter"),
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_ranks": hit_ranks,
        "hits": evaluated_hits,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for trace in traces:
        strat = trace.get("strategy", "unknown")
        split = trace.get("split", "unknown")
        key = f"{strat}:{split}"
        groups.setdefault(key, []).append(trace)

    results: dict[str, Any] = {}
    for key, items in sorted(groups.items()):
        strat, split = key.split(":")
        total = len(items)
        hit1 = sum(t["hit_at_1"] for t in items)
        hit3 = sum(t["hit_at_3"] for t in items)

        results[key] = {
            "strategy": strat,
            "split": split,
            "total": total,
            "hit1_count": hit1,
            "hit1_ratio": f"{hit1}/{total}",
            "hit1_pct": round(hit1 / total * 100, 1) if total else 0.0,
            "hit3_count": hit3,
            "hit3_ratio": f"{hit3}/{total}",
            "hit3_pct": round(hit3 / total * 100, 1) if total else 0.0,
        }

    return results
