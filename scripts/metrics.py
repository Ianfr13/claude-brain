#!/usr/bin/env python3
"""
Claude Brain - Sistema de Métricas
Rastreia uso e eficácia do brain
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import contextmanager

DB_PATH = Path("/root/claude-brain/memory/brain.db")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_metrics():
    """Cria tabela de métricas"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                category TEXT,
                project TEXT,
                query TEXT,
                results_count INTEGER DEFAULT 0,
                top_score REAL,
                useful INTEGER,
                feedback TEXT,
                session_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                searches INTEGER DEFAULT 0,
                decisions_saved INTEGER DEFAULT 0,
                learnings_saved INTEGER DEFAULT 0,
                useful_count INTEGER DEFAULT 0,
                not_useful_count INTEGER DEFAULT 0
            )
        ''')

        # Adiciona coluna project se ela não existir (para tabelas existentes)
        try:
            c.execute('PRAGMA table_info(metrics)')
            columns = {row[1] for row in c.fetchall()}
            if 'project' not in columns:
                c.execute('ALTER TABLE metrics ADD COLUMN project TEXT')
        except Exception:
            # Se houver erro, ignora (a coluna pode já existir)
            pass

        # Cria indices
        c.execute('CREATE INDEX IF NOT EXISTS idx_metrics_action ON metrics(action)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_metrics_date ON metrics(created_at)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_metrics_project ON metrics(project)')


def log_action(action: str, category: str = None, query: str = None,
               results_count: int = 0, top_score: float = None, project: str = None) -> int:
    """Registra uma ação do brain"""
    init_metrics()
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO metrics (action, category, project, query, results_count, top_score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (action, category, project, query, results_count, top_score))

        # Atualiza stats diárias
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute('''
            INSERT INTO daily_stats (date, searches, decisions_saved, learnings_saved)
            VALUES (?, 0, 0, 0)
            ON CONFLICT(date) DO NOTHING
        ''', (today,))

        if action == "search":
            c.execute('UPDATE daily_stats SET searches = searches + 1 WHERE date = ?', (today,))
        elif action == "decide":
            c.execute('UPDATE daily_stats SET decisions_saved = decisions_saved + 1 WHERE date = ?', (today,))
        elif action == "learn":
            c.execute('UPDATE daily_stats SET learnings_saved = learnings_saved + 1 WHERE date = ?', (today,))

        return c.lastrowid


def mark_useful(metric_id: int = None, useful: bool = True, feedback: str = None):
    """Marca se a última ação foi útil"""
    init_metrics()
    with get_db() as conn:
        c = conn.cursor()

        if metric_id is None:
            # Pega a última ação
            c.execute('SELECT id FROM metrics ORDER BY id DESC LIMIT 1')
            row = c.fetchone()
            if row:
                metric_id = row['id']
            else:
                return

        c.execute('''
            UPDATE metrics SET useful = ?, feedback = ? WHERE id = ?
        ''', (1 if useful else 0, feedback, metric_id))

        # Atualiza stats diárias
        today = datetime.now().strftime("%Y-%m-%d")
        if useful:
            c.execute('UPDATE daily_stats SET useful_count = useful_count + 1 WHERE date = ?', (today,))
        else:
            c.execute('UPDATE daily_stats SET not_useful_count = not_useful_count + 1 WHERE date = ?', (today,))


def get_effectiveness() -> Dict:
    """Calcula eficácia geral do brain"""
    init_metrics()
    with get_db() as conn:
        c = conn.cursor()

        # Total de ações
        c.execute('SELECT COUNT(*) as total FROM metrics')
        total = c.fetchone()['total']

        # Ações avaliadas
        c.execute('SELECT COUNT(*) as rated FROM metrics WHERE useful IS NOT NULL')
        rated = c.fetchone()['rated']

        # Úteis vs não úteis
        c.execute('SELECT COUNT(*) as useful FROM metrics WHERE useful = 1')
        useful = c.fetchone()['useful']

        c.execute('SELECT COUNT(*) as not_useful FROM metrics WHERE useful = 0')
        not_useful = c.fetchone()['not_useful']

        # Por tipo de ação
        c.execute('''
            SELECT action, COUNT(*) as count,
                   SUM(CASE WHEN useful = 1 THEN 1 ELSE 0 END) as useful_count
            FROM metrics
            GROUP BY action
        ''')
        by_action = {row['action']: {'total': row['count'], 'useful': row['useful_count'] or 0}
                     for row in c.fetchall()}

        # Score médio das buscas
        c.execute('SELECT AVG(top_score) as avg_score FROM metrics WHERE action = "search" AND top_score IS NOT NULL')
        avg_score = c.fetchone()['avg_score']

        # Eficácia
        effectiveness = (useful / rated * 100) if rated > 0 else 0

        return {
            "total_actions": total,
            "rated_actions": rated,
            "useful": useful,
            "not_useful": not_useful,
            "effectiveness_pct": round(effectiveness, 1),
            "avg_search_score": round(avg_score, 3) if avg_score else None,
            "by_action": by_action
        }


def get_daily_report(days: int = 7) -> List[Dict]:
    """Relatório diário dos últimos N dias"""
    init_metrics()
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT * FROM daily_stats
            ORDER BY date DESC LIMIT ?
        ''', (days,))
        return [dict(row) for row in c.fetchall()]


