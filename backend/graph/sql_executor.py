"""Node: execute generated SQL against SQLite."""

import logging

from graph.state import ChatState

logger = logging.getLogger(__name__)


def sql_executor(state: ChatState) -> ChatState:
    """Execute generated_sql against SQLite. Populate sql_result or sql_error."""
    # TODO: implement — call db.get_connection(), execute, serialize results
    raise NotImplementedError
