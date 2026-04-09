from __future__ import annotations

import json
import sys
from pathlib import Path

from examples.rag_jaquad.scripts.prepare_jaquad import convert_split_dir, convert_split_file, main


def _write_split_file(path: Path, *, prefix: str, count: int) -> None:
    source = {
        "version": "JaQuAD-version-0.1.0",
        "data": [
            {
                "title": f"記事{prefix}",
                "paragraphs": [
                    {
                        "context": f"{prefix}の本文です。",
                        "qas": [
                            {
                                "id": f"{prefix}-{index}",
                                "question": f"{prefix}-{index}の質問は?",
                                "answers": [{"text": f"答え{index}", "answer_start": 0}],
                            }
                            for index in range(count)
                        ],
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")


def test_convert_split_file_emits_corpus_and_queries(tmp_path: Path) -> None:
    source = {
        "version": "JaQuAD-version-0.1.0",
        "data": [
            {
                "title": "記事A",
                "paragraphs": [
                    {
                        "context": "東京は日本の首都です。",
                        "qas": [
                            {
                                "id": "q1",
                                "question": "日本の首都は?",
                                "answers": [{"text": "東京", "answer_start": 0}],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    input_file = tmp_path / "jaquad_dev_0000.json"
    input_file.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")

    corpus_out = tmp_path / "corpus.jsonl"
    queries_out = tmp_path / "queries.jsonl"

    stats = convert_split_file(input_file, corpus_out, queries_out, split="dev")

    assert stats["docs"] == 1
    assert stats["queries"] == 1

    docs = [json.loads(line) for line in corpus_out.read_text(encoding="utf-8").splitlines()]
    queries = [json.loads(line) for line in queries_out.read_text(encoding="utf-8").splitlines()]

    assert docs[0]["doc_id"] == "dev:q1"
    assert docs[0]["title"] == "記事A"
    assert docs[0]["context"] == "東京は日本の首都です。"

    assert queries[0]["query_id"] == "q1"
    assert queries[0]["question"] == "日本の首都は?"
    assert queries[0]["gold_answers"] == ["東京"]
    assert queries[0]["gold_doc_ids"] == ["dev:q1"]


def test_validation_sampling_is_reproducible_for_same_seed(tmp_path: Path) -> None:
    from examples.rag_jaquad.scripts.prepare_jaquad import convert_split_dir

    split_dir = tmp_path / "dev"
    split_dir.mkdir()
    _write_split_file(split_dir / "jaquad_dev_0000.json", prefix="q", count=10)

    run1_corpus = tmp_path / "run1" / "corpus.jsonl"
    run1_queries = tmp_path / "run1" / "queries.jsonl"
    run2_corpus = tmp_path / "run2" / "corpus.jsonl"
    run2_queries = tmp_path / "run2" / "queries.jsonl"

    stats1 = convert_split_dir(
        split_dir,
        run1_corpus,
        run1_queries,
        split="validation",
        sample_size=4,
        sample_seed=123,
    )
    stats2 = convert_split_dir(
        split_dir,
        run2_corpus,
        run2_queries,
        split="validation",
        sample_size=4,
        sample_seed=123,
    )

    assert stats1["selected_queries"] == stats2["selected_queries"]
    assert run1_queries.read_text(encoding="utf-8") == run2_queries.read_text(encoding="utf-8")
    assert run1_corpus.read_text(encoding="utf-8") == run2_corpus.read_text(encoding="utf-8")


def test_validation_sampling_changes_with_different_seed(tmp_path: Path) -> None:
    from examples.rag_jaquad.scripts.prepare_jaquad import convert_split_dir

    split_dir = tmp_path / "dev"
    split_dir.mkdir()
    _write_split_file(split_dir / "jaquad_dev_0000.json", prefix="q", count=10)

    run1_queries = tmp_path / "run1" / "queries.jsonl"
    run2_queries = tmp_path / "run2" / "queries.jsonl"

    stats1 = convert_split_dir(
        split_dir,
        tmp_path / "run1" / "corpus.jsonl",
        run1_queries,
        split="validation",
        sample_size=4,
        sample_seed=1,
    )
    stats2 = convert_split_dir(
        split_dir,
        tmp_path / "run2" / "corpus.jsonl",
        run2_queries,
        split="validation",
        sample_size=4,
        sample_seed=2,
    )

    assert stats1["selected_queries"] != stats2["selected_queries"]
    assert run1_queries.read_text(encoding="utf-8") != run2_queries.read_text(encoding="utf-8")


def test_validation_sample_size_larger_than_available_selects_all(tmp_path: Path) -> None:
    split_dir = tmp_path / "dev"
    split_dir.mkdir()
    _write_split_file(split_dir / "jaquad_dev_0000.json", prefix="q", count=3)

    corpus_out = tmp_path / "out" / "corpus.jsonl"
    queries_out = tmp_path / "out" / "queries.jsonl"

    stats = convert_split_dir(
        split_dir,
        corpus_out,
        queries_out,
        split="validation",
        sample_size=10,
        sample_seed=42,
    )

    assert stats["docs"] == 3
    assert stats["queries"] == 3
    assert stats["selected_queries"] == ["q-0", "q-1", "q-2"]

    docs = [json.loads(line) for line in corpus_out.read_text(encoding="utf-8").splitlines()]
    queries = [json.loads(line) for line in queries_out.read_text(encoding="utf-8").splitlines()]
    assert [doc["doc_id"] for doc in docs] == ["validation:q-0", "validation:q-1", "validation:q-2"]
    assert [query["gold_doc_ids"][0] for query in queries] == [doc["doc_id"] for doc in docs]


def test_main_prints_validation_selected_queries(tmp_path: Path, monkeypatch, capsys) -> None:
    input_root = tmp_path / "raw" / "JaQuAD" / "data"
    (input_root / "train").mkdir(parents=True)
    (input_root / "dev").mkdir(parents=True)
    _write_split_file(input_root / "train" / "train_0000.json", prefix="train", count=2)
    _write_split_file(input_root / "dev" / "dev_0000.json", prefix="dev", count=5)

    output_root = tmp_path / "processed"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_jaquad.py",
            "--input-root",
            str(input_root),
            "--output-root",
            str(output_root),
            "--validation-sample-size",
            "2",
            "--validation-sample-seed",
            "7",
        ],
    )

    main()

    summary = json.loads(capsys.readouterr().out)
    assert "selected_queries" in summary["validation"]
    assert len(summary["validation"]["selected_queries"]) == 2
    assert summary["train"]["queries"] == 2
