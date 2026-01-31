#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo Decisions

Comandos de decisoes arquiteturais:
- cmd_decide: Salva decisao arquitetural
- cmd_decisions: Lista decisoes
- cmd_confirm: Confirma que decisao esta correta
- cmd_contradict: Marca decisao como incorreta
"""

from .base import Colors, c, print_header, print_success, print_error, print_info
from scripts.memory_store import (
    save_decision, get_decisions,
    confirm_knowledge, contradict_knowledge
)
from scripts.metrics import log_action


def cmd_decide(args):
    """Salva uma decisao arquitetural no banco de dados.

    Decisoes sao escolhas tecnicas importantes que afetam o projeto,
    como escolha de tecnologias, padroes de design, etc.

    Args:
        args: Namespace do argparse contendo:
            - decision (list[str]): Texto da decisao
            - project (str, optional): Nome do projeto
            - reason (str, optional): Justificativa da decisao
            - alternatives (str, optional): Alternativas consideradas
            - fact (bool): Se True, marca como fato ja confirmado

    Returns:
        None. Imprime sucesso com ID e status (hipotese/fato).

    Examples:
        $ brain decide "Usar FastAPI para API REST" -p meu-projeto
        * Decisao salva (ID: 1) como hipotese

        $ brain decide "Python 3.12 e a versao minima" --fact
        * Fato salvo (ID: 2) ja confirmado
    """
    if not args.decision:
        print_error("Uso: brain decide <decisao> [--project X] [--reason Y] [--fact]")
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
        print_success(f"Fato salvo (ID: {did}) ja confirmado")
    else:
        print_success(f"Decisao salva (ID: {did}) como hipotese")


def cmd_decisions(args):
    """Lista decisoes arquiteturais salvas.

    Exibe todas as decisoes registradas, opcionalmente filtradas
    por projeto, mostrando status e justificativa.

    Args:
        args: Namespace do argparse contendo:
            - project (str, optional): Filtrar por projeto
            - limit (int, optional): Limite de resultados (default: 10)

    Returns:
        None. Imprime lista de decisoes com status e data.

    Examples:
        $ brain decisions
        Decisoes Arquiteturais
        [meu-projeto] Usar FastAPI para API REST
          Razao: Suporte async nativo
          Status: active | 2024-01-15

        $ brain decisions -p vsl-analysis -l 5
        ...
    """
    decisions = get_decisions(project=args.project, limit=args.limit or 10)

    if not decisions:
        print_info("Nenhuma decisao encontrada.")
        return

    print_header("Decisoes Arquiteturais")
    for d in decisions:
        proj = c(f"[{d['project']}]", Colors.YELLOW) if d['project'] else ""
        status = c(d['status'], Colors.GREEN if d['status'] == 'active' else Colors.DIM)
        print(f"\n{proj} {d['decision']}")
        if d['reasoning']:
            print(c(f"  Razao: {d['reasoning']}", Colors.DIM))
        print(c(f"  Status: {status} | {d['created_at'][:10]}", Colors.DIM))


def cmd_confirm(args):
    """Confirma que um conhecimento esta correto.

    Aumenta a confianca de uma decisao/learning, movendo
    de hipotese para confirmado apos validacao.

    Args:
        args: Namespace do argparse contendo:
            - table (str): Tabela (decisions|learnings|memories)
            - id (int): ID do registro

    Returns:
        None. Imprime novo score de confianca.

    Examples:
        $ brain confirm decisions 15
        * Confirmado! Nova confianca: 85%

        $ brain confirm learnings 3
        * Confirmado! Nova confianca: 90%
    """
    if not args.table or not args.id:
        print_error("Uso: brain confirm <decisions|learnings|memories> <id>")
        return

    table = args.table
    record_id = args.id

    new_score = confirm_knowledge(table, record_id)
    print_success(f"Confirmado! Nova confianca: {new_score*100:.0f}%")


def cmd_contradict(args):
    """Marca um conhecimento como incorreto ou desatualizado.

    Reduz a confianca e marca como contradito. Use quando
    descobrir que uma decisao/learning esta errado.

    Args:
        args: Namespace do argparse contendo:
            - table (str): Tabela (decisions|learnings|memories)
            - id (int): ID do registro
            - reason (str, optional): Motivo da contradicao

    Returns:
        None. Imprime confirmacao.

    Examples:
        $ brain contradict decisions 15 -r "Nao funciona em Docker"
        x Marcado como contradito/incorreto
          Motivo: Nao funciona em Docker

        $ brain contradict learnings 3
        x Marcado como contradito/incorreto
    """
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
