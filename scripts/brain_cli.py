#!/usr/bin/env python3
"""
Claude Brain - CLI Unificado (Enhanced)
Interface completa para memória, RAG e knowledge graph
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

from scripts.memory_store import (
    init_db, save_memory, save_decision, save_learning,
    save_entity, save_relation, save_preference, save_pattern,
    search_memories, get_decisions, get_all_learnings, find_solution,
    get_entity, get_entity_graph, get_related_entities,
    get_preference, get_all_preferences, get_pattern,
    export_context, get_stats as memory_stats,
    # Sistema de maturação
    record_usage, contradict_knowledge, confirm_knowledge,
    get_hypotheses, get_contradicted, supersede_knowledge, get_knowledge_by_maturity,
    # Delete
    delete_record
)
from scripts.rag_engine import (
    index_file, index_directory, search as simple_search,
    get_context_for_query as simple_context, get_stats as rag_stats
)
# Tenta usar FAISS para busca semântica
try:
    from scripts.faiss_rag import semantic_search, get_context_for_query as faiss_context, get_stats as faiss_stats
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

def search(query, doc_type=None, limit=5):
    """Busca híbrida: FAISS se disponível, senão simples"""
    if HAS_FAISS:
        return semantic_search(query, doc_type, limit)
    return simple_search(query, doc_type, limit)

def get_context_for_query(query, max_tokens=2000):
    """Contexto híbrido"""
    if HAS_FAISS:
        return faiss_context(query, max_tokens)
    return simple_context(query, max_tokens)
from scripts.metrics import (
    log_action, mark_useful, get_effectiveness, print_dashboard
)

# Diretórios permitidos para indexação (proteção contra path traversal)
ALLOWED_INDEX_PATHS = [
    Path("/root/claude-brain"),
    Path("/root/vsl-analysis"),
    Path("/root/vsl-tools"),
    Path("/root/slack-claude-bot"),
    Path("/root/claude-swarm-plugin"),
    Path.home() / "projects",  # ~/projects
]


def _is_path_allowed(path: Path) -> bool:
    """Verifica se o path está dentro de diretórios permitidos."""
    resolved = path.resolve()
    return any(
        resolved == allowed or allowed in resolved.parents
        for allowed in ALLOWED_INDEX_PATHS
    )


class Colors:
    """ANSI colors para output bonito"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def c(text: str, color: str) -> str:
    """Aplica cor ao texto (desativa cores em pipes/redirecionamentos)"""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{Colors.END}"


def print_header(text: str):
    print(f"\n{c(text, Colors.BOLD + Colors.CYAN)}")
    print("─" * 50)


def print_success(text: str):
    print(c(f"✓ {text}", Colors.GREEN))


def print_error(text: str):
    print(c(f"✗ {text}", Colors.RED))


def print_info(text: str):
    print(c(f"ℹ {text}", Colors.BLUE))


# ============ COMANDOS DE MEMÓRIA ============

def cmd_remember(args):
    """Salva uma memória geral"""
    if not args.text:
        print_error("Uso: brain remember <texto>")
        return

    text = " ".join(args.text)
    category = args.category or "general"
    importance = args.importance or 5

    mid = save_memory("general", text, category=category, importance=importance)
    print_success(f"Memória salva (ID: {mid})")


def cmd_decide(args):
    """Salva uma decisão arquitetural"""
    if not args.decision:
        print_error("Uso: brain decide <decisão> [--project X] [--reason Y] [--fact]")
        return

    decision = " ".join(args.decision)
    is_fact = getattr(args, 'fact', False)

    did = save_decision(
        decision,
        reasoning=args.reason,
        project=args.project,
        alternatives=args.alternatives,
        is_established=is_fact
    )
    log_action("decide", category=args.project)

    if is_fact:
        print_success(f"Fato salvo (ID: {did}) ✓ já confirmado")
    else:
        print_success(f"Decisão salva (ID: {did}) ○ como hipótese")


def cmd_learn(args):
    """Salva um aprendizado de erro"""
    if not args.error or not args.solution:
        print_error("Uso: brain learn <erro> --solution <solução> [-c contexto] [--cause causa] [--fact]")
        return

    error = " ".join(args.error)
    is_fact = getattr(args, 'fact', False)

    lid = save_learning(
        error_type=error,
        solution=args.solution,
        prevention=args.prevention,
        project=args.project,
        context=getattr(args, 'context', None),
        root_cause=getattr(args, 'cause', None),
        error_message=getattr(args, 'message', None),
        is_established=is_fact
    )
    log_action("learn", category=error)

    if is_fact:
        print_success(f"Solução conhecida salva (ID: {lid}) ✓ já confirmada")
    else:
        print_success(f"Aprendizado salvo (ID: {lid}) ○ como hipótese")


