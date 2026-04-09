from __future__ import annotations

import json
from pathlib import Path

from examples.rag_jaquad.scripts.prepare_jaquad import convert_split_file


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
