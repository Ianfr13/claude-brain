#!/usr/bin/env python3
"""
Claude Brain - Memory Package

Este pacote modulariza o sistema de memoria persistente do Claude Brain.
Todas as funcoes publicas sao re-exportadas aqui para manter compatibilidade
com o codigo existente que faz:

    from scripts.memory_store import save_memory, search_memories, ...

Apos a migracao, pode-se usar:

    from scripts.memory import save_memory, search_memories, ...

Estrutura dos modulos:
- base.py: Conexao (get_db), constantes, utilitarios, init_db
- memories.py: save_memory, search_memories
- decisions.py: save_decision, get_decisions, update_decision_outcome
- learnings.py: save_learning, find_solution, get_all_learnings
- entities.py: save_entity, get_entity, get_entity_graph, get_related_entities
- relations.py: save_relation
- patterns.py: save_pattern, get_pattern, increment_pattern_usage
- preferences.py: save_preference, get_preference, get_all_preferences
- sessions.py: save_session, get_recent_sessions
- maturity.py: record_usage, confirm_knowledge, contradict_knowledge, etc
- stats.py: get_stats, export_context
- delete.py: delete_record, delete_by_search

Total: ~50 funcoes publicas organizadas em 11 modulos
"""

# ============ BASE ============
from .base import (
    # Conexao
    get_db,
    # Constantes
    DB_PATH,
    ALLOWED_TABLES,
    ALL_TABLES,
    MATURITY_STATES,
    # Inicializacao
    init_db,
    migrate_db,
    # Utilitarios internos (para uso em outros modulos)
    _hash,
    _escape_like,
    _similarity,
)

# ============ MEMORIES ============
from .memories import (
    save_memory,
    search_memories,
)

# ============ DECISIONS ============
from .decisions import (
    save_decision,
    get_decisions,
    update_decision_outcome,
)

# ============ LEARNINGS ============
from .learnings import (
    save_learning,
    find_solution,
    get_all_learnings,
)

# ============ ENTITIES ============
from .entities import (
    save_entity,
    get_entity,
    get_entity_graph,
    get_related_entities,
    get_all_entities,
)

# ============ RELATIONS ============
from .relations import (
    save_relation,
)

# ============ PATTERNS ============
from .patterns import (
    save_pattern,
    get_pattern,
    increment_pattern_usage,
    get_all_patterns,
)

# ============ PREFERENCES ============
from .preferences import (
    save_preference,
    get_preference,
    get_all_preferences,
)

# ============ SESSIONS ============
from .sessions import (
    save_session,
    get_recent_sessions,
)

# ============ MATURITY ============
from .maturity import (
    record_usage,
    contradict_knowledge,
    confirm_knowledge,
    get_knowledge_by_maturity,
    get_hypotheses,
    get_contradicted,
    supersede_knowledge,
)

# ============ STATS & EXPORT ============
from .stats import (
    get_stats,
    export_context,
)

# ============ DELETE ============
from .delete import (
    delete_record,
    delete_by_search,
)


# ============ EXPORTS ============
# Lista completa para import * (nao recomendado, mas mantido para compatibilidade)
__all__ = [
    # Base
    'get_db', 'DB_PATH', 'ALLOWED_TABLES', 'ALL_TABLES', 'MATURITY_STATES',
    'init_db', 'migrate_db',
    # Memories
    'save_memory', 'search_memories',
    # Decisions
    'save_decision', 'get_decisions', 'update_decision_outcome',
    # Learnings
    'save_learning', 'find_solution', 'get_all_learnings',
    # Entities
    'save_entity', 'get_entity', 'get_entity_graph', 'get_related_entities', 'get_all_entities',
    # Relations
    'save_relation',
    # Patterns
    'save_pattern', 'get_pattern', 'increment_pattern_usage', 'get_all_patterns',
    # Preferences
    'save_preference', 'get_preference', 'get_all_preferences',
    # Sessions
    'save_session', 'get_recent_sessions',
    # Maturity
    'record_usage', 'contradict_knowledge', 'confirm_knowledge',
    'get_knowledge_by_maturity', 'get_hypotheses', 'get_contradicted', 'supersede_knowledge',
    # Stats & Export
    'get_stats', 'export_context',
    # Delete
    'delete_record', 'delete_by_search',
]


# ============ AUTO-INIT ============
# Inicializa o banco ao importar (comportamento original de memory_store.py)
init_db()
