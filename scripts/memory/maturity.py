#!/usr/bin/env python3
"""
Claude Brain - Maturity Module

Este modulo gerencia o sistema de maturacao de conhecimento.
Conhecimentos (decisions, learnings) passam por estados:
  hypothesis (0.3) -> testing (0.5) -> confirmed (0.8)
  ou -> deprecated (0.1) -> contradicted (0.0)

Funcoes principais:
- record_usage: Registra uso e atualiza confianca
- confirm_knowledge: Confirma explicitamente um conhecimento
- contradict_knowledge: Marca conhecimento como incorreto
- supersede_knowledge: Substitui conhecimento antigo por novo
- get_knowledge_by_maturity: Busca por status de maturidade
- get_hypotheses: Lista conhecimentos nao confirmados
- get_contradicted: Lista conhecimentos contraditos

Relacionamentos:
- base.py: get_db, ALLOWED_TABLES, MATURITY_STATES
- decisions.py: save_decision (para supersede)
- learnings.py: save_learning (para supersede)
- memories.py: save_memory (para supersede)
- __init__.py: re-exporta todas as funcoes publicas
"""

import logging
from typing import Optional, List, Dict, Any

from .base import get_db, ALLOWED_TABLES, MATURITY_STATES

logger = logging.getLogger(__name__)


def record_usage(table: str, record_id: int, was_useful: bool = True) -> float:
    """
    Registra uso de um conhecimento e atualiza confianca.

    Args:
        table: Nome da tabela ('decisions', 'learnings', 'memories')
        record_id: ID do registro
        was_useful: Se o conhecimento foi util neste uso

    Returns:
        Novo score de confianca (0.0 a 1.0)

    Raises:
        ValueError: Se tabela nao for permitida
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela invalida: {table}")

    with get_db() as conn:
        c = conn.cursor()

        # Incrementa uso
        c.execute(f'''
            UPDATE {table} SET
                times_used = times_used + 1,
                times_confirmed = times_confirmed + ?
            WHERE id = ?
        ''', (1 if was_useful else 0, record_id))

        # Recalcula confianca
        c.execute(f'''
            SELECT times_used, times_confirmed, times_contradicted, maturity_status
            FROM {table} WHERE id = ?
        ''', (record_id,))
        row = c.fetchone()

        if not row:
            return 0.5

        used = row['times_used'] or 1
        confirmed = row['times_confirmed'] or 0
        contradicted = row['times_contradicted'] or 0
        status = row['maturity_status'] or 'hypothesis'

        # Calcula score baseado em confirmacoes vs contradicoes
        if used > 0:
            confirm_rate = confirmed / used
            contradict_rate = contradicted / used if used > 0 else 0
            new_score = min(0.95, max(0.05, 0.5 + (confirm_rate * 0.4) - (contradict_rate * 0.5)))
        else:
            new_score = MATURITY_STATES.get(status, 0.5)

        # Atualiza status baseado no score e uso
        new_status = status
        if used >= 3:  # Precisa de pelo menos 3 usos para mudar status
            if new_score >= 0.7:
                new_status = "confirmed"
            elif new_score <= 0.2:
                new_status = "deprecated"
            elif status == "hypothesis":
                new_status = "testing"

        c.execute(f'''
            UPDATE {table} SET confidence_score = ?, maturity_status = ?
            WHERE id = ?
        ''', (new_score, new_status, record_id))

        return new_score


def contradict_knowledge(table: str, record_id: int, reason: Optional[str] = None,
                         replacement_id: Optional[int] = None) -> None:
    """
    Marca um conhecimento como contradito/incorreto.

    Args:
        table: Nome da tabela ('decisions', 'learnings', 'memories')
        record_id: ID do registro
        reason: Motivo da contradicao (opcional, nao usado atualmente)
        replacement_id: ID do conhecimento que substitui este (opcional)

    Raises:
        ValueError: Se tabela nao for permitida
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela invalida: {table}")

    with get_db() as conn:
        c = conn.cursor()

        c.execute(f'''
            UPDATE {table} SET
                times_contradicted = times_contradicted + 1,
                maturity_status = CASE
                    WHEN times_contradicted >= 2 THEN 'contradicted'
                    ELSE 'deprecated'
                END,
                confidence_score = CASE
                    WHEN times_contradicted >= 2 THEN 0.0
                    ELSE confidence_score * 0.5
                END,
                superseded_by = COALESCE(?, superseded_by)
            WHERE id = ?
        ''', (replacement_id, record_id))


