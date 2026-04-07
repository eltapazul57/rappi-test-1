"""Node: classify user intent."""

import logging

from graph.state import ChatState

logger = logging.getLogger(__name__)


def intent_classifier(state: ChatState) -> ChatState:
    """Classify whether the user wants data (SQL path) or general help."""
    # TODO: implement — call LLM to classify intent
    raise NotImplementedError
