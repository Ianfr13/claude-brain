#!/usr/bin/env python3
"""
Claude Brain - Session Manager
Gerencia resumos de sessão para não perder contexto

Persistência:
- Arquivo JSON em /root/claude-brain/memory/session.json (principal)
- Backup automático na tabela 'active_sessions' do SQLite
- Recuperação automática do SQLite se arquivo não existir
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from scripts.memory_store import save_session, get_recent_sessions, save_memory, save_decision, get_db, DB_PATH

# Caminho persistente (não mais em /tmp)
SESSION_FILE = Path("/root/claude-brain/memory/session.json")

# Garante que diretório existe
SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)


def _init_active_sessions_table():
    """Cria tabela de sessões ativas se não existir"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS active_sessions (
                id INTEGER PRIMARY KEY,
                session_id TEXT UNIQUE NOT NULL,
                project TEXT,
                data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')


def _backup_to_sqlite(session_data: dict):
    """Faz backup da sessão ativa no SQLite"""
    _init_active_sessions_table()
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO active_sessions (session_id, project, data, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                data = excluded.data,
                updated_at = CURRENT_TIMESTAMP
        ''', (session_data["id"], session_data.get("project"), json.dumps(session_data)))


def _restore_from_sqlite() -> Optional[dict]:
    """Tenta restaurar sessão do SQLite se arquivo não existir"""
    _init_active_sessions_table()
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT data FROM active_sessions
                ORDER BY updated_at DESC LIMIT 1
            ''')
            row = c.fetchone()
            if row:
                return json.loads(row['data'])
    except (json.JSONDecodeError, sqlite3.Error) as e:
        print(f"⚠ Erro ao restaurar sessão do SQLite: {e}")
    return None


def _clear_sqlite_session(session_id: str):
    """Remove sessão do backup SQLite"""
    _init_active_sessions_table()
    with get_db() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM active_sessions WHERE session_id = ?', (session_id,))


def start_session(project: str = None) -> str:
    """Inicia uma nova sessão"""
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    session_data = {
        "id": session_id,
        "project": project or os.getcwd().split("/")[-1],
        "started_at": datetime.now().isoformat(),
        "decisions": [],
        "files_modified": [],
        "notes": []
    }

    # Salva em arquivo E no SQLite
    SESSION_FILE.write_text(json.dumps(session_data, indent=2))
    _backup_to_sqlite(session_data)

    print(f"✓ Sessão iniciada: {session_id}")
    return session_id


def add_decision(decision: str):
    """Adiciona decisão à sessão atual"""
    if not SESSION_FILE.exists():
        # Tenta restaurar do SQLite antes de criar nova
        restored = _restore_from_sqlite()
        if restored:
            SESSION_FILE.write_text(json.dumps(restored, indent=2))
        else:
            start_session()

    data = json.loads(SESSION_FILE.read_text())
    data["decisions"].append({
        "text": decision,
        "time": datetime.now().isoformat()
    })
    SESSION_FILE.write_text(json.dumps(data, indent=2))
    _backup_to_sqlite(data)  # Backup no SQLite


def add_file(file_path: str):
    """Adiciona arquivo modificado à sessão"""
    if not SESSION_FILE.exists():
        # Tenta restaurar do SQLite
        restored = _restore_from_sqlite()
        if restored:
            SESSION_FILE.write_text(json.dumps(restored, indent=2))
        else:
            return

    data = json.loads(SESSION_FILE.read_text())
    if file_path not in data["files_modified"]:
        data["files_modified"].append(file_path)
        SESSION_FILE.write_text(json.dumps(data, indent=2))
        _backup_to_sqlite(data)  # Backup no SQLite


def add_note(note: str):
    """Adiciona nota à sessão"""
    if not SESSION_FILE.exists():
        # Tenta restaurar do SQLite antes de criar nova
        restored = _restore_from_sqlite()
        if restored:
            SESSION_FILE.write_text(json.dumps(restored, indent=2))
        else:
            start_session()

    data = json.loads(SESSION_FILE.read_text())
    data["notes"].append(note)
    SESSION_FILE.write_text(json.dumps(data, indent=2))
    _backup_to_sqlite(data)  # Backup no SQLite


