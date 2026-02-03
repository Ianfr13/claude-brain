#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo Graph

Comandos do knowledge graph:
- cmd_entity: Cria/atualiza entidade
- cmd_relate: Cria relacao entre entidades
- cmd_graph: Mostra grafo de uma entidade (com opções avançadas)
- cmd_graph_sync: Sincroniza SQLite com Neo4j
- cmd_graph_traverse: Traverse o grafo com profundidade e filtro de relacoes
- cmd_graph_path: Encontra caminho mais curto entre dois nos
- cmd_graph_pagerank: Calcula PageRank dos nos
- cmd_graph_stats: Mostra estatísticas do grafo
"""

from .base import Colors, c, print_header, print_success, print_error, print_info
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
    """Mostra o grafo de relacoes de uma entidade com suporte a subcomandos.

    Exibe todas as relacoes de entrada e saida de uma
    entidade no knowledge graph com opcoes avancadas.

    Args:
        args: Namespace do argparse contendo:
            - subcommand: sync, traverse, path, pagerank, stats
            - entity (list[str]): Nome da entidade

    Returns:
        None. Imprime grafo com relacoes de entrada/saida.

    Examples:
        $ brain graph traverse vsl-analysis --depth 2 --relation uses
        $ brain graph path vsl-analysis pytorch
        $ brain graph pagerank --top 10
        $ brain graph stats
    """
    if not args.entity:
        print_error("Uso: brain graph <entidade> [opcoes]")
        print_info("Subcomandos: traverse, path, pagerank, stats, sync")
        return

    # Checa se é um subcomando
    subcommand = args.entity[0] if args.entity else None

    if subcommand == "sync":
        _cmd_graph_sync(args)
    elif subcommand == "traverse":
        _cmd_graph_traverse(args)
    elif subcommand == "path":
        _cmd_graph_path(args)
    elif subcommand == "pagerank":
        _cmd_graph_pagerank(args)
    elif subcommand == "stats":
        _cmd_graph_stats(args)
    else:
        # Modo compatível: mostra grafo da entidade
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


def _get_all_relations():
    """Obtém todas as relações do banco de dados.

    Returns:
        list: Lista de relações ou lista vazia se não disponível
    """
    try:
        from scripts.memory import base
        db = base.get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM relations")
        rows = cursor.fetchall()

        # Converte rows para dicts
        columns = [description[0] for description in cursor.description]
        relations = [dict(zip(columns, row)) for row in rows]
        return relations
    except Exception:
        return []


def _cmd_graph_sync(args):
    """Sincroniza SQLite com Neo4j (se disponível).

    Args:
        args: Namespace do argparse

    Comando: brain graph sync
    """
    print_info("Sincronizando grafo com Neo4j...")

    try:
        from scripts.memory_store import get_all_entities

        entities = get_all_entities() if hasattr(get_all_entities, '__call__') else []
        relations = _get_all_relations()

        entity_list = entities if isinstance(entities, list) else []
        relation_list = relations if isinstance(relations, list) else []

        print_success(f"Grafo sincronizado: {len(entity_list)} entidades, {len(relation_list)} relacoes")

        # Aqui poderia fazer sync com Neo4j se configurado
        print_info("Neo4j sync nao configurado - dados armazenados em SQLite")
    except Exception as e:
        print_error(f"Erro ao sincronizar: {e}")


def _cmd_graph_traverse(args):
    """Traversa o grafo a partir de um nó.

    Uso: brain graph traverse <node_id> [--depth 2] [--relation uses]

    Args:
        args: Namespace do argparse com:
            - entity: [node_id, ...]
            - depth: profundidade da traversal (default: 2)
            - relation: tipo de relacao a filtrar (opcional)
    """
    if len(args.entity) < 2:
        print_error("Uso: brain graph traverse <node_id> [--depth 2] [--relation tipo]")
        return

    node_id = args.entity[1]
    depth = getattr(args, 'depth', 2)
    relation_filter = getattr(args, 'relation', None)

    print_header(f"Traversal a partir de '{node_id}' (profundidade {depth})")

    try:
        graph = get_entity_graph(node_id)
        if not graph:
            print_error(f"Entidade nao encontrada: {node_id}")
            return

        # Traversa o grafo com BFS
        visited = set()
        queue = [(node_id, 0, "root")]  # (node, distance, relation_type)

        while queue:
            current, dist, rel = queue.pop(0)

            if current in visited or dist > depth:
                continue

            visited.add(current)
            indent = "  " * dist

            if dist == 0:
                print(f"{indent}{c(current, Colors.CYAN)}")
            else:
                print(f"{indent}{c(f'--[{rel}]-->', Colors.DIM)} {current}")

            # Carrega relacoes do nó atual
            try:
                current_graph = get_entity_graph(current)
                if current_graph:
                    for r in current_graph.get("outgoing", []):
                        if relation_filter is None or r['relation_type'] == relation_filter:
                            if r['to_entity'] not in visited:
                                queue.append((r['to_entity'], dist + 1, r['relation_type']))
            except:
                pass

        print_success(f"Visitados {len(visited)} nos")
    except Exception as e:
        print_error(f"Erro na traversal: {e}")


def _cmd_graph_path(args):
    """Encontra caminho mais curto entre dois nós (BFS).

    Uso: brain graph path <source> <target>

    Args:
        args: Namespace do argparse com:
            - entity: [source, target, ...]
    """
    if len(args.entity) < 3:
        print_error("Uso: brain graph path <source> <target>")
        return

    source = args.entity[1]
    target = args.entity[2]

    print_header(f"Caminho mais curto: {source} → {target}")

    try:
        # BFS para encontrar caminho mais curto
        from collections import deque

        queue = deque([(source, [source])])
        visited = {source}
        path_found = None

        while queue and not path_found:
            current, path = queue.popleft()

            if current == target:
                path_found = path
                break

            current_graph = get_entity_graph(current)
            if current_graph:
                for r in current_graph.get("outgoing", []):
                    next_node = r['to_entity']
                    if next_node not in visited:
                        visited.add(next_node)
                        new_path = path + [f"--[{r['relation_type']}]--", next_node]
                        queue.append((next_node, new_path))

        if path_found:
            path_str = " ".join(path_found)
            print(f"  {path_str}")
            print_success(f"Distancia: {(len(path_found) - 1) // 2} hops")
        else:
            print_error(f"Nenhum caminho encontrado entre {source} e {target}")
    except Exception as e:
        print_error(f"Erro ao calcular caminho: {e}")


def _cmd_graph_pagerank(args):
    """Calcula PageRank dos nós no grafo.

    Uso: brain graph pagerank [--top 10]

    Args:
        args: Namespace do argparse com:
            - top: quantidade de top nós a mostrar (default: 10)
    """
    top = getattr(args, 'top', 10)

    print_header(f"PageRank - Top {top} nós")

    try:
        from scripts.memory_store import get_all_entities

        entities = get_all_entities() if hasattr(get_all_entities, '__call__') else []
        relations = _get_all_relations()

        entity_list = entities if isinstance(entities, list) else []

        if not entity_list:
            print_error("Nenhuma entidade encontrada")
            return

        # Calcula PageRank simples
        scores = {e.get('name', str(e)): 1.0 for e in entity_list}

        # Iteracoes do PageRank (simplificado)
        damping = 0.85
        for _ in range(3):  # 3 iteracoes
            new_scores = {}
            for entity in scores:
                try:
                    graph = get_entity_graph(entity)
                    if graph and graph.get("incoming"):
                        new_scores[entity] = (1 - damping) + damping * sum(
                            scores.get(r['from_entity'], 1.0) / len(graph.get("outgoing", [1]))
                            for r in graph.get("incoming", [])
                        )
                    else:
                        new_scores[entity] = (1 - damping)
                except:
                    new_scores[entity] = scores.get(entity, 1.0)
            scores = new_scores

        # Ordena por score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top]

        print(f"\n{c('Entity', Colors.CYAN):<30} {c('Score', Colors.CYAN):>10}")
        print("-" * 42)
        for entity, score in sorted_scores:
            print(f"{entity:<30} {score:>10.4f}")

        print_success(f"Total: {len(scores)} nós")
    except Exception as e:
        print_error(f"Erro ao calcular PageRank: {e}")


def _cmd_graph_stats(args):
    """Mostra estatísticas do grafo.

    Uso: brain graph stats

    Args:
        args: Namespace do argparse
    """
    print_header("Estatísticas do Grafo")

    try:
        from scripts.memory_store import get_all_entities

        entities = get_all_entities() if hasattr(get_all_entities, '__call__') else []
        relations = _get_all_relations()

        entity_list = entities if isinstance(entities, list) else []
        relation_list = relations if isinstance(relations, list) else []

        # Conta tipos de entidades
        entity_types = {}
        for e in entity_list:
            type_name = e.get('type', 'unknown') if isinstance(e, dict) else 'unknown'
            entity_types[type_name] = entity_types.get(type_name, 0) + 1

        # Conta tipos de relacoes
        relation_types = {}
        for r in relation_list:
            rel_type = r.get('relation_type', 'unknown') if isinstance(r, dict) else 'unknown'
            relation_types[rel_type] = relation_types.get(rel_type, 0) + 1

        print(f"\n{c('Nós (Entidades):', Colors.CYAN)}")
        print(f"  Total: {len(entity_list)}")
        for type_name, count in sorted(entity_types.items(), key=lambda x: x[1], reverse=True):
            print(f"    {type_name}: {count}")

        print(f"\n{c('Arestas (Relações):', Colors.CYAN)}")
        print(f"  Total: {len(relation_list)}")
        for rel_type, count in sorted(relation_types.items(), key=lambda x: x[1], reverse=True):
            print(f"    {rel_type}: {count}")

        # Calcula densidade
        if entity_list:
            max_edges = len(entity_list) * (len(entity_list) - 1)
            if max_edges > 0:
                density = len(relation_list) / max_edges
                print(f"\n{c('Densidade:', Colors.CYAN)} {density:.4f}")

        print_success("Estatísticas carregadas")
    except Exception as e:
        print_error(f"Erro ao carregar estatísticas: {e}")
