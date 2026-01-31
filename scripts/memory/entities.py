#!/usr/bin/env python3
"""
Claude Brain - Entities Module

Este modulo gerencia entidades do knowledge graph (tabela 'entities').
Entidades sao nos do grafo (projetos, tecnologias, conceitos, etc).

Funcoes principais:
- save_entity: Salva ou atualiza uma entidade
- get_entity: Busca uma entidade por nome
- get_entity_graph: Retorna grafo completo de uma entidade
- get_related_entities: Busca entidades relacionadas com profundidade
- get_all_entities: Lista todas as entidades

Relacionamentos:
- base.py: get_db
- relations.py: usa entidades para criar relacoes
- __init__.py: re-exporta todas as funcoes publicas
"""

import json
from typing import Optional, List, Dict, Any

from .base import get_db


def save_entity(name: str, type: str, description: Optional[str] = None,
                properties: Optional[Dict[str, Any]] = None) -> int:
    """Salva ou atualiza uma entidade.

    Args:
        name: Nome unico da entidade (ex: "python", "claude-brain")
        type: Tipo da entidade (ex: "language", "project", "technology")
        description: Descricao textual (opcional)
        properties: Dict com propriedades extras (sera JSON)

    Returns:
        ID da entidade (novo ou atualizado via UPSERT)
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO entities (name, type, description, properties, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(name) DO UPDATE SET
                type = excluded.type,
                description = COALESCE(excluded.description, entities.description),
                properties = COALESCE(excluded.properties, entities.properties),
                updated_at = CURRENT_TIMESTAMP
        ''', (name, type, description, json.dumps(properties) if properties else None))
        return c.lastrowid


def get_entity(name: str) -> Optional[Dict[str, Any]]:
    """Busca uma entidade por nome.

    Args:
        name: Nome da entidade

    Returns:
        Dict com campos da entidade ou None se nao encontrada
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM entities WHERE name = ?', (name,))
        row = c.fetchone()
        return dict(row) if row else None


def get_entity_graph(name: str) -> Optional[Dict[str, Any]]:
    """Retorna grafo completo de uma entidade.

    Inclui a entidade central e todas as relacoes de entrada/saida.

    Args:
        name: Nome da entidade central

    Returns:
        Dict com:
        - entity: dados da entidade
        - outgoing: relacoes de saida (esta entidade -> outras)
        - incoming: relacoes de entrada (outras -> esta entidade)
        Ou None se entidade nao existir
    """
    entity = get_entity(name)
    if not entity:
        return None

    with get_db() as conn:
        c = conn.cursor()

        # Relacoes de saida
        c.execute('''
            SELECT r.*, e.type as to_type, e.description as to_desc
            FROM relations r
            LEFT JOIN entities e ON r.to_entity = e.name
            WHERE r.from_entity = ?
        ''', (name,))
        outgoing = [dict(row) for row in c.fetchall()]

        # Relacoes de entrada
        c.execute('''
            SELECT r.*, e.type as from_type, e.description as from_desc
            FROM relations r
            LEFT JOIN entities e ON r.from_entity = e.name
            WHERE r.to_entity = ?
        ''', (name,))
        incoming = [dict(row) for row in c.fetchall()]

    return {
        "entity": entity,
        "outgoing": outgoing,
        "incoming": incoming
    }


def get_related_entities(name: str, relation_type: Optional[str] = None, depth: int = 1) -> List[Dict[str, Any]]:
    """Busca entidades relacionadas (com profundidade).

    Faz travessia do grafo a partir da entidade inicial.
    Usa conexao unica para evitar N+1 queries.

    Args:
        name: Nome da entidade inicial
        relation_type: Filtrar por tipo de relacao (opcional)
        depth: Profundidade maxima da travessia (default: 1, max: 10)

    Returns:
        Lista de dicts com:
        - entity: nome da entidade relacionada
        - relation: tipo da relacao
        - depth: profundidade em que foi encontrada
    """
    # Limitar profundidade maxima para evitar stack overflow
    MAX_DEPTH = 10
    depth = min(depth, MAX_DEPTH)

    visited = set()
    results = []

    # Refactoring: Conexao unica para toda a travessia (evita N+1)
    with get_db() as conn:
        c = conn.cursor()

        def _traverse(entity_name: str, current_depth: int):
            if current_depth > depth or entity_name in visited:
                return
            visited.add(entity_name)

            sql = 'SELECT to_entity, relation_type FROM relations WHERE from_entity = ?'
            params = [entity_name]

            if relation_type:
                sql += ' AND relation_type = ?'
                params.append(relation_type)

            c.execute(sql, params)

            for row in c.fetchall():
                results.append({
                    "entity": row['to_entity'],
                    "relation": row['relation_type'],
                    "depth": current_depth
                })
                _traverse(row['to_entity'], current_depth + 1)

        _traverse(name, 1)

    return results


def get_all_entities(type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Lista todas as entidades.

    Args:
        type: Filtrar por tipo (opcional)
        limit: Numero maximo de resultados (default: 100)

    Returns:
        Lista de dicts com campos da entidade (properties deserializado)
    """
    with get_db() as conn:
        c = conn.cursor()
        if type:
            c.execute('''
                SELECT * FROM entities
                WHERE type = ?
                ORDER BY updated_at DESC LIMIT ?
            ''', (type, limit))
        else:
            c.execute('''
                SELECT * FROM entities
                ORDER BY updated_at DESC LIMIT ?
            ''', (limit,))

        entities = []
        for row in c.fetchall():
            entity = dict(row)
            if entity.get('properties'):
                try:
                    entity['properties'] = json.loads(entity['properties'])
                except (json.JSONDecodeError, TypeError):
                    pass
            entities.append(entity)
        return entities
