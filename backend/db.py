"""Database initialization and access layer."""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_PATH, EXCEL_PATH

logger = logging.getLogger(__name__)

_connection: sqlite3.Connection | None = None

WEEK_COLS_METRICS = [
    "L8W_ROLL", "L7W_ROLL", "L6W_ROLL", "L5W_ROLL",
    "L4W_ROLL", "L3W_ROLL", "L2W_ROLL", "L1W_ROLL", "L0W_ROLL",
]
WEEK_COLS_ORDERS = ["L8W", "L7W", "L6W", "L5W", "L4W", "L3W", "L2W", "L1W", "L0W"]


def get_connection() -> sqlite3.Connection:
    """Return the singleton SQLite connection. Raises RuntimeError if not initialized."""
    # TODO: implement
    raise NotImplementedError


def load_data(excel_path: Path = EXCEL_PATH, db_path: Path = DB_PATH) -> None:
    """Load Excel sheets into SQLite and create the orders_enriched view."""
    # TODO: implement
    raise NotImplementedError


def get_schema() -> str:
    """Return a human-readable schema string for injection into LLM prompts."""
    # TODO: implement
    raise NotImplementedError
