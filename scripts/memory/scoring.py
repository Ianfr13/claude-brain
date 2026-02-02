#!/usr/bin/env python3
"""
Claude Brain - Scoring and Conflict Resolution

Sistema inteligente de ranking de resultados e detecção de conflitos.

Implementa:
1. Score composto (5 fatores): Especificidade + Recência + Confiança + Uso + Validação
2. Ranking automático de resultados
3. Detecção de conflitos (resultados com scores próximos)
4. Decaimento por desuso (diminui confiança se não usado)
5. Boost por confirmação (aumenta confiança se confirmado)

Funções principais:
- calculate_relevance_score: Score composto para um resultado
- rank_results: Ordena resultados por score
- detect_conflicts: Encontra pares de resultados conflitantes
- decay_unused: Aplica decaimento por desuso
- boost_confirmed: Aumenta confiança quando confirmado

Fórmula de Score:
    SCORE = (E × 0.25) + (R × 0.20) + (C × 0.25) + (U × 0.15) + (V × 0.15)

    E = Especificidade (0.0 - 1.0)
    R = Recência (0.0 - 1.0)
    C = Confiança (confidence_score existente)
    U = Uso (baseado em times_used)
    V = Validação (confirmed / (confirmed + contradicted + 1))
"""

from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
from .base import get_db
import json


def calculate_specificity_score(record: Dict[str, Any], current_project: Optional[str] = None) -> float:
    """
    Calcula score de especificidade (0.0 - 1.0).

    1.0: Projeto exato + contexto específico
    0.8: Projeto exato, sem contexto
    0.5: Conhecimento geral (sem projeto)
    0.3: Outro projeto
    """
    project = record.get('project')

    if current_project:
        if project == current_project:
            # Projeto exato
            has_context = bool(record.get('context'))
            return 1.0 if has_context else 0.8
        elif project is None:
            # Conhecimento geral
            return 0.5
        else:
            # Outro projeto
            return 0.3
    else:
        # Sem projeto especificado
        if project is None:
            return 0.5
        else:
            return 0.3


def calculate_recency_score(record: Dict[str, Any]) -> float:
    """
    Calcula score de recência (0.0 - 1.0).

    1.0: Última semana
    0.8: Último mês
    0.6: Últimos 3 meses
    0.4: Últimos 6 meses
    0.2: Mais antigo
    """
    # Tenta diferentes campos de timestamp
    timestamp_str = (
        record.get('last_accessed') or
        record.get('last_occurred') or
        record.get('updated_at') or
        record.get('created_at')
    )

    if not timestamp_str:
        return 0.5  # Padrão se não tiver timestamp

    try:
        # Parse timestamp (formato SQLite: YYYY-MM-DD HH:MM:SS)
        record_date = datetime.strptime(timestamp_str[:19], '%Y-%m-%d %H:%M:%S')
        days_old = (datetime.now() - record_date).days

        if days_old <= 7:
            return 1.0
        elif days_old <= 30:
            return 0.8
        elif days_old <= 90:
            return 0.6
        elif days_old <= 180:
            return 0.4
        else:
            return 0.2
    except (ValueError, TypeError):
        return 0.5


def calculate_usage_score(record: Dict[str, Any]) -> float:
    """
    Calcula score de uso (0.0 - 1.0).

    Baseado em:
    - access_count (para memories)
    - frequency (para learnings)
    - times_used (para maturity)

    Normaliza: quantos mais acessos, maior o score (até 1.0)
    """
    # Tenta diferentes campos de contagem
    count = (
        record.get('access_count') or
        record.get('frequency') or
        record.get('times_used') or
        0
    )

    # Normaliza: cada 10 acessos = +0.1, máximo 1.0
    return min(count / 10.0, 1.0)


def calculate_validation_score(record: Dict[str, Any]) -> float:
    """
    Calcula score de validação (0.0 - 1.0).

    Baseado em maturity_status:
    - confirmed: 1.0 (conhecimento validado)
    - hypothesis: 0.4 (ainda sendo testado)
    - testing: 0.6 (em teste)
    - deprecated: 0.2 (não usa mais)
    - contradicted: 0.0 (está errado)

    Ou baseado em times_confirmed vs times_contradicted.
    """
    maturity_status = record.get('maturity_status')

    status_scores = {
        'confirmed': 1.0,
        'testing': 0.6,
        'hypothesis': 0.4,
        'deprecated': 0.2,
        'contradicted': 0.0,
    }

    if maturity_status in status_scores:
        return status_scores[maturity_status]

    # Fallback: calcula baseado em confirmação vs contradição
    times_confirmed = record.get('times_confirmed', 0) or 0
    times_contradicted = record.get('times_contradicted', 0) or 0

    if times_confirmed + times_contradicted == 0:
        return 0.5  # Sem validação ainda

    ratio = times_confirmed / (times_confirmed + times_contradicted + 1)
    return ratio