def cmd_solve(args):
    """Busca solução para um erro"""
    if not args.error:
        print_error("Uso: brain solve <erro>")
        return

    error = " ".join(args.error)
    solution = find_solution(error_type=error, error_message=error)

    if solution:
        print_header("Solução Encontrada")
        print(f"{c('Erro:', Colors.YELLOW)} {solution['error_type']}")
        print(f"{c('Solução:', Colors.GREEN)} {solution['solution']}")
        if solution['prevention']:
            print(f"{c('Prevenção:', Colors.BLUE)} {solution['prevention']}")
        print(f"{c('Frequência:', Colors.DIM)} {solution['frequency']} ocorrências")
    else:
        print_info("Nenhuma solução encontrada para este erro.")


def cmd_recall(args):
    """Busca na memória"""
    query = " ".join(args.query) if args.query else None
    results = search_memories(
        query=query,
        type=args.type,
        limit=args.limit or 10
    )

    if not results:
        print_info("Nenhuma memória encontrada.")
        return

    print_header(f"Memórias ({len(results)} resultados)")
    for r in results:
        importance = "★" * min(r['importance'], 5)
        mem_type = r['type']
        print(f"\n{c(f'[{mem_type}]', Colors.CYAN)} {importance}")
        print(f"  {r['content'][:200]}...")
        print(c(f"  Acessos: {r['access_count']} | {r['created_at'][:10]}", Colors.DIM))


def cmd_decisions(args):
    """Lista decisões"""
    decisions = get_decisions(project=args.project, limit=args.limit or 10)

    if not decisions:
        print_info("Nenhuma decisão encontrada.")
        return

    print_header("Decisões Arquiteturais")
    for d in decisions:
        proj = c(f"[{d['project']}]", Colors.YELLOW) if d['project'] else ""
        status = c(d['status'], Colors.GREEN if d['status'] == 'active' else Colors.DIM)
        print(f"\n{proj} {d['decision']}")
        if d['reasoning']:
            print(c(f"  Razão: {d['reasoning']}", Colors.DIM))
        print(c(f"  Status: {status} | {d['created_at'][:10]}", Colors.DIM))


def cmd_learnings(args):
    """Lista aprendizados"""
    learnings = get_all_learnings(limit=args.limit or 10)

    if not learnings:
        print_info("Nenhum aprendizado registrado.")
        return

    print_header("Aprendizados de Erros")
    for l in learnings:
        freq = c(f"({l['frequency']}x)", Colors.YELLOW)
        print(f"\n{c(l['error_type'], Colors.RED)} {freq}")
        if l.get('context'):
            print(f"  {c('Contexto:', Colors.CYAN)} {l['context']}")
        if l.get('root_cause'):
            print(f"  {c('Causa:', Colors.YELLOW)} {l['root_cause']}")
        print(f"  {c('Solução:', Colors.GREEN)} {l['solution']}")
        if l.get('prevention'):
            print(f"  {c('Prevenção:', Colors.BLUE)} {l['prevention']}")


# ============ COMANDOS DE RAG ============

def cmd_index(args):
    """Indexa arquivo ou diretório"""
    if not args.path:
        print_error("Uso: brain index <arquivo|diretório>")
        return

    path = Path(args.path[0])

    # Validação de segurança contra path traversal
    if not _is_path_allowed(path):
        print_error(f"Path não permitido: {path}")
        print_info("Diretórios permitidos:")
        for allowed in ALLOWED_INDEX_PATHS:
            print(f"  - {allowed}")
        return

    if path.is_file():
        print_info(f"Indexando arquivo: {path}")
        result = index_file(str(path))
        if result:
            chunks = result.get('chunk_count', result.get('chunks', '?'))
            print_success(f"Indexado: {chunks} chunks")
        else:
            print_error("Falha ao indexar arquivo")

    elif path.is_dir():
        print_info(f"Indexando diretório: {path}")
        print()
        count = index_directory(str(path), recursive=not args.no_recursive)
        print()
        print_success(f"Indexados: {count} arquivos")

    else:
        print_error(f"Não encontrado: {path}")


