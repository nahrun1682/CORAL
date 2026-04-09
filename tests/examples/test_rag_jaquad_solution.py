from __future__ import annotations

import json
from pathlib import Path

import pytest

from examples.rag_jaquad.seed.solution import run


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
        encoding="utf-8",
    )


def test_run_returns_schema_and_relevant_doc_ids(tmp_path: Path) -> None:
    queries = [
        {"query_id": "q1", "question": "日本の首都はどこですか?"},
        {"query_id": "q2", "question": "富士山がある県は?"},
    ]
    corpus = [
        {"doc_id": "validation:d1", "title": "地理", "context": "日本の首都は東京です。"},
        {"doc_id": "validation:d2", "title": "山", "context": "富士山は静岡県と山梨県にまたがる。"},
        {"doc_id": "validation:d3", "title": "雑学", "context": "海の深さはさまざま。"},
    ]
    queries_file = tmp_path / "validation" / "queries.jsonl"
    corpus_file = tmp_path / "validation" / "corpus.jsonl"
    _write_jsonl(queries_file, queries)
    _write_jsonl(corpus_file, corpus)

    rows = run(str(queries_file), corpus_file=str(corpus_file), top_k=2)

    assert len(rows) == 2
    assert rows[0]["query_id"] == "q1"
    assert isinstance(rows[0]["answer"], str) and rows[0]["answer"]
    assert rows[0]["retrieved_doc_ids"][0] == "validation:d1"
    assert rows[1]["retrieved_doc_ids"][0] == "validation:d2"
    assert all(len(row["retrieved_doc_ids"]) <= 2 for row in rows)


def test_run_raises_readable_error_for_invalid_queries_jsonl(tmp_path: Path) -> None:
    queries_file = tmp_path / "validation" / "queries.jsonl"
    queries_file.parent.mkdir(parents=True, exist_ok=True)
    queries_file.write_text('{"query_id":"q1","question":"ok"}\n{broken', encoding="utf-8")
    _write_jsonl(
        tmp_path / "validation" / "corpus.jsonl",
        [{"doc_id": "validation:d1", "title": "", "context": "東京"}],
    )

    with pytest.raises(ValueError, match="queries.jsonl line 2"):
        run(str(queries_file), corpus_file=str(tmp_path / "validation" / "corpus.jsonl"))
