"""Database initialization and access layer."""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_PATH, METRICS_CSV_PATH, ORDERS_CSV_PATH

logger = logging.getLogger(__name__)

_connection: sqlite3.Connection | None = None

# Column names as they appear in the CSVs
WEEK_COLS_METRICS = [
    "L8W_VALUE", "L7W_VALUE", "L6W_VALUE", "L5W_VALUE",
    "L4W_VALUE", "L3W_VALUE", "L2W_VALUE", "L1W_VALUE", "L0W_VALUE",
]
WEEK_COLS_ORDERS = ["L8W", "L7W", "L6W", "L5W", "L4W", "L3W", "L2W", "L1W", "L0W"]


def get_connection() -> sqlite3.Connection:
    """Return the singleton SQLite connection. Raises RuntimeError if not initialized."""
    if _connection is None:
        raise RuntimeError("Database not initialized. The server failed to load data on startup.")
    return _connection


def load_data(
    metrics_path: Path = METRICS_CSV_PATH,
    orders_path: Path = ORDERS_CSV_PATH,
    db_path: Path = DB_PATH,
) -> None:
    """Load CSVs into SQLite and create the orders_enriched view."""
    global _connection

    if not metrics_path.exists():
        raise FileNotFoundError(
            f"Metrics CSV not found at {metrics_path}. "
            "Place input_metrics.csv in the data/ folder."
        )
    if not orders_path.exists():
        raise FileNotFoundError(
            f"Orders CSV not found at {orders_path}. "
            "Place orders.csv in the data/ folder."
        )

    logger.info("Loading %s ...", metrics_path.name)
    df_metrics = pd.read_csv(metrics_path)

    logger.info("Loading %s ...", orders_path.name)
    df_orders = pd.read_csv(orders_path)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)

    df_metrics.to_sql("input_metrics", conn, if_exists="replace", index=False)
    df_orders.to_sql("orders", conn, if_exists="replace", index=False)

    conn.execute("DROP VIEW IF EXISTS orders_enriched")
    conn.execute("""
        CREATE VIEW orders_enriched AS
        SELECT
            o.COUNTRY, o.CITY, o.ZONE,
            o.L8W, o.L7W, o.L6W, o.L5W,
            o.L4W, o.L3W, o.L2W, o.L1W, o.L0W,
            z.ZONE_TYPE,
            z.ZONE_PRIORITIZATION
        FROM orders o
        LEFT JOIN (
            SELECT DISTINCT COUNTRY, CITY, ZONE, ZONE_TYPE, ZONE_PRIORITIZATION
            FROM input_metrics
        ) z ON o.COUNTRY = z.COUNTRY
           AND o.CITY    = z.CITY
           AND o.ZONE    = z.ZONE
    """)
    conn.commit()

    _connection = conn
    logger.info(
        "Database ready — %d metric rows, %d order rows.",
        len(df_metrics),
        len(df_orders),
    )


def get_schema() -> str:
    """Return a human-readable schema string for injection into LLM prompts."""
    conn = get_connection()
    lines: list[str] = []

    cursor = conn.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
    )
    for name, obj_type in cursor.fetchall():
        lines.append(f"\n[{obj_type.upper()}] {name}")
        col_cursor = conn.execute(f"PRAGMA table_info({name})")
        for col in col_cursor.fetchall():
            lines.append(f"  - {col[1]} ({col[2]})")

    return "\n".join(lines)
