#!/usr/bin/env python3
"""
Migration 002: Adicionar coluna project à tabela metrics

Problema: log_action() estava sendo chamada com project=... mas a função
nao aceitava esse parametro, causando erro.

Solucao: Adicionar coluna project à tabela metrics para rastrear qual
projeto a acao pertence.

Autor: python-pro-skill
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("/root/claude-brain/memory/brain.db")


def column_exists(conn, table, column):
    """Verifica se uma coluna existe na tabela"""
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in c.fetchall()}
    return column in columns


def run_migration():
    """Executa a migracao"""
    print(f"\n{'='*60}")
    print(f"Migration 002: Adicionar coluna project à tabela metrics")
    print(f"{'='*60}")
    print(f"Inicio: {datetime.now().isoformat()}")
    print(f"Banco: {DB_PATH}")

    # Cria DB se nao existir
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    try:
        # Verifica se a coluna ja existe
        if column_exists(conn, "metrics", "project"):
            print("\n[SKIP] Coluna 'project' ja existe na tabela metrics")
            return

        # Adiciona a coluna
        c = conn.cursor()
        print("\nAdicionando coluna 'project' à tabela metrics...")
        c.execute("ALTER TABLE metrics ADD COLUMN project TEXT")
        print("  ✓ Coluna 'project' adicionada com sucesso")

        # Cria indice para melhor performance
        print("\nCriando indice para coluna project...")
        c.execute("CREATE INDEX IF NOT EXISTS idx_metrics_project ON metrics(project)")
        print("  ✓ Indice criado com sucesso")

        conn.commit()

        print(f"\n{'='*60}")
        print(f"RESULTADO")
        print(f"{'='*60}")
        print(f"  Coluna adicionada: project (TEXT)")
        print(f"  Indice criado: idx_metrics_project")
        print(f"\nMigracao concluida com sucesso!")

    except Exception as e:
        conn.rollback()
        print(f"\nERRO: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if "--verify" not in sys.argv:
        run_migration()
