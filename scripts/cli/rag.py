#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo RAG

Comandos de busca semantica e indexacao:
- cmd_index: Indexa arquivo/diretorio
- cmd_search: Busca semantica
- cmd_context: Retorna contexto para Claude
- cmd_ask: Consulta inteligente combinada
- cmd_related: Encontra documentos relacionados
"""

from pathlib import Path

from .base import (
    Colors, c, print_header, print_success, print_error, print_info,
    ALLOWED_INDEX_PATHS, is_path_allowed
)
from scripts.rag_engine import (
    index_file, index_directory,
    search as simple_search,
    get_context_for_query as simple_context
)
from scripts.memory_store import get_decisions, find_solution
from scripts.memory import rank_results, detect_conflicts
from scripts.metrics import log_action

# Tenta usar FAISS para busca semantica
try:
    from scripts.faiss_rag import (
        semantic_search,
        get_context_for_query as faiss_context
    )
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False


def search(query, doc_type=None, limit=5):
    """Busca hibrida: FAISS se disponivel, senao simples"""
    if HAS_FAISS:
        return semantic_search(query, doc_type, limit)
    return simple_search(query, doc_type, limit)


def get_context_for_query(query, max_tokens=2000):
    """Contexto hibrido"""
    if HAS_FAISS:
        return faiss_context(query, max_tokens)
    return simple_context(query, max_tokens)


def cmd_index(args):
    """Indexa arquivo ou diretorio para busca semantica.

    Processa arquivos de texto/codigo e cria embeddings para
    permitir busca semantica posterior via brain search.

    Args:
        args: Namespace do argparse contendo:
            - path (list[str]): Caminho do arquivo ou diretorio
            - no_recursive (bool): Nao indexar subdiretorios

    Returns:
        None. Imprime progresso e total de chunks indexados.

    Examples:
        $ brain index /root/meu-projeto
        i Indexando diretorio: /root/meu-projeto
        * Indexados: 42 arquivos

        $ brain index README.md
        i Indexando arquivo: README.md
        * Indexado: 5 chunks

    Notes:
        Apenas paths permitidos podem ser indexados (seguranca).
    """
    if not args.path:
        print_error("Uso: brain index <arquivo|diretorio>")
        return

    path = Path(args.path[0])

    # Validacao de seguranca contra path traversal
    if not is_path_allowed(path):
        print_error(f"Path nao permitido: {path}")
        print_info("Diretorios permitidos:")
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
        print_info(f"Indexando diretorio: {path}")
        print()
        count = index_directory(str(path), recursive=not args.no_recursive)
        print()
        print_success(f"Indexados: {count} arquivos")

    else:
        print_error(f"Nao encontrado: {path}")


def cmd_search(args):
    """Busca semantica nos documentos indexados.

    Usa embeddings e FAISS para encontrar documentos semanticamente
    similares a query, independente de palavras-chave exatas.

    Args:
        args: Namespace do argparse contendo:
            - query (list[str]): Texto da busca
            - type (str, optional): Filtrar por tipo de documento
            - limit (int, optional): Limite de resultados (default: 5)

    Returns:
        None. Imprime resultados com score de similaridade.

    Examples:
        $ brain search "como configurar autenticacao"
        Resultados para: 'como configurar autenticacao'
        [0.85] auth/README.md
          Configure o JWT secret em .env...

        $ brain search "deploy docker" -l 10
        ...
    """
    if not args.query:
        print_error("Uso: brain search <query>")
        return

    query = " ".join(args.query)
    results = search(query, doc_type=args.type, limit=args.limit or 5)

    # Log da acao
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

    print(c(f"\nFoi util? brain useful | brain useless", Colors.DIM))


def cmd_context(args):
    """Retorna contexto formatado para injecao no Claude.

    Busca e formata contexto relevante para ser usado
    como input adicional em conversas com o Claude.

    Args:
        args: Namespace do argparse contendo:
            - query (list[str]): Texto da busca
            - tokens (int, optional): Limite de tokens (default: 2000)

    Returns:
        None. Imprime contexto formatado ou mensagem de vazio.

    Examples:
        $ brain context "deploy kubernetes"
        # Contexto relevante:
        ...documentos sobre kubernetes...

        $ brain context "api rest" --tokens 1000
        ...
    """
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
    """Consulta inteligente que combina todas as fontes com ranking automático.

    Busca em learnings, decisoes e documentos para fornecer
    a melhor resposta possivel para a duvida do usuario.

    Se -p project fornecido, prioriza contexto do projeto especificado.

    Implementa:
    - Ranking por score composto (especificidade, recência, confiança, uso, validação)
    - Detecção automática de conflitos (resultados com scores próximos)

    Args:
        args: Namespace do argparse contendo:
            - query (list[str]): Pergunta ou duvida
            - project (str, optional): Projeto para priorizar contexto

    Returns:
        None. Imprime resultados rankos com detecção de conflitos.

    Examples:
        $ brain ask "como resolver ModuleNotFoundError" -p vsl-analysis
        MELHOR RESULTADO:
        * 85% ModuleNotFoundError → pip install <pacote>

        OUTRAS SOLUÇÕES:
        o 65% (CONFLITO) ConnectionError → verificar redis-server

        $ brain ask "qual banco de dados usar"
        ...
    """
    if not args.query:
        print_error("Uso: brain ask <pergunta> [-p projeto]")
        return

    query = " ".join(args.query)
    project = getattr(args, 'project', None)

    # Coleta resultados de todas as fontes
    all_results = []

    # 1. Busca em learnings (erros/solucoes)
    solution = find_solution(error_type=query, error_message=query, similarity_threshold=0.4, project=project)
    if solution:
        solution['_type'] = 'learning'
        solution['_display_name'] = f"{solution.get('error_type')} → {solution.get('solution', '')[:50]}"
        all_results.append(solution)

    # 2. Busca em decisoes
    decisions = get_decisions(project=project, limit=50)
    if not decisions and project:
        decisions = get_decisions(project=None, limit=50)

    # Filtra decisões relevantes à query
    query_words = set(query.lower().split())
    for d in decisions:
        text = f"{d['decision']} {d.get('reasoning', '')} {d.get('project', '')}".lower()
        if any(word in text for word in query_words if len(word) > 3):
            d['_type'] = 'decision'
            d['_display_name'] = d.get('decision', '')[:70]
            all_results.append(d)

    # 3. Busca semantica nos docs
    doc_results = search(query, limit=3)
    for r in doc_results:
        r['_type'] = 'document'
        r['_display_name'] = f"{r.get('source', '')} - {r.get('text', '')[:40]}"
        # Converte score do RAG em confidence_score
        if 'score' in r:
            r['confidence_score'] = r['score']
        all_results.append(r)

    if not all_results:
        print(c("\nNada encontrado no brain para essa query.", Colors.RED))
        print(c("   Apos resolver, salve com: brain learn/decide", Colors.DIM))
        return

    # Rankeia todos os resultados por score composto
    ranked = rank_results(all_results, query, project)

    # Detecta conflitos
    conflicts = detect_conflicts(ranked, threshold=0.10)

    # Exibe resultados
    print_header(f"Resultados para: '{query}'")

    # Mostra top 1 resultado
    if ranked:
        top = ranked[0]
        score = top.get('relevance_score', 0)
        status_icon = "*" if top.get('maturity_status') == 'confirmed' else "o"
        proj = f" [{top.get('project')}]" if top.get('project') else ""
        type_label = top.get('_type', 'unknown').upper()

        print(f"\n{c('MELHOR RESULTADO:', Colors.GREEN)} {status_icon} {score*100:.0f}% [{type_label}]{proj}")
        print(f"   {top.get('_display_name', '')}")

        if top.get('_type') == 'learning':
            if top.get('solution'):
                print(f"   Solucao: {top['solution']}")
            if top.get('prevention'):
                print(f"   Prevencao: {top['prevention']}")

    # Mostra outros resultados (top 2-4)
    if len(ranked) > 1:
        print(f"\n{c('OUTRAS OPCOES:', Colors.CYAN)}")
        for i, r in enumerate(ranked[1:4], 1):
            score = r.get('relevance_score', 0)
            status_icon = "*" if r.get('maturity_status') == 'confirmed' else "o"
            conflict_warn = " (CONFLITO)" if any(c[1] == r for c in conflicts) else ""
            type_label = r.get('_type', 'unknown').upper()
            proj = f" [{r.get('project')}]" if r.get('project') else ""

            print(f"\n   {status_icon} {score*100:.0f}%{conflict_warn} [{type_label}]{proj}")
            print(f"      {r.get('_display_name', '')[:60]}")

    # Aviso se houver conflitos
    if conflicts:
        print(f"\n{c('⚠ CONFLITOS DETECTADOS:', Colors.YELLOW)}")
        print(c("   Resultados com scores muito próximos - ambiguidade na busca", Colors.DIM))
        print(c("   Considere: brain decide, brain learn (para validar escolha)", Colors.DIM))

    # Log da acao
    log_action("ask", query=query, results_count=len(ranked), project=project)

    print(c(f"\nUtil? brain useful | Errado? brain contradict <table> <id>", Colors.DIM))


def cmd_related(args):
    """Encontra documentos relacionados por similaridade.

    Busca documentos semanticamente similares ao arquivo
    especificado, util para descobrir dependencias.

    Args:
        args: Namespace do argparse contendo:
            - source (list[str]): Caminho do arquivo fonte
            - limit (int, optional): Limite de resultados (default: 5)

    Returns:
        None. Imprime lista de documentos relacionados com score.

    Examples:
        $ brain related auth/login.py
        Documentos relacionados a: auth/login.py
          [0.82] auth/jwt.py
          [0.75] tests/test_auth.py
          [0.68] docs/AUTH.md
    """
    if not args.source:
        print_error("Uso: brain related <arquivo>")
        return

    source = args.source[0]
    # Busca documentos similares usando o nome do arquivo como query
    filename = Path(source).stem
    results = search(filename, limit=args.limit or 5)

    if not results:
        print_info("Nenhum documento relacionado encontrado.")
        return

    print_header(f"Documentos relacionados a: {source}")
    for r in results:
        if r['source'] != source:  # Exclui o proprio arquivo
            score = r.get('score', 0)
            score_str = f"{score:.2f}" if isinstance(score, float) else str(score)
            print(f"  [{score_str}] {r['source']}")