def get_recent_actions(limit: int = 20) -> List[Dict]:
    """Ações recentes"""
    init_metrics()
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT action, category, project, query, results_count, top_score, useful, created_at
            FROM metrics
            ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
        return [dict(row) for row in c.fetchall()]


def print_dashboard():
    """Imprime dashboard de métricas"""
    eff = get_effectiveness()
    daily = get_daily_report(7)

    print("\n" + "=" * 60)
    print("🧠 CLAUDE BRAIN - DASHBOARD DE EFICÁCIA")
    print("=" * 60)

    # Eficácia geral
    print(f"\n📊 EFICÁCIA GERAL")
    print(f"   Total de ações: {eff['total_actions']}")
    print(f"   Avaliadas: {eff['rated_actions']}")
    if eff['rated_actions'] > 0:
        print(f"   ✅ Úteis: {eff['useful']}")
        print(f"   ❌ Não úteis: {eff['not_useful']}")
        print(f"   📈 Taxa de eficácia: {eff['effectiveness_pct']}%")
    if eff['avg_search_score']:
        print(f"   🎯 Score médio de busca: {eff['avg_search_score']}")

    # Por tipo
    if eff['by_action']:
        print(f"\n📋 POR TIPO DE AÇÃO")
        for action, stats in eff['by_action'].items():
            rate = (stats['useful'] / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"   {action}: {stats['total']} ações ({rate:.0f}% útil)")

    # Últimos 7 dias
    if daily:
        print(f"\n📅 ÚLTIMOS 7 DIAS")
        print(f"   {'Data':<12} {'Buscas':<8} {'Decisões':<10} {'Aprendiz.':<10} {'Útil':<6} {'Inútil':<6}")
        print(f"   {'-'*52}")
        for d in daily:
            print(f"   {d['date']:<12} {d['searches']:<8} {d['decisions_saved']:<10} {d['learnings_saved']:<10} {d['useful_count']:<6} {d['not_useful_count']:<6}")

    print("\n" + "=" * 60)


# Inicializa ao importar
init_metrics()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print_dashboard()
    elif sys.argv[1] == "useful":
        mark_useful(useful=True, feedback=sys.argv[2] if len(sys.argv) > 2 else None)
        print("✅ Marcado como útil")
    elif sys.argv[1] == "useless":
        mark_useful(useful=False, feedback=sys.argv[2] if len(sys.argv) > 2 else None)
        print("❌ Marcado como não útil")
    elif sys.argv[1] == "stats":
        print_dashboard()
    else:
        print("Uso: metrics.py [useful|useless|stats] [feedback]")
