#!/usr/bin/env python3
"""
Claude Brain - Preferences Module

Este modulo gerencia preferencias do usuario (tabela 'preferences').
Preferencias sao configuracoes/escolhas detectadas automaticamente.

Funcoes principais:
- save_preference: Salva ou atualiza uma preferencia
- get_preference: Busca valor de uma preferencia
- get_all_preferences: Lista todas as preferencias

Relacionamentos:
- base.py: get_db
- __init__.py: re-exporta todas as funcoes publicas
"""

from typing import Optional, Dict

from .base import get_db


def save_preference(key: str, value: str, confidence: float = 0.5, source: Optional[str] = None) -> None:
    """Salva ou atualiza uma preferencia.

    Se a preferencia ja existir, aumenta times_observed
    e usa a maior confianca entre atual e nova.

    Args:
        key: Chave da preferencia (ex: "test_framework", "editor", "language")
        value: Valor da preferencia (ex: "pytest", "vscode", "python")
        confidence: Confianca de 0.0 a 1.0 (default: 0.5)
        source: Origem da observacao (ex: "manual", "detected", "claude.md")
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO preferences (key, value, confidence, source, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                confidence = MAX(preferences.confidence, excluded.confidence),
                times_observed = preferences.times_observed + 1,
                updated_at = CURRENT_TIMESTAMP
        ''', (key, value, confidence, source))


def get_preference(key: str) -> Optional[str]:
    """Busca valor de uma preferencia.

    Args:
        key: Chave da preferencia

    Returns:
        Valor da preferencia ou None se nao encontrada
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT value FROM preferences WHERE key = ?', (key,))
        row = c.fetchone()
        return row['value'] if row else None


def get_all_preferences(min_confidence: float = 0.3) -> Dict[str, str]:
    """Retorna todas as preferencias acima de uma confianca minima.

    Args:
        min_confidence: Confianca minima para incluir (default: 0.3)

    Returns:
        Dict mapeando key -> value, ordenado por times_observed
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT key, value FROM preferences
            WHERE confidence >= ?
            ORDER BY times_observed DESC
        ''', (min_confidence,))
        return {row['key']: row['value'] for row in c.fetchall()}
