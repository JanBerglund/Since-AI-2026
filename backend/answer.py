"""Answer PVAG questions from the top retrieved clauses."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from rag_answer import ask_with_rag
from retrieval import PVAGRetriever, SearchResult


DEFAULT_MIN_SCORE = 0.65
TOP_K = 5


def answer_question(
    question: str,
    retriever: PVAGRetriever,
    *,
    min_score: float = DEFAULT_MIN_SCORE,
    answerer: Callable[[str, Sequence[SearchResult]], str] = ask_with_rag,
) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")
    if not 0 <= min_score <= 1:
        raise ValueError("Minimum score must be between 0 and 1")
    results = retriever.search(question, k=TOP_K)
    if not results or results[0].score < min_score:
        return "No relevant clause found"

    answer = answerer(question, results)
    sources = "\n".join(
        f"- [{result.clause.id}] {result.clause.title}: {result.clause.source_url}"
        for result in results
    )
    return f"{answer}\n\nRetrieved clauses and source URLs:\n{sources}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Answer a PVAG question using locally retrieved clauses."
    )
    parser.add_argument("question", nargs="+", help="Natural-language question")
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help=f"Skip the LLM below this cosine score (default: {DEFAULT_MIN_SCORE})",
    )
    args = parser.parse_args()
    try:
        retriever = PVAGRetriever()
        answer = answer_question(" ".join(args.question), retriever, min_score=args.min_score)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Could not answer question: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(answer)


if __name__ == "__main__":
    main()
