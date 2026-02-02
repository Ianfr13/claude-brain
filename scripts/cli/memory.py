#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo Memory

Comandos de memoria geral:
- cmd_remember: Salva memoria geral
- cmd_recall: Busca na memoria
- cmd_memories: Lista memorias (alias para recall sem query)
"""

from .base import Colors, c, print_header, print_success, print_error, print_info
from scripts.memory_store import save_memory, search_memories


def cmd_remember(args):
    """Salva uma memoria geral no banco de dados.

    Memorias sao informacoes gerais que nao se encaixam em decisoes
    ou aprendizados. Podem ser preferencias, fatos, observacoes, etc.

    Args:
        args: Namespace do argparse contendo:
            - text (list[str]): Texto da memoria a ser salva
            - category (str, optional): Categoria (default: "general" ou "geral")
            - importance (int, optional): Importancia 1-10 (default: 5)
            - project (str, optional): Projeto associado (se None, e conhecimento geral)

    Returns:
        None. Imprime mensagem de sucesso com ID ou erro.

    Examples:
        $ brain remember "Redis precisa pickle para objetos" -c geral
        * Memoria salva (ID: 1) [GERAL]

        $ brain remember "Nossa API usa TTL 24h" -p vsl-analysis
        * Memoria salva (ID: 2) [vsl-analysis]
    """
    if not args.text:
        print_error("Uso: brain remember <texto> [-c categoria] [-p projeto]")
        return

    text = " ".join(args.text)
    project = getattr(args, 'project', None)

    # Se tem projeto, e especifico; se nao tem, e geral
    if project:
        category = args.category or "workflow"
        metadata = {"project": project}
    else:
        category = args.category or "geral"
        metadata = {}

    importance = args.importance or 5

    mid = save_memory("general", text, category=category, importance=importance, metadata=metadata)

    scope = f"[{project}]" if project else "[GERAL]"
    print_success(f"Memoria salva (ID: {mid}) {scope}")


def cmd_recall(args):
    """Busca na memoria por texto ou tipo.

    Pesquisa nas memorias salvas usando correspondencia de texto
    e filtros opcionais por tipo.

    Args:
        args: Namespace do argparse contendo:
            - query (list[str], optional): Texto para buscar
            - type (str, optional): Filtrar por tipo de memoria
            - limit (int, optional): Limite de resultados (default: 10)

    Returns:
        None. Imprime lista de memorias encontradas.

    Examples:
        $ brain recall "preferencia"
        Memorias (3 resultados)
        [general] *****
          Usuario prefere respostas em portugues...

        $ brain recall -t decision -l 5
        Memorias (5 resultados)
        ...
    """
    query = " ".join(args.query) if args.query else None
    results = search_memories(
        query=query,
        type=args.type,
        limit=args.limit or 10
    )

    if not results:
        print_info("Nenhuma memoria encontrada.")
        return

    print_header(f"Memorias ({len(results)} resultados)")
    for r in results:
        importance = "*" * min(r['importance'], 5)
        mem_type = r['type']
        print(f"\n{c(f'[{mem_type}]', Colors.CYAN)} {importance}")
        print(f"  {r['content'][:200]}...")
        print(c(f"  Acessos: {r['access_count']} | {r['created_at'][:10]}", Colors.DIM))