def get_current_session() -> Optional[dict]:
    """Retorna sessão atual (arquivo ou SQLite)"""
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())

    # Tenta restaurar do SQLite
    restored = _restore_from_sqlite()
    if restored:
        # Restaura o arquivo também
        SESSION_FILE.write_text(json.dumps(restored, indent=2))
        return restored

    return None


def end_session(summary: str = None):
    """Finaliza sessão e salva no brain"""
    # Tenta restaurar se arquivo não existir
    if not SESSION_FILE.exists():
        restored = _restore_from_sqlite()
        if restored:
            SESSION_FILE.write_text(json.dumps(restored, indent=2))
        else:
            print("Nenhuma sessão ativa")
            return

    data = json.loads(SESSION_FILE.read_text())

    # Calcula duração
    started = datetime.fromisoformat(data["started_at"])
    duration = int((datetime.now() - started).total_seconds() / 60)

    # Gera resumo automático se não fornecido
    if not summary:
        parts = []
        if data["decisions"]:
            parts.append(f"{len(data['decisions'])} decisões")
        if data["files_modified"]:
            parts.append(f"{len(data['files_modified'])} arquivos modificados")
        if data["notes"]:
            parts.append(f"{len(data['notes'])} notas")
        summary = f"Sessão de {duration}min: " + ", ".join(parts) if parts else f"Sessão de {duration}min"

    # Salva no brain
    save_session(
        session_id=data["id"],
        project=data["project"],
        summary=summary,
        key_decisions=data["decisions"],
        files_modified=data["files_modified"],
        duration_minutes=duration
    )

    # Salva decisões individualmente
    for d in data["decisions"]:
        save_decision(d["text"], project=data["project"])

    # Limpa sessão (arquivo e SQLite)
    SESSION_FILE.unlink()
    _clear_sqlite_session(data["id"])

    print(f"✓ Sessão salva: {data['id']}")
    print(f"  Duração: {duration} min")
    print(f"  Projeto: {data['project']}")
    print(f"  Decisões: {len(data['decisions'])}")
    print(f"  Arquivos: {len(data['files_modified'])}")


def show_session():
    """Mostra sessão atual"""
    data = get_current_session()
    if not data:
        print("Nenhuma sessão ativa")
        print("Use: brain session start")
        return

    started = datetime.fromisoformat(data["started_at"])
    duration = int((datetime.now() - started).total_seconds() / 60)

    print(f"\n📋 Sessão: {data['id']}")
    print(f"   Projeto: {data['project']}")
    print(f"   Duração: {duration} min")

    if data["decisions"]:
        print(f"\n   Decisões ({len(data['decisions'])}):")
        for d in data["decisions"][-5:]:
            print(f"   • {d['text']}")

    if data["files_modified"]:
        print(f"\n   Arquivos ({len(data['files_modified'])}):")
        for f in data["files_modified"][-5:]:
            print(f"   • {Path(f).name}")

    if data["notes"]:
        print(f"\n   Notas ({len(data['notes'])}):")
        for n in data["notes"][-3:]:
            print(f"   • {n}")


def show_history(limit: int = 5):
    """Mostra sessões anteriores"""
    sessions = get_recent_sessions(limit=limit)

    if not sessions:
        print("Nenhuma sessão anterior")
        return

    print(f"\n📚 Últimas {len(sessions)} sessões:\n")
    for s in sessions:
        print(f"   [{s['session_id']}] {s['project'] or 'N/A'}")
        print(f"   {s['summary'] or 'Sem resumo'}")
        print(f"   Duração: {s['duration_minutes'] or '?'} min")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_session()
    elif sys.argv[1] == "start":
        project = sys.argv[2] if len(sys.argv) > 2 else None
        start_session(project)
    elif sys.argv[1] == "end":
        summary = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        end_session(summary)
    elif sys.argv[1] == "note":
        note = " ".join(sys.argv[2:])
        add_note(note)
        print(f"✓ Nota adicionada")
    elif sys.argv[1] == "decision":
        decision = " ".join(sys.argv[2:])
        add_decision(decision)
        print(f"✓ Decisão adicionada")
    elif sys.argv[1] == "history":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        show_history(limit)
    elif sys.argv[1] == "show":
        show_session()
    else:
        print("Uso: session_manager.py [start|end|note|decision|history|show]")
