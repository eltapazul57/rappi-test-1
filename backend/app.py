"""FastAPI application entry point."""

import json
import logging
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pandas as pd

import db
import insights as insights_module
from config import CORS_ORIGINS, MAX_CONVERSATION_HISTORY
from graph import compiled_graph
from graph.state import ChatState

_ALLOWED_TABLES = {"input_metrics", "orders", "orders_enriched"}

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
    if db._connection is None:
        raise HTTPException(
            status_code=503,
            detail="Database not loaded. Place rappi_data.xlsx in data/ and restart.",
        )
    conn = db.get_connection()
    df_metrics = pd.read_sql("SELECT * FROM input_metrics", conn)
    df_orders = pd.read_sql("SELECT * FROM orders", conn)
    report = insights_module.generate_report(df_metrics, df_orders)
    return InsightsResponse(report=report)


# ---------------------------------------------------------------------------
# Debug / inspection endpoints — read-only, for development
# ---------------------------------------------------------------------------

@app.get("/debug/tables")
def debug_tables() -> list[dict]:
    """List all tables and views with their row counts."""
    conn = db.get_connection()
    cursor = conn.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY type, name"
    )
    results = []
    for name, obj_type in cursor.fetchall():
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        except Exception:
            count = None
        results.append({"name": name, "type": obj_type, "rows": count})
    return results


@app.get("/debug/preview/{table_name}")
def debug_preview(table_name: str, limit: int = 20) -> list[dict]:
    """Return the first N rows of a table or view as JSON."""
    if table_name not in _ALLOWED_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown table '{table_name}'. Allowed: {sorted(_ALLOWED_TABLES)}",
        )
    limit = max(1, min(limit, 200))
    conn = db.get_connection()
    cursor = conn.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


@app.get("/debug/metrics")
def debug_metrics() -> list[str]:
    """Return all distinct METRIC values from input_metrics, sorted."""
    conn = db.get_connection()
    cursor = conn.execute("SELECT DISTINCT METRIC FROM input_metrics ORDER BY METRIC")
    return [row[0] for row in cursor.fetchall()]


@app.get("/debug/insights/anomalies")
def debug_anomalies() -> list[dict]:
    """Raw output of detect_anomalies — sorted by absolute change."""
    conn = db.get_connection()
    df = pd.read_sql("SELECT * FROM input_metrics", conn)
    result = insights_module.detect_anomalies(df)
    return result.to_dict(orient="records")


@app.get("/debug/insights/trends")
def debug_trends() -> list[dict]:
    """Raw output of detect_concerning_trends — sorted by streak length."""
    conn = db.get_connection()
    df = pd.read_sql("SELECT * FROM input_metrics", conn)
    result = insights_module.detect_concerning_trends(df)
    return result.to_dict(orient="records")


@app.get("/debug/insights/benchmarks")
def debug_benchmarks() -> list[dict]:
    """Raw output of benchmark_zones — underperformers first (most negative z-score)."""
    conn = db.get_connection()
    df = pd.read_sql("SELECT * FROM input_metrics", conn)
    result = insights_module.benchmark_zones(df)
    return result.to_dict(orient="records")


@app.get("/debug/insights/correlations")
def debug_correlations() -> list[dict]:
    """Raw output of compute_correlations — sorted by absolute correlation."""
    conn = db.get_connection()
    df = pd.read_sql("SELECT * FROM input_metrics", conn)
    result = insights_module.compute_correlations(df)
    return result.to_dict(orient="records")


@app.get("/debug/insights/opportunities")
def debug_opportunities() -> list[dict]:
    """Raw output of detect_opportunities — zones with order growth and metric gaps."""
    conn = db.get_connection()
    df_metrics = pd.read_sql("SELECT * FROM input_metrics", conn)
    df_orders = pd.read_sql("SELECT * FROM orders", conn)
    result = insights_module.detect_opportunities(df_metrics, df_orders)
    return result.to_dict(orient="records")


@app.get("/debug/insights/report")
def debug_report() -> dict:
    """Raw structured Markdown from generate_report — no LLM, instant response."""
    conn = db.get_connection()
    df_metrics = pd.read_sql("SELECT * FROM input_metrics", conn)
    df_orders = pd.read_sql("SELECT * FROM orders", conn)
    raw = insights_module.generate_report(df_metrics, df_orders)
    return {"report": raw}
