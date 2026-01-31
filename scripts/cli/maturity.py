#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo Maturity

Comandos do sistema de maturacao de conhecimento:
- cmd_hypotheses: Lista hipoteses pendentes
- cmd_supersede: Substitui conhecimento antigo
- cmd_maturity: Estatisticas de maturidade
"""

from .base import Colors, c, print_header, print_success, print_error, print_info
from scripts.memory_store import (
    get_hypotheses, get_contradicted,
    supersede_knowledge, get_knowledge_by_maturity
)


def cmd_hypotheses(args):
    """Lista conhecimentos nao confirmados (hipoteses).

    Mostra decisoes e learnings que ainda precisam de
    validacao para aumentar sua confianca.

    Args:
        args: Namespace do argparse contendo:
            - limit (int, optional): Limite de resultados (default: 15)

    Returns:
        None. Imprime lista de hipoteses pendentes.

    Examples:
        $ brain hypotheses
        Hipoteses Pendentes (precisam validacao)
        [decisions#15] o 50%
           Usar Redis para cache...
           Usos: 2 | Criado: 2024-01-15

        $ brain hypotheses -l 5
        ...
    """
    hypotheses = get_hypotheses(limit=args.limit or 15)

    if not hypotheses:
        print_info("Nenhuma hipotese pendente. Tudo confirmado!")
        return

    print_header("Hipoteses Pendentes (precisam validacao)")

    for h in hypotheses:
        icon = "o" if h['maturity_status'] == 'hypothesis' else "?"
        score = f"{h['confidence_score']*100:.0f}%" if h['confidence_score'] else "50%"
        uses = h.get('times_used', 0)

        table_icon = {'decisions': '[D]', 'learnings': '[L]', 'memories': '[M]'}.get(h['source_table'], '?')

        print(f"\n{table_icon} [{h['source_table']}#{h['id']}] {c(icon, Colors.YELLOW)} {score}")
        print(f"   {h['summary'][:80]}...")
        print(c(f"   Usos: {uses} | Criado: {h['created_at'][:10]}", Colors.DIM))


def cmd_supersede(args):
    """Substitui um conhecimento antigo por versao atualizada.

    Cria novo registro e marca o antigo como deprecated.
    Util quando ha evolucao do conhecimento.

    Args:
        args: Namespace do argparse contendo:
            - table (str): Tabela (decisions|learnings|memories)
            - id (int): ID do registro antigo
            - new (str): Novo conhecimento
            - reason (str, optional): Motivo da substituicao

    Returns:
        None. Imprime ID do novo registro.

    Examples:
        $ brain supersede decisions 15 -n "Usar FAISS em vez de ChromaDB"
        * Substituido! Novo ID: 16
          Antigo #15 marcado como deprecated

        $ brain supersede learnings 3 -n "Nova solucao" -r "Versao antiga"
        ...
    """
    if not args.table or not args.id or not args.new:
        print_error("Uso: brain supersede <table> <id> --new 'novo conhecimento' [--reason 'motivo']")
        return

    new_id = supersede_knowledge(
        args.table, args.id,
        args.new,
        reason=args.reason
    )
    print_success(f"Substituido! Novo ID: {new_id}")
    print(c(f"  Antigo #{args.id} marcado como deprecated", Colors.DIM))


def cmd_maturity(args):
    """Mostra estatisticas de maturidade do conhecimento.

    Exibe quantos registros estao em cada estado de maturidade
    (hypothesis, testing, confirmed, deprecated).

    Args:
        args: Namespace do argparse (sem argumentos especificos)

    Returns:
        None. Imprime estatisticas por tabela e status.

    Examples:
        $ brain maturity
        Maturidade do Conhecimento

        DECISIONS
          * confirmed: 15
          o hypothesis: 97

        LEARNINGS
          * confirmed: 3
          o hypothesis: 9

        CONTRADITOS (revisar/remover):
          x [decisions#5] Usar ChromaDB...
    """
    print_header("Maturidade do Conhecimento")

    tables = ['decisions', 'learnings', 'memories']

    for table in tables:
        print(f"\n{c(table.upper(), Colors.CYAN)}")

        for status in ['confirmed', 'testing', 'hypothesis', 'deprecated']:
            items = get_knowledge_by_maturity(table, status=status, limit=100)
            count = len(items)
            if count > 0:
                icon = {'confirmed': '*', 'testing': '?', 'hypothesis': 'o', 'deprecated': 'x'}.get(status, '?')
                color = {'confirmed': Colors.GREEN, 'testing': Colors.YELLOW, 'hypothesis': Colors.DIM, 'deprecated': Colors.RED}.get(status, Colors.DIM)
                print(f"  {c(icon, color)} {status}: {count}")

    # Contraditos
    contradicted = get_contradicted(limit=5)
    if contradicted:
        print(f"\n{c('CONTRADITOS (revisar/remover):', Colors.RED)}")
        for item in contradicted[:3]:
            print(f"  x [{item['source_table']}#{item['id']}] {item['summary'][:50]}...")
