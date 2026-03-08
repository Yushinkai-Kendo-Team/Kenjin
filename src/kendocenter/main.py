"""FastAPI application entry point."""

from fastapi import FastAPI

from kendocenter.api.routes_search import router as search_router
from kendocenter.api.routes_terms import router as terms_router

app = FastAPI(
    title="YSK Kenjin API",
    description="YSK Kenjin — AI assistant for Yushinkai Kendo Team",
    version="0.2.0",
)

app.include_router(search_router)
app.include_router(terms_router)


@app.get("/")
def root():
    return {
        "name": "YSK Kenjin",
        "version": "0.2.0",
        "license": "AGPL-3.0",
        "docs": "/docs",
    }
