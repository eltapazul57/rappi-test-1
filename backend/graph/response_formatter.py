"""Node: format results into a user-facing natural language response."""

import logging

from graph.state import ChatState

logger = logging.getLogger(__name__)


def response_formatter(state: ChatState) -> ChatState:
    """Format sql_result (or fallback) into a user-facing natural language response."""
    # TODO: implement — call LLM to narrate results, add business interpretation and follow-up suggestion
    raise NotImplementedError
