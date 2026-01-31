#!/usr/bin/env python3
"""
Claude Brain - Database Health Check

Verifica saude do banco de dados:
- Integridade
- Indices
- Estatisticas
- Performance de queries
- Relacoes orfas
- Dados duplicados

Uso:
  python db_health.py          # Relatorio completo
  python db_health.py --fix    # Corrige problemas automaticamente
  python db_health.py --vacuum # Roda VACUUM para compactar banco
"""

import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

DB_PATH = Path("/root/claude-brain/memory/brain.db")


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    END = '\033[0m'


def c(text: str, color: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{Colors.END}"


def get_db_size() -> Tuple[int, str]:
    """Retorna tamanho do banco em bytes e formatado"""
    size = os.path.getsize(DB_PATH)
    if size < 1024:
        formatted = f"{size} B"
    elif size < 1024 * 1024:
        formatted = f"{size / 1024:.1f} KB"
    else:
        formatted = f"{size / (1024 * 1024):.2f} MB"
    return size, formatted


def check_integrity(conn) -> bool:
    """Verifica integridade do banco"""
    c = conn.cursor()
    c.execute("PRAGMA integrity_check")
    result = c.fetchone()[0]
    return result == "ok"


def get_table_stats(conn) -> Dict[str, Dict]:
    """Retorna estatisticas de cada tabela"""
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in c.fetchall()]

    stats = {}
    for table in tables:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]

        # Estima tamanho
        c.execute(f"SELECT * FROM {table} LIMIT 1")
        columns = [desc[0] for desc in c.description] if c.description else []

        stats[table] = {
            "rows": count,
            "columns": len(columns)
        }

    return stats


def get_index_stats(conn) -> List[Dict]:
    """Retorna informacoes sobre indices"""
    c = conn.cursor()
    c.execute("""
        SELECT name, tbl_name, sql
        FROM sqlite_master
        WHERE type='index' AND sql IS NOT NULL
        ORDER BY tbl_name
    """)
    return [{"name": row[0], "table": row[1], "sql": row[2]} for row in c.fetchall()]


def check_orphan_relations(conn) -> List[Dict]:
    """Verifica relacoes com entidades inexistentes"""
    c = conn.cursor()
    c.execute("""
        SELECT r.id, r.from_entity, r.to_entity, r.relation_type
        FROM relations r
        LEFT JOIN entities e1 ON r.from_entity = e1.name
        LEFT JOIN entities e2 ON r.to_entity = e2.name
        WHERE e1.id IS NULL OR e2.id IS NULL
    """)
    return [dict(row) for row in c.fetchall()]


def check_duplicate_memories(conn) -> List[Dict]:
    """Verifica memorias duplicadas (mesmo content_hash)"""
    c = conn.cursor()
    c.execute("""
        SELECT content_hash, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
        FROM memories
        WHERE content_hash IS NOT NULL
        GROUP BY content_hash
        HAVING cnt > 1
    """)
    return [dict(row) for row in c.fetchall()]


def check_null_hashes(conn) -> int:
    """Conta memorias sem hash (podem ser duplicatas)"""
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM memories WHERE content_hash IS NULL")
    return c.fetchone()[0]


def analyze_query_performance(conn) -> List[Dict]:
    """Analisa performance das queries principais"""
    queries = [
        ("search_memories", "SELECT * FROM memories WHERE type = 'general' ORDER BY importance DESC LIMIT 10"),
        ("get_decisions", "SELECT * FROM decisions WHERE status = 'active' ORDER BY created_at DESC LIMIT 10"),
        ("find_solution", "SELECT * FROM learnings WHERE error_type = 'test' ORDER BY frequency DESC LIMIT 1"),
        ("get_entity_graph_out", "SELECT * FROM relations WHERE from_entity = 'test'"),
        ("get_entity_graph_in", "SELECT * FROM relations WHERE to_entity = 'test'"),
        ("get_hypotheses", "SELECT * FROM decisions WHERE maturity_status = 'hypothesis' LIMIT 10"),
    ]

    results = []
    c = conn.cursor()

    for name, query in queries:
        c.execute(f"EXPLAIN QUERY PLAN {query}")
        plan = c.fetchone()
        plan_detail = dict(plan)['detail'] if plan else "N/A"

        uses_index = "USING INDEX" in plan_detail or "USING COVERING INDEX" in plan_detail
        is_scan = "SCAN" in plan_detail and not uses_index

        results.append({
            "name": name,
            "plan": plan_detail,
            "uses_index": uses_index,
            "is_scan": is_scan
        })

    return results


