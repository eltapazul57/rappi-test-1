"""Node: generate a SQLite query from the user's natural language question."""

import logging

from openai import OpenAI

import db
from config import MAX_RETRIES, OPENAI_API_KEY, OPENAI_MODEL
from graph.state import ChatState
from prompts import BOT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=OPENAI_API_KEY)


def _clean_sql(raw: str) -> str:
    """Strip markdown code fences if the model wrapped the SQL in them."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # drop first line (```sql or ```) and last line (```)
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return text.strip()


def sql_generator(state: ChatState) -> ChatState:
    """Generate a SQLite-compatible SQL query from the user message."""
    schema = db.get_schema()
    system_prompt = BOT_SYSTEM_PROMPT.format(schema=schema)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(state["messages"])
    messages.append({"role": "user", "content": state["user_message"]})

    if state.get("sql_error"):
        retry_attempt = max(1, state.get("retry_count", 1))
        messages.append({
            "role": "user",
            "content": (
                "This is a SQL retry.\n"
                f"Attempt: {retry_attempt} of {MAX_RETRIES}.\n"
                f"SQLite error from the previous attempt: {state['sql_error']}\n"
                "Fix the query considering that error and return ONLY the corrected SQL query."
            ),
        })

    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        max_tokens=500,
        temperature=0,
    )
    sql = _clean_sql(response.choices[0].message.content)
    logger.info("Generated SQL: %s", sql)
    return {**state, "generated_sql": sql, "sql_error": None}
