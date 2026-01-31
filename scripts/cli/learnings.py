#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo Learnings

Comandos de aprendizados de erros:
- cmd_learn: Salva aprendizado erro/solucao
- cmd_learnings: Lista aprendizados
- cmd_solve: Busca solucao para erro
"""

from .base import Colors, c, print_header, print_success, print_error, print_info
from scripts.memory_store import save_learning, get_all_learnings, find_solution
from scripts.metrics import log_action


def cmd_learn(args):
    """Salva um aprendizado de erro/solucao no banco de dados.

    Learnings sao pares erro-solucao que permitem ao brain lembrar
    como resolver problemas que ja foram enfrentados antes.

    Args:
        args: Namespace do argparse contendo:
            - error (list[str]): Tipo/nome do erro
            - solution (str): Solucao aplicada (obrigatorio)
            - context (str, optional): O que estava fazendo
            - cause (str, optional): Causa raiz do erro
            - prevention (str, optional): Como evitar no futuro
            - project (str, optional): Projeto relacionado
            - message (str, optional): Mensagem de erro completa
            - fact (bool): Se True, marca como solucao ja confirmada

    Returns:
        None. Imprime sucesso com ID e status (hipotese/fato).

    Examples:
        $ brain learn "ModuleNotFoundError" -s "pip install torch"
        * Aprendizado salvo (ID: 1) como hipotese

        $ brain learn "CUDA OOM" -s "Reduzir batch size" -c "Treinando modelo"
        * Aprendizado salvo (ID: 2) como hipotese
    """
    if not args.error or not args.solution:
        print_error("Uso: brain learn <erro> --solution <solucao> [-c contexto] [--cause causa] [--fact]")
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
        print_success(f"Solucao conhecida salva (ID: {lid}) ja confirmada")
    else:
        print_success(f"Aprendizado salvo (ID: {lid}) como hipotese")


def cmd_solve(args):
    """Busca solucao para um erro no banco de learnings.

    Pesquisa nos aprendizados salvos para encontrar solucoes
    conhecidas para o erro especificado.

    Args:
        args: Namespace do argparse contendo:
            - error (list[str]): Tipo ou mensagem de erro

    Returns:
        None. Imprime solucao encontrada ou mensagem de nao encontrado.

    Examples:
        $ brain solve "ModuleNotFoundError torch"
        Solucao Encontrada
        Erro: ModuleNotFoundError
        Solucao: pip install torch
        Frequencia: 3 ocorrencias

        $ brain solve "erro desconhecido"
        i Nenhuma solucao encontrada para este erro.
    """
    if not args.error:
        print_error("Uso: brain solve <erro>")
        return

    error = " ".join(args.error)
    solution = find_solution(error_type=error, error_message=error)

    if solution:
        print_header("Solucao Encontrada")
        print(f"{c('Erro:', Colors.YELLOW)} {solution['error_type']}")
        print(f"{c('Solucao:', Colors.GREEN)} {solution['solution']}")
        if solution['prevention']:
            print(f"{c('Prevencao:', Colors.BLUE)} {solution['prevention']}")
        print(f"{c('Frequencia:', Colors.DIM)} {solution['frequency']} ocorrencias")
    else:
        print_info("Nenhuma solucao encontrada para este erro.")


def cmd_learnings(args):
    """Lista aprendizados de erros salvos.

    Exibe todos os pares erro-solucao registrados, mostrando
    contexto, causa raiz e frequencia de ocorrencia.

    Args:
        args: Namespace do argparse contendo:
            - limit (int, optional): Limite de resultados (default: 10)

    Returns:
        None. Imprime lista de learnings com frequencia.

    Examples:
        $ brain learnings
        Aprendizados de Erros
        ModuleNotFoundError (3x)
          Contexto: Iniciando projeto novo
          Solucao: pip install <pacote>
          Prevencao: requirements.txt atualizado

        $ brain learnings -l 5
        ...
    """
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
        print(f"  {c('Solucao:', Colors.GREEN)} {l['solution']}")
        if l.get('prevention'):
            print(f"  {c('Prevencao:', Colors.BLUE)} {l['prevention']}")
