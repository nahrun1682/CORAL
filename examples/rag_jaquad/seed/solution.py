"""Minimal Japanese RAG baseline for JaQuAD.

The baseline is intentionally lightweight and deterministic:
- Character n-gram overlap retrieval over validation corpus.
- Extractive answer from top-ranked context sentence.
"""

from __future__ import annotations

import json
from pathlib import Path
import re


def _load_jsonl(path: Path, *, label: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} line {line_no}: invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{label} line {line_no}: row must be an object")
        rows.append(payload)
    return rows


def _char_ngrams(text: str, n: int = 2) -> set[str]:
    normalized = re.sub(r"\s+", "", text)
    if not normalized:
        return set()
    if len(normalized) < n:
        return {normalized}
    return {normalized[i : i + n] for i in range(len(normalized) - n + 1)}


def _overlap_score(query: str, text: str) -> float:
    q_set = _char_ngrams(query)
    t_set = _char_ngrams(text)
    if not q_set or not t_set:
        return 0.0
    overlap = len(q_set.intersection(t_set))
    return overlap / len(q_set)


def _best_sentence(question: str, context: str) -> str:
    sentences = [segment.strip() for segment in re.split(r"[。！？\n]+", context) if segment.strip()]
    if not sentences:
        return context.strip()[:120]
    return max(sentences, key=lambda sentence: _overlap_score(question, sentence))


def run(
    validation_queries_file: str,
    *,
    corpus_file: str | None = None,
    top_k: int = 5,
) -> list[dict[str, object]]:
    queries_path = Path(validation_queries_file)
    if corpus_file:
        corpus_path = Path(corpus_file)
    else:
        sibling_corpus = queries_path.with_name("corpus.jsonl")
        default_corpus = Path("data/processed/validation/corpus.jsonl")
        corpus_path = sibling_corpus if sibling_corpus.exists() else default_corpus

    queries = _load_jsonl(queries_path, label="queries.jsonl")
    corpus_rows = _load_jsonl(corpus_path, label="corpus.jsonl")

    normalized_corpus: list[dict[str, str]] = []
    for index, row in enumerate(corpus_rows):
        doc_id = row.get("doc_id")
        context = row.get("context")
        title = row.get("title", "")
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError(f"corpus.jsonl line {index + 1}: invalid doc_id")
        if not isinstance(context, str) or not context.strip():
            raise ValueError(f"corpus.jsonl line {index + 1}: invalid context")
        normalized_corpus.append({"doc_id": doc_id, "text": f"{title} {context}".strip(), "context": context})

    if top_k <= 0:
        top_k = 1

    outputs: list[dict[str, object]] = []
    for index, query in enumerate(queries):
        query_id = query.get("query_id")
        question = query.get("question")
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"queries.jsonl line {index + 1}: invalid query_id")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"queries.jsonl line {index + 1}: invalid question")

        ranked = sorted(
            normalized_corpus,
            key=lambda doc: _overlap_score(question, doc["text"]),
            reverse=True,
        )
        top_docs = ranked[:top_k]
        answer = _best_sentence(question, top_docs[0]["context"]) if top_docs else ""
        outputs.append(
            {
                "query_id": query_id,
                "answer": answer,
                "retrieved_doc_ids": [doc["doc_id"] for doc in top_docs],
            }
        )

    return outputs


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--corpus", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    output = run(args.queries, corpus_file=args.corpus, top_k=args.top_k)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
