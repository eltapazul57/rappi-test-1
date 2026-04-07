"""Database initialization and access layer."""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_PATH, EXCEL_PATH

logger = logging.getLogger(__name__)

_connection: sqlite3.Connection | None = None

METRICS_SHEET = "RAW_INPUT_METRICS"
ORDERS_SHEET = "RAW_ORDERS"


def get_connection() -> sqlite3.Connection:
    """Return the singleton SQLite connection. Raises RuntimeError if not initialized."""
    if _connection is None:
        raise RuntimeError("Database not initialized. The server failed to load data on startup.")
    return _connection


def load_data(
    excel_path: Path = EXCEL_PATH,
    db_path: Path = DB_PATH,
) -> None:
    """Load the workbook into SQLite and create the orders_enriched view."""
    global _connection

    if not excel_path.exists():
        raise FileNotFoundError(
            f"Workbook not found at {excel_path}. "
            "Place rappi_data.xlsx in the data/ folder."
        )

    logger.info("Loading workbook %s ...", excel_path.name)
    workbook = pd.ExcelFile(excel_path)
    if METRICS_SHEET not in workbook.sheet_names:
        raise ValueError(
            f"Sheet {METRICS_SHEET!r} not found in {excel_path.name}. "
            f"Available sheets: {workbook.sheet_names}"
        )
    if ORDERS_SHEET not in workbook.sheet_names:
        raise ValueError(
            f"Sheet {ORDERS_SHEET!r} not found in {excel_path.name}. "
            f"Available sheets: {workbook.sheet_names}"
        )

    df_metrics = pd.read_excel(workbook, sheet_name=METRICS_SHEET).dropna(how="all")
    df_orders = pd.read_excel(workbook, sheet_name=ORDERS_SHEET).dropna(how="all")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)

    df_metrics.to_sql("input_metrics", conn, if_exists="replace", index=False)
    df_orders.to_sql("orders", conn, if_exists="replace", index=False)

    conn.execute("DROP VIEW IF EXISTS orders_enriched")
    conn.execute("""
        CREATE VIEW orders_enriched AS
        SELECT
            o.COUNTRY, o.CITY, o.ZONE, o.METRIC,
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