def cmd_search(args):
    """Busca semântica"""
    if not args.query:
        print_error("Uso: brain search <query>")
        return

    query = " ".join(args.query)
    results = search(query, doc_type=args.type, limit=args.limit or 5)

    # Log da ação
    top_score = results[0]['score'] if results else None
    log_action("search", query=query, results_count=len(results), top_score=top_score)

    if not results:
        print_info("Nenhum resultado encontrado.")
        return

    print_header(f"Resultados para: '{query}'")
    for r in results:
        score = r.get('score', 0)
        score_str = f"{score:.2f}" if isinstance(score, float) else str(score)
        score_color = Colors.GREEN if score > 0.7 else Colors.YELLOW if score > 0.4 else Colors.DIM
        print(f"\n{c(f'[{score_str}]', score_color)} {c(r['source'], Colors.CYAN)}")
        print(f"  {r['text'][:200]}...")

    print(c(f"\n💡 Foi útil? brain useful | brain useless", Colors.DIM))


def cmd_context(args):
    """Retorna contexto para Claude"""
    if not args.query:
        print_error("Uso: brain context <query>")
        return

    query = " ".join(args.query)
    context = get_context_for_query(query, max_tokens=args.tokens or 2000)

    if context:
        print(context)
    else:
        print_info("Nenhum contexto relevante encontrado.")


def cmd_ask(args):
    """Consulta inteligente ao brain - combina busca semantica + decisoes + learnings"""
    if not args.query:
        print_error("Uso: brain ask <pergunta>")
        return

    query = " ".join(args.query)
    found_anything = False

    # 1. Busca em learnings (erros/soluções)
    solution = find_solution(error_type=query, error_message=query, similarity_threshold=0.4)
    if solution:
        found_anything = True
        confidence = solution.get('confidence_score', 0.5) or 0.5
        status_icon = "✓" if solution.get('maturity_status') == 'confirmed' else "○"
        print(f"\n{c('💡 SOLUÇÃO CONHECIDA:', Colors.GREEN)} {status_icon} {confidence*100:.0f}%")
        print(f"   Erro: {solution['error_type']}")
        print(f"   Solução: {solution['solution']}")
        if solution.get('context'):
            print(f"   Contexto: {solution['context']}")
        if solution.get('prevention'):
            print(f"   Prevenção: {solution['prevention']}")

    # 2. Busca em decisões
    decisions = get_decisions(limit=50)
    relevant_decisions = []
    query_words = set(query.lower().split())
    for d in decisions:
        text = f"{d['decision']} {d.get('reasoning', '')} {d.get('project', '')}".lower()
        if any(word in text for word in query_words if len(word) > 3):
            relevant_decisions.append(d)

    if relevant_decisions[:3]:
        found_anything = True
        print(f"\n{c('📋 DECISÕES RELACIONADAS:', Colors.CYAN)}")
        for d in relevant_decisions[:3]:
            conf = d.get('confidence_score', 0.5) or 0.5
            status = "✓" if d.get('maturity_status') == 'confirmed' else "○"
            proj = f"[{d['project']}] " if d.get('project') else ""
            print(f"   {status} {conf*100:.0f}% {proj}{d['decision'][:70]}")

    # 3. Busca semântica nos docs (apenas se não encontrou nada específico)
    if not found_anything:
        results = search(query, limit=3)
        if results:
            found_anything = True
            print(f"\n{c('📄 DOCUMENTOS RELEVANTES:', Colors.YELLOW)}")
            for r in results[:3]:
                score = r.get('score', 0)
                print(f"   [{score:.1f}] {r['source']}")
                print(f"        {r['text'][:100]}...")

    if not found_anything:
        print(c("\n❌ Nada encontrado no brain para essa query.", Colors.RED))
        print(c("   Após resolver, salve com: brain learn/decide", Colors.DIM))
    else:
        print(c(f"\n💡 Útil? brain useful | Errado? brain contradict <table> <id>", Colors.DIM))


def cmd_related(args):
    """Encontra documentos relacionados (busca por similaridade de conteúdo)"""
    if not args.source:
        print_error("Uso: brain related <arquivo>")
        return

    source = args.source[0]
    # Busca documentos similares usando o nome do arquivo como query
    from pathlib import Path
    filename = Path(source).stem
    results = search(filename, limit=args.limit or 5)

    if not results:
        print_info("Nenhum documento relacionado encontrado.")
        return

    print_header(f"Documentos relacionados a: {source}")
    for r in results:
        if r['source'] != source:  # Exclui o próprio arquivo
            score = r.get('score', 0)
            score_str = f"{score:.2f}" if isinstance(score, float) else str(score)
            print(f"  [{score_str}] {r['source']}")


# ============ KNOWLEDGE GRAPH ============

