#!/usr/bin/env python3
"""
Testes unitários para Neo4j Wrapper

Requisitos:
- pytest: pip install pytest
- Neo4j rodando localmente (opcional para alguns testes)

Rodar:
    pytest test_neo4j_wrapper.py -v
    pytest test_neo4j_wrapper.py -v -k "test_add_node"
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Import do módulo
from neo4j_wrapper import (
    Neo4jGraph,
    Neo4jWrapperError,
    Neo4jConnectionError,
    Neo4jQueryError,
    Neo4jSyncError,
)


# ============ FIXTURES ============

@pytest.fixture
def mock_driver():
    """Mock do driver Neo4j"""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value = session
    driver.verify_connectivity.return_value = None
    return driver, session


@pytest.fixture
def graph_instance(mock_driver):
    """Instância de Neo4jGraph com driver mockado"""
    driver, session = mock_driver
    
    graph = Neo4jGraph(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password"
    )
    
    # Injetar driver mockado
    graph._driver = driver
    
    yield graph
    
    # Limpeza
    graph.close()


# ============ TESTES DE INICIALIZAÇÃO ============

class TestNeo4jGraphInit:
    """Testes de inicialização"""

    def test_init_valid(self):
        """Teste inicialização com parâmetros válidos"""
        graph = Neo4jGraph(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password"
        )
        assert graph.uri == "bolt://localhost:7687"
        assert graph.user == "neo4j"
        assert graph.password == "password"
        assert graph._driver is None
        assert graph.timeout == 30.0

    def test_init_missing_uri(self):
        """Teste erro se URI está vazia"""
        with pytest.raises(ValueError, match="uri.*obrigatório"):
            Neo4jGraph(uri="", user="neo4j", password="password")

    def test_init_missing_user(self):
        """Teste erro se user está vazio"""
        with pytest.raises(ValueError, match="user.*obrigatório"):
            Neo4jGraph(uri="bolt://localhost:7687", user="", password="password")

    def test_init_missing_password(self):
        """Teste erro se password está vazia"""
        with pytest.raises(ValueError, match="password.*obrigatório"):
            Neo4jGraph(uri="bolt://localhost:7687", user="neo4j", password="")


# ============ TESTES DE CONEXÃO ============

class TestNeo4jConnection:
    """Testes de conexão"""

    @patch('neo4j_wrapper.GraphDatabase.driver')
    def test_connect_success(self, mock_db_driver):
        """Teste conexão bem-sucedida"""
        mock_driver = MagicMock()
        mock_db_driver.return_value = mock_driver

        graph = Neo4jGraph(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password"
        )
        graph.connect()

        assert graph._driver is not None
        mock_driver.verify_connectivity.assert_called_once()

    @patch('neo4j_wrapper.GraphDatabase.driver')
    def test_connect_auth_error(self, mock_db_driver):
        """Teste erro de autenticação"""
        from neo4j.exceptions import AuthError
        
        mock_db_driver.side_effect = AuthError("Invalid credentials")

        graph = Neo4jGraph(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="wrong"
        )

        with pytest.raises(Neo4jConnectionError, match="autenticação"):
            graph.connect()

    def test_close_not_connected(self):
        """Teste fechar sem estar conectado"""
        graph = Neo4jGraph(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password"
        )
        # Não deve lançar erro
        graph.close()
        assert graph._driver is None

    def test_close_connected(self, graph_instance):
        """Teste fechar conexão ativa"""
        driver_mock = graph_instance._driver
        session_mock = MagicMock()
        
        graph_instance._session = session_mock

        graph_instance.close()

        assert graph_instance._driver is None
        assert graph_instance._session is None
        session_mock.close.assert_called_once()
        driver_mock.close.assert_called_once()


# ============ TESTES DE OPERAÇÕES CRUD ============

class TestCRUDOperations:
    """Testes de operações CRUD"""

    def test_add_node_success(self, graph_instance):
        """Teste adicionar nó com sucesso"""
        mock_session = graph_instance._driver.session()
        mock_result = MagicMock()
        mock_record = {"n": {"id": "test_001", "name": "Test"}}
        
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result

        node = graph_instance.add_node(
            "TestNode",
            "test_001",
            {"name": "Test"}
        )

        assert node["id"] == "test_001"
        assert node["name"] == "Test"
        mock_session.run.assert_called_once()

    def test_add_node_missing_type(self, graph_instance):
        """Teste erro se node_type vazio"""
        with pytest.raises(ValueError, match="node_type.*obrigatório"):
            graph_instance.add_node("", "test_001", {})

    def test_add_node_missing_id(self, graph_instance):
        """Teste erro se node_id vazio"""
        with pytest.raises(ValueError, match="node_id.*obrigatório"):
            graph_instance.add_node("TestNode", "", {})

    def test_add_edge_success(self, graph_instance):
        """Teste adicionar aresta com sucesso"""
        mock_session = graph_instance._driver.session()
        mock_result = MagicMock()
        mock_record = {"r": {"weight": 0.95}}
        
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result

        edge = graph_instance.add_edge(
            "from_001",
            "to_001",
            "relates_to",
            weight=0.95
        )

        assert edge["weight"] == 0.95
        mock_session.run.assert_called_once()

    def test_add_edge_invalid_weight(self, graph_instance):
        """Teste erro se weight fora do intervalo"""
        with pytest.raises(ValueError, match="weight.*0.0.*1.0"):
            graph_instance.add_edge("from", "to", "rel", weight=1.5)

    def test_get_node_found(self, graph_instance):
        """Teste recuperar nó existente"""
        mock_session = graph_instance._driver.session()
        mock_result = MagicMock()
        mock_record = {"n": {"id": "test_001", "name": "Test"}}
        
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result

        node = graph_instance.get_node("test_001")

        assert node["id"] == "test_001"

    def test_get_node_not_found(self, graph_instance):
        """Teste nó não encontrado"""
        mock_session = graph_instance._driver.session()
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        node = graph_instance.get_node("nonexistent")

        assert node is None

    def test_delete_node_success(self, graph_instance):
        """Teste deletar nó"""
        mock_session = graph_instance._driver.session()
        mock_result = MagicMock()
        mock_record = {"deleted": 1}
        
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result

        deleted_count = graph_instance.delete_node("test_001")

        assert deleted_count == 1


# ============ TESTES DE QUERIES OTIMIZADAS ============

class TestOptimizedQueries:
    """Testes de queries otimizadas"""

    def test_traverse_success(self, graph_instance):
        """Teste traversal com sucesso"""
        mock_session = graph_instance._driver.session()
        mock_result = MagicMock()
        mock_records = [
            {"n": {"id": "node_1"}},
            {"n": {"id": "node_2"}},
        ]
        mock_result.__iter__.return_value = iter(mock_records)
        mock_session.run.return_value = mock_result

        results = graph_instance.traverse("start_001", depth=2)

        assert len(results) == 2
        assert results[0]["id"] == "node_1"

    def test_traverse_invalid_depth(self, graph_instance):
        """Teste erro se depth inválida"""
        with pytest.raises(ValueError, match="depth.*1.*5"):
            graph_instance.traverse("start", depth=10)

    def test_shortest_path_found(self, graph_instance):
        """Teste encontrar caminho"""
        mock_session = graph_instance._driver.session()
        mock_result = MagicMock()
        
        # Mock do caminho
        mock_path = MagicMock()
        mock_node1 = MagicMock()
        mock_node1.__getitem__.return_value = "node_1"
        mock_node2 = MagicMock()
        mock_node2.__getitem__.return_value = "node_2"
        
        mock_path.nodes = [mock_node1, mock_node2]
        
        mock_record = {"path": mock_path, "distance": 1}
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result

        path, distance = graph_instance.shortest_path("from", "to")

        assert len(path) == 2
        assert distance == 1

    def test_shortest_path_not_found(self, graph_instance):
        """Teste caminho não encontrado"""
        mock_session = graph_instance._driver.session()
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        result = graph_instance.shortest_path("from", "to")

        assert result is None

    def test_pagerank_success(self, graph_instance):
        """Teste PageRank"""
        mock_session = graph_instance._driver.session()
        mock_records = [
            {"id": "node_1", "score": 0.9},
            {"id": "node_2", "score": 0.7},
        ]
        mock_session.run.return_value = mock_records

        rankings = graph_instance.pagerank(top_k=2)

        assert len(rankings) == 2
        assert rankings[0][0] == "node_1"


# ============ TESTES DE EXCEÇÕES ============

class TestExceptions:
    """Testes de exceções customizadas"""

    def test_exception_hierarchy(self):
        """Teste hierarquia de exceções"""
        assert issubclass(Neo4jConnectionError, Neo4jWrapperError)
        assert issubclass(Neo4jQueryError, Neo4jWrapperError)
        assert issubclass(Neo4jSyncError, Neo4jWrapperError)

    def test_raise_custom_exception(self):
        """Teste lançar exceção customizada"""
        with pytest.raises(Neo4jWrapperError):
            raise Neo4jConnectionError("Test error")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