def fix_orphan_relations(conn, orphans: List[Dict]) -> int:
    """Remove relacoes orfas"""
    if not orphans:
        return 0

    c = conn.cursor()
    for orphan in orphans:
        c.execute("DELETE FROM relations WHERE id = ?", (orphan['id'],))

    conn.commit()
    return len(orphans)


def fix_null_hashes(conn) -> int:
    """Adiciona hashes faltantes em memorias"""
    import hashlib

    c = conn.cursor()
    c.execute("SELECT id, content FROM memories WHERE content_hash IS NULL")
    memories = c.fetchall()

    fixed = 0
    for mem in memories:
        content_hash = hashlib.sha256(mem[1].encode()).hexdigest()[:32]
        c.execute("UPDATE memories SET content_hash = ? WHERE id = ?", (content_hash, mem[0]))
        fixed += 1

    conn.commit()
    return fixed


def vacuum_database(conn) -> Tuple[int, int]:
    """Compacta o banco de dados"""
    size_before = os.path.getsize(DB_PATH)
    conn.execute("VACUUM")
    conn.execute("ANALYZE")
    size_after = os.path.getsize(DB_PATH)
    return size_before, size_after


def print_report(fix: bool = False, vacuum: bool = False):
    """Imprime relatorio completo de saude"""
    print(f"\n{c('='*60, Colors.CYAN)}")
    print(f"{c(' DATABASE HEALTH CHECK - Claude Brain', Colors.BOLD)}")
    print(f"{c('='*60, Colors.CYAN)}")
    print(f"{c(f'Data: {datetime.now().isoformat()}', Colors.DIM)}")
    print(f"{c(f'Banco: {DB_PATH}', Colors.DIM)}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1. Tamanho e Integridade
    print(f"\n{c('[ INTEGRIDADE ]', Colors.BOLD)}")
    size_bytes, size_fmt = get_db_size()
    integrity = check_integrity(conn)
    print(f"  Tamanho: {size_fmt}")
    print(f"  Integridade: {c('OK', Colors.GREEN) if integrity else c('FALHA', Colors.RED)}")

    # 2. Estatisticas de Tabelas
    print(f"\n{c('[ TABELAS ]', Colors.BOLD)}")
    table_stats = get_table_stats(conn)
    total_rows = 0
    for table, stats in sorted(table_stats.items()):
        total_rows += stats['rows']
        print(f"  {table:20}: {stats['rows']:5} registros ({stats['columns']} colunas)")
    print(f"  {'-'*35}")
    print(f"  {'TOTAL':20}: {total_rows:5} registros")

    # 3. Indices
    print(f"\n{c('[ INDICES ]', Colors.BOLD)}")
    indexes = get_index_stats(conn)
    tables_with_indexes = set()
    for idx in indexes:
        tables_with_indexes.add(idx['table'])
    print(f"  Total de indices: {len(indexes)}")
    print(f"  Tabelas com indices: {len(tables_with_indexes)}")

    # 4. Performance de Queries
    print(f"\n{c('[ PERFORMANCE DE QUERIES ]', Colors.BOLD)}")
    perf = analyze_query_performance(conn)
    issues = 0
    for q in perf:
        if q['is_scan']:
            status = c("[SCAN]", Colors.YELLOW)
            issues += 1
        elif q['uses_index']:
            status = c("[INDEX]", Colors.GREEN)
        else:
            status = c("[OK]", Colors.DIM)
        print(f"  {status} {q['name']}")

    if issues > 0:
        print(f"\n  {c(f'ALERTA: {issues} queries fazendo table scan', Colors.YELLOW)}")

    # 5. Relacoes Orfas
    print(f"\n{c('[ RELACOES ORFAS ]', Colors.BOLD)}")
    orphans = check_orphan_relations(conn)
    if orphans:
        print(f"  {c(f'Encontradas: {len(orphans)}', Colors.YELLOW)}")
        for o in orphans[:5]:
            print(f"    {o['from_entity']} -> {o['to_entity']} ({o['relation_type']})")
        if fix:
            fixed = fix_orphan_relations(conn, orphans)
            print(f"  {c(f'Removidas: {fixed}', Colors.GREEN)}")
    else:
        print(f"  {c('Nenhuma', Colors.GREEN)}")

    # 6. Duplicatas e Hashes
    print(f"\n{c('[ DUPLICATAS ]', Colors.BOLD)}")
    duplicates = check_duplicate_memories(conn)
    null_hashes = check_null_hashes(conn)

    if duplicates:
        print(f"  {c(f'Memorias duplicadas: {len(duplicates)}', Colors.YELLOW)}")
    else:
        print(f"  {c('Memorias duplicadas: 0', Colors.GREEN)}")

    if null_hashes > 0:
        print(f"  {c(f'Memorias sem hash: {null_hashes}', Colors.YELLOW)}")
        if fix:
            fixed = fix_null_hashes(conn)
            print(f"  {c(f'Hashes adicionados: {fixed}', Colors.GREEN)}")
    else:
        print(f"  {c('Memorias sem hash: 0', Colors.GREEN)}")

    # 7. Vacuum
    if vacuum:
        print(f"\n{c('[ VACUUM ]', Colors.BOLD)}")
        before, after = vacuum_database(conn)
        saved = before - after
        print(f"  Antes: {before / 1024:.1f} KB")
        print(f"  Depois: {after / 1024:.1f} KB")
        print(f"  {c(f'Economizado: {saved / 1024:.1f} KB', Colors.GREEN)}")

    # Resumo
    print(f"\n{c('='*60, Colors.CYAN)}")
    print(f"{c('RESUMO', Colors.BOLD)}")
    print(f"{c('='*60, Colors.CYAN)}")

    health_score = 100
    issues_found = []

    if not integrity:
        health_score -= 50
        issues_found.append("Falha de integridade")

    if orphans:
        health_score -= 10
        issues_found.append(f"{len(orphans)} relacoes orfas")

    if duplicates:
        health_score -= 5
        issues_found.append(f"{len(duplicates)} duplicatas")

    if null_hashes > 0:
        health_score -= 5
        issues_found.append(f"{null_hashes} memorias sem hash")

    scan_count = sum(1 for q in perf if q['is_scan'])
    if scan_count > 0:
        health_score -= scan_count * 5
        issues_found.append(f"{scan_count} queries sem indice")

    if health_score >= 90:
        status_color = Colors.GREEN
        status_text = "EXCELENTE"
    elif health_score >= 70:
        status_color = Colors.YELLOW
        status_text = "BOM"
    else:
        status_color = Colors.RED
        status_text = "PRECISA ATENCAO"

    print(f"\n  Health Score: {c(f'{health_score}%', status_color)} - {c(status_text, status_color)}")

    if issues_found:
        print(f"\n  Problemas encontrados:")
        for issue in issues_found:
            print(f"    - {issue}")

    if not fix and (orphans or null_hashes > 0):
        print(f"\n  {c('Dica: Use --fix para corrigir problemas automaticamente', Colors.DIM)}")

    if not vacuum:
        print(f"  {c('Dica: Use --vacuum para compactar o banco', Colors.DIM)}")

    conn.close()
    print()


if __name__ == "__main__":
    fix = "--fix" in sys.argv
    vacuum = "--vacuum" in sys.argv
    print_report(fix=fix, vacuum=vacuum)