def confirm_knowledge(table: str, record_id: int) -> float:
    """
    Confirma explicitamente que um conhecimento esta correto.

    Wrapper para record_usage com was_useful=True.

    Args:
        table: Nome da tabela ('decisions', 'learnings', 'memories')
        record_id: ID do registro

    Returns:
        Novo score de confianca

    Raises:
        ValueError: Se tabela nao for permitida
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela invalida: {table}")

    return record_usage(table, record_id, was_useful=True)


def get_knowledge_by_maturity(table: str, status: Optional[str] = None,
                               min_confidence: float = 0.0,
                               limit: int = 20) -> List[Dict[str, Any]]:
    """
    Busca conhecimentos por status de maturidade.

    Args:
        table: Nome da tabela ('decisions', 'learnings', 'memories')
        status: Filtrar por status especifico (opcional)
        min_confidence: Confianca minima (default: 0.0)
        limit: Numero maximo de resultados (default: 20)

    Returns:
        Lista de dicts com campos do registro + status_icon

    Raises:
        ValueError: Se tabela nao for permitida
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela invalida: {table}")

    with get_db() as conn:
        c = conn.cursor()

        sql = f'''
            SELECT *,
                CASE maturity_status
                    WHEN 'confirmed' THEN '✓'
                    WHEN 'testing' THEN '?'
                    WHEN 'hypothesis' THEN '○'
                    WHEN 'deprecated' THEN '✗'
                    WHEN 'contradicted' THEN '⊗'
                    ELSE '?'
                END as status_icon
            FROM {table}
            WHERE confidence_score >= ?
        '''
        params: List[Any] = [min_confidence]

        if status:
            sql += ' AND maturity_status = ?'
            params.append(status)

        sql += ' ORDER BY confidence_score DESC, times_used DESC LIMIT ?'
        params.append(limit)

        c.execute(sql, params)
        return [dict(row) for row in c.fetchall()]


def get_hypotheses(table: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retorna conhecimentos que ainda sao hipoteses (nao confirmados).
    Util para revisao periodica.

    Args:
        table: Filtrar por tabela especifica (opcional)
        limit: Numero maximo de resultados (default: 10)

    Returns:
        Lista de dicts com source_table, id, summary, confidence_score, etc

    Raises:
        ValueError: Se tabela especificada nao for permitida
    """
    if table is not None and table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela invalida: {table}")

    results = []

    # Queries especificas para cada tabela
    queries = {
        'decisions': '''
            SELECT 'decisions' as source_table, id, decision as summary,
                confidence_score, maturity_status, times_used, created_at
            FROM decisions
            WHERE maturity_status IN ('hypothesis', 'testing')
        ''',
        'learnings': '''
            SELECT 'learnings' as source_table, id, error_type || ': ' || solution as summary,
                confidence_score, maturity_status, times_used, created_at
            FROM learnings
            WHERE maturity_status IN ('hypothesis', 'testing')
        ''',
        # NOTA: memories nao tem colunas de maturidade, removido do query
    }

    # Database optimization: memories nao tem colunas de maturidade
    tables_to_query = [table] if table else ['decisions', 'learnings']

    with get_db() as conn:
        c = conn.cursor()

        for t in tables_to_query:
            if t in queries:
                try:
                    c.execute(queries[t] + ' ORDER BY created_at DESC LIMIT ?', (limit,))
                    results.extend([dict(row) for row in c.fetchall()])
                except Exception as e:
                    logger.warning(f"Erro ao buscar hipoteses em {t}: {e}")
                    continue

    return sorted(results, key=lambda x: x.get('confidence_score', 0))[:limit]


def get_contradicted(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retorna conhecimentos que foram contraditos.
    Util para auditoria e limpeza.

    Args:
        limit: Numero maximo de resultados (default: 10)

    Returns:
        Lista de dicts com source_table, id, summary, times_contradicted, etc
    """
    results = []

    with get_db() as conn:
        c = conn.cursor()

        # Query especifica para cada tabela
        queries = {
            'decisions': '''
                SELECT 'decisions' as source_table, id, decision as summary,
                    confidence_score, times_contradicted, superseded_by
                FROM decisions
                WHERE maturity_status IN ('deprecated', 'contradicted')
            ''',
            'learnings': '''
                SELECT 'learnings' as source_table, id, error_type || ': ' || solution as summary,
                    confidence_score, times_contradicted, superseded_by
                FROM learnings
                WHERE maturity_status IN ('deprecated', 'contradicted')
            ''',
            # NOTA: memories nao tem colunas de maturidade, removido
        }

        for t, query in queries.items():
            try:
                c.execute(query + ' ORDER BY times_contradicted DESC LIMIT ?', (limit,))
                results.extend([dict(row) for row in c.fetchall()])
            except Exception as e:
                logger.warning(f"Erro ao buscar contradicted em {t}: {e}")
                continue

    return results[:limit]


def supersede_knowledge(table: str, old_id: int, new_content: str,
                        reason: Optional[str] = None, **kwargs: Any) -> int:
    """
    Substitui um conhecimento antigo por um novo.
    Marca o antigo como deprecated e cria o novo.

    Args:
        table: Nome da tabela ('decisions', 'learnings', 'memories')
        old_id: ID do conhecimento a ser substituido
        new_content: Conteudo do novo conhecimento
        reason: Motivo da substituicao (opcional)
        **kwargs: Argumentos extras para a funcao de criacao

    Returns:
        ID do novo conhecimento

    Raises:
        ValueError: Se tabela nao for permitida ou desconhecida
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela invalida: {table}")

    # Import local para evitar circular imports
    from .decisions import save_decision
    from .learnings import save_learning
    from .memories import save_memory

    # Cria o novo conhecimento
    if table == 'decisions':
        new_id = save_decision(new_content, reasoning=reason, **kwargs)
    elif table == 'learnings':
        new_id = save_learning(new_content, **kwargs)
    elif table == 'memories':
        new_id = save_memory('updated', new_content, **kwargs)
    else:
        raise ValueError(f"Tabela desconhecida: {table}")

    # Marca o antigo como superseded
    contradict_knowledge(table, old_id, reason=reason, replacement_id=new_id)

    return new_id
