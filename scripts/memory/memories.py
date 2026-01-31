#!/usr/bin/env python3
"""
Claude Brain - Memories Module

Este modulo gerencia memorias gerais (tabela 'memories').
Memorias sao informacoes textuais com categoria, importancia e embeddings.

Funcoes principais:
- save_memory: Salva uma memoria (evita duplicatas via hash)
- search_memories: Busca memorias por criterios combinados

Relacionamentos:
- base.py: get_db, _hash, _escape_like
- __init__.py: re-exporta save_memory, search_memories
"""

import json
from typing import Optional, List, Dict, Any

from .base import get_db, _hash, _escape_like


def save_memory(memory_type: str, content: str, category: Optional[str] = None,
                metadata: Optional[Dict[str, Any]] = None, importance: int = 5) -> int:
    """Salva uma memoria no banco, evitando duplicatas.

    Se o conteudo ja existir, incrementa o contador de acesso e retorna o ID existente.

    Args:
        memory_type: Tipo da memoria (general, session, extracted, etc)
        content: Conteudo textual da memoria
        category: Categoria opcional para agrupamento
        metadata: Dicionario com metadados extras (sera serializado como JSON)
        importance: Nivel de importancia de 1-10 (default: 5)

    Returns:
        ID da memoria (nova ou existente se duplicata)
    """
    content_hash = _hash(content)

    with get_db() as conn:
        c = conn.cursor()

        # Verifica se ja existe
        c.execute('SELECT id, access_count FROM memories WHERE content_hash = ?', (content_hash,))
        existing = c.fetchone()

        if existing:
            # Incrementa acesso
            c.execute('''
                UPDATE memories
                SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (existing['id'],))
            return existing['id']

        # Insere nova
        c.execute('''
            INSERT INTO memories (type, category, content, content_hash, metadata, importance)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (memory_type, category, content, content_hash,
              json.dumps(metadata) if metadata else None, importance))

        return c.lastrowid


def search_memories(query: Optional[str] = None, type: Optional[str] = None, category: Optional[str] = None,
                    min_importance: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    """Busca memorias por criterios combinados.

    Args:
        query: Texto para busca LIKE no conteudo (opcional)
        type: Filtrar por tipo de memoria (opcional)
        category: Filtrar por categoria (opcional)
        min_importance: Importancia minima (0-10, default: 0)
        limit: Numero maximo de resultados (default: 10)

    Returns:
        Lista de dicts com os campos da memoria, ordenados por importancia/acesso/data
    """
    with get_db() as conn:
        c = conn.cursor()

        sql = "SELECT * FROM memories WHERE importance >= ?"
        params: List[Any] = [min_importance]

        if type:
            sql += " AND type = ?"
            params.append(type)
        if category:
            sql += " AND category = ?"
            params.append(category)
        if query:
            sql += " AND content LIKE ? ESCAPE '\\'"
            params.append(f"%{_escape_like(query)}%")

        sql += " ORDER BY importance DESC, access_count DESC, created_at DESC LIMIT ?"
        params.append(limit)

        c.execute(sql, params)
        return [dict(row) for row in c.fetchall()]
