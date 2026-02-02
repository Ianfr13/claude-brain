#!/usr/bin/env python3
"""
Claude Brain CLI - Package

Este pacote contem os modulos do CLI do Claude Brain:
- base: Classes e funcoes base (Colors, print_*, etc)
- memory: Comandos de memoria (remember, recall)
- decisions: Comandos de decisoes (decide, decisions, confirm, contradict)
- learnings: Comandos de learnings (learn, learnings, solve)
- graph: Comandos do knowledge graph (entity, relate, graph)
- rag: Comandos de RAG (index, search, context, ask, related)
- preferences: Comandos de preferencias (prefer, prefs, pattern, snippet)
- maturity: Comandos de maturidade (hypotheses, supersede, maturity)
- utils: Comandos utilitarios (delete, forget, export, stats, help, etc)

Exports principais:
- main: Funcao principal do CLI
- Colors: Classe de cores ANSI
- Todas as funcoes cmd_* dos submodulos
"""

# Base - Classes e funcoes utilitarias
from .base import (
    Colors, c,
    print_header, print_success, print_error, print_info,
    ALLOWED_INDEX_PATHS, is_path_allowed
)

# Memory - Comandos de memoria
from .memory import cmd_remember, cmd_recall

# Decisions - Comandos de decisoes
from .decisions import cmd_decide, cmd_decisions, cmd_confirm, cmd_contradict

# Learnings - Comandos de learnings
from .learnings import cmd_learn, cmd_learnings, cmd_solve

# Graph - Comandos do knowledge graph
from .graph import cmd_entity, cmd_relate, cmd_graph

# RAG - Comandos de busca semantica
from .rag import cmd_index, cmd_search, cmd_context, cmd_ask, cmd_related

# Preferences - Comandos de preferencias e padroes
from .preferences import cmd_prefer, cmd_prefs, cmd_pattern, cmd_snippet

# Maturity - Sistema de maturacao
from .maturity import cmd_hypotheses, cmd_supersede, cmd_maturity

# Utils - Comandos utilitarios
from .utils import (
    cmd_delete, cmd_forget, cmd_export, cmd_stats, cmd_help,
    cmd_useful, cmd_useless, cmd_dashboard, cmd_extract
)

# Workflow - Sessoes de trabalho com contexto
from .workflow import cmd_workflow

__all__ = [
    # Base
    'Colors', 'c',
    'print_header', 'print_success', 'print_error', 'print_info',
    'ALLOWED_INDEX_PATHS', 'is_path_allowed',
    # Memory
    'cmd_remember', 'cmd_recall',
    # Decisions
    'cmd_decide', 'cmd_decisions', 'cmd_confirm', 'cmd_contradict',
    # Learnings
    'cmd_learn', 'cmd_learnings', 'cmd_solve',
    # Graph
    'cmd_entity', 'cmd_relate', 'cmd_graph',
    # RAG
    'cmd_index', 'cmd_search', 'cmd_context', 'cmd_ask', 'cmd_related',
    # Preferences
    'cmd_prefer', 'cmd_prefs', 'cmd_pattern', 'cmd_snippet',
    # Maturity
    'cmd_hypotheses', 'cmd_supersede', 'cmd_maturity',
    # Utils
    'cmd_delete', 'cmd_forget', 'cmd_export', 'cmd_stats', 'cmd_help',
    'cmd_useful', 'cmd_useless', 'cmd_dashboard', 'cmd_extract',
    # Workflow
    'cmd_workflow',
]
