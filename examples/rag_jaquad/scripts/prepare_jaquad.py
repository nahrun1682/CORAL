from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def _extract_records(payload: dict[str, Any], split: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    docs: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []

    for article in payload.get("data", []):
        title = article.get("title", "")
        for paragraph in article.get("paragraphs", []):
            context = paragraph.get("context", "")
            for qa in paragraph.get("qas", []):
                qid = str(qa.get("id", "")).strip()
                question = str(qa.get("question", "")).strip()
                answers = qa.get("answers", [])

                if not qid or not question or not context:
                    continue

                gold_answers = [
                    str(ans.get("text", "")).strip()
                    for ans in answers
                    if str(ans.get("text", "")).strip()
                ]
                if not gold_answers:
                    continue

                doc_id = f"{split}:{qid}"
                docs.append(
                    {
                        "doc_id": doc_id,
                        "title": title,
                        "context": context,
                    }
                )
                queries.append(
                    {
                        "query_id": qid,
                        "question": question,
                        "gold_answers": gold_answers,
                        "gold_doc_ids": [doc_id],
                    }
                )

    return docs, queries


def convert_split_file(
    input_file: Path,
    corpus_out: Path,
    queries_out: Path,
    *,
    split: str,
) -> dict[str, int]:
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    docs, queries = _extract_records(payload, split=split)

    with corpus_out.open("a", encoding="utf-8") as cf:
        for doc in docs:
            cf.write(json.dumps(doc, ensure_ascii=False) + "\n")

    with queries_out.open("a", encoding="utf-8") as qf:
        for query in queries:
            qf.write(json.dumps(query, ensure_ascii=False) + "\n")

    return {"docs": len(docs), "queries": len(queries)}


def convert_split_dir(
    split_dir: Path,
    corpus_out: Path,
    queries_out: Path,
    *,
    split: str,
    sample_size: int | None = None,
    sample_seed: int = 42,
) -> dict[str, Any]:
    if sample_size is not None and sample_size < 0:
        raise ValueError("validation-sample-size must be non-negative")

    corpus_out.parent.mkdir(parents=True, exist_ok=True)
    queries_out.parent.mkdir(parents=True, exist_ok=True)

    docs: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []
    totals: dict[str, Any] = {"docs": 0, "queries": 0, "files": 0}
    for file in sorted(split_dir.glob("*.json")):
        payload = json.loads(file.read_text(encoding="utf-8"))
        file_docs, file_queries = _extract_records(payload, split=split)
        stats = {"docs": len(file_docs), "queries": len(file_queries)}
        totals["docs"] += stats["docs"]
        totals["queries"] += stats["queries"]
        totals["files"] += 1
        docs.extend(file_docs)
        queries.extend(file_queries)

    selected_indices = list(range(len(queries)))
    if split == "validation" and sample_size is not None and sample_size < len(queries):
        rng = random.Random(sample_seed)
        selected_indices = sorted(rng.sample(range(len(queries)), sample_size))

    selected_docs = [docs[index] for index in selected_indices]
    selected_queries = [queries[index] for index in selected_indices]

    corpus_out.write_text("", encoding="utf-8")
    queries_out.write_text("", encoding="utf-8")

    with corpus_out.open("a", encoding="utf-8") as cf:
        for doc in selected_docs:
            cf.write(json.dumps(doc, ensure_ascii=False) + "\n")

    with queries_out.open("a", encoding="utf-8") as qf:
        for query in selected_queries:
            qf.write(json.dumps(query, ensure_ascii=False) + "\n")

    totals["docs"] = len(selected_docs)
    totals["queries"] = len(selected_queries)
    if split == "validation":
        totals["selected_queries"] = [query["query_id"] for query in selected_queries]
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert JaQuAD JSON files to RAG-friendly JSONL")
    parser.add_argument("--input-root", type=Path, required=True, help="Path to JaQuAD data root (contains train/ and dev/)")
    parser.add_argument("--output-root", type=Path, required=True, help="Where processed JSONL files will be written")
    parser.add_argument("--validation-sample-size", type=int, default=200, help="Number of validation queries to sample")
    parser.add_argument("--validation-sample-seed", type=int, default=42, help="Seed for validation sampling")
    args = parser.parse_args()

    splits = {"train": "train", "dev": "validation"}

    summary: dict[str, dict[str, Any]] = {}
    for src_name, out_name in splits.items():
        split_dir = args.input_root / src_name
        if not split_dir.exists():
            raise FileNotFoundError(f"Missing split directory: {split_dir}")

        stats = convert_split_dir(
            split_dir=split_dir,
            corpus_out=args.output_root / out_name / "corpus.jsonl",
            queries_out=args.output_root / out_name / "queries.jsonl",
            split=out_name,
            sample_size=args.validation_sample_size if out_name == "validation" else None,
            sample_seed=args.validation_sample_seed,
        )
        summary[out_name] = stats

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
