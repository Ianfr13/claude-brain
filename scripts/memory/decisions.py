#!/usr/bin/env python3
"""
Claude Brain - Decisions Module

Este modulo gerencia decisoes arquiteturais (tabela 'decisions').
Decisoes tem sistema de maturidade: hypothesis -> testing -> confirmed.

Funcoes principais:
- save_decision: Salva uma decisao arquitetural
- get_decisions: Lista decisoes filtradas por projeto/status
- update_decision_outcome: Atualiza resultado de uma decisao

Relacionamentos:
- base.py: get_db
- maturity.py: funcoes de maturacao (confirm, contradict, supersede)
- __init__.py: re-exporta todas as funcoes publicas
"""

from typing import Optional, List, Dict, Any

from .base import get_db


def save_decision(decision: str, reasoning: Optional[str] = None, project: Optional[str] = None,
                  context: Optional[str] = None, alternatives: Optional[str] = None,
                  is_established: bool = False) -> int:
    """Salva uma decisao arquitetural no banco.

    Args:
        decision: Texto descrevendo a decisao tomada
        reasoning: Justificativa/motivo da decisao (opcional)
        project: Nome do projeto relacionado (opcional)
        context: Contexto em que a decisao foi tomada (opcional)
        alternatives: Alternativas consideradas (opcional)
        is_established: Se True, e conhecimento estabelecido (best practice)
                       e comeca como 'confirmed' com confianca 0.85.
                       Se False (padrao), comeca como 'hypothesis' com confianca 0.5.

    Returns:
        ID da decisao criada
    """
    status = "confirmed" if is_established else "hypothesis"
    confidence = 0.85 if is_established else 0.5

    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO decisions (project, context, decision, reasoning, alternatives,
                                   maturity_status, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (project, context, decision, reasoning, alternatives, status, confidence))
        return c.lastrowid


def update_decision_outcome(decision_id: int, outcome: str, status: Optional[str] = None) -> None:
    """Atualiza resultado de uma decisao.

    Args:
        decision_id: ID da decisao
        outcome: Texto descrevendo o resultado
        status: Novo status opcional ('active', 'deprecated', etc)
    """
    with get_db() as conn:
        c = conn.cursor()
        if status:
            c.execute('''
                UPDATE decisions SET outcome = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (outcome, status, decision_id))
        else:
            c.execute('''
                UPDATE decisions SET outcome = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (outcome, decision_id))


def get_decisions(project: Optional[str] = None, status: str = 'active', limit: int = 10) -> List[Dict[str, Any]]:
    """Busca decisoes filtradas por projeto e status.

    Args:
        project: Filtrar por projeto (opcional)
        status: Filtrar por status (default: 'active')
        limit: Numero maximo de resultados (default: 10)

    Returns:
        Lista de dicts com os campos da decisao
    """
    with get_db() as conn:
        c = conn.cursor()

        if project:
            c.execute('''
                SELECT * FROM decisions WHERE project = ? AND status = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (project, status, limit))
        else:
            c.execute('''
                SELECT * FROM decisions WHERE status = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (status, limit))

        return [dict(row) for row in c.fetchall()]
