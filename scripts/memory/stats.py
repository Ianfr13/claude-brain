#!/usr/bin/env python3
"""
Claude Brain - Stats and Export Module

Este modulo gerencia estatisticas e exportacao de contexto.

Funcoes principais:
- get_stats: Retorna estatisticas do banco
- export_context: Exporta contexto formatado para Claude

Relacionamentos:
- base.py: get_db, ALL_TABLES
- decisions.py: get_decisions
- learnings.py: get_all_learnings
- preferences.py: get_all_preferences
- entities.py: get_entity_graph
- __init__.py: re-exporta todas as funcoes publicas
"""

from typing import Optional, Dict, Any

from .base import get_db, ALL_TABLES
from .decisions import get_decisions
from .learnings import get_all_learnings
from .preferences import get_all_preferences
from .entities import get_entity_graph


def get_stats() -> Dict[str, Any]:
    """Retorna estatisticas do banco.

    Returns:
        Dict com:
        - Contagem de cada tabela (memories, decisions, learnings, etc)
        - top_preferences: 3 preferencias mais observadas
        - top_errors: 3 erros mais frequentes
    """
    with get_db() as conn:
        c = conn.cursor()

        stats = {}

        for table in ALL_TABLES:
            c.execute(f'SELECT COUNT(*) FROM {table}')
            stats[table] = c.fetchone()[0]

        # Preferencias mais observadas
        c.execute('SELECT key, times_observed FROM preferences ORDER BY times_observed DESC LIMIT 3')
        stats['top_preferences'] = [dict(row) for row in c.fetchall()]

        # Erros mais frequentes
        c.execute('SELECT error_type, frequency FROM learnings ORDER BY frequency DESC LIMIT 3')
        stats['top_errors'] = [dict(row) for row in c.fetchall()]

    return stats


def export_context(project: Optional[str] = None, include_learnings: bool = True) -> str:
    """Exporta contexto formatado para Claude.

    Gera um documento Markdown com informacoes relevantes do brain
    para incluir no contexto de uma conversa.

    Args:
        project: Filtrar por projeto especifico (opcional)
        include_learnings: Incluir erros a evitar (default: True)

    Returns:
        String Markdown formatada com preferencias, decisoes,
        learnings e grafo de entidades
    """
    output = ["# Contexto da Memoria\n"]

    # Preferencias
    prefs = get_all_preferences()
    if prefs:
        output.append("## Preferencias Conhecidas")
        for k, v in list(prefs.items())[:10]:
            output.append(f"- **{k}**: {v}")
        output.append("")

    # Decisoes recentes
    decisions = get_decisions(project, limit=5)
    if decisions:
        output.append("## Decisoes Recentes")
        for d in decisions:
            proj = f"[{d['project']}] " if d['project'] else ""
            output.append(f"- {proj}{d['decision']}")
            if d['reasoning']:
                output.append(f"  - Razao: {d['reasoning']}")
        output.append("")

    # Aprendizados (erros a evitar)
    if include_learnings:
        learnings = get_all_learnings(limit=5)
        if learnings:
            output.append("## Erros a Evitar")
            for l in learnings:
                output.append(f"- **{l['error_type']}**: {l['prevention'] or l['solution']}")
            output.append("")

    # Entidades do projeto
    if project:
        graph = get_entity_graph(project)
        if graph:
            output.append(f"## Contexto: {project}")
            if graph['entity'].get('description'):
                output.append(f"{graph['entity']['description']}\n")
            if graph['outgoing']:
                output.append("Tecnologias/Dependencias:")
                for r in graph['outgoing']:
                    output.append(f"- [{r['relation_type']}] {r['to_entity']}")
            output.append("")

    return "\n".join(output)
