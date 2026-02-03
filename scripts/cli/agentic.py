#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo Agentic

Comando agentic-ask que usa:
1. Query decomposition: Quebra query complexa em sub-queries
2. Ensemble search: Busca em múltiplas fontes
3. Result consolidation: Consolida resultados

Usa Brain Job system para executar em background se necessário.
"""

import json
from typing import List, Dict, Any
from .base import Colors, c, print_header, print_success, print_error, print_info
from scripts.metrics import log_action


def decompose_query(query: str, max_sub_queries: int = 3) -> List[str]:
    """Decompõe uma query complexa em sub-queries.

    Estratégia:
    - Se contém 'AND': split por AND
    - Se contém 'OR': cria alternativas
    - Senão: retorna query original + variações
    """
    query = query.strip()

    # Estratégia 1: Split por AND
    if " and " in query.lower():
        parts = [p.strip() for p in query.split(" and ")]
        return parts[:max_sub_queries]

    # Estratégia 2: Split por OR
    if " or " in query.lower():
        parts = [p.strip() for p in query.split(" or ")]
        return parts[:max_sub_queries]

    # Estratégia 3: Query original + variações semânticas
    sub_queries = [query]

    # Tenta extrair palavras-chave e criar sub-queries
    words = query.split()
    if len(words) > 3:
        # Sub-query com primeiras 3 palavras
        sub_queries.append(" ".join(words[:3]))
        # Sub-query com últimas 3 palavras
        sub_queries.append(" ".join(words[-3:]))

    return sub_queries[:max_sub_queries]


def ensemble_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca em múltiplas fontes: decisions, learnings, RAG, entidades.

    Consolida resultados com scores de relevância.
    """
    results = []

    # Fonte 1: Decisions (via get_decisions)
    try:
        from scripts.memory_store import get_decisions, search_memories
        decisions = get_decisions(limit=3)

        # Filtra decisions por relevância à query
        for d in (decisions if isinstance(decisions, list) else []):
            decision_text = d.get('decision', str(d)) if isinstance(d, dict) else str(d)
            if query.lower() in decision_text.lower():
                results.append({
                    "type": "decision",
                    "source": "memory_store",
                    "content": decision_text,
                    "score": 0.8,
                })
    except Exception as e:
        print_info(f"Decisions search failed: {e}")

    # Fonte 2: Learnings (via find_solution)
    try:
        from scripts.memory_store import find_solution
        solution = find_solution(query)
        if solution:
            results.append({
                "type": "learning",
                "source": "memory_store",
                "content": solution.get('solution', str(solution)) if isinstance(solution, dict) else str(solution),
                "score": 0.75,
            })
    except Exception as e:
        print_info(f"Learnings search failed: {e}")

    # Fonte 3: RAG (busca semântica)
    try:
        from scripts.faiss_rag import semantic_search as rag_search
        rag_results = rag_search(query, limit=3)
        for r in (rag_results if isinstance(rag_results, list) else []):
            results.append({
                "type": "document",
                "source": "faiss_rag",
                "content": r.get('content', str(r)) if isinstance(r, dict) else str(r),
                "score": 0.7,
                "metadata": r.get('metadata', {}) if isinstance(r, dict) else {},
            })
    except Exception as e:
        print_info(f"RAG indisponível: {e}")

    # Fonte 4: Entidades
    try:
        from scripts.memory_store import get_entity_graph
        entity = get_entity_graph(query.split()[0])
        if entity:
            results.append({
                "type": "entity",
                "source": "knowledge_graph",
                "content": json.dumps(entity, indent=2),
                "score": 0.65,
            })
    except Exception as e:
        print_info(f"Entity graph search failed: {e}")

    # Ordena por score
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:limit]


def consolidate_results(sub_query_results: Dict[str, List[Dict]]) -> List[Dict]:
    """Consolida resultados de múltiplas sub-queries.

    Deduplication por conteúdo similar e merge de scores.
    """
    consolidated = {}

    for sub_query, results in sub_query_results.items():
        for result in results:
            # Cria chave de deduplicação (primeiros 100 chars)
            key = result.get("content", "")[:100]

            if key not in consolidated:
                consolidated[key] = result.copy()
                consolidated[key]["sub_queries"] = [sub_query]
            else:
                # Merge: aumenta score se encontrado em múltiplas sub-queries
                consolidated[key]["score"] = min(1.0, consolidated[key].get("score", 0.5) + 0.1)
                consolidated[key]["sub_queries"].append(sub_query)

    # Retorna consolidado ordenado por score
    results = list(consolidated.values())
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


