#!/usr/bin/env python3
"""
Migration 001: Otimizacao de Indices do Claude Brain

Analise realizada em 2025-01-31:
- Identificadas queries com FULL TABLE SCAN
- Criados indices para cobrir os padroes de acesso mais comuns
- Indices compostos para ORDER BY com filtros

Problemas resolvidos:
1. relations.to_entity: FULL TABLE SCAN nas queries de incoming
2. sessions.project: FULL TABLE SCAN
3. decisions.maturity_status: FULL TABLE SCAN nas queries de maturidade
4. ORDER BY sem indice causando TEMP B-TREE

Autor: database-optimizer-skill
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("/root/claude-brain/memory/brain.db")

# Indices a serem criados
INDEXES_TO_CREATE = [
    # relations - query de incoming precisa de indice em to_entity
    ("idx_relations_to", "relations", "to_entity"),

    # sessions - filtro por projeto + ordenacao por data
    ("idx_sessions_project_date", "sessions", "project, created_at DESC"),

    # decisions - status com data para queries frequentes
    ("idx_decisions_status_date", "decisions", "status, created_at DESC"),

    # decisions - maturity com confidence para sistema de maturacao
    ("idx_decisions_maturity", "decisions", "maturity_status, confidence_score DESC"),

    # learnings - frequencia e data para ordenacao
    ("idx_learnings_freq_date", "learnings", "frequency DESC, last_occurred DESC"),

    # learnings - maturity para sistema de maturacao
    ("idx_learnings_maturity", "learnings", "maturity_status, confidence_score DESC"),

    # memories - covering index para ordenacao comum
    # NOTA: SQLite nao suporta DESC em CREATE INDEX diretamente para todas as colunas
    # mas o otimizador consegue usar o indice em ambas direcoes
    ("idx_memories_importance", "memories", "importance, access_count, created_at"),
]


def get_existing_indexes(conn):
    """Retorna set de nomes de indices existentes"""
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='index'")
    return {row[0] for row in c.fetchall()}


def create_index(conn, name, table, columns):
    """Cria um indice se nao existir"""
    c = conn.cursor()
    sql = f"CREATE INDEX IF NOT EXISTS {name} ON {table}({columns})"
    print(f"  Executando: {sql}")
    c.execute(sql)


def run_migration():
    """Executa a migracao"""
    print(f"\n{'='*60}")
    print(f"Migration 001: Otimizacao de Indices")
    print(f"{'='*60}")
    print(f"Inicio: {datetime.now().isoformat()}")
    print(f"Banco: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    try:
        existing = get_existing_indexes(conn)
        print(f"\nIndices existentes: {len(existing)}")

        created = 0
        skipped = 0

        print(f"\nCriando indices...\n")

        for name, table, columns in INDEXES_TO_CREATE:
            if name in existing:
                print(f"  [SKIP] {name} - ja existe")
                skipped += 1
            else:
                create_index(conn, name, table, columns)
                created += 1

        conn.commit()

        # Roda ANALYZE para atualizar estatisticas
        print(f"\nAtualizando estatisticas (ANALYZE)...")
        conn.execute("ANALYZE")
        conn.commit()

        print(f"\n{'='*60}")
        print(f"RESULTADO")
        print(f"{'='*60}")
        print(f"  Indices criados: {created}")
        print(f"  Indices pulados: {skipped}")
        print(f"  Total de indices: {len(get_existing_indexes(conn))}")
        print(f"\nMigracao concluida com sucesso!")

    except Exception as e:
        conn.rollback()
        print(f"\nERRO: {e}")
        raise
    finally:
        conn.close()


def verify_indexes():
    """Verifica se os indices estao sendo usados"""
    print(f"\n{'='*60}")
    print(f"VERIFICACAO DE USO DOS INDICES")
    print(f"{'='*60}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    test_queries = [
        ("relations incoming", "EXPLAIN QUERY PLAN SELECT * FROM relations WHERE to_entity = 'test'"),
        ("sessions por projeto", "EXPLAIN QUERY PLAN SELECT * FROM sessions WHERE project = 'test' ORDER BY created_at DESC"),
        ("decisions maturity", "EXPLAIN QUERY PLAN SELECT * FROM decisions WHERE maturity_status = 'hypothesis' ORDER BY confidence_score DESC"),
        ("learnings freq", "EXPLAIN QUERY PLAN SELECT * FROM learnings ORDER BY frequency DESC, last_occurred DESC LIMIT 10"),
    ]

    all_good = True

    for name, query in test_queries:
        c.execute(query)
        plan = c.fetchone()['detail']
        using_index = 'USING INDEX' in plan or 'USING COVERING INDEX' in plan
        status = "OK" if using_index else "SCAN"
        symbol = "+" if using_index else "!"

        if not using_index:
            all_good = False

        print(f"\n[{symbol}] {name}")
        print(f"    Plan: {plan}")

    conn.close()

    if all_good:
        print(f"\n Todos os indices estao sendo utilizados corretamente!")
    else:
        print(f"\n ALERTA: Algumas queries ainda fazem SCAN completo")

    return all_good


if __name__ == "__main__":
    import sys

    if "--verify" in sys.argv:
        verify_indexes()
    elif "--dry-run" in sys.argv:
        print("DRY RUN - Indices que seriam criados:")
        for name, table, columns in INDEXES_TO_CREATE:
            print(f"  CREATE INDEX {name} ON {table}({columns})")
    else:
        run_migration()
        print()
        verify_indexes()
