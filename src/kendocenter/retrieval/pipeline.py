"""Full retrieval pipeline: query -> retrieve -> format prompt -> (optional) generate."""

from __future__ import annotations

from kendocenter.retrieval.retriever import Retriever
from kendocenter.retrieval.prompt_builder import build_prompt, format_context
from kendocenter.storage.models import RetrievalResult
from kendocenter.generation.claude_cli import ask_claude


class RetrievalPipeline:
    """Orchestrates the full retrieval flow."""

    def __init__(self, retriever: Retriever | None = None):
        self.retriever = retriever or Retriever()

    def query(
        self,
        question: str,
        n_results: int | None = None,
        language: str | None = None,
        generate: bool = False,
    ) -> RetrievalResult:
        """Process a kendo question through the full retrieval pipeline.

        Args:
            question: The user's kendo question.
            n_results: Max semantic search results.
            language: Filter results by language.
            generate: If True, call Claude Code CLI to generate an answer.

        Returns:
            RetrievalResult with search results, formatted prompt, and optional AI answer.
        """
        # Step 1: Retrieve from both stores
        glossary_match, search_results = self.retriever.retrieve(
            question, n_results=n_results, language=language
        )

        # Step 2: Build the formatted prompt
        formatted_prompt = build_prompt(question, search_results, glossary_match)

        # Step 3: Optionally generate an answer via Claude Code CLI
        ai_answer = ""
        if generate:
            ai_answer = ask_claude(formatted_prompt)

        return RetrievalResult(
            query=question,
            results=search_results,
            glossary_match=glossary_match,
            formatted_prompt=formatted_prompt,
            ai_answer=ai_answer,
        )
