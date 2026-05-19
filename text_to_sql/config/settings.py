"""
Global configuration for the Text-to-SQL pipeline.

Centralises all tuneable parameters: model paths,
vector-store settings, SLM endpoint, and retry limits.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = PROJECT_ROOT.parent  # where YAML files live
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"
DUMMY_DB_PATH = DATA_DIR / "dummy.sqlite3"

# ── Embedding model ─────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# ── SLM configuration (Groq) ─────────────────────────────
# Uses Groq's OpenAI-compatible API for fast inference.
# Set GROQ_API_KEY in .env file.
SLM_BASE_URL = os.getenv(
    "SLM_BASE_URL",
    "https://api.groq.com/openai/v1",
)
SLM_API_KEY = os.getenv("GROQ_API_KEY", "")
SLM_MODEL = os.getenv(
    "SLM_MODEL", "llama-3.3-70b-versatile",
)

# ── Pipeline tunables ────────────────────────────────────
TOP_K_COLUMNS = 15          # columns to retrieve per query
MAX_RETRIES = 2             # self-correction retries
CONFIDENCE_THRESHOLD = 0.60  # below → ask human

# ── Schema YAML file names ───────────────────────────────
SCHEMA_FILES = {
    "databricks": "DBKS_semantic_model(2).yaml",
    "snowflake": "Snowflake_semantic_model(2).yaml",
    "bigquery": "GBQ_big_yaml.yaml",
}

# ── Supported SQL dialects per platform ──────────────────
DIALECT_MAP = {
    "databricks": "databricks",
    "snowflake": "snowflake",
    "bigquery": "bigquery",
}
