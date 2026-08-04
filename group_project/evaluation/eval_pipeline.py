"""Evaluation pipeline for University Admission RAG Assistant.

Runs A/B evaluation with local proxy metrics by default. RAGAS integration is
kept available for environments with Gemini/OpenAI judge credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.common import tokenize, write_json  # noqa: E402
from src.task10_generation import generate_with_citation  # noqa: E402
from src.task4_chunking_indexing import corpus_fingerprint  # noqa: E402

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"
CACHE_PATH = Path(__file__).parent / "eval_cache.json"


def load_golden_dataset() -> list[dict]:
    return json.loads(GOLDEN_DATASET_PATH.read_text(encoding="utf-8"))


def _f1(expected: str, actual: str) -> float:
    exp = tokenize(expected)
    act = tokenize(actual)
    if not exp or not act:
        return 0.0
    common = 0
    remaining = act.copy()
    for token in exp:
        if token in remaining:
            common += 1
            remaining.remove(token)
    precision = common / len(act)
    recall = common / len(exp)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _source_match(expected_source: str, sources: list[dict]) -> float:
    if expected_source in {"none", "multiple"}:
        return 1.0 if expected_source == "none" else 0.5
    expected = expected_source.lower()
    for source in sources:
        meta = source.get("metadata", {}) or {}
        values = " ".join(str(meta.get(k, "")) for k in ["source", "url", "title"]).lower()
        if expected in values or any(part and part in values for part in expected.split("/")[-1].split("-")[:3]):
            return 1.0
    return 0.0


def local_proxy_metrics(item: dict, result: dict) -> dict:
    answer = result.get("answer", "")
    sources = result.get("sources", [])
    contexts = " ".join(source.get("content", "") for source in sources)
    expected = item.get("expected_answer", "")
    expected_context = item.get("expected_context", "")
    citation_coverage = 1.0 if "[" in answer and "]" in answer else 0.0
    if answer.startswith("I cannot verify this information") and item.get("category") == "out_of_scope":
        citation_coverage = 1.0
    return {
        "faithfulness": round(min(1.0, citation_coverage * (0.5 + 0.5 * _f1(contexts, answer))), 4),
        "answer_relevance": round(_f1(expected, answer), 4),
        "context_recall": round(max(_f1(expected_context, contexts), _source_match(item.get("source", ""), sources)), 4),
        "context_precision": round(min(1.0, citation_coverage + 0.25 * _f1(item.get("question", ""), contexts)), 4),
    }


def run_config(dataset: list[dict], config_name: str, limit: int | None = None) -> list[dict]:
    rows: list[dict] = []
    subset = dataset[:limit] if limit else dataset
    retrieval_options = {"mode": "dense_only"} if config_name == "Config B - Dense only" else {}
    for item in subset:
        result = generate_with_citation(item["question"], top_k=5, retrieval_options=retrieval_options)
        metrics = local_proxy_metrics(item, result)
        rows.append({"question": item["question"], "category": item["category"], "result": result, "metrics": metrics})
    return rows


def average_metrics(rows: list[dict]) -> dict:
    keys = ["faithfulness", "answer_relevance", "context_recall", "context_precision"]
    if not rows:
        return {key: 0.0 for key in keys}
    return {key: round(sum(row["metrics"][key] for row in rows) / len(rows), 4) for key in keys}


def compare_configs(dataset: list[dict], limit: int | None = None, resume: bool = False) -> dict:
    if resume and CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    os.environ["FORCE_LOCAL_GENERATION"] = "1"
    comparison = {
        "framework": "Local proxy evaluation — not official RAGAS scores",
        "ran_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "corpus_fingerprint": corpus_fingerprint(),
        "configs": {
            "Config A - Hybrid RAG": run_config(dataset, "Config A - Hybrid RAG", limit),
            "Config B - Dense only": run_config(dataset, "Config B - Dense only", limit),
        },
    }
    write_json(CACHE_PATH, comparison)
    return comparison


def evaluate_with_ragas(dataset: list[dict], limit: int | None = None):
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")):
        raise RuntimeError("RAGAS judge requires GEMINI_API_KEY or OPENAI_API_KEY")
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    rows = []
    for item in (dataset[:limit] if limit else dataset):
        result = generate_with_citation(item["question"], top_k=5)
        rows.append(
            {
                "question": item["question"],
                "answer": result["answer"],
                "contexts": [source.get("content", "") for source in result.get("sources", [])],
                "ground_truth": item["expected_answer"],
            }
        )
    return evaluate(
        Dataset.from_list(rows),
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
    )


def export_results(comparison: dict) -> None:
    config_a = comparison["configs"]["Config A - Hybrid RAG"]
    config_b = comparison["configs"]["Config B - Dense only"]
    avg_a = average_metrics(config_a)
    avg_b = average_metrics(config_b)
    metrics = ["faithfulness", "answer_relevance", "context_recall", "context_precision"]
    bottom = sorted(config_a, key=lambda row: sum(row["metrics"].values()))[:3]

    lines = [
        "# RAG Evaluation Results",
        "",
        f"- Run time: {comparison['ran_at']}",
        f"- Framework: {comparison['framework']}",
        "- Judge model: local deterministic proxy",
        f"- Corpus fingerprint: {comparison['corpus_fingerprint']}",
        f"- Test cases: {len(config_a)}",
        "",
        "## A/B Metrics",
        "",
        "| Metric | Config A | Config B | Delta |",
        "|---|---:|---:|---:|",
    ]
    for metric in metrics:
        lines.append(f"| {metric} | {avg_a[metric]:.4f} | {avg_b[metric]:.4f} | {avg_a[metric] - avg_b[metric]:.4f} |")
    avg_all_a = sum(avg_a.values()) / len(avg_a)
    avg_all_b = sum(avg_b.values()) / len(avg_b)
    lines.append(f"| **Average** | **{avg_all_a:.4f}** | **{avg_all_b:.4f}** | **{avg_all_a - avg_all_b:.4f}** |")
    lines.extend(
        [
            "",
            "## Bottom 3",
            "",
            "| Question | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in bottom:
        m = row["metrics"]
        lines.append(
            f"| {row['question']} | {m['faithfulness']:.4f} | {m['answer_relevance']:.4f} | "
            f"{m['context_recall']:.4f} | {m['context_precision']:.4f} | Retrieval/grounding | "
            "Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |"
        )
    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "| Action | Expected impact |",
            "|---|---|",
            "| Enable BAAI/bge-m3 by setting `ADMISSION_RAG_DOWNLOAD_MODELS=1` after model cache is available. | Better multilingual semantic matching for Vietnamese admission questions. |",
            "| Add curated tables for HUST/HCMUS cutoff scores and quotas. | Higher context precision for numeric questions. |",
            "| Run official RAGAS with Gemini/OpenAI judge when quota is available. | Replace proxy metrics with judge-based faithfulness and relevance scores. |",
        ]
    )
    RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--ragas", action="store_true")
    args = parser.parse_args()

    dataset = load_golden_dataset()
    if args.ragas:
        result = evaluate_with_ragas(dataset, limit=args.limit)
        print(result)
    comparison = compare_configs(dataset, limit=args.limit, resume=args.resume)
    export_results(comparison)
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
