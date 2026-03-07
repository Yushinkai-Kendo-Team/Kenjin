"""Search API endpoints."""

from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter

from kendocenter.retrieval.pipeline import RetrievalPipeline

router = APIRouter()
_pipeline: RetrievalPipeline | None = None


def get_pipeline() -> RetrievalPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RetrievalPipeline()
    return _pipeline


class SearchRequest(BaseModel):
    question: str
    n_results: int = 8
    language: str | None = None
    generate: bool = False


class SearchResponse(BaseModel):
    query: str
    glossary_match: dict | None = None
    results: list[dict] = []
    formatted_prompt: str = ""
    ai_answer: str = ""


@router.post("/api/search", response_model=SearchResponse)
def search_kendo(request: SearchRequest) -> SearchResponse:
    """Search the kendo knowledge base.

    Set `generate: true` to also get an AI answer from Claude Code CLI.
    """
    pipeline = get_pipeline()
    result = pipeline.query(
        request.question,
        n_results=request.n_results,
        language=request.language,
        generate=request.generate,
    )

    return SearchResponse(
        query=result.query,
        glossary_match=result.glossary_match,
        results=[
            {
                "text": r.text,
                "metadata": r.metadata,
                "distance": r.distance,
            }
            for r in result.results
        ],
        formatted_prompt=result.formatted_prompt,
        ai_answer=result.ai_answer,
    )
