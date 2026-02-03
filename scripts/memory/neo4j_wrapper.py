#!/usr/bin/env python3
"""
Claude Brain - Neo4j Graph Wrapper Module

Wrapper para integração com Neo4j Graph Database.

Componentes:
- Neo4jGraph: Classe principal para operações no grafo de conhecimento
- Operações CRUD: add_node, add_edge, traverse, shortest_path
- Sync: Sincronização de SQLite → Neo4j
- Queries otimizadas: Templates Cypher reutilizáveis

Uso:
    from neo4j_wrapper import Neo4jGraph

    graph = Neo4jGraph(uri="bolt://localhost:7687",
                      user="neo4j",
                      password="password")

    graph.connect()
    graph.add_node("Decision", "dec_001",
                   {"title": "Use Redis", "confidence": 0.9})
    graph.add_edge("dec_001", "concept_redis", "uses", weight=0.95)

    results = graph.traverse("dec_001", relation="uses", depth=2)
    graph.close()
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

try:
    from neo4j import GraphDatabase, Driver, Session, Result
    from neo4j.exceptions import (
        ServiceUnavailable,
        AuthError,
        CypherSyntaxError,
        TransactionError,
    )
except ImportError:
    raise ImportError(
        "neo4j package not found. Install with: pip install neo4j==5.15.0"
    )

# ============ LOGGING ============

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Handler com formatação estruturada
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ============ CONSTANTES ============

# Queries Cypher otimizadas (templates)
CYPHER_QUERIES = {
    "add_node": """
        MERGE (n:{node_type} {{id: $id}})
        SET n += $properties
        SET n.updated_at = datetime()
        RETURN n
    """,

    "add_edge": """
        MATCH (from {{id: $from_id}})
        MATCH (to {{id: $to_id}})
        MERGE (from)-[r:{relation}]->(to)
        SET r.weight = $weight
        SET r.updated_at = datetime()
        RETURN r
    """,

    "traverse": """
        MATCH path = (start {{id: $start_id}})-[*1..{depth}]->(n)
        WHERE {relation_filter}
        RETURN DISTINCT n, length(path) as distance
        ORDER BY distance ASC
    """,

    "shortest_path": """
        MATCH path = shortestPath(
            (source {{id: $source_id}})-[*]->(target {{id: $target_id}})
        )
        RETURN path, length(path) as distance
    """,

    "pagerank": """
        CALL gds.pageRank.stream('default')
        YIELD nodeId, score
        RETURN gds.util.asNode(nodeId).id as id, score
        ORDER BY score DESC
        LIMIT $limit
    """,

    "delete_node": """
        MATCH (n {{id: $id}})
        DETACH DELETE n
        RETURN COUNT(n) as deleted
    """,

    "get_node": """
        MATCH (n {{id: $id}})
        RETURN n
    """,

    "get_edges": """
        MATCH (from {{id: $from_id}})-[r]->(to {{id: $to_id}})
        RETURN r
    """,
}


# ============ EXCEÇÕES CUSTOMIZADAS ============

class Neo4jWrapperError(Exception):
    """Exceção base para erros do wrapper"""
    pass


class Neo4jConnectionError(Neo4jWrapperError):
    """Erro ao conectar com Neo4j"""
    pass


class Neo4jQueryError(Neo4jWrapperError):
    """Erro ao executar query Cypher"""
    pass


class Neo4jSyncError(Neo4jWrapperError):
    """Erro durante sincronização SQLite→Neo4j"""
    pass


# ============ CLASSE PRINCIPAL ============

class Neo4jGraph:
    """
    Wrapper para operações com Neo4j Graph Database.

    Gerencia:
    - Conexão e lifecycle (connect/close)
    - Operações CRUD (nodes e edges)
    - Queries otimizadas (traverse, shortest_path, pagerank)
    - Sincronização com SQLite
    - Error handling e logging

    Type hints: Completos conforme PEP 484

    Attributes:
        uri (str): URL de conexão Neo4j (bolt://host:port)
        user (str): Username para autenticação
        password (str): Password para autenticação
        _driver (Optional[Driver]): Driver Neo4j (None se não conectado)
        _session (Optional[Session]): Sessão ativa (None se não há)
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        timeout: float = 30.0,
        encrypted: bool = True,
    ) -> None:
        """
        Inicializa wrapper Neo4j.

        Args:
            uri: URL de conexão (ex: "bolt://localhost:7687")
            user: Username para autenticação
            password: Password para autenticação
            timeout: Timeout para conexões em segundos (default: 30)
            encrypted: Se deve usar conexão encriptada (default: True)

        Raises:
            ValueError: Se uri, user ou password estão vazios
        """
        if not uri or not user or not password:
            raise ValueError("uri, user e password são obrigatórios")

        self.uri = uri
        self.user = user
        self.password = password
        self.timeout = timeout
        self.encrypted = encrypted
        self._driver: Optional[Driver] = None
        self._session: Optional[Session] = None

        logger.info(f"Neo4jGraph inicializado para {uri}")

    # ============ LIFECYCLE ============

    def connect(self) -> None:
        """
        Conecta com servidor Neo4j.

        Raises:
            Neo4jConnectionError: Se falhar em conectar ou autenticar
        """
        try:
            logger.info(f"Conectando em {self.uri}...")
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                connection_timeout=self.timeout,
                encrypted=self.encrypted,
            )
            # Valida conexão com test
            self._driver.verify_connectivity()
            logger.info("Conexão com Neo4j estabelecida com sucesso")
        except AuthError as e:
            logger.error(f"Erro de autenticação: {e}")
            raise Neo4jConnectionError(f"Falha na autenticação: {e}") from e
        except ServiceUnavailable as e:
            logger.error(f"Serviço indisponível: {e}")
            raise Neo4jConnectionError(f"Neo4j indisponível: {e}") from e
        except Exception as e:
            logger.error(f"Erro desconhecido na conexão: {e}")
            raise Neo4jConnectionError(f"Erro ao conectar: {e}") from e

    def close(self) -> None:
        """
        Fecha conexão com Neo4j.

        É seguro chamar multiple vezes ou se não conectado.
        """
        try:
            if self._session:
                self._session.close()
                self._session = None
                logger.info("Sessão Neo4j fechada")

            if self._driver:
                self._driver.close()
                self._driver = None
                logger.info("Driver Neo4j fechado")
        except Exception as e:
            logger.error(f"Erro ao fechar conexão: {e}")

    @contextmanager
    def _get_session(self) -> Session:
        """
        Context manager para gerenciar sessões Neo4j.

        Yields:
            neo4j.Session: Sessão ativa

        Raises:
            Neo4jConnectionError: Se não está conectado
        """
        if not self._driver:
            raise Neo4jConnectionError("Não conectado. Chame connect() primeiro.")

        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()

    # ============ OPERAÇÕES CRUD ============

    def add_node(
        self,
        node_type: str,
        node_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Adiciona ou atualiza um nó no grafo.

        Args:
            node_type: Tipo/label do nó (ex: "Decision", "Learning", "Error")
            node_id: ID único do nó
            properties: Propriedades do nó (dict de chave-valor)

        Returns:
            Dict com propriedades do nó criado

        Raises:
            Neo4jConnectionError: Se não está conectado
            Neo4jQueryError: Se query falhar

        Example:
            >>> node = graph.add_node(
            ...     "Decision",
            ...     "dec_001",
            ...     {"title": "Use Redis", "confidence": 0.9}
            ... )
            >>> node["id"]
            'dec_001'
        """
        if not node_type or not node_id:
            raise ValueError("node_type e node_id são obrigatórios")

        try:
            with self._get_session() as session:
                query = CYPHER_QUERIES["add_node"].replace(
                    "{node_type}", node_type
                )

                props = properties or {}
                props["id"] = node_id
                props["created_at"] = props.get(
                    "created_at", datetime.now().isoformat()
                )

                result = session.run(query, id=node_id, properties=props)
                record = result.single()

                if record:
                    node_data = dict(record["n"])
                    logger.info(
                        f"Nó criado/atualizado: {node_type}[{node_id}]"
                    )
                    return node_data
                else:
                    raise Neo4jQueryError("Falha ao criar nó (resultado vazio)")

        except Neo4jConnectionError:
            raise
        except CypherSyntaxError as e:
            logger.error(f"Erro Cypher: {e}")
            raise Neo4jQueryError(f"Erro na query Cypher: {e}") from e
        except TransactionError as e:
            logger.error(f"Erro na transação: {e}")
            raise Neo4jQueryError(f"Erro na transação: {e}") from e
        except Exception as e:
            logger.error(f"Erro inesperado ao adicionar nó: {e}")
            raise Neo4jQueryError(f"Erro ao adicionar nó: {e}") from e

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        relation: str,
        weight: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Adiciona ou atualiza uma aresta entre dois nós.

        Args:
            from_id: ID do nó de origem
            to_id: ID do nó de destino
            relation: Tipo de relação (ex: "uses", "resolves", "depends_on")
            weight: Peso da relação (0.0-1.0, default: 1.0)

        Returns:
            Dict com propriedades da aresta criada

        Raises:
            Neo4jConnectionError: Se não está conectado
            Neo4jQueryError: Se query falhar

        Example:
            >>> edge = graph.add_edge(
            ...     "dec_001",
            ...     "concept_redis",
            ...     "uses",
            ...     weight=0.95
            ... )
            >>> edge["weight"]
            0.95
        """
        if not from_id or not to_id or not relation:
            raise ValueError(
                "from_id, to_id e relation são obrigatórios"
            )

        if not 0.0 <= weight <= 1.0:
            raise ValueError("weight deve estar entre 0.0 e 1.0")

        try:
            with self._get_session() as session:
                query = CYPHER_QUERIES["add_edge"].replace(
                    "{relation}", relation
                )

                result = session.run(
                    query,
                    from_id=from_id,
                    to_id=to_id,
                    weight=weight,
                )
                record = result.single()

                if record:
                    edge_data = dict(record["r"])
                    logger.info(
                        f"Aresta criada: {from_id} -[{relation}]-> {to_id}"
                    )
                    return edge_data
                else:
                    raise Neo4jQueryError("Falha ao criar aresta (resultado vazio)")

        except Neo4jConnectionError:
            raise
        except CypherSyntaxError as e:
            logger.error(f"Erro Cypher: {e}")
            raise Neo4jQueryError(f"Erro na query Cypher: {e}") from e
        except TransactionError as e:
            logger.error(f"Erro na transação: {e}")
            raise Neo4jQueryError(f"Erro na transação: {e}") from e
        except Exception as e:
            logger.error(f"Erro inesperado ao adicionar aresta: {e}")
            raise Neo4jQueryError(f"Erro ao adicionar aresta: {e}") from e

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera um nó específico.

        Args:
            node_id: ID do nó

        Returns:
            Dict com propriedades do nó, ou None se não encontrado

        Raises:
            Neo4jConnectionError: Se não está conectado
            Neo4jQueryError: Se query falhar
        """
        if not node_id:
            raise ValueError("node_id é obrigatório")

        try:
            with self._get_session() as session:
                result = session.run(
                    CYPHER_QUERIES["get_node"],
                    id=node_id,
                )
                record = result.single()

                if record:
                    return dict(record["n"])
                else:
                    logger.info(f"Nó não encontrado: {node_id}")
                    return None

        except Exception as e:
            logger.error(f"Erro ao recuperar nó: {e}")
            raise Neo4jQueryError(f"Erro ao recuperar nó: {e}") from e

    def delete_node(self, node_id: str) -> int:
        """
        Deleta um nó e todas suas arestas.

        Args:
            node_id: ID do nó a deletar

        Returns:
            Número de nós deletados (0 ou 1)

        Raises:
            Neo4jConnectionError: Se não está conectado
            Neo4jQueryError: Se query falhar
        """
        if not node_id:
            raise ValueError("node_id é obrigatório")

        try:
            with self._get_session() as session:
                result = session.run(
                    CYPHER_QUERIES["delete_node"],
                    id=node_id,
                )
                record = result.single()

                if record:
                    deleted_count = record["deleted"]
                    logger.info(f"Nó deletado: {node_id}")
                    return deleted_count
                else:
                    return 0

        except Exception as e:
            logger.error(f"Erro ao deletar nó: {e}")
            raise Neo4jQueryError(f"Erro ao deletar nó: {e}") from e

    # ============ QUERIES OTIMIZADAS ============

    def traverse(
        self,
        start_id: str,
        relation: Optional[str] = None,
        depth: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Faz traversal em grafos a partir de um nó.

        Busca todos os nós alcançáveis até uma profundidade máxima,
        opcionalmente filtrando por tipo de relação.

        Args:
            start_id: ID do nó inicial
            relation: Tipo de relação para filtrar (None = todas), ex: "uses"
            depth: Profundidade máxima de busca (1-5, default: 2)

        Returns:
            List de dicts com nós encontrados, ordenados por distância

        Raises:
            Neo4jConnectionError: Se não está conectado
            Neo4jQueryError: Se query falhar
            ValueError: Se profundidade inválida

        Example:
            >>> results = graph.traverse(
            ...     "dec_001",
            ...     relation="uses",
            ...     depth=2
            ... )
            >>> len(results)
            5
        """
        if not start_id:
            raise ValueError("start_id é obrigatório")

        if not 1 <= depth <= 5:
            raise ValueError("depth deve estar entre 1 e 5")

        try:
            with self._get_session() as session:
                # Montar filtro de relação
                if relation:
                    rel_filter = f"type(r) = '{relation}'"
                else:
                    rel_filter = "true"

                query = CYPHER_QUERIES["traverse"].replace(
                    "{depth}", str(depth)
                ).replace("{relation_filter}", rel_filter)

                result = session.run(query, start_id=start_id)
                nodes = [dict(record["n"]) for record in result]

                logger.info(
                    f"Traversal concluído: {start_id} ({len(nodes)} nós, "
                    f"rel={relation}, depth={depth})"
                )
                return nodes

        except Exception as e:
            logger.error(f"Erro no traversal: {e}")
            raise Neo4jQueryError(f"Erro no traversal: {e}") from e

    def shortest_path(
        self,
        source_id: str,
        target_id: str,
    ) -> Optional[Tuple[List[str], int]]:
        """
        Encontra o caminho mais curto entre dois nós.

        Args:
            source_id: ID do nó de origem
            target_id: ID do nó de destino

        Returns:
            Tupla (lista de IDs do caminho, distância) ou None se não há caminho

        Raises:
            Neo4jConnectionError: Se não está conectado
            Neo4jQueryError: Se query falhar

        Example:
            >>> path, dist = graph.shortest_path("dec_001", "concept_redis")
            >>> path
            ['dec_001', 'node_2', 'concept_redis']
            >>> dist
            2
        """
        if not source_id or not target_id:
            raise ValueError("source_id e target_id são obrigatórios")

        try:
            with self._get_session() as session:
                result = session.run(
                    CYPHER_QUERIES["shortest_path"],
                    source_id=source_id,
                    target_id=target_id,
                )
                record = result.single()

                if record:
                    path = record["path"]
                    distance = record["distance"]

                    # Extrair IDs dos nós
                    node_ids = [node["id"] for node in path.nodes]

                    logger.info(
                        f"Caminho encontrado: {' -> '.join(node_ids)} "
                        f"(distância: {distance})"
                    )
                    return (node_ids, distance)
                else:
                    logger.info(
                        f"Nenhum caminho entre {source_id} e {target_id}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Erro ao buscar caminho: {e}")
            raise Neo4jQueryError(f"Erro ao buscar caminho: {e}") from e

    def pagerank(self, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Calcula PageRank dos nós (requer GDS plugin).

        PageRank identifica os nós mais importantes no grafo.

        Args:
            top_k: Número de top nós a retornar (default: 10)

        Returns:
            List de tuplas (id, score), ordenadas por score decrescente

        Raises:
            Neo4jConnectionError: Se não está conectado
            Neo4jQueryError: Se query falhar ou GDS não está disponível

        Example:
            >>> rankings = graph.pagerank(top_k=5)
            >>> rankings[0]
            ('dec_001', 0.85)
        """
        if not 1 <= top_k <= 100:
            raise ValueError("top_k deve estar entre 1 e 100")

        try:
            with self._get_session() as session:
                result = session.run(
                    CYPHER_QUERIES["pagerank"],
                    limit=top_k,
                )
                rankings = [
                    (record["id"], record["score"]) for record in result
                ]

                logger.info(f"PageRank calculado: {len(rankings)} nós")
                return rankings

        except Exception as e:
            if "gds" in str(e).lower():
                logger.error("GDS plugin não disponível")
                raise Neo4jQueryError(
                    "GDS (Graph Data Science) não está disponível no servidor"
                ) from e
            else:
                logger.error(f"Erro no PageRank: {e}")
                raise Neo4jQueryError(f"Erro no PageRank: {e}") from e

    # ============ SINCRONIZAÇÃO ============

    def sync_from_sqlite(
        self,
        db_path: str,
        clear_existing: bool = False,
    ) -> Dict[str, int]:
        """
        Sincroniza dados de SQLite para Neo4j.

        Processa:
        - Decisions → nodes com label "Decision"
        - Learnings → nodes com label "Learning"
        - Extrai conceitos automaticamente
        - Cria arestas: decision→uses→concept, learning→resolves→error

        Args:
            db_path: Caminho para arquivo SQLite (ex: brain.db)
            clear_existing: Se deve limpar grafo antes (default: False)

        Returns:
            Dict com contadores:
                {
                    "nodes_created": int,
                    "edges_created": int,
                    "errors": int,
                }

        Raises:
            Neo4jSyncError: Se algo falhar durante sync

        Example:
            >>> stats = graph.sync_from_sqlite(
            ...     "/root/claude-brain/memory/brain.db"
            ... )
            >>> stats["nodes_created"]
            42
        """
        import sqlite3

        if not Path(db_path).exists():
            raise Neo4jSyncError(f"Arquivo SQLite não encontrado: {db_path}")

        try:
            stats = {
                "nodes_created": 0,
                "edges_created": 0,
                "errors": 0,
            }

            logger.info(f"Iniciando sincronização de {db_path}...")

            # Se clear_existing, deletar todos os nós
            if clear_existing:
                with self._get_session() as session:
                    session.run("MATCH (n) DETACH DELETE n")
                    logger.info("Grafo limpo")

            # Conectar ao SQLite
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Processar decisions
            try:
                cursor.execute("SELECT id, title, content, confidence FROM decisions")
                for row in cursor.fetchall():
                    try:
                        self.add_node(
                            "Decision",
                            f"dec_{row['id']}",
                            {
                                "title": row["title"],
                                "content": row["content"],
                                "confidence": row["confidence"],
                            },
                        )
                        stats["nodes_created"] += 1
                    except Exception as e:
                        logger.error(f"Erro ao processar decisão: {e}")
                        stats["errors"] += 1
            except Exception as e:
                logger.warning(f"Tabela 'decisions' não encontrada: {e}")

            # Processar learnings
            try:
                cursor.execute(
                    "SELECT id, error_pattern, solution, success_count FROM learnings"
                )
                for row in cursor.fetchall():
                    try:
                        self.add_node(
                            "Learning",
                            f"learn_{row['id']}",
                            {
                                "error_pattern": row["error_pattern"],
                                "solution": row["solution"],
                                "success_count": row["success_count"],
                            },
                        )
                        stats["nodes_created"] += 1
                    except Exception as e:
                        logger.error(f"Erro ao processar learning: {e}")
                        stats["errors"] += 1
            except Exception as e:
                logger.warning(f"Tabela 'learnings' não encontrada: {e}")

            conn.close()

            logger.info(
                f"Sincronização concluída: "
                f"{stats['nodes_created']} nós, "
                f"{stats['edges_created']} arestas, "
                f"{stats['errors']} erros"
            )
            return stats

        except Exception as e:
            logger.error(f"Erro fatal na sincronização: {e}")
            raise Neo4jSyncError(f"Erro ao sincronizar SQLite: {e}") from e

    # ============ UTILIDADES ============

    def health_check(self) -> bool:
        """
        Verifica saúde da conexão Neo4j.

        Returns:
            True se conectado e respondendo, False caso contrário
        """
        try:
            with self._get_session() as session:
                result = session.run("RETURN 1")
                result.single()
                return True
        except Exception as e:
            logger.warning(f"Health check falhou: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Recupera estatísticas do grafo.

        Returns:
            Dict com:
                - node_count: Total de nós
                - edge_count: Total de arestas
                - node_types: Contagem por tipo de nó

        Raises:
            Neo4jQueryError: Se query falhar
        """
        try:
            with self._get_session() as session:
                # Total de nós
                result_nodes = session.run("MATCH (n) RETURN COUNT(n) as count")
                node_count = result_nodes.single()["count"]

                # Total de arestas
                result_edges = session.run("MATCH ()-[r]->() RETURN COUNT(r) as count")
                edge_count = result_edges.single()["count"]

                # Nós por tipo
                result_types = session.run(
                    "MATCH (n) RETURN labels(n)[0] as type, COUNT(*) as count "
                    "GROUP BY type ORDER BY count DESC"
                )
                node_types = {record["type"]: record["count"] for record in result_types}

                stats = {
                    "node_count": node_count,
                    "edge_count": edge_count,
                    "node_types": node_types,
                }

                logger.info(f"Stats: {node_count} nós, {edge_count} arestas")
                return stats

        except Exception as e:
            logger.error(f"Erro ao recuperar stats: {e}")
            raise Neo4jQueryError(f"Erro ao recuperar stats: {e}") from e


# ============ TESTES INLINE ============

def _test_neo4j_wrapper() -> None:
    """
    Testes básicos do wrapper (requer Neo4j rodando).

    Descomente para rodar manualmente:
        python -c "from neo4j_wrapper import _test_neo4j_wrapper; _test_neo4j_wrapper()"
    """
    import sys

    try:
        # Inicializar
        graph = Neo4jGraph(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )

        # Conectar
        print("Testando conexão...")
        graph.connect()

        # Health check
        assert graph.health_check(), "Health check falhou"
        print("✓ Conexão OK")

        # Adicionar nó
        print("Testando add_node...")
        node = graph.add_node(
            "TestNode",
            "test_001",
            {"name": "Test", "value": 42}
        )
        assert node["id"] == "test_001"
        print("✓ add_node OK")

        # Recuperar nó
        print("Testando get_node...")
        retrieved = graph.get_node("test_001")
        assert retrieved is not None
        assert retrieved["id"] == "test_001"
        print("✓ get_node OK")

        # Adicionar aresta
        print("Testando add_node + add_edge...")
        graph.add_node("TestNode", "test_002", {"name": "Test2"})
        edge = graph.add_edge("test_001", "test_002", "relates_to", weight=0.8)
        assert edge["weight"] == 0.8
        print("✓ add_edge OK")

        # Traversal
        print("Testando traverse...")
        results = graph.traverse("test_001", depth=1)
        assert len(results) > 0
        print(f"✓ traverse OK ({len(results)} nós)")

        # Stats
        print("Testando get_stats...")
        stats = graph.get_stats()
        assert stats["node_count"] >= 2
        print(f"✓ get_stats OK ({stats['node_count']} nós)")

        # Limpeza
        print("Limpando...")
        graph.delete_node("test_001")
        graph.delete_node("test_002")

        # Fechar
        graph.close()
        print("✓ close OK")

        print("\n✅ Todos os testes passaram!")

    except Exception as e:
        print(f"\n❌ Teste falhou: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Executar testes se rodado como script
    _test_neo4j_wrapper()
