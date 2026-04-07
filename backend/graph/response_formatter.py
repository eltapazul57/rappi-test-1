"""Node: turn raw SQL results into a natural language response."""

import json
import logging

from openai import OpenAI

from config import MAX_TOKENS, OPENAI_API_KEY, OPENAI_MODEL
from graph.state import ChatState

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=OPENAI_API_KEY)

_DATA_SYSTEM = """You are a Rappi operations analyst assistant helping non-technical teams
understand their data. You received a user question, the SQL that was run, and the results.

Your response must:
1. Directly answer the question in plain business language.
2. Highlight the most important finding (best/worst zone, biggest change, etc.).
3. Add one sentence of business context or implication.
4. End with one proactive follow-up suggestion ("You might also want to look at...").

Keep it concise — 3 to 6 sentences total. Respond in the same language as the user's question."""

_GENERAL_SYSTEM = """You are a Rappi operations analyst assistant. You help teams analyze
operational metrics (Perfect Orders, Lead Penetration, Gross Profit UE, etc.) across zones,
cities, and countries. Answer conversationally. If the user seems to want data, tell them
what kind of question to ask. Respond in the same language as the user's message."""

_FALLBACK_SYSTEM = """You are a Rappi operations analyst assistant. The system tried to run
a database query to answer the user's question but encountered an error after multiple retries.
Apologize briefly, explain you couldn't retrieve the data, and suggest they rephrase the question
or ask something slightly different. Respond in the same language as the user's message."""


def response_formatter(state: ChatState) -> ChatState:
    """Format sql_result (or fallback) into a user-facing natural language response."""
    if state.get("sql_result"):
        data = json.loads(state["sql_result"])
        preview = json.dumps(data[:30], ensure_ascii=False, indent=2)
        user_content = (
            f"User question: {state['user_message']}\n\n"
            f"SQL executed:\n{state.get('generated_sql', 'N/A')}\n\n"
            f"Results ({len(data)} rows total, showing up to 30):\n{preview}"
        )
        system = _DATA_SYSTEM

    elif state["intent"] == "data_query":
        # SQL path exhausted retries — graceful fallback
        user_content = state["user_message"]
        system = _FALLBACK_SYSTEM

    else:
        user_content = state["user_message"]
        system = _GENERAL_SYSTEM

    messages = [{"role": "system", "content": system}]
    messages.extend(state["messages"])
    messages.append({"role": "user", "content": user_content})

    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=0.3,
    )
    answer = response.choices[0].message.content.strip()
    logger.info("Response formatted (%d chars).", len(answer))
    return {**state, "response": answer}