def cmd_entity(args):
    """Gerencia entidades"""
    if not args.name:
        print_error("Uso: brain entity <nome> <tipo> [descrição]")
        return

    name = args.name[0]
    type_ = args.name[1] if len(args.name) > 1 else "unknown"
    desc = " ".join(args.name[2:]) if len(args.name) > 2 else None

    save_entity(name, type_, desc)
    print_success(f"Entidade '{name}' ({type_}) salva")


def cmd_relate(args):
    """Cria relação entre entidades"""
    if not args.relation or len(args.relation) < 3:
        print_error("Uso: brain relate <de> <para> <tipo>")
        return

    from_e, to_e, rel_type = args.relation[0], args.relation[1], args.relation[2]
    save_relation(from_e, to_e, rel_type)
    print_success(f"Relação: {from_e} --[{rel_type}]--> {to_e}")


def cmd_graph(args):
    """Mostra grafo de uma entidade"""
    if not args.entity:
        print_error("Uso: brain graph <entidade>")
        return

    name = args.entity[0]
    graph = get_entity_graph(name)

    if not graph:
        print_error(f"Entidade não encontrada: {name}")
        return

    e = graph["entity"]
    print_header(f"{e['name']} ({e['type']})")

    if e['description']:
        print(f"  {e['description']}")

    if graph["outgoing"]:
        print(f"\n{c('Relações de saída:', Colors.CYAN)}")
        for r in graph["outgoing"]:
            print(f"  → [{r['relation_type']}] {r['to_entity']}")

    if graph["incoming"]:
        print(f"\n{c('Relações de entrada:', Colors.CYAN)}")
        for r in graph["incoming"]:
            print(f"  ← [{r['relation_type']}] {r['from_entity']}")


# ============ PREFERÊNCIAS ============

def cmd_prefer(args):
    """Salva uma preferência"""
    if not args.pref or len(args.pref) < 2:
        print_error("Uso: brain prefer <chave> <valor>")
        return

    key = args.pref[0]
    value = " ".join(args.pref[1:])
    save_preference(key, value, confidence=0.9, source="manual")
    print_success(f"Preferência salva: {key} = {value}")


def cmd_prefs(args):
    """Lista preferências"""
    prefs = get_all_preferences(min_confidence=0.3)

    if not prefs:
        print_info("Nenhuma preferência registrada.")
        return

    print_header("Preferências Conhecidas")
    for k, v in prefs.items():
        print(f"  {c(k, Colors.CYAN)}: {v}")


# ============ PADRÕES DE CÓDIGO ============

def cmd_pattern(args):
    """Salva um padrão de código"""
    if not args.pattern or len(args.pattern) < 2:
        print_error("Uso: brain pattern <nome> <código>")
        return

    name = args.pattern[0]
    code = " ".join(args.pattern[1:])
    save_pattern(name, code, language=args.language)
    print_success(f"Padrão '{name}' salvo")


def cmd_snippet(args):
    """Busca um padrão de código"""
    if not args.name:
        print_error("Uso: brain snippet <nome>")
        return

    code = get_pattern(args.name[0])
    if code:
        print(code)
    else:
        print_error(f"Padrão não encontrado: {args.name[0]}")


# ============ UTILIDADES ============

def cmd_export(args):
    """Exporta contexto para Claude"""
    context = export_context(project=args.project, include_learnings=True)
    print(context)


def cmd_stats(args):
    """Mostra estatísticas"""
    m_stats = memory_stats()
    r_stats = rag_stats()

    print_header("Estatísticas do Claude Brain")

    print(f"\n{c('Memória:', Colors.CYAN)}")
    for k, v in m_stats.items():
        if not k.startswith('top_'):
            print(f"  {k}: {v}")

    if m_stats.get('top_preferences'):
        print(f"\n  {c('Top preferências:', Colors.DIM)}")
        for p in m_stats['top_preferences']:
            print(f"    {p['key']}: {p['times_observed']}x")

    if m_stats.get('top_errors'):
        print(f"\n  {c('Erros frequentes:', Colors.DIM)}")
        for e in m_stats['top_errors']:
            print(f"    {e['error_type']}: {e['frequency']}x")

    print(f"\n{c('RAG:', Colors.CYAN)}")
    print(f"  Documentos: {r_stats['documents']}")
    print(f"  Chunks: {r_stats['chunks']}")
    if r_stats.get('doc_types'):
        print(f"  Tipos: {', '.join(r_stats['doc_types'])}")
    elif r_stats.get('sources'):
        print(f"  Fontes: {len(r_stats['sources'])}")

    # Eficácia
    eff = get_effectiveness()
    if eff['total_actions'] > 0:
        print(f"\n{c('Eficácia:', Colors.CYAN)}")
        print(f"  Ações: {eff['total_actions']}")
        if eff['rated_actions'] > 0:
            print(f"  Taxa: {eff['effectiveness_pct']}% útil")


