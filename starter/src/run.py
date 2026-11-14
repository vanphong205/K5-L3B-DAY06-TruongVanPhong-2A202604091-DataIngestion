"""Pipeline entry point for Day 06 Data Ingestion Engineering.

Runs Strategy A (fixed_size), Strategy B (by_paragraph), and Strategy C (by_paragraph + filter)
against the benchmark questions, evaluates Hit@1 and Evidence Hit@3, and exports traces.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure starter is in sys.path
root_dir = Path(__file__).resolve().parents[2]
starter_dir = Path(__file__).resolve().parents[1]
if str(starter_dir) not in sys.path:
    sys.path.insert(0, str(starter_dir))

load_dotenv()

from src.embeddings import OllamaEmbedder
from src.evaluation import evaluate_query, summarize
from src.store import PgVectorStore


def find_file(relative_paths: list[Path]) -> Path:
    for p in relative_paths:
        if p.exists():
            return p
    raise FileNotFoundError(f"Could not find any of: {[str(p) for p in relative_paths]}")


def load_benchmark() -> list[dict[str, Any]]:
    path = find_file(
        [
            root_dir / "benchmark" / "questions.json",
            starter_dir / "benchmark" / "questions.json",
            Path("benchmark") / "questions.json",
        ]
    )
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    print("=" * 70)
    print(" DAY 06: DATA INGESTION ENGINEERING BENCHMARK RUNNER")
    print("=" * 70)

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("Error: DATABASE_URL is not set in environment or .env")

    print("\n[1/4] Loading benchmark questions...")
    questions = load_benchmark()
    dev_q = [q for q in questions if q.get("split") == "dev"]
    test_q = [q for q in questions if q.get("split") == "test"]
    print(f" Loaded {len(questions)} total questions: {len(dev_q)} dev, {len(test_q)} test.")

    print("\n[2/4] Connecting to PgVectorStore and Ollama Embedder...")
    embedder = OllamaEmbedder()
    store = PgVectorStore(database_url=db_url, dimensions=embedder.dimensions)
    print(f" Embedder: {embedder.model_name} (dim: {embedder.dimensions})")

    # Define the 3 strategies
    # Strategy A: fixed_size, no filter
    # Strategy B: by_paragraph, no filter
    # Strategy C: by_paragraph, with metadata filter when query provides filter
    strategies = [
        {"name": "A_fixed_size", "store_strategy": "fixed_size", "use_filter": False},
        {"name": "B_by_paragraph", "store_strategy": "by_paragraph", "use_filter": False},
        {"name": "C_by_paragraph_filter", "store_strategy": "by_paragraph", "use_filter": True},
    ]

    all_traces: list[dict[str, Any]] = []

    print("\n[3/4] Running retrieval and evaluation across 3 strategies...")
    for strat in strategies:
        strat_name = strat["name"]
        store_strat = strat["store_strategy"]
        use_filter = strat["use_filter"]
        print(f"\n--> Evaluating Strategy: {strat_name}...")

        t0 = time.perf_counter()
        for q in questions:
            q_text = q["question"]
            q_vec = embedder.embed_query(q_text)

            filters = q.get("filter") if use_filter else None
            hits = store.search(strategy=store_strat, query_vector=q_vec, top_k=3, filters=filters)

            eval_res = evaluate_query(q, hits)
            eval_res["strategy"] = strat_name
            eval_res["store_strategy"] = store_strat
            eval_res["applied_filter"] = filters
            all_traces.append(eval_res)

        elapsed = time.perf_counter() - t0
        print(f" Completed {len(questions)} queries for {strat_name} in {elapsed:.2f}s.")

    print("\n[4/4] Summarizing evaluation metrics...")
    summary = summarize(all_traces)

    print("\n" + "=" * 70)
    print(f"{'Strategy':<26} | {'Split':<5} | {'Hit@1 (n/N)':<12} | {'Evidence Hit@3 (n/N)':<20}")
    print("-" * 70)
    for key, data in summary.items():
        strat = data["strategy"]
        split = data["split"]
        hit1 = f"{data['hit1_ratio']} ({data['hit1_pct']}%)"
        hit3 = f"{data['hit3_ratio']} ({data['hit3_pct']}%)"
        print(f"{strat:<26} | {split:<5} | {hit1:<12} | {hit3:<20}")
    print("=" * 70)

    # Save results to both results/ and starter/results/
    for out_dir in [root_dir / "results", starter_dir / "results"]:
        out_dir.mkdir(parents=True, exist_ok=True)

        # Traces
        traces_file = out_dir / "traces.json"
        traces_file.write_text(json.dumps(all_traces, ensure_ascii=False, indent=2), encoding="utf-8")

        # Metrics
        metrics_file = out_dir / "metrics.json"
        metrics_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        # Markdown summary report
        md_lines = [
            "# Benchmark Retrieval Results Summary",
            "",
            f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Embedding Model: `{embedder.model_name}` (dim: {embedder.dimensions})",
            "",
            "| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) |",
            "|---|---|---|---|",
        ]
        for key, d in summary.items():
            md_lines.append(
                f"| `{d['strategy']}` | **{d['split']}** | {d['hit1_ratio']} ({d['hit1_pct']}%) | {d['hit3_ratio']} ({d['hit3_pct']}%) |"
            )

        md_file = out_dir / "benchmark_summary.md"
        md_file.write_text("\n".join(md_lines), encoding="utf-8")

    print("\n Results saved to results/traces.json and results/metrics.json")
    print("Pipeline run completed successfully!")


if __name__ == "__main__":
    main()
