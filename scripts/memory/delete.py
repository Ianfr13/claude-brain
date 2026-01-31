#!/usr/bin/env python3
"""
Claude Brain - Delete Module

Este modulo gerencia operacoes de delecao de registros.

Funcoes principais:
- delete_record: Deleta um registro especifico
- delete_by_search: Busca e opcionalmente deleta registros

Relacionamentos:
- base.py: get_db, ALLOWED_TABLES, _escape_like
- __init__.py: re-exporta todas as funcoes publicas
"""

import logging
from typing import Optional, List, Dict, Any

from .base import get_db, ALLOWED_TABLES, _escape_like

logger = logging.getLogger(__name__)


def delete_record(table: str, record_id: int) -> bool:
    """Deleta um registro especifico.

    Args:
        table: Nome da tabela ('memories', 'decisions', 'learnings')
        record_id: ID do registro a deletar

    Returns:
        True se registro foi deletado, False se nao encontrado

    Raises:
        ValueError: Se tabela nao for permitida
    """
    if table not in ALLOWED_TABLES:
        logger.warning(f"Tentativa de delete em tabela nao permitida: {table}")
        raise ValueError(f"Tabela invalida: {table}")

    with get_db() as conn:
        c = conn.cursor()
        c.execute(f'DELETE FROM {table} WHERE id = ?', (record_id,))
        deleted = c.rowcount > 0
        if deleted:
            logger.info(f"Deletado registro {table}#{record_id}")
        return deleted


def delete_by_search(query: str, table: Optional[str] = None, dry_run: bool = True) -> List[Dict[str, Any]]:
    """
    Encontra registros por busca LIKE e opcionalmente deleta.

    Args:
        query: Texto para buscar
        table: Tabela especifica ('memories', 'decisions', 'learnings') ou None para todas
        dry_run: Se True (default), apenas mostra o que seria deletado

    Returns:
        Lista de registros encontrados/deletados com campos:
        - id: ID do registro
        - table: Nome da tabela
        - content: Primeiros 100 chars do conteudo (truncado se maior)

    Raises:
        ValueError: Se tabela especificada nao for permitida
    """
    if table and table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela invalida: {table}")

    tables_to_search = [table] if table else list(ALLOWED_TABLES)
    results = []
    escaped_query = _escape_like(query)

    with get_db() as conn:
        c = conn.cursor()

        for tbl in tables_to_search:
            # Campo de conteudo varia por tabela
            content_field = 'content' if tbl == 'memories' else 'decision' if tbl == 'decisions' else 'solution'

            c.execute(f'''
                SELECT id, {content_field} as content FROM {tbl}
                WHERE {content_field} LIKE ? ESCAPE '\\'
            ''', (f'%{escaped_query}%',))

            for row in c.fetchall():
                results.append({
                    'id': row['id'],
                    'table': tbl,
                    'content': row['content'][:100] + '...' if len(row['content']) > 100 else row['content']
                })

        if not dry_run:
            for r in results:
                c.execute(f"DELETE FROM {r['table']} WHERE id = ?", (r['id'],))
            if results:
                logger.info(f"delete_by_search deletou {len(results)} registros para query '{query}'")

    return results
