"""FastAPI endpoint question answering."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from answer import DEFAULT_MIN_SCORE, TOP_K
from rag_answer import ask_with_rag
from retrieval import PVAGRetriever, SearchResult


DATA_DIR = Path(__file__).resolve().parent / "data"


class ChatRequest(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=2000)]


class ClauseSource(BaseModel):
    id: str
    title: str
    score: float
    source_url: str
    text: str
    advisory: str


class ChatResponse(BaseModel):
    answer: str
    relevant: bool
    clauses: list[ClauseSource]


def _format_sources(results: list[SearchResult]) -> list[ClauseSource]:
    return [
        ClauseSource(
            id=result.clause.id,
            title=result.clause.title,
            score=result.score,
            source_url=result.clause.source_url,
            text=result.clause.text,
            advisory=result.clause.advisory,
        )
        for result in results
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.retriever = PVAGRetriever(
        clauses_path=DATA_DIR / "clauses.json",
        embeddings_path=DATA_DIR / "embeddings.npy",
    )
    yield


app = FastAPI(title="PVAG Question Answering API", lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty")

    retriever: PVAGRetriever = request.app.state.retriever
    results = retriever.search(question, k=TOP_K)
    if not results or results[0].score < DEFAULT_MIN_SCORE:
        return ChatResponse(
            answer="No relevant clause found",
            relevant=False,
            clauses=_format_sources(results),
        )

    try:
        answer = ask_with_rag(question, results)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return ChatResponse(
        answer=answer,
        relevant=True,
        clauses=_format_sources(results),
    )
