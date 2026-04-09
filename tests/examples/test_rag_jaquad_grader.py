from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from coral.config import GraderConfig
import examples.rag_jaquad.eval.grader as grader_module
from examples.rag_jaquad.eval.grader import Grader


def _write_queries(path: Path) -> None:
    rows = [
        {
            "query_id": "q1",
            "question": "日本の首都は?",
            "gold_answers": ["東京"],
            "gold_doc_ids": ["validation:doc-1"],
        },
        {
            "query_id": "q2",
            "question": "富士山はどこにある?",
            "gold_answers": ["静岡県"],
            "gold_doc_ids": ["validation:doc-2"],
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
        encoding="utf-8",
    )


def _make_grader(tmp_path: Path, *, use_fallback: bool = False) -> Grader:
    codebase_path = tmp_path / "codebase"
    private_dir = tmp_path / "private"
    codebase_path.mkdir()
    (private_dir / "eval" / "fixtures").mkdir(parents=True)

    if use_fallback:
        _write_queries(private_dir / "eval" / "fixtures" / "validation_queries.jsonl")
    else:
        _write_queries(codebase_path / "data" / "processed" / "validation" / "queries.jsonl")

    grader = Grader(GraderConfig(timeout=300, args={"program_file": "solution.py"}))
    grader.codebase_path = str(codebase_path)
    grader.private_dir = str(private_dir)
    return grader


def _run_result() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")


def test_answer_f1_recall_and_combined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grader = _make_grader(tmp_path)

    predictions = [
        {"query_id": "q1", "answer": "東京", "retrieved_doc_ids": ["validation:doc-1", "validation:other"]},
        {"query_id": "q2", "answer": "静岡県", "retrieved_doc_ids": ["validation:missing", "validation:doc-2"]},
    ]
    calls: list[tuple[str, tuple[str, ...]]] = []
    seen_query_rows: list[dict[str, object]] = []

    def fake_run_program(self, filename: str, *cmd_args: str):
        queries_path = Path(cmd_args[cmd_args.index("--queries") + 1])
        seen_query_rows[:] = [json.loads(line) for line in queries_path.read_text(encoding="utf-8").splitlines()]
        output_file = Path(cmd_args[cmd_args.index("--output") + 1])
        output_file.write_text(json.dumps(predictions, ensure_ascii=False), encoding="utf-8")
        calls.append((filename, cmd_args))
        return _run_result()

    monkeypatch.setattr(grader_module, "perf_counter", lambda: 10.0)
    monkeypatch.setattr(grader_module.TaskGrader, "run_program", fake_run_program)

    result = grader.evaluate()

    assert result.aggregated == pytest.approx(1.0)
    assert all(set(row) == {"query_id", "question"} for row in seen_query_rows)
    explanation = result.scores["eval"].explanation or ""
    assert "combined=1.0000" in explanation
    assert "answer_f1=1.0000" in explanation
    assert "recall@5=1.0000" in explanation
    assert "latency_sec=0.0000" in explanation
    assert "latency_score=1.0000" in explanation
    assert "n=2" in explanation
    assert calls and calls[0][0] == "solution.py"


def test_missing_prediction_reduces_score_over_full_query_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grader = _make_grader(tmp_path)

    predictions = [
        {"query_id": "q1", "answer": "東京", "retrieved_doc_ids": ["validation:doc-1"]},
    ]

    def fake_run_program(self, filename: str, *cmd_args: str):
        output_file = Path(cmd_args[cmd_args.index("--output") + 1])
        output_file.write_text(json.dumps(predictions, ensure_ascii=False), encoding="utf-8")
        return _run_result()

    monkeypatch.setattr(grader_module, "perf_counter", lambda: 12.0)
    monkeypatch.setattr(grader_module.TaskGrader, "run_program", fake_run_program)

    result = grader.evaluate()

    assert result.aggregated == pytest.approx(0.55)
    explanation = result.scores["eval"].explanation or ""
    assert "n=2" in explanation
    assert "answer_f1=0.5000" in explanation
    assert "recall@5=0.5000" in explanation


def test_predictions_top_level_not_list_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grader = _make_grader(tmp_path)

    def fake_run_program(self, filename: str, *cmd_args: str):
        output_file = Path(cmd_args[cmd_args.index("--output") + 1])
        output_file.write_text(json.dumps({"query_id": "q1"}), encoding="utf-8")
        return _run_result()

    monkeypatch.setattr(grader_module.TaskGrader, "run_program", fake_run_program)

    result = grader.evaluate()

    assert result.aggregated is None
    assert "must be a list" in (result.feedback or "").lower()


def test_required_key_missing_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grader = _make_grader(tmp_path)

    def fake_run_program(self, filename: str, *cmd_args: str):
        output_file = Path(cmd_args[cmd_args.index("--output") + 1])
        output_file.write_text(
            json.dumps([
                {"query_id": "q1", "answer": "東京"},
                {"query_id": "q2", "answer": "静岡県", "retrieved_doc_ids": ["validation:doc-2"]},
            ], ensure_ascii=False),
            encoding="utf-8",
        )
        return _run_result()

    monkeypatch.setattr(grader_module.TaskGrader, "run_program", fake_run_program)

    result = grader.evaluate()

    assert result.aggregated is None
    assert "missing required keys" in (result.feedback or "").lower()


def test_duplicate_query_id_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grader = _make_grader(tmp_path)

    def fake_run_program(self, filename: str, *cmd_args: str):
        output_file = Path(cmd_args[cmd_args.index("--output") + 1])
        output_file.write_text(
            json.dumps([
                {"query_id": "q1", "answer": "東京", "retrieved_doc_ids": ["validation:doc-1"]},
                {"query_id": "q1", "answer": "東京", "retrieved_doc_ids": ["validation:doc-1"]},
            ], ensure_ascii=False),
            encoding="utf-8",
        )
        return _run_result()

    monkeypatch.setattr(grader_module.TaskGrader, "run_program", fake_run_program)

    result = grader.evaluate()

    assert result.aggregated is None
    assert "duplicate prediction" in (result.feedback or "").lower()


def test_run_program_non_zero_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grader = _make_grader(tmp_path)

    def fake_run_program(self, filename: str, *cmd_args: str):
        return subprocess.CompletedProcess(args=["python"], returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(grader_module.TaskGrader, "run_program", fake_run_program)

    result = grader.evaluate()

    assert result.aggregated is None
    assert "program failed" in (result.feedback or "").lower()


def test_prediction_query_id_mismatch_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grader = _make_grader(tmp_path)

    predictions = [
        {"query_id": "unexpected", "answer": "東京", "retrieved_doc_ids": ["validation:doc-1"]},
        {"query_id": "q2", "answer": "静岡県", "retrieved_doc_ids": ["validation:doc-2"]},
    ]

    def fake_run_program(self, filename: str, *cmd_args: str):
        output_file = Path(cmd_args[cmd_args.index("--output") + 1])
        output_file.write_text(json.dumps(predictions, ensure_ascii=False), encoding="utf-8")
        return _run_result()

    monkeypatch.setattr("examples.rag_jaquad.eval.grader.TaskGrader.run_program", fake_run_program)

    result = grader.evaluate()

    assert result.aggregated is None
    assert "does not match validation data" in (result.feedback or "").lower()


def test_validation_fixture_is_used_when_processed_queries_are_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grader = _make_grader(tmp_path, use_fallback=True)

    predictions = [
        {"query_id": "sample-1", "answer": "奈良", "retrieved_doc_ids": ["validation:sample-1"]},
        {"query_id": "sample-2", "answer": "聖武天皇", "retrieved_doc_ids": ["validation:sample-2"]},
    ]
    captured_rows: list[dict[str, object]] = []

    def fake_run_program(self, filename: str, *cmd_args: str):
        queries_path = Path(cmd_args[cmd_args.index("--queries") + 1])
        captured_rows[:] = [json.loads(line) for line in queries_path.read_text(encoding="utf-8").splitlines()]
        output_file = Path(cmd_args[cmd_args.index("--output") + 1])
        output_file.write_text(json.dumps(predictions, ensure_ascii=False), encoding="utf-8")
        return _run_result()

    monkeypatch.setattr(grader_module, "perf_counter", lambda: 14.0)
    monkeypatch.setattr(grader_module.TaskGrader, "run_program", fake_run_program)

    grader.evaluate()

    assert all(set(row) == {"query_id", "question"} for row in captured_rows)
