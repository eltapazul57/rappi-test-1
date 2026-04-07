"""LangGraph conversation graph.

Flow:
  intent_classifier
    ├─ data_query ──> sql_generator ──> sql_executor
    │                                       ├─ success ──> response_formatter
    │                                       └─ error   ──> error_handler ──> sql_generator (retry, max MAX_RETRIES)
    └─ general ─────────────────────────────────────── ──> response_formatter
"""

from langgraph.graph import END, START, StateGraph

from graph.error_handler import error_handler
from graph.intent_classifier import intent_classifier
from graph.response_formatter import response_formatter
from graph.routing import route_intent, route_retry, route_sql_result
from graph.sql_executor import sql_executor
from graph.sql_generator import sql_generator
from graph.state import ChatState


def build_graph() -> StateGraph:
    """Assemble and compile the LangGraph conversation graph."""
    graph = StateGraph(ChatState)

    graph.add_node("intent_classifier", intent_classifier)
    graph.add_node("sql_generator", sql_generator)
    graph.add_node("sql_executor", sql_executor)
    graph.add_node("error_handler", error_handler)
    graph.add_node("response_formatter", response_formatter)

    graph.add_edge(START, "intent_classifier")
    graph.add_conditional_edges("intent_classifier", route_intent)
    graph.add_edge("sql_generator", "sql_executor")
    graph.add_conditional_edges("sql_executor", route_sql_result)
    graph.add_conditional_edges("error_handler", route_retry)
    graph.add_edge("response_formatter", END)

    return graph.compile()


compiled_graph = build_graph()