def cmd_useful(args):
    """Marca última ação como útil"""
    feedback = " ".join(args.feedback) if args.feedback else None
    mark_useful(useful=True, feedback=feedback)
    log_action("feedback", category="useful")
    print_success("Marcado como útil")


def cmd_useless(args):
    """Marca última ação como não útil"""
    feedback = " ".join(args.feedback) if args.feedback else None
    mark_useful(useful=False, feedback=feedback)
    log_action("feedback", category="useless")
    print_error("Marcado como não útil")


def cmd_extract(args):
    """Extrai conhecimento do histórico do Claude Code"""
    from scripts.extract_history import find_claude_sessions, process_session

    print_header("Extrator de Histórico")

    sessions = find_claude_sessions()
    sessions.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    sessions = sessions[:args.limit]

    print_info(f"Encontradas {len(sessions)} sessões")

    total = {"decisions": 0, "learnings": 0, "memories": 0}

    for session in sessions:
        stats = process_session(session, dry_run=args.dry_run)
        for key in total:
            total[key] += stats[key]
        if any(stats.values()):
            print(f"  {c('✓', Colors.GREEN)} {session.name[:30]}: {stats}")

    print(f"\n{c('Total:', Colors.CYAN)} {total['decisions']} decisões, {total['learnings']} learnings, {total['memories']} memórias")

    if args.dry_run:
        print_info("Modo dry-run - nada foi salvo")


def cmd_hypotheses(args):
    """Lista conhecimentos que ainda são hipóteses (não confirmados)"""
    hypotheses = get_hypotheses(limit=args.limit or 15)

    if not hypotheses:
        print_info("Nenhuma hipótese pendente. Tudo confirmado!")
        return

    print_header("Hipóteses Pendentes (precisam validação)")

    for h in hypotheses:
        icon = "○" if h['maturity_status'] == 'hypothesis' else "?"
        score = f"{h['confidence_score']*100:.0f}%" if h['confidence_score'] else "50%"
        uses = h.get('times_used', 0)

        table_icon = {'decisions': '📋', 'learnings': '📚', 'memories': '💭'}.get(h['source_table'], '?')

        print(f"\n{table_icon} [{h['source_table']}#{h['id']}] {c(icon, Colors.YELLOW)} {score}")
        print(f"   {h['summary'][:80]}...")
        print(c(f"   Usos: {uses} | Criado: {h['created_at'][:10]}", Colors.DIM))


def cmd_confirm(args):
    """Confirma que um conhecimento está correto"""
    if not args.table or not args.id:
        print_error("Uso: brain confirm <decisions|learnings|memories> <id>")
        return

    table = args.table
    record_id = args.id

    new_score = confirm_knowledge(table, record_id)
    print_success(f"Confirmado! Nova confiança: {new_score*100:.0f}%")


def cmd_contradict(args):
    """Marca um conhecimento como incorreto/desatualizado"""
    if not args.table or not args.id:
        print_error("Uso: brain contradict <decisions|learnings|memories> <id> [--reason 'motivo']")
        return

    table = args.table
    record_id = args.id
    reason = args.reason

    contradict_knowledge(table, record_id, reason=reason)
    print_error(f"Marcado como contradito/incorreto")
    if reason:
        print(c(f"  Motivo: {reason}", Colors.DIM))


def cmd_supersede(args):
    """Substitui um conhecimento antigo por um novo"""
    if not args.table or not args.id or not args.new:
        print_error("Uso: brain supersede <table> <id> --new 'novo conhecimento' [--reason 'motivo']")
        return

    new_id = supersede_knowledge(
        args.table, args.id,
        args.new,
        reason=args.reason
    )
    print_success(f"Substituído! Novo ID: {new_id}")
    print(c(f"  Antigo #{args.id} marcado como deprecated", Colors.DIM))


