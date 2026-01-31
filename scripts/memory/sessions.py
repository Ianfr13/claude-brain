#!/usr/bin/env python3
"""
Claude Brain - Sessions Module

Este modulo gerencia sessoes de trabalho (tabela 'sessions').
Sessoes guardam resumo e contexto de sessoes anteriores do Claude.

Funcoes principais:
- save_session: Salva resumo de uma sessao
- get_recent_sessions: Busca sessoes recentes

Relacionamentos:
- base.py: get_db
- __init__.py: re-exporta todas as funcoes publicas
"""

import json
from typing import Optional, List, Dict, Any

from .base import get_db


def save_session(session_id: str, project: Optional[str] = None, summary: Optional[str] = None,
                 key_decisions: Optional[List[Dict[str, Any]]] = None, files_modified: Optional[List[str]] = None,
                 duration_minutes: Optional[int] = None) -> None:
    """Salva resumo de uma sessao.

    Args:
        session_id: ID unico da sessao
        project: Nome do projeto trabalhado (opcional)
        summary: Resumo textual do que foi feito (opcional)
        key_decisions: Lista de decisoes importantes tomadas (sera JSON)
        files_modified: Lista de arquivos modificados (sera JSON)
        duration_minutes: Duracao da sessao em minutos (opcional)

    Note:
        Usa UPSERT - se a sessao ja existir, atualiza os campos.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO sessions (session_id, project, summary, key_decisions, files_modified, duration_minutes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                summary = excluded.summary,
                key_decisions = excluded.key_decisions,
                files_modified = excluded.files_modified,
                duration_minutes = excluded.duration_minutes
        ''', (session_id, project, summary,
              json.dumps(key_decisions) if key_decisions else None,
              json.dumps(files_modified) if files_modified else None,
              duration_minutes))


def get_recent_sessions(project: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca sessoes recentes.

    Args:
        project: Filtrar por projeto (opcional)
        limit: Numero maximo de resultados (default: 5)

    Returns:
        Lista de dicts com campos da sessao, ordenados por created_at DESC
    """
    with get_db() as conn:
        c = conn.cursor()

        if project:
            c.execute('''
                SELECT * FROM sessions WHERE project = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (project, limit))
        else:
            c.execute('''
                SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?
            ''', (limit,))

        return [dict(row) for row in c.fetchall()]
