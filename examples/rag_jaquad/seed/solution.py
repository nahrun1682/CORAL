"""Baseline placeholder for JaQuAD RAG task.

This seed emits the required prediction schema:
`query_id: str`, `answer: str`, `retrieved_doc_ids: list[str]`.
Agents are expected to replace it with a real RAG pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path


def run(validation_queries_file: str) -> list[dict[str, object]]:
    rows = []
    for line in Path(validation_queries_file).read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        rows.append(
            {
                "query_id": item["query_id"],
                "answer": "",
                "retrieved_doc_ids": [],
            }
        )
    return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = run(args.queries)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
