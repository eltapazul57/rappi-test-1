"""Conditional edge routing functions for the conversation graph."""

from typing import Literal

from config import MAX_RETRIES
from graph.state import ChatState


def route_intent(state: ChatState) -> Literal["sql_generator", "response_formatter"]:
    """Route after intent classification."""
    return "sql_generator" if state["intent"] == "data_query" else "response_formatter"


def route_sql_result(state: ChatState) -> Literal["response_formatter", "error_handler"]:
    """Route after SQL execution."""
    return "error_handler" if state.get("sql_error") else "response_formatter"


def route_retry(state: ChatState) -> Literal["sql_generator", "response_formatter"]:
    """Retry SQL generation or give up after MAX_RETRIES."""
    return "sql_generator" if state["retry_count"] < MAX_RETRIES else "response_formatter"
