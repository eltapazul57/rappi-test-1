"""Shared state definition for the conversation graph."""

from typing import Optional

from typing_extensions import TypedDict


class ChatState(TypedDict):
    """State passed between all nodes in the graph."""

    user_message: str
    session_id: str
    messages: list[dict]       # last N turns: [{role, content}]
    intent: str                # "data_query" | "general"
    generated_sql: Optional[str]
    sql_result: Optional[str]  # JSON-serialized query results
    sql_error: Optional[str]
    retry_count: int
    response: str
