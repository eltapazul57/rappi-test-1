"""FastAPI application entry point."""

import json
import logging
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
from config import CORS_ORIGINS, MAX_CONVERSATION_HISTORY
from graph import compiled_graph
from graph.state import ChatState

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


@app.on_event("startup")
def startup() -> None:
    """Load data from the Excel workbook into SQLite on server start."""
    try:
        db.load_data()
    except FileNotFoundError as exc:
        logger.error("Startup data load failed: %s", exc)
    except Exception as exc:
        logger.error("Unexpected error loading data: %s", exc)


@app.get("/health")
def health() -> dict:
    """Health check — also reports whether the database is loaded."""
    loaded = db._connection is not None
    return {"status": "ok", "database": "loaded" if loaded else "not loaded"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Receive a user message and return a natural language answer."""
    if db._connection is None:
        raise HTTPException(
            status_code=503,
            detail="Database not loaded. Place rappi_data.xlsx in data/ and restart.",
        )

    session_id = request.session_id or str(uuid.uuid4())
    history = conversation_store.get(session_id, [])

    initial_state: ChatState = {
        "user_message": request.message,
        "session_id": session_id,
        "messages": history,
        "intent": "",
        "generated_sql": None,
        "sql_result": None,
        "sql_error": None,
        "retry_count": 0,
        "response": "",
    }

    result = compiled_graph.invoke(initial_state)

    # Update conversation history and trim to MAX_CONVERSATION_HISTORY turns
    updated_history = history + [
        {"role": "user", "content": request.message},
        {"role": "assistant", "content": result["response"]},
    ]
    conversation_store[session_id] = updated_history[-MAX_CONVERSATION_HISTORY * 2:]

    data: list = []
    if result.get("sql_result"):
        try:
            data = json.loads(result["sql_result"])
        except json.JSONDecodeError:
            pass

    return ChatResponse(
        answer=result["response"],
        data=data,
        sql=result.get("generated_sql"),
        session_id=session_id,
    )


@app.post("/insights", response_model=InsightsResponse)
def insights() -> InsightsResponse:
    """Generate and return the automated weekly insights report."""
    # TODO: implement — load data from db, call generate_report
    raise NotImplementedError