def format_result(result: Dict, index: int = 0):
    """Formata resultado para exibição.

    Exibe: tipo, score, conteúdo, metadata.
    """
    result_type = result.get("type", "unknown")
    score = result.get("score", 0.0)
    content = result.get("content", "")
    sub_queries = result.get("sub_queries", [])

    # Header
    type_color = {
        "decision": Colors.CYAN,
        "learning": Colors.GREEN,
        "document": Colors.YELLOW,
        "entity": Colors.BLUE,
    }.get(result_type, Colors.YELLOW)

    print(f"\n{c(f'[{index + 1}] {result_type.upper()}', type_color)} "
          f"{c(f'(score: {score:.2f})', Colors.DIM)}")

    if sub_queries:
        print(f"    {c('Sub-queries:', Colors.DIM)} {', '.join(sub_queries)}")

    # Content (primeiras linhas)
    lines = content.split("\n")
    for line in lines[:5]:  # Max 5 linhas
        if line.strip():
            print(f"    {line}")

    if len(lines) > 5:
        print(f"    {c('... (mais linhas)', Colors.DIM)}")

    # Metadata
    metadata = result.get("metadata", {})
    if metadata:
        print(f"    {c('Metadata:', Colors.DIM)} {metadata}")


def cmd_agentic_ask(args):
    """Busca inteligente com decomposição de queries e ensemble search.

    Fluxo:
    1. Decompõe query complexa em sub-queries
    2. Busca cada sub-query em múltiplas fontes
    3. Consolida e deduplicata resultados
    4. Exibe com formatação bonita

    Uso: brain agentic-ask '<query>' [-p projeto] [--explain]

    Args:
        args: Namespace do argparse com:
            - query (list[str]): Query para buscar
            - project: Projeto específico (opcional)
            - explain: Mostra explicação do processo (default: False)

    Examples:
        $ brain agentic-ask 'redis cache ttl'
        $ brain agentic-ask 'fastapi dependency injection' -p vsl-analysis
        $ brain agentic-ask 'deployment issues and solutions' --explain
    """
    if not args.query:
        print_error("Uso: brain agentic-ask '<query>' [-p projeto] [--explain]")
        return

    query = " ".join(args.query)
    project = getattr(args, 'project', None)
    explain = getattr(args, 'explain', False)

    print_header("Busca Inteligente (Agentic Ask)")
    print(f"Query: {c(query, Colors.CYAN)}")

    if project:
        print(f"Projeto: {c(project, Colors.CYAN)}")

    # Log da busca
    log_action("agentic_ask", query, project=project)

    # Passo 1: Decompõe query
    if explain:
        print(f"\n{c('Passo 1: Decomposição de Query', Colors.BOLD)}")

    sub_queries = decompose_query(query, max_sub_queries=3)

    if explain:
        print(f"  Sub-queries geradas: {len(sub_queries)}")
        for i, sq in enumerate(sub_queries, 1):
            print(f"    {i}. {sq}")

    # Passo 2: Ensemble search
    if explain:
        print(f"\n{c('Passo 2: Ensemble Search (múltiplas fontes)', Colors.BOLD)}")

    sub_query_results = {}
    for sub_query in sub_queries:
        if explain:
            print(f"  Buscando: {sub_query}")

        try:
            results = ensemble_search(sub_query, limit=5)
            sub_query_results[sub_query] = results

            if explain:
                print(f"    → {len(results)} resultados encontrados")
        except Exception as e:
            print_error(f"Erro ao buscar '{sub_query}': {e}")
            sub_query_results[sub_query] = []

    # Passo 3: Consolidação
    if explain:
        print(f"\n{c('Passo 3: Consolidação e Deduplicação', Colors.BOLD)}")

    consolidated = consolidate_results(sub_query_results)

    if explain:
        print(f"  Resultados consolidados: {len(consolidated)}")

    # Exibição final
    print(f"\n{c('═' * 50, Colors.DIM)}")
    print(f"{c('RESULTADOS', Colors.BOLD)}: {len(consolidated)} encontrados\n")

    if not consolidated:
        print_error("Nenhum resultado encontrado")
        return

    for i, result in enumerate(consolidated[:10]):  # Max 10 resultados
        format_result(result, i)

    print(f"\n{c('═' * 50, Colors.DIM)}")
    print_success(f"Busca completada: {len(consolidated)} resultado(s) relevante(s)")

    if explain:
        print(f"\n{c('Estatísticas:', Colors.DIM)}")
        print(f"  Sub-queries processadas: {len(sub_queries)}")
        print(f"  Fontes consultadas: Decisions, Learnings, RAG, Entities")
        print(f"  Tempo de resposta: ~instant (local)")
