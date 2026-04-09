from __future__ import annotations

import json
import re
import tempfile
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any

from coral.grader import TaskGrader
from coral.types import ScoreBundle


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tokenize(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if any(ch.isspace() for ch in text):
        return [token for token in re.split(r"\s+", text) if token]
    return list(text)


def _f1_score(prediction: str, gold: str) -> float:
    pred_tokens = _tokenize(prediction)
    gold_tokens = _tokenize(gold)
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0

    pred_counts = Counter(pred_tokens)
    gold_counts = Counter(gold_tokens)
    overlap = sum((pred_counts & gold_counts).values())
    if overlap == 0:
        return 0.0

    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _validate_prediction(item: Any, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"Prediction at index {index} must be an object.")

    required = {"query_id", "answer", "retrieved_doc_ids"}
    missing = [key for key in required if key not in item]
    if missing:
        raise ValueError(f"Prediction at index {index} is missing required keys: {', '.join(sorted(missing))}.")

    query_id = item["query_id"]
    answer = item["answer"]
    retrieved_doc_ids = item["retrieved_doc_ids"]

    if not isinstance(query_id, str) or not query_id.strip():
        raise ValueError(f"Prediction at index {index} has an invalid query_id.")
    if not isinstance(answer, str):
        raise ValueError(f"Prediction at index {index} has an invalid answer.")
    if not isinstance(retrieved_doc_ids, list) or any(not isinstance(doc_id, str) for doc_id in retrieved_doc_ids):
        raise ValueError(f"Prediction at index {index} has an invalid retrieved_doc_ids list.")

    return {
        "query_id": query_id,
        "answer": answer,
        "retrieved_doc_ids": retrieved_doc_ids,
    }


class Grader(TaskGrader):
    def evaluate(self) -> float | ScoreBundle:
        program_file = self.args.get("program_file", "solution.py")
        queries_file = Path(self.codebase_path) / "data" / "processed" / "validation" / "queries.jsonl"
        fallback_queries = Path(self.private_dir) / "eval" / "fixtures" / "validation_queries.jsonl"

        def fail(message: str) -> ScoreBundle:
            return self.fail(message, feedback=message)

        if not queries_file.exists():
            if fallback_queries.exists():
                queries_file = fallback_queries
            else:
                return fail("Missing processed dataset. Run scripts/download_jaquad.sh and scripts/prepare_jaquad.py first.")

        try:
            gold_rows = _load_jsonl(queries_file)
        except Exception as exc:
            return fail(f"Failed to load validation queries: {exc}")

        gold_by_id: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(gold_rows):
            query_id = row.get("query_id")
            if not isinstance(query_id, str) or not query_id.strip():
                return fail(f"Validation query at index {index} has an invalid query_id.")
            gold_by_id[query_id] = row

        with tempfile.TemporaryDirectory() as td:
            output_file = Path(td) / "predictions.json"
            start = perf_counter()
            try:
                result = self.run_program(program_file, "--queries", str(queries_file), "--output", str(output_file))
            except Exception as exc:
                return fail(f"Evaluation failed: {exc}")
            latency_sec = perf_counter() - start

            if result.returncode != 0:
                return fail(f"Program failed: {result.stderr[-1000:]}")
            if not output_file.exists():
                return fail("Program did not write predictions output.")

            try:
                preds_raw = json.loads(output_file.read_text(encoding="utf-8"))
            except Exception as exc:
                return fail(f"Predictions must be valid JSON: {exc}")

        if not isinstance(preds_raw, list):
            return fail("Predictions must be a list.")

        predictions: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(preds_raw):
            try:
                pred = _validate_prediction(item, index)
            except ValueError as exc:
                return fail(str(exc))

            query_id = pred["query_id"]
            if query_id in predictions:
                return fail(f"Duplicate prediction for query_id {query_id!r}.")
            if query_id not in gold_by_id:
                return fail(f"Prediction query_id {query_id!r} does not match validation data.")
            predictions[query_id] = pred

        matched_ids = [query_id for query_id in gold_by_id if query_id in predictions]
        missing_ids = [query_id for query_id in gold_by_id if query_id not in predictions]

        if not matched_ids:
            return fail("No matching predictions were found.")

        answer_f1_values: list[float] = []
        recall_values: list[float] = []
        for query_id in matched_ids:
            gold_row = gold_by_id[query_id]
            pred = predictions[query_id]
            gold_answers = gold_row.get("gold_answers", [])
            gold_doc_ids = gold_row.get("gold_doc_ids", [])

            if not isinstance(gold_answers, list) or not gold_answers:
                return fail(f"Validation query {query_id!r} is missing gold answers.")
            if not isinstance(gold_doc_ids, list) or not gold_doc_ids:
                return fail(f"Validation query {query_id!r} is missing gold_doc_ids.")

            answer_f1_values.append(max(_f1_score(pred["answer"], str(gold_answer)) for gold_answer in gold_answers))
            recall_values.append(
                1.0 if set(gold_doc_ids).intersection(pred["retrieved_doc_ids"][:5]) else 0.0
            )

        n = len(matched_ids)
        answer_f1 = sum(answer_f1_values) / n
        recall_at_5 = sum(recall_values) / n
        latency_per_query = latency_sec / n if n else 0.0
        latency_score = max(0.0, 1.0 - latency_per_query / 15.0)
        combined = 0.55 * answer_f1 + 0.35 * recall_at_5 + 0.10 * latency_score

        explanation = (
            f"combined={combined:.4f}, "
            f"answer_f1={answer_f1:.4f}, "
            f"recall@5={recall_at_5:.4f}, "
            f"latency_sec={latency_per_query:.4f}, "
            f"latency_score={latency_score:.4f}, "
            f"n={n}"
        )
        if missing_ids:
            explanation += f", skipped_missing={len(missing_ids)}"

        return self.score(combined, explanation)
