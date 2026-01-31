"""
Centralized path configuration for Claude Brain.

All hardcoded paths are consolidated here to support:
- Environment variable overrides
- Docker containerization
- Multiple deployment environments
"""

import os
from pathlib import Path

# Base directory (can be overridden by BRAIN_DIR env var)
BRAIN_DIR = Path(os.getenv("BRAIN_DIR", "/root/claude-brain"))

# Memory/Database paths
MEMORY_DIR = BRAIN_DIR / "memory"
DB_PATH = Path(os.getenv("DB_PATH", MEMORY_DIR / "brain.db"))

# RAG (Retrieval-Augmented Generation) paths
RAG_DIR = BRAIN_DIR / "rag"
RAG_FAISS_DIR = Path(os.getenv("RAG_FAISS_DIR", RAG_DIR / "faiss"))
CACHE_FILE = RAG_DIR / "query_cache.json"
FAISS_INDEX_FILE = RAG_FAISS_DIR / "index.faiss"
FAISS_META_FILE = RAG_FAISS_DIR / "metadata.json"

# Logging paths
LOG_DIR = Path(os.getenv("LOG_DIR", BRAIN_DIR / "logs"))
LOG_FILE = LOG_DIR / "brain.log"

# Dashboard
DASHBOARD_DIR = BRAIN_DIR / "dashboard"
DASHBOARD_FILE = DASHBOARD_DIR / "index.html"

# Config
CONFIG_DIR = BRAIN_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "brain_config.json"

# Scripts
SCRIPTS_DIR = BRAIN_DIR / "scripts"
HOOKS_DIR = BRAIN_DIR / "hooks"

# CLI wrapper
CLI_SCRIPT = BRAIN_DIR / "brain"

# Directories allowed for indexing (security)
ALLOWED_INDEX_PATHS = [
    BRAIN_DIR,
    Path("/root/vsl-analysis"),
    Path("/root/claude-code-projects"),
    Path.home() / ".claude",
]


def ensure_dirs():
    """Create necessary directories if they don't exist."""
    for directory in [MEMORY_DIR, RAG_DIR, RAG_FAISS_DIR, LOG_DIR, CONFIG_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    # Debug: Print all paths
    print("Claude Brain Path Configuration")
    print("=" * 50)
    print(f"BRAIN_DIR:          {BRAIN_DIR}")
    print(f"DB_PATH:            {DB_PATH}")
    print(f"RAG_DIR:            {RAG_DIR}")
    print(f"RAG_FAISS_DIR:      {RAG_FAISS_DIR}")
    print(f"LOG_DIR:            {LOG_DIR}")
    print(f"DASHBOARD_FILE:     {DASHBOARD_FILE}")
    print(f"CONFIG_FILE:        {CONFIG_FILE}")
    print("=" * 50)
    ensure_dirs()
    print("✅ All directories created/verified")
