"""Minimal Japanese RAG baseline for JaQuAD.

The baseline is intentionally lightweight and deterministic:
- Character n-gram overlap retrieval over validation corpus.
- Extractive answer from top-ranked context sentence.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Callable


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


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _strip_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1]
    return stripped


def _load_openai_api_key(env_file: str | Path | None = None) -> str | None:
    env_value = os.getenv("OPENAI_API_KEY")
    if env_value:
        return env_value.strip() or None

    candidate = Path(env_file) if env_file is not None else Path(".env")
    if not candidate.exists():
        return None

    for line in candidate.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "OPENAI_API_KEY":
            parsed = _strip_quotes(value)
            return parsed or None
    return None


def _default_openai_client_factory(api_key: str) -> object:
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _warn_openai_fallback(stage: str, error: Exception) -> None:
    print(
        f"[rag_jaquad] OpenAI {stage} failed ({type(error).__name__}: {error}); "
        "falling back to local heuristic path.",
        file=sys.stderr,
    )


def _extract_openai_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text.strip()

    choices = getattr(response, "choices", None)
    if choices:
        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()

    outputs = getattr(response, "output", None)
    if outputs:
        text_chunks: list[str] = []
        for item in outputs:
            content_items = getattr(item, "content", [])
            for content_item in content_items:
                text = getattr(content_item, "text", None)
                if isinstance(text, str):
                    text_chunks.append(text)
        if text_chunks:
            return "".join(text_chunks).strip()

    return ""


def _embed_texts(client: object, texts: list[str], *, model: str) -> list[list[float]]:
    embeddings_api = getattr(client, "embeddings")
    response = embeddings_api.create(input=texts, model=model)
    data = getattr(response, "data", None)
    if data is None:
        raise ValueError("embeddings response missing data")
    return [list(getattr(item, "embedding")) for item in data]


def _generate_answer(client: object, *, model: str, question: str, retrieved_docs: list[dict[str, str]]) -> str:
    context_lines = []
    for doc in retrieved_docs:
        context_lines.append(f"[{doc['doc_id']}] {doc['context']}")
    context = "\n".join(context_lines)
    prompt = (
        "あなたは日本語QAアシスタントです。\n"
        "次のコンテキストだけを使って、質問に対する答えを簡潔に日本語で返してください。\n"
        "わからない場合は「不明です」と答えてください。\n\n"
        f"質問: {question}\n\n"
        f"コンテキスト:\n{context}\n"
    )
    responses_api = getattr(client, "responses")
    response = responses_api.create(model=model, input=prompt)
    answer = _extract_openai_text(response)
    return answer or _best_sentence(question, context)


def _run_openai_path(
    queries: list[dict[str, str]],
    corpus_rows: list[dict[str, str]],
    *,
    client: object,
    top_k: int,
    embeddings_model: str,
    generation_model: str,
) -> list[dict[str, object]]:
    corpus_texts = [row["text"] for row in corpus_rows]
    corpus_vectors = _embed_texts(client, corpus_texts, model=embeddings_model)
    outputs: list[dict[str, object]] = []

    for query in queries:
        query_id = query["query_id"]
        question = query["question"]
        query_vector = _embed_texts(client, [question], model=embeddings_model)[0]

        ranked = sorted(
            enumerate(corpus_rows),
            key=lambda item: (-_cosine_similarity(query_vector, corpus_vectors[item[0]]), item[0]),
        )
        top_indexes = [index for index, _ in ranked[:top_k]]
        retrieved_docs = [corpus_rows[index] for index in top_indexes]
        answer = _generate_answer(
            client,
            model=generation_model,
            question=question,
            retrieved_docs=retrieved_docs,
        )
        outputs.append(
            {
                "query_id": query_id,
                "answer": answer,
                "retrieved_doc_ids": [doc["doc_id"] for doc in retrieved_docs],
            }
        )

    return outputs


def _heuristic_run(
    queries: list[dict[str, str]],
    corpus_rows: list[dict[str, str]],
    *,
    top_k: int,
) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    for query in queries:
        query_id = query["query_id"]
        question = query["question"]
        ranked = sorted(
            corpus_rows,
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


def run(
    validation_queries_file: str,
    *,
    corpus_file: str | None = None,
    top_k: int = 5,
    openai_client: object | None = None,
    client_factory: Callable[[str], object] | None = None,
    env_file: str | Path | None = None,
    embeddings_model: str = "text-embedding-3-small",
    generation_model: str = "gpt-4o-mini",
    strict_openai: bool = False,
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

    normalized_queries: list[dict[str, str]] = []
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

    for index, query in enumerate(queries):
        query_id = query.get("query_id")
        question = query.get("question")
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"queries.jsonl line {index + 1}: invalid query_id")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"queries.jsonl line {index + 1}: invalid question")
        normalized_queries.append({"query_id": query_id, "question": question})

    resolved_client = openai_client
    if resolved_client is None:
        api_key = _load_openai_api_key(env_file)
        if api_key:
            try:
                factory = client_factory or _default_openai_client_factory
                resolved_client = factory(api_key)
            except Exception as exc:
                if strict_openai:
                    raise
                _warn_openai_fallback("client initialization", exc)

    if resolved_client is not None:
        try:
            return _run_openai_path(
                normalized_queries,
                normalized_corpus,
                client=resolved_client,
                top_k=top_k,
                embeddings_model=embeddings_model,
                generation_model=generation_model,
            )
        except Exception as exc:
            if strict_openai:
                raise
            _warn_openai_fallback("runtime", exc)

    return _heuristic_run(normalized_queries, normalized_corpus, top_k=top_k)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--corpus", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--strict-openai", action="store_true")
    args = parser.parse_args()

    output = run(
        args.queries,
        corpus_file=args.corpus,
        top_k=args.top_k,
        strict_openai=args.strict_openai,
    )
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
