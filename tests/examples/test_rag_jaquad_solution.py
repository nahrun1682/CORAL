from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

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


def test_run_uses_openai_client_for_retrieval_and_generation(tmp_path: Path) -> None:
    queries_file = tmp_path / "validation" / "queries.jsonl"
    corpus_file = tmp_path / "validation" / "corpus.jsonl"
    _write_jsonl(
        queries_file,
        [{"query_id": "q1", "question": "富士山はどこにありますか?"}],
    )
    _write_jsonl(
        corpus_file,
        [
            {"doc_id": "d1", "title": "東京", "context": "東京は日本の首都です。"},
            {"doc_id": "d2", "title": "富士山", "context": "富士山は静岡県と山梨県にまたがります。"},
        ],
    )

    class FakeClient:
        def __init__(self) -> None:
            self.embedding_inputs: list[object] = []
            self.response_prompts: list[object] = []
            self.embeddings = SimpleNamespace(create=self._create_embeddings)
            self.responses = SimpleNamespace(create=self._create_response)

        def _create_embeddings(self, *, input: object, model: str) -> object:
            self.embedding_inputs.append(input)
            mapping = {
                "東京 東京は日本の首都です。": [1.0, 0.0],
                "富士山 富士山は静岡県と山梨県にまたがります。": [0.0, 1.0],
                "富士山はどこにありますか?": [0.0, 0.9],
            }
            if isinstance(input, str):
                vectors = [mapping[input]]
            else:
                vectors = [mapping[item] for item in input]
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=vector) for vector in vectors]
            )

        def _create_response(self, *, model: str, input: object, **kwargs: object) -> object:
            self.response_prompts.append(input)
            return SimpleNamespace(output_text="山梨県と静岡県にまたがります。")

    fake_client = FakeClient()

    rows = run(
        str(queries_file),
        corpus_file=str(corpus_file),
        top_k=1,
        openai_client=fake_client,
    )

    assert rows == [
        {
            "query_id": "q1",
            "answer": "山梨県と静岡県にまたがります。",
            "retrieved_doc_ids": ["d2"],
        }
    ]
    assert len(fake_client.embedding_inputs) == 2
    assert len(fake_client.response_prompts) == 1
    assert "富士山" in str(fake_client.response_prompts[0])


def test_run_loads_openai_api_key_from_dotenv_via_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    queries_file = tmp_path / "validation" / "queries.jsonl"
    corpus_file = tmp_path / "validation" / "corpus.jsonl"
    env_file = tmp_path / ".env"
    _write_jsonl(
        queries_file,
        [{"query_id": "q1", "question": "富士山はどこにありますか?"}],
    )
    _write_jsonl(
        corpus_file,
        [
            {"doc_id": "d1", "title": "東京", "context": "東京は日本の首都です。"},
            {"doc_id": "d2", "title": "富士山", "context": "富士山は静岡県と山梨県にまたがります。"},
        ],
    )
    env_file.write_text("OPENAI_API_KEY=sk-from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    seen_api_keys: list[str] = []

    class FakeClient:
        def __init__(self) -> None:
            self.embeddings = SimpleNamespace(create=self._create_embeddings)
            self.responses = SimpleNamespace(create=self._create_response)

        def _create_embeddings(self, *, input: object, model: str) -> object:
            mapping = {
                "東京 東京は日本の首都です。": [1.0, 0.0],
                "富士山 富士山は静岡県と山梨県にまたがります。": [0.0, 1.0],
                "富士山はどこにありますか?": [0.0, 0.9],
            }
            vectors = [mapping[input]] if isinstance(input, str) else [mapping[item] for item in input]
            return SimpleNamespace(data=[SimpleNamespace(embedding=vector) for vector in vectors])

        def _create_response(self, *, model: str, input: object, **kwargs: object) -> object:
            return SimpleNamespace(output_text="山梨県と静岡県にまたがります。")

    def factory(api_key: str) -> FakeClient:
        seen_api_keys.append(api_key)
        return FakeClient()

    rows = run(
        str(queries_file),
        corpus_file=str(corpus_file),
        top_k=1,
        env_file=str(env_file),
        client_factory=factory,
    )

    assert seen_api_keys == ["sk-from-dotenv"]
    assert rows[0]["retrieved_doc_ids"] == ["d2"]
    assert rows[0]["answer"] == "山梨県と静岡県にまたがります。"


def test_run_falls_back_to_local_heuristic_when_openai_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    queries_file = tmp_path / "validation" / "queries.jsonl"
    corpus_file = tmp_path / "validation" / "corpus.jsonl"
    _write_jsonl(
        queries_file,
        [{"query_id": "q1", "question": "日本の首都はどこですか?"}],
    )
    _write_jsonl(
        corpus_file,
        [
            {"doc_id": "d1", "title": "地理", "context": "日本の首都は東京です。"},
            {"doc_id": "d2", "title": "雑学", "context": "海の深さはさまざまです。"},
        ],
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    rows = run(str(queries_file), corpus_file=str(corpus_file), top_k=1)

    assert rows[0]["retrieved_doc_ids"] == ["d1"]
    assert "東京" in rows[0]["answer"]
