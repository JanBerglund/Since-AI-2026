"""Embedding-based retrieval for the scraped PVAG clauses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from scrape import Clause


MODEL_NAME = "BAAI/bge-small-en-v1.5"
CLAUSES_PATH = Path("data/clauses.json")
EMBEDDINGS_PATH = Path("data/embeddings.npy")
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Encoder(Protocol):
    def encode(
        self,
        sentences: list[str],
        *,
        convert_to_numpy: bool,
        show_progress_bar: bool,
    ) -> NDArray[np.float32]: ...


@dataclass(frozen=True)
class SearchResult:
    clause: Clause
    score: float

    @property
    def id(self) -> str:
        return self.clause.id

    @property
    def title(self) -> str:
        return self.clause.title

    @property
    def source_url(self) -> str:
        return self.clause.source_url


def _new_encoder(model_name: str) -> Encoder:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class PVAGRetriever:
    def __init__(
        self,
        clauses_path: Path = CLAUSES_PATH,
        embeddings_path: Path = EMBEDDINGS_PATH,
        model_name: str = MODEL_NAME,
        encoder: Encoder | None = None,
        rebuild: bool = False,
    ) -> None:
        self.clauses_path = clauses_path
        self.embeddings_path = embeddings_path
        self.model_name = model_name
        self.encoder = encoder if encoder is not None else _new_encoder(model_name)
        raw_clauses = json.loads(clauses_path.read_text(encoding="utf-8"))
        if not isinstance(raw_clauses, list) or not raw_clauses:
            raise ValueError(f"{clauses_path} must contain a non-empty JSON list")
        self.clauses = [Clause.model_validate(record) for record in raw_clauses]
        self.embeddings = self._load_or_build_embeddings(rebuild)

    def _embedding_texts(self) -> list[str]:
        # Include titles for context while keeping the clause wording verbatim in storage.
        return [f"{clause.title}\n{clause.text}" for clause in self.clauses]

    def _encode(
        self,
        texts: list[str],
        *,
        show_progress_bar: bool,
    ) -> NDArray[np.float32]:
        vectors = np.asarray(
            self.encoder.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=show_progress_bar,
            ),
            dtype=np.float32,
        )
        if vectors.ndim != 2 or vectors.shape[0] != len(texts) or vectors.shape[1] == 0:
            raise ValueError(
                f"Encoder returned invalid embedding shape {vectors.shape} for {len(texts)} texts"
            )
        if not np.isfinite(vectors).all():
            raise ValueError("Encoder returned embeddings containing non-finite values")
        return vectors

    def _load_or_build_embeddings(self, rebuild: bool) -> NDArray[np.float32]:
        if not rebuild and self.embeddings_path.exists():
            is_current = (
                self.embeddings_path.stat().st_mtime_ns >= self.clauses_path.stat().st_mtime_ns
            )
            if is_current:
                cached = np.load(self.embeddings_path, allow_pickle=False)
                if (
                    cached.ndim == 2
                    and cached.shape[0] == len(self.clauses)
                    and cached.shape[1] > 0
                    and np.isfinite(cached).all()
                ):
                    return np.asarray(cached, dtype=np.float32)

        embeddings = self._encode(self._embedding_texts(), show_progress_bar=True)
        self.embeddings_path.parent.mkdir(parents=True, exist_ok=True)
        with self.embeddings_path.open("wb") as file:
            np.save(file, embeddings, allow_pickle=False)
        return embeddings

    def search(
        self,
        query: str,
        k: int = 5,
        topic: str | None = None,
        chapter: str | None = None,
        id_prefix: str | None = None,
        *,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        if top_k is not None:
            k = top_k
        if not query.strip():
            raise ValueError("query must not be empty")
        if k < 1:
            raise ValueError("k must be at least 1")
        requested_chapter = (
            chapter.casefold().removeprefix("v") if chapter is not None else None
        )

        candidates = [
            index
            for index, clause in enumerate(self.clauses)
            if (topic is None or topic.casefold() in clause.topics)
            and (
                requested_chapter is None
                or clause.chapter.casefold().removeprefix("v") == requested_chapter
            )
            and (id_prefix is None or clause.id.casefold().startswith(id_prefix.casefold()))
        ]
        if not candidates:
            return []

        query_text = QUERY_PREFIX + query
        query_vector = self._encode([query_text], show_progress_bar=False)[0]
        vectors = self.embeddings[candidates]
        denominators = np.linalg.norm(vectors, axis=1) * np.linalg.norm(query_vector)
        if np.any(denominators == 0):
            raise ValueError("Cannot calculate cosine similarity for a zero-length embedding")
        scores = (vectors @ query_vector) / denominators
        ranked = np.argsort(-scores, kind="stable")[:k]
        return [
            SearchResult(clause=self.clauses[candidates[index]], score=float(scores[index]))
            for index in ranked
        ]
