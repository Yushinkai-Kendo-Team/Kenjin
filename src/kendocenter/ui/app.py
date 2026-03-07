"""Streamlit UI for YKC Kenjin."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

from kendocenter.retrieval.pipeline import RetrievalPipeline
from kendocenter.storage.database import Database
from kendocenter.storage.vector_store import VectorStore
from kendocenter.generation.claude_cli import is_claude_available


LOGO_URL = "https://avatars.githubusercontent.com/u/266327333"

st.set_page_config(
    page_title="YKC Kenjin",
    page_icon=LOGO_URL,
    layout="wide",
)


@st.cache_resource
def get_pipeline():
    return RetrievalPipeline()


@st.cache_resource
def get_db():
    db = Database()
    db.initialize()
    return db


def main():
    # Header with logo
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        st.image(LOGO_URL, width=64)
    with col_title:
        st.title("YKC Kenjin")
        st.caption("AI Assistant for Yushinkai Kendo Club")

    # Sidebar
    with st.sidebar:
        db = get_db()

        # --- Knowledge Base Sources ---
        st.header("Knowledge Base")
        source_stats = db.get_source_stats()
        total_sources = db.count_sources()
        total_terms = db.count_terms()

        try:
            vs = VectorStore()
            total_chunks = vs.count
        except Exception:
            total_chunks = 0

        if total_sources > 0:
            st.metric("Total Sources", total_sources)
            cols = st.columns(2)
            with cols[0]:
                st.metric("Glossary Terms", total_terms)
            with cols[1]:
                st.metric("Vector Chunks", total_chunks)

            st.markdown("**Sources by category:**")
            for stat in source_stats:
                st.markdown(f"- **{stat['category']}**: {stat['count']} files")
        else:
            st.info(
                "No sources ingested yet. Run:\n\n"
                "```\npython scripts/ingest_all.py --reset\n```"
            )

        st.markdown("---")

        # --- Glossary Browser ---
        st.header("Glossary Browser")

        # Category filter
        categories = db.get_categories()
        cat_options = ["All"] + [c["category"] for c in categories]
        selected_cat = st.selectbox("Category", cat_options)

        # Search within glossary
        term_search = st.text_input("Search terms", placeholder="e.g. kamae")

        # Get filtered terms
        cat_filter = selected_cat if selected_cat != "All" else ""
        terms = db.search_terms(
            query=term_search, category=cat_filter, limit=100
        )

        if terms:
            st.markdown(f"**{len(terms)} terms**")
            for term in terms:
                kanji = f" ({term['term_kanji']})" if term.get("term_kanji") else ""
                with st.expander(f"{term['term_romaji']}{kanji}"):
                    st.write(term["definition"])
                    st.caption(f"Category: {term['category']}")
        else:
            st.info("No terms found. Run the ingestion script first.")

    # Main area: Knowledge Search
    st.markdown("### Ask about Kendo")

    question = st.text_input(
        "Your question:",
        placeholder="What is the difference between chiisai men and ooki men?",
        key="main_question",
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        language_filter = st.selectbox(
            "Language", ["All", "English only", "Vietnamese only"],
            key="lang_filter",
        )
    with col2:
        n_results = st.slider("Max results", 3, 15, 8, key="n_results")
    with col3:
        claude_installed = is_claude_available()
        ask_claude_checked = st.checkbox(
            "Ask Claude Code",
            value=False,
            disabled=not claude_installed,
            help="Auto-send prompt to Claude Code CLI and display AI answer"
                 if claude_installed
                 else "Claude Code CLI not found in PATH",
            key="ask_claude",
        )

    lang_map = {"All": None, "English only": "en", "Vietnamese only": "vn"}
    language = lang_map[language_filter]

    if question:
        pipeline = get_pipeline()

        with st.spinner("Searching kendo knowledge base..."):
            result = pipeline.query(
                question, n_results=n_results, language=language,
                generate=False,  # retrieve first, generate separately for better UX
            )

        # Show glossary match
        if result.glossary_match:
            m = result.glossary_match
            kanji = f" ({m['term_kanji']})" if m.get("term_kanji") else ""
            st.markdown("#### Glossary Match")
            st.success(
                f"**{m['term_romaji']}{kanji}**\n\n"
                f"{m['definition']}\n\n"
                f"*Category: {m.get('category', 'general')} | Source: Glossary.pdf*"
            )

        # Show semantic search results
        if result.results:
            st.markdown(f"#### Related Knowledge ({len(result.results)} results)")
            for i, r in enumerate(result.results, 1):
                source = r.metadata.get("source", "unknown")
                doc_type = r.metadata.get("type", "unknown")
                lang = r.metadata.get("language", "en")
                relevance = 1 - r.distance

                with st.expander(
                    f"[{i}] {source} ({doc_type}) — relevance: {relevance:.0%}"
                ):
                    st.markdown(r.text)
                    file_path = r.metadata.get("file_path", "")
                    caption_parts = [
                        f"Type: {doc_type}",
                        f"Language: {lang}",
                        f"Subject: {r.metadata.get('subject', 'N/A')}",
                    ]
                    if file_path:
                        caption_parts.append(f"Path: {file_path}")
                    st.caption(" | ".join(caption_parts))
        elif not result.glossary_match:
            st.warning("No results found. Try rephrasing your question.")

        # AI Answer section
        if ask_claude_checked and result.has_results:
            st.markdown("---")
            st.markdown("#### AI Answer (Claude Code)")

            from kendocenter.generation.claude_cli import is_claude_ready, ask_claude

            ready, status_msg = is_claude_ready()
            if not ready:
                st.warning(
                    f"Claude Code is not ready: {status_msg}\n\n"
                    "Run `claude login` in a terminal to authenticate, "
                    "then try again. Showing the copy-paste prompt below instead."
                )
            else:
                with st.spinner("Asking Claude Code... (this may take a moment)"):
                    ai_answer = ask_claude(result.formatted_prompt)

                if ai_answer.startswith("[Error]"):
                    st.error(
                        f"{ai_answer}\n\n"
                        "You can still copy the prompt below and paste it manually."
                    )
                else:
                    st.markdown(ai_answer)

        # Copy prompt section (always available as fallback)
        st.markdown("---")
        prompt_expanded = not (
            ask_claude_checked
            and result.has_results
            and "ready" not in locals().get("status_msg", "")
            and locals().get("ready", False)
        )
        with st.expander(
            "Prompt for Claude Code (copy-paste)",
            expanded=prompt_expanded,
        ):
            st.caption(
                "Copy this prompt and paste it into Claude Code for an AI-generated answer "
                "with full kendo context."
            )
            st.code(result.formatted_prompt, language=None)
            st.caption(f"Prompt length: {len(result.formatted_prompt):,} characters")

    # Footer
    st.markdown("---")
    st.caption(
        "YKC Kenjin | Open-source kendo knowledge retrieval | AGPL-3.0 License"
    )


if __name__ == "__main__":
    main()