def calculate_relevance_score(
    record: Dict[str, Any],
    query: str = "",
    current_project: Optional[str] = None
) -> float:
    """
    Calcula score composto (0.0 - 1.0) para um resultado.

    SCORE = (E × 0.25) + (R × 0.20) + (C × 0.25) + (U × 0.15) + (V × 0.15)

    Args:
        record: Dicionário com campos de resultado (decision, learning, memory, etc)
        query: Query de busca (para contexto)
        current_project: Projeto atual para calcular especificidade

    Returns:
        Score composto 0.0 - 1.0
    """
    E = calculate_specificity_score(record, current_project)
    R = calculate_recency_score(record)
    C = record.get('confidence_score', 0.5) or 0.5
    U = calculate_usage_score(record)
    V = calculate_validation_score(record)

    # Clamp para 0.0 - 1.0
    score = (E * 0.25) + (R * 0.20) + (C * 0.25) + (U * 0.15) + (V * 0.15)
    return max(0.0, min(1.0, score))


def rank_results(
    results: List[Dict[str, Any]],
    query: str = "",
    project: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Ordena resultados por score composto, adicionando 'relevance_score' a cada um.

    Args:
        results: Lista de resultados (decisions, learnings, memories, etc)
        query: Query de busca
        project: Projeto atual

    Returns:
        Lista ordenada por relevance_score DESC, com campo 'relevance_score' adicionado
    """
    # Calcula score para cada resultado
    for record in results:
        record['relevance_score'] = calculate_relevance_score(record, query, project)

    # Ordena por score DESC
    return sorted(results, key=lambda r: r['relevance_score'], reverse=True)


def detect_conflicts(
    ranked_results: List[Dict[str, Any]],
    threshold: float = 0.10
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Detecta pares de resultados conflitantes (scores próximos demais).

    Conflito = quando dois resultados têm scores muito próximos (< threshold),
    indicando que a busca não foi conclusiva e há ambiguidade.

    Args:
        ranked_results: Resultados já ranked com 'relevance_score'
        threshold: Diferença máxima para considerar conflito (default: 0.10)

    Returns:
        Lista de tuplas (record1, record2) que conflitam
    """
    conflicts = []

    for i in range(len(ranked_results) - 1):
        r1 = ranked_results[i]
        r2 = ranked_results[i + 1]

        score1 = r1.get('relevance_score', 0)
        score2 = r2.get('relevance_score', 0)

        diff = abs(score1 - score2)

        # Se scores são muito próximos, é conflito
        if diff < threshold:
            conflicts.append((r1, r2))

    return conflicts


def decay_unused(record_id: int, table: str) -> None:
    """
    Aplica decaimento por desuso: reduz confidence_score.

    Utilizado quando um resultado foi retornado mas o usuário não o utilizou.
    Decai em 0.01 (1%) a cada vez.

    Args:
        record_id: ID do record
        table: Nome da tabela ('decisions', 'learnings', 'memories')
    """
    with get_db() as conn:
        c = conn.cursor()

        # Valida table
        valid_tables = ['decisions', 'learnings', 'memories']
        if table not in valid_tables:
            raise ValueError(f"Table must be one of {valid_tables}")

        # Reduz confidence (mínimo 0.0)
        c.execute(f'''
            UPDATE {table}
            SET confidence_score = MAX(0.0, COALESCE(confidence_score, 0.5) - 0.01),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (record_id,))


def boost_confirmed(record_id: int, table: str) -> None:
    """
    Aumenta confiança quando resultado é confirmado pelo usuário.

    Implementado em 'brain useful' e 'brain confirm'.

    Args:
        record_id: ID do record
        table: Nome da tabela ('decisions', 'learnings', 'memories')
    """
    with get_db() as conn:
        c = conn.cursor()

        # Valida table
        valid_tables = ['decisions', 'learnings', 'memories']
        if table not in valid_tables:
            raise ValueError(f"Table must be one of {valid_tables}")

        # Aumenta confidence e times_confirmed (mínimo 1.0)
        c.execute(f'''
            UPDATE {table}
            SET confidence_score = MIN(1.0, COALESCE(confidence_score, 0.5) + 0.05),
                times_confirmed = COALESCE(times_confirmed, 0) + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (record_id,))


def get_decision_score_components(record: Dict[str, Any], project: Optional[str] = None) -> Dict[str, float]:
    """
    Retorna breakdown dos componentes de score para debug/display.

    Útil para entender por que um resultado foi rankeado dessa forma.

    Args:
        record: Record para análise
        project: Projeto atual

    Returns:
        Dict com E, R, C, U, V, score_total
    """
    E = calculate_specificity_score(record, project)
    R = calculate_recency_score(record)
    C = record.get('confidence_score', 0.5) or 0.5
    U = calculate_usage_score(record)
    V = calculate_validation_score(record)

    score_total = (E * 0.25) + (R * 0.20) + (C * 0.25) + (U * 0.15) + (V * 0.15)
    score_total = max(0.0, min(1.0, score_total))

    return {
        'specificity': E,       # 0.25x
        'recency': R,           # 0.20x
        'confidence': C,        # 0.25x
        'usage': U,             # 0.15x
        'validation': V,        # 0.15x
        'score_total': score_total,
        'weighted': {
            'specificity': E * 0.25,
            'recency': R * 0.20,
            'confidence': C * 0.25,
            'usage': U * 0.15,
            'validation': V * 0.15,
        }
    }
