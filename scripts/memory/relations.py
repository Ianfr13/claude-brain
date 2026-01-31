#!/usr/bin/env python3
"""
Claude Brain - Relations Module

Este modulo gerencia relacoes entre entidades (tabela 'relations').
Relacoes sao as arestas do knowledge graph.

Funcoes principais:
- save_relation: Salva uma relacao entre entidades (cria entidades se necessario)

Relacionamentos:
- base.py: get_db
- entities.py: save_entity (para criar entidades automaticamente)
- __init__.py: re-exporta save_relation
"""

import json
from typing import Optional, Dict, Any

from .base import get_db
from .entities import save_entity


def save_relation(from_entity: str, to_entity: str, relation_type: str,
                  weight: float = 1.0, properties: Optional[Dict[str, Any]] = None) -> None:
    """Salva uma relacao entre entidades.

    Se as entidades nao existirem, sao criadas automaticamente com type="unknown".

    Args:
        from_entity: Nome da entidade de origem
        to_entity: Nome da entidade de destino
        relation_type: Tipo da relacao (ex: "uses", "depends_on", "created_by")
        weight: Peso da relacao, 0.0 a 1.0 (default: 1.0)
        properties: Dict com propriedades extras da relacao (sera JSON)

    Note:
        Usa UPSERT - se a relacao ja existir (mesmo from/to/type),
        atualiza weight e properties.
    """
    # Garante que entidades existem
    with get_db() as conn:
        c = conn.cursor()

        c.execute('SELECT 1 FROM entities WHERE name = ?', (from_entity,))
        if not c.fetchone():
            save_entity(from_entity, "unknown")

        c.execute('SELECT 1 FROM entities WHERE name = ?', (to_entity,))
        if not c.fetchone():
            save_entity(to_entity, "unknown")

        c.execute('''
            INSERT INTO relations (from_entity, to_entity, relation_type, weight, properties)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(from_entity, to_entity, relation_type) DO UPDATE SET
                weight = excluded.weight,
                properties = excluded.properties
        ''', (from_entity, to_entity, relation_type, weight,
              json.dumps(properties) if properties else None))
