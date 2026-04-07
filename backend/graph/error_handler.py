"""Node: handle SQL execution errors and manage retries."""

import logging

from graph.state import ChatState

logger = logging.getLogger(__name__)


def error_handler(state: ChatState) -> ChatState:
    """Log SQL error and increment retry_count for re-entry into sql_generator."""
    logger.warning("SQL error on attempt %d: %s", state["retry_count"] + 1, state.get("sql_error"))
    return {**state, "retry_count": state["retry_count"] + 1}
