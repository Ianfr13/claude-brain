#!/usr/bin/env python3
"""
Claude Brain - Patterns Module

Este modulo gerencia padroes de codigo (tabela 'patterns').
Patterns sao snippets de codigo frequentemente usados.

Funcoes principais:
- save_pattern: Salva um padrao de codigo
- get_pattern: Busca um padrao por nome (sem side-effects)
- increment_pattern_usage: Incrementa contador de uso
- get_all_patterns: Lista todos os padroes

Relacionamentos:
- base.py: get_db
- __init__.py: re-exporta todas as funcoes publicas
"""

from typing import Optional, List, Dict, Any

from .base import get_db


def save_pattern(name: str, code: str, pattern_type: Optional[str] = None, language: Optional[str] = None) -> None:
    """Salva um padrao de codigo.

    Args:
        name: Nome unico do padrao (ex: "python_fastapi_endpoint")
        code: Codigo do padrao
        pattern_type: Tipo do padrao (ex: "snippet", "template", "boilerplate")
        language: Linguagem do codigo (ex: "python", "javascript")

    Note:
        Usa UPSERT - se o padrao ja existir, atualiza o codigo
        e incrementa usage_count.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO patterns (name, pattern_type, code, language)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                code = excluded.code,
                pattern_type = excluded.pattern_type,
                usage_count = patterns.usage_count + 1,
                last_used = CURRENT_TIMESTAMP
        ''', (name, pattern_type, code, language))


def get_pattern(name: str) -> Optional[str]:
    """Busca um padrao de codigo (sem side-effects).

    Nao incrementa contador de uso. Para registrar uso,
    chamar increment_pattern_usage() separadamente.

    Args:
        name: Nome do padrao

    Returns:
        Codigo do padrao ou None se nao encontrado
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT code FROM patterns WHERE name = ?', (name,))
        row = c.fetchone()
        return row['code'] if row else None


def increment_pattern_usage(name: str) -> bool:
    """Incrementa contador de uso de um pattern.

    Usar separadamente de get_pattern() para controle fino
    de quando registrar uso.

    Args:
        name: Nome do padrao

    Returns:
        True se o padrao foi encontrado e atualizado, False caso contrario
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            UPDATE patterns SET usage_count = usage_count + 1, last_used = CURRENT_TIMESTAMP
            WHERE name = ?
        ''', (name,))
        return c.rowcount > 0


def get_all_patterns(pattern_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Lista todos os padroes.

    Args:
        pattern_type: Filtrar por tipo (opcional)
        limit: Numero maximo de resultados (default: 100)

    Returns:
        Lista de dicts ordenados por usage_count DESC
    """
    with get_db() as conn:
        c = conn.cursor()
        if pattern_type:
            c.execute('''
                SELECT * FROM patterns
                WHERE pattern_type = ?
                ORDER BY usage_count DESC, last_used DESC LIMIT ?
            ''', (pattern_type, limit))
        else:
            c.execute('''
                SELECT * FROM patterns
                ORDER BY usage_count DESC, last_used DESC LIMIT ?
            ''', (limit,))

        return [dict(row) for row in c.fetchall()]
