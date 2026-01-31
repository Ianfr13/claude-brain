#!/usr/bin/env python3
"""
Claude Brain - Auto Indexer
Monitora diretórios e indexa novos arquivos automaticamente
"""

import time
import sys
import json
from pathlib import Path
from datetime import datetime

from scripts.rag_engine import index_file, load_index

# Carrega configuração externa
CONFIG_PATH = Path(__file__).parent.parent / "config" / "brain_config.json"

def _load_config() -> dict:
    """Carrega configuração do arquivo externo, com fallback para defaults."""
    defaults = {
        "watch_dirs": ["/root/claude-brain"],
        "extensions": [".md", ".py", ".js", ".ts", ".yaml", ".yml", ".json", ".txt"],
        "ignore_patterns": [".git", "__pycache__", "node_modules", ".venv"],
        "indexer": {"check_interval_seconds": 60}
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding='utf-8') as f:
                return {**defaults, **json.load(f)}
        except (json.JSONDecodeError, IOError):
            pass
    return defaults

_config = _load_config()

# Configuração (do arquivo externo)
WATCH_DIRS = _config.get("watch_dirs", ["/root/claude-brain"])
EXTENSIONS = _config.get("extensions", [".md", ".py"])
IGNORE_PATTERNS = _config.get("ignore_patterns", [".git"])
CHECK_INTERVAL = _config.get("indexer", {}).get("check_interval_seconds", 60)


def should_ignore(path: Path) -> bool:
    """Verifica se deve ignorar o arquivo"""
    path_str = str(path)
    return any(pattern in path_str for pattern in IGNORE_PATTERNS)


def get_all_files(directories: list) -> dict:
    """Retorna todos os arquivos com seus mtimes"""
    files = {}
    for dir_path in directories:
        path = Path(dir_path)
        if not path.exists():
            continue

        for ext in EXTENSIONS:
            for file in path.rglob(f"*{ext}"):
                if should_ignore(file):
                    continue
                files[str(file)] = file.stat().st_mtime

    return files


def get_indexed_files() -> set:
    """Retorna arquivos já indexados"""
    index = load_index()
    return set(doc["source"] for doc in index.get("documents", {}).values())


def index_new_files(files: dict, indexed: set) -> int:
    """Indexa arquivos novos ou modificados"""
    count = 0
    for file_path, mtime in files.items():
        if file_path not in indexed:
            result = index_file(file_path)
            if result and result.get("status") == "indexed":
                print(f"  ✓ {Path(file_path).name} ({result['chunks']} chunks)")
                count += 1

    return count


def run_once():
    """Executa uma vez"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Verificando arquivos...")

    files = get_all_files(WATCH_DIRS)
    indexed = get_indexed_files()

    new_count = len(files) - len(indexed & set(files.keys()))
    if new_count > 0:
        print(f"  Encontrados {new_count} arquivos novos")
        count = index_new_files(files, indexed)
        print(f"  Indexados: {count}")
    else:
        print("  Nenhum arquivo novo")


def run_daemon():
    """Executa em loop"""
    print(f"🔍 Auto Indexer iniciado")
    print(f"   Monitorando: {len(WATCH_DIRS)} diretórios")
    print(f"   Intervalo: {CHECK_INTERVAL}s")
    print(f"   Extensões: {', '.join(EXTENSIONS)}")
    print()

    try:
        while True:
            run_once()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\nParando...")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        run_daemon()
    else:
        run_once()