def cmd_maturity(args):
    """Mostra estatísticas de maturidade do conhecimento"""
    print_header("Maturidade do Conhecimento")

    tables = ['decisions', 'learnings', 'memories']

    for table in tables:
        print(f"\n{c(table.upper(), Colors.CYAN)}")

        for status in ['confirmed', 'testing', 'hypothesis', 'deprecated']:
            items = get_knowledge_by_maturity(table, status=status, limit=100)
            count = len(items)
            if count > 0:
                icon = {'confirmed': '✓', 'testing': '?', 'hypothesis': '○', 'deprecated': '✗'}.get(status, '?')
                color = {'confirmed': Colors.GREEN, 'testing': Colors.YELLOW, 'hypothesis': Colors.DIM, 'deprecated': Colors.RED}.get(status, Colors.DIM)
                print(f"  {c(icon, color)} {status}: {count}")

    # Contraditos
    contradicted = get_contradicted(limit=5)
    if contradicted:
        print(f"\n{c('CONTRADITOS (revisar/remover):', Colors.RED)}")
        for item in contradicted[:3]:
            print(f"  ⊗ [{item['source_table']}#{item['id']}] {item['summary'][:50]}...")


def cmd_dashboard(args):
    """Mostra dashboard de eficácia"""
    print_dashboard()


def cmd_delete(args):
    """Deleta um registro específico"""
    import sys

    if not args.table or args.id is None:
        print_error("Uso: brain delete <memories|decisions|learnings> <id> [-f]")
        sys.exit(1)

    if not args.force:
        # Robustez: Verificar se stdin é terminal antes de pedir input
        if not sys.stdin.isatty():
            print_error("Use -f/--force em modo não-interativo (pipe/script)")
            sys.exit(1)
        confirm = input(f"Deletar {args.table} #{args.id}? [s/N] ")
        if confirm.lower() != 's':
            print_info("Cancelado.")
            return

    if delete_record(args.table, args.id):
        print_success(f"Deletado {args.table} #{args.id}")
    else:
        print_error(f"Registro não encontrado")
        sys.exit(1)


def cmd_forget(args):
    """Busca e deleta registros por busca semântica"""
    if not args.query:
        print_error("Uso: brain forget <query> [-t table] [--threshold 0.8] [--execute]")
        return

    query = " ".join(args.query)

    # Busca semântica
    results = search(query, doc_type=args.table, limit=10)

    if not results:
        print_info("Nenhum resultado encontrado.")
        return

    print(f"\n{'[DRY-RUN] ' if not args.execute else ''}Resultados para '{query}':\n")

    to_delete = []
    for r in results:
        score = r.get('score', 0)
        if score >= args.threshold:
            source = r.get('source', 'unknown')
            text = r.get('text', '')[:100]

            # Tenta extrair table e id do source (formato: "table:id" ou similar)
            table_id = None
            if ':' in source:
                parts = source.split(':')
                if len(parts) >= 2 and parts[0] in ['memories', 'decisions', 'learnings']:
                    try:
                        table_id = (parts[0], int(parts[1]))
                    except ValueError:
                        pass

            score_color = Colors.GREEN if score > 0.8 else Colors.YELLOW
            print(f"  {c(f'[{score:.0%}]', score_color)} {c(source, Colors.CYAN)}")
            print(f"       {text}...")

            if table_id:
                to_delete.append(table_id)

            if args.execute and table_id:
                if delete_record(table_id[0], table_id[1]):
                    print(c(f"       -> Deletado!", Colors.RED))

    if not args.execute:
        print(f"\n{c('Use --execute para deletar os registros acima.', Colors.DIM)}")
        if to_delete:
            print(c(f"Encontrados {len(to_delete)} registros deletáveis.", Colors.DIM))


