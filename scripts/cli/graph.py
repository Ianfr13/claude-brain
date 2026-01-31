#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo Graph

Comandos do knowledge graph:
- cmd_entity: Cria/atualiza entidade
- cmd_relate: Cria relacao entre entidades
- cmd_graph: Mostra grafo de uma entidade
"""

from .base import Colors, c, print_header, print_success, print_error
from scripts.memory_store import save_entity, save_relation, get_entity_graph


def cmd_entity(args):
    """Cria ou atualiza uma entidade no knowledge graph.

    Entidades sao nos do grafo que representam projetos,
    tecnologias, pessoas, conceitos, etc.

    Args:
        args: Namespace do argparse contendo:
            - name (list[str]): Nome, tipo e descricao da entidade

    Returns:
        None. Imprime confirmacao de salvamento.

    Examples:
        $ brain entity redis technology "Cache em memoria"
        * Entidade 'redis' (technology) salva

        $ brain entity vsl-analysis project "Sistema de analise de VSL"
        * Entidade 'vsl-analysis' (project) salva
    """
    if not args.name:
        print_error("Uso: brain entity <nome> <tipo> [descricao]")
        return

    name = args.name[0]
    type_ = args.name[1] if len(args.name) > 1 else "unknown"
    desc = " ".join(args.name[2:]) if len(args.name) > 2 else None

    save_entity(name, type_, desc)
    print_success(f"Entidade '{name}' ({type_}) salva")


def cmd_relate(args):
    """Cria relacao entre duas entidades no knowledge graph.

    Relacoes conectam entidades, como "projeto usa tecnologia"
    ou "pessoa trabalha em projeto".

    Args:
        args: Namespace do argparse contendo:
            - relation (list[str]): [origem, destino, tipo_relacao]

    Returns:
        None. Imprime confirmacao da relacao criada.

    Examples:
        $ brain relate vsl-analysis pytorch uses
        * Relacao: vsl-analysis --[uses]--> pytorch

        $ brain relate joao meu-projeto maintains
        * Relacao: joao --[maintains]--> meu-projeto
    """
    if not args.relation or len(args.relation) < 3:
        print_error("Uso: brain relate <de> <para> <tipo>")
        return

    from_e, to_e, rel_type = args.relation[0], args.relation[1], args.relation[2]
    save_relation(from_e, to_e, rel_type)
    print_success(f"Relacao: {from_e} --[{rel_type}]--> {to_e}")


def cmd_graph(args):
    """Mostra o grafo de relacoes de uma entidade.

    Exibe todas as relacoes de entrada e saida de uma
    entidade no knowledge graph.

    Args:
        args: Namespace do argparse contendo:
            - entity (list[str]): Nome da entidade

    Returns:
        None. Imprime grafo com relacoes de entrada/saida.

    Examples:
        $ brain graph vsl-analysis
        vsl-analysis (project)
          Analise automatica de VSL

        Relacoes de saida:
          -> [uses] pytorch
          -> [uses] fastapi

        Relacoes de entrada:
          <- [maintains] joao
    """
    if not args.entity:
        print_error("Uso: brain graph <entidade>")
        return

    name = args.entity[0]
    graph = get_entity_graph(name)

    if not graph:
        print_error(f"Entidade nao encontrada: {name}")
        return

    e = graph["entity"]
    print_header(f"{e['name']} ({e['type']})")

    if e['description']:
        print(f"  {e['description']}")

    if graph["outgoing"]:
        print(f"\n{c('Relacoes de saida:', Colors.CYAN)}")
        for r in graph["outgoing"]:
            print(f"  -> [{r['relation_type']}] {r['to_entity']}")

    if graph["incoming"]:
        print(f"\n{c('Relacoes de entrada:', Colors.CYAN)}")
        for r in graph["incoming"]:
            print(f"  <- [{r['relation_type']}] {r['from_entity']}")
