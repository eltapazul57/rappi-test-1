"""Node: execute the generated SQL against SQLite."""

import json
import logging
import sqlite3

import db
from graph.state import ChatState

logger = logging.getLogger(__name__)


def sql_executor(state: ChatState) -> ChatState:
    """Execute generated_sql against SQLite. Populate sql_result or sql_error."""
    sql = state.get("generated_sql", "")
    if not sql:
        return {**state, "sql_error": "No SQL was generated."}

    try:
        conn = db.get_connection()
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        result = [dict(zip(columns, row)) for row in rows]
        serialized = json.dumps(result, ensure_ascii=False, default=str)
        logger.info("SQL returned %d rows.", len(result))
        return {**state, "sql_result": serialized, "sql_error": None}
    except sqlite3.Error as exc:
        logger.warning("SQL execution error: %s", exc)
        return {**state, "sql_result": None, "sql_error": str(exc)}