def cmd_help(args):
    """Mostra ajuda"""
    print("""
🧠 Claude Brain - Sistema de Memória Inteligente

╭─────────────────────────────────────────────────────────────╮
│ MEMÓRIA                                                     │
├─────────────────────────────────────────────────────────────┤
│ brain remember <texto>           Salva memória geral        │
│ brain decide <decisão>           Salva decisão arquitetural │
│ brain learn <erro> --solution X  Salva aprendizado de erro  │
│ brain solve <erro>               Busca solução para erro    │
│ brain recall [query]             Busca na memória           │
│ brain decisions                  Lista decisões             │
│ brain learnings                  Lista aprendizados         │
├─────────────────────────────────────────────────────────────┤
│ RAG (Busca Semântica)                                       │
├─────────────────────────────────────────────────────────────┤
│ brain index <path>               Indexa arquivo/diretório   │
│ brain search <query>             Busca semântica            │
│ brain context <query>            Contexto para Claude       │
│ brain related <arquivo>          Documentos relacionados    │
├─────────────────────────────────────────────────────────────┤
│ KNOWLEDGE GRAPH                                             │
├─────────────────────────────────────────────────────────────┤
│ brain entity <nome> <tipo>       Cria/atualiza entidade     │
│ brain relate <de> <para> <rel>   Cria relação               │
│ brain graph <entidade>           Mostra grafo               │
├─────────────────────────────────────────────────────────────┤
│ PREFERÊNCIAS & PADRÕES                                      │
├─────────────────────────────────────────────────────────────┤
│ brain prefer <chave> <valor>     Salva preferência          │
│ brain prefs                      Lista preferências         │
│ brain pattern <nome> <código>    Salva snippet              │
│ brain snippet <nome>             Busca snippet              │
├─────────────────────────────────────────────────────────────┤
│ DELETE                                                      │
├─────────────────────────────────────────────────────────────┤
│ brain delete <table> <id> [-f]   Deleta registro específico │
│ brain forget <query> [--execute] Busca e deleta registros   │
├─────────────────────────────────────────────────────────────┤
│ UTILIDADES                                                  │
├─────────────────────────────────────────────────────────────┤
│ brain export [--project X]       Exporta contexto           │
│ brain stats                      Estatísticas               │
╰─────────────────────────────────────────────────────────────╯

Opções comuns:
  --project, -p    Filtrar por projeto
  --limit, -l      Limitar resultados
  --type, -t       Filtrar por tipo

Exemplos:
  brain remember "Usuário prefere código conciso"
  brain decide "Usar FastAPI" -p meu-projeto --reason "Melhor performance"
  brain learn "ImportError" --solution "pip install X" --prevention "Verificar deps"
  brain index /root/meu-projeto
  brain search "como configurar auth"
  brain entity "redis" "technology" "Cache layer"
  brain relate "meu-projeto" "redis" "uses"
  brain delete decisions 15 -f
  brain forget "redis config" --execute
""")


