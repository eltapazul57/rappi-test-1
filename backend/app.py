"""FastAPI application entry point."""

import logging
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import CORS_ORIGINS, MAX_CONVERSATION_HISTORY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Rappi Operations Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

conversation_store: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    """Request body for POST /chat."""
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Response body for POST /chat."""
    answer: str
    data: list
    sql: str | None
    session_id: str


class InsightsResponse(BaseModel):
    """Response body for POST /insights."""
    report: str


@app.get("/health")
def health() -> dict:
    """Health check."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Receive a user message and return a natural language answer."""
    # TODO: implement — invoke compiled_graph, manage conversation_store
    raise NotImplementedError


@app.post("/insights", response_model=InsightsResponse)
def insights() -> InsightsResponse:
    """Generate and return the automated weekly insights report."""
    # TODO: implement — load data from db, call generate_report
    raise NotImplementedError
