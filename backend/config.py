"""Central configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "rappi.db"
EXCEL_PATH = DATA_DIR / "rappi_data.xlsx"

OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1000"))

CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))
MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "10"))

ANOMALY_THRESHOLD: float = float(os.getenv("ANOMALY_THRESHOLD", "0.10"))
TREND_MIN_WEEKS: int = int(os.getenv("TREND_MIN_WEEKS", "3"))
BENCHMARK_STD_THRESHOLD: float = float(os.getenv("BENCHMARK_STD_THRESHOLD", "1.0"))
CORRELATION_MIN_ABS: float = float(os.getenv("CORRELATION_MIN_ABS", "0.3"))