def main():
    parser = argparse.ArgumentParser(description="Claude Brain CLI", add_help=False)
    subparsers = parser.add_subparsers(dest="command")

    # Memória
    p = subparsers.add_parser("remember")
    p.add_argument("text", nargs="*")
    p.add_argument("-c", "--category")
    p.add_argument("-i", "--importance", type=int)

    p = subparsers.add_parser("decide")
    p.add_argument("decision", nargs="*")
    p.add_argument("-p", "--project")
    p.add_argument("-r", "--reason")
    p.add_argument("-a", "--alternatives")
    p.add_argument("--fact", action="store_true", help="Marcar como fato estabelecido (já confirmado)")

    p = subparsers.add_parser("learn")
    p.add_argument("error", nargs="*")
    p.add_argument("-s", "--solution", required=True)
    p.add_argument("--prevention")
    p.add_argument("-p", "--project")
    p.add_argument("-c", "--context", help="O que estava fazendo quando o erro ocorreu")
    p.add_argument("--cause", help="Causa raiz do erro")
    p.add_argument("-m", "--message", help="Mensagem de erro completa")
    p.add_argument("--fact", action="store_true", help="Marcar como solução conhecida/documentada (já confirmada)")

    p = subparsers.add_parser("solve")
    p.add_argument("error", nargs="*")

    p = subparsers.add_parser("ask", help="Consulta inteligente (semantica + decisoes + learnings)")
    p.add_argument("query", nargs="*")

    p = subparsers.add_parser("recall")
    p.add_argument("query", nargs="*")
    p.add_argument("-t", "--type")
    p.add_argument("-l", "--limit", type=int)

    p = subparsers.add_parser("decisions")
    p.add_argument("-p", "--project")
    p.add_argument("-l", "--limit", type=int)

    p = subparsers.add_parser("learnings")
    p.add_argument("-l", "--limit", type=int)

    # RAG
    p = subparsers.add_parser("index")
    p.add_argument("path", nargs="*")
    p.add_argument("--no-recursive", action="store_true")

    p = subparsers.add_parser("search")
    p.add_argument("query", nargs="*")
    p.add_argument("-t", "--type")
    p.add_argument("-l", "--limit", type=int)

    p = subparsers.add_parser("context")
    p.add_argument("query", nargs="*")
    p.add_argument("--tokens", type=int)

    p = subparsers.add_parser("related")
    p.add_argument("source", nargs="*")
    p.add_argument("-l", "--limit", type=int)

    # Knowledge Graph
    p = subparsers.add_parser("entity")
    p.add_argument("name", nargs="*")

    p = subparsers.add_parser("relate")
    p.add_argument("relation", nargs="*")

    p = subparsers.add_parser("graph")
    p.add_argument("entity", nargs="*")

    # Preferências
    p = subparsers.add_parser("prefer")
    p.add_argument("pref", nargs="*")

    subparsers.add_parser("prefs")

    # Padrões
    p = subparsers.add_parser("pattern")
    p.add_argument("pattern", nargs="*")
    p.add_argument("--language", "-L")

    p = subparsers.add_parser("snippet")
    p.add_argument("name", nargs="*")

    # Utilidades
    p = subparsers.add_parser("export")
    p.add_argument("-p", "--project")

    subparsers.add_parser("stats")
    subparsers.add_parser("help")

    # Extrator de histórico
    p = subparsers.add_parser("extract")
    p.add_argument("--dry-run", action="store_true", help="Mostra o que seria extraído sem salvar")
    p.add_argument("-l", "--limit", type=int, default=10, help="Limite de sessões")

    # Métricas
    p = subparsers.add_parser("useful")
    p.add_argument("feedback", nargs="*")

    p = subparsers.add_parser("useless")
    p.add_argument("feedback", nargs="*")

    subparsers.add_parser("dashboard")

    # Sistema de maturação
    p = subparsers.add_parser("hypotheses", help="Lista conhecimentos não confirmados")
    p.add_argument("-l", "--limit", type=int, default=15)

    p = subparsers.add_parser("confirm", help="Confirma que conhecimento está correto")
    p.add_argument("table", nargs="?", choices=["decisions", "learnings", "memories"])
    p.add_argument("id", nargs="?", type=int)

    p = subparsers.add_parser("contradict", help="Marca conhecimento como incorreto")
    p.add_argument("table", nargs="?", choices=["decisions", "learnings", "memories"])
    p.add_argument("id", nargs="?", type=int)
    p.add_argument("-r", "--reason", help="Motivo da contradição")

    p = subparsers.add_parser("supersede", help="Substitui conhecimento antigo por novo")
    p.add_argument("table", nargs="?", choices=["decisions", "learnings", "memories"])
    p.add_argument("id", nargs="?", type=int)
    p.add_argument("-n", "--new", required=True, help="Novo conhecimento")
    p.add_argument("-r", "--reason", help="Motivo da substituição")

    p = subparsers.add_parser("maturity", help="Estatísticas de maturidade")

    # Delete
    p = subparsers.add_parser("delete", help="Deleta registro específico")
    p.add_argument("table", nargs="?", choices=["memories", "decisions", "learnings"])
    p.add_argument("id", nargs="?", type=int, help="ID do registro")
    p.add_argument("-f", "--force", action="store_true", help="Não pedir confirmação")

    # Forget (busca e deleta)
    p = subparsers.add_parser("forget", help="Busca e deleta registros")
    p.add_argument("query", nargs="*", help="Query de busca")
    p.add_argument("-t", "--table", choices=["memories", "decisions", "learnings"])
    p.add_argument("--threshold", type=float, default=0.8, help="Score mínimo para deletar")
    p.add_argument("--execute", action="store_true", help="Executar deleção (padrão é dry-run)")

    args = parser.parse_args()

    commands = {
        "remember": cmd_remember,
        "decide": cmd_decide,
        "learn": cmd_learn,
        "solve": cmd_solve,
        "ask": cmd_ask,
        "recall": cmd_recall,
        "decisions": cmd_decisions,
        "learnings": cmd_learnings,
        "index": cmd_index,
        "search": cmd_search,
        "context": cmd_context,
        "related": cmd_related,
        "entity": cmd_entity,
        "relate": cmd_relate,
        "graph": cmd_graph,
        "prefer": cmd_prefer,
        "prefs": cmd_prefs,
        "pattern": cmd_pattern,
        "snippet": cmd_snippet,
        "export": cmd_export,
        "stats": cmd_stats,
        "help": cmd_help,
        "useful": cmd_useful,
        "useless": cmd_useless,
        "dashboard": cmd_dashboard,
        "extract": cmd_extract,
        # Maturação
        "hypotheses": cmd_hypotheses,
        "confirm": cmd_confirm,
        "contradict": cmd_contradict,
        "supersede": cmd_supersede,
        "maturity": cmd_maturity,
        # Delete
        "delete": cmd_delete,
        "forget": cmd_forget,
    }

    # Robustez: Try/except global com exit codes apropriados
    try:
        if args.command in commands:
            commands[args.command](args)
        else:
            cmd_help(args)
    except KeyboardInterrupt:
        print("\n" + c("Interrompido pelo usuário.", Colors.DIM))
        sys.exit(130)
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
