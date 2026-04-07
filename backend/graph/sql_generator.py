"""Node: generate SQL from natural language."""

import logging

from graph.state import ChatState

logger = logging.getLogger(__name__)


def sql_generator(state: ChatState) -> ChatState:
    """Generate a SQLite-compatible SQL query from the user message."""
    # TODO: implement — call LLM with BOT_SYSTEM_PROMPT + conversation history
    raise NotImplementedError
