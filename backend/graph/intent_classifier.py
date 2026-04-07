"""Node: classify user intent as data_query or general."""

import logging

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from graph.state import ChatState

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=OPENAI_API_KEY)

_SYSTEM = (
    "You are an intent classifier for a Rappi operations analytics chatbot. "
    "Reply with exactly one word:\n"
    "- 'data_query' if the user wants data, metrics, statistics, analysis, comparisons, "
    "trends, rankings, or any information from the database.\n"
    "- 'general' for greetings, thanks, questions about how you work, or off-topic messages."
)


def intent_classifier(state: ChatState) -> ChatState:
    """Classify whether the user wants data (SQL path) or general help."""
    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": state["user_message"]},
        ],
        max_tokens=5,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip().lower()
    intent = raw if raw in ("data_query", "general") else "data_query"
    logger.info("Intent classified as: %s (raw=%r)", intent, raw)
    return {**state, "intent": intent}
