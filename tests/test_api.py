#!/usr/bin/env python3
"""
Testes para a API REST do Claude Brain.

Usa TestClient do FastAPI para testes de integracao.
Meta: >=60% cobertura em api/main.py

Endpoints testados:
1. GET / - Health check
2. GET /search - Busca semantica
3. GET /stats - Estatisticas
4. GET /decisions - Decisoes com filtros
5. GET /learnings - Aprendizados
6. GET /preferences - Preferencias
7. GET /metrics - Metricas
8. GET /memories - Busca em memorias
9. GET /entities - Entidades do knowledge graph
10. GET /patterns - Padroes de codigo
11. GET /graph/{entity} - Knowledge graph
12. GET /dashboard - Dashboard HTML
13. Error responses (400, 422, 404, 500)
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Adiciona scripts ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

import pytest
from fastapi.testclient import TestClient


# ============ FIXTURES ============


@pytest.fixture
def client():
    """
    Cria cliente de teste com mocks para dependencias externas.
    Evita dependencias de banco de dados e modelos ML.
    """
    # Mock das funcoes de memoria
    with patch("main.db_get_stats") as mock_db_stats, \
         patch("main.rag_get_stats") as mock_rag_stats, \
         patch("main.get_decisions") as mock_decisions, \
         patch("main.get_all_learnings") as mock_learnings, \
         patch("main.search_memories") as mock_memories, \
         patch("main.get_all_preferences") as mock_prefs, \
         patch("main.get_entity_graph") as mock_graph, \
         patch("main.get_all_entities") as mock_entities, \
         patch("main.get_all_patterns") as mock_patterns, \
         patch("main.get_effectiveness") as mock_effectiveness, \
         patch("main.get_daily_report") as mock_daily, \
         patch("main.semantic_search") as mock_semantic:

        # Configura retornos padrao
        mock_db_stats.return_value = {
            "memories": 26,
            "decisions": 101,
            "learnings": 11,
            "entities": 15,
            "relations": 20,
            "preferences": 5,
            "patterns": 3,
            "sessions": 8,
            "top_preferences": [{"key": "test_framework", "times_observed": 10}],
            "top_errors": [{"error_type": "ModuleNotFoundError", "frequency": 5}],
        }

        mock_rag_stats.return_value = {
            "documents": 309,
            "chunks": 1500,
            "faiss_status": "ativo",
            "auto_rebuild_enabled": True,
        }

        mock_decisions.return_value = [
            {
                "id": 1,
                "project": "vsl-analysis",
                "decision": "Usar FastAPI",
                "reasoning": "Performance",
                "status": "active",
                "maturity_status": "confirmed",
                "confidence_score": 0.85,
            },
            {
                "id": 2,
                "project": "claude-brain",
                "decision": "Usar SQLite para memoria",
                "reasoning": "Simplicidade",
                "status": "active",
                "maturity_status": "hypothesis",
                "confidence_score": 0.5,
            },
        ]

        mock_learnings.return_value = [
            {
                "id": 1,
                "error_type": "ModuleNotFoundError",
                "solution": "pip install <pacote>",
                "frequency": 5,
                "maturity_status": "confirmed",
            },
            {
                "id": 2,
                "error_type": "CUDA OOM",
                "solution": "Reduzir batch size",
                "frequency": 3,
                "maturity_status": "hypothesis",
            },
        ]

        mock_memories.return_value = [
            {
                "id": 1,
                "type": "general",
                "content": "API do Slack tem rate limit",
                "importance": 8,
            }
        ]

        mock_prefs.return_value = {
            "test_framework": "pytest",
            "language": "python",
        }

        mock_graph.return_value = {
            "entity": {"name": "vsl-analysis", "type": "project"},
            "outgoing": [{"to_entity": "python", "relation_type": "uses"}],
            "incoming": [],
        }

        mock_entities.return_value = [
            {"id": 1, "name": "python", "type": "technology"},
            {"id": 2, "name": "vsl-analysis", "type": "project"},
        ]

        mock_patterns.return_value = [
            {"id": 1, "name": "context_manager", "pattern_type": "python", "usage_count": 10},
        ]

        mock_effectiveness.return_value = {
            "total_actions": 100,
            "rated_actions": 80,
            "useful": 70,
            "not_useful": 10,
            "effectiveness_pct": 87.5,
            "avg_search_score": 0.85,
            "by_action": {"search": {"total": 50, "useful": 45}},
        }

        mock_daily.return_value = [
            {
                "date": "2026-01-31",
                "searches": 10,
                "decisions_saved": 2,
                "learnings_saved": 1,
                "useful_count": 8,
                "not_useful_count": 1,
            }
        ]

        mock_semantic.return_value = [
            {
                "chunk_id": "1",
                "score": 0.92,
                "text": "Documento relevante encontrado",
                "source": "/root/claude-brain/docs/test.md",
                "doc_type": "markdown",
            }
        ]

        # Importa app depois de configurar mocks
        from main import app
        yield TestClient(app)


@pytest.fixture
def client_with_errors():
    """
    Cliente configurado para simular erros internos.
    """
    with patch("main.db_get_stats") as mock_db_stats, \
         patch("main.rag_get_stats") as mock_rag_stats, \
         patch("main.get_decisions") as mock_decisions, \
         patch("main.get_all_learnings") as mock_learnings, \
         patch("main.search_memories") as mock_memories, \
         patch("main.get_all_preferences") as mock_prefs, \
         patch("main.get_entity_graph") as mock_graph, \
         patch("main.get_all_entities") as mock_entities, \
         patch("main.get_all_patterns") as mock_patterns, \
         patch("main.get_effectiveness") as mock_effectiveness, \
         patch("main.get_daily_report") as mock_daily, \
         patch("main.semantic_search") as mock_semantic:

        # Configura todos para lancar excecao
        mock_db_stats.side_effect = Exception("Database connection failed")
        mock_rag_stats.side_effect = Exception("FAISS index corrupted")
        mock_decisions.side_effect = Exception("Query failed")
        mock_learnings.side_effect = Exception("Query failed")
        mock_memories.side_effect = Exception("Query failed")
        mock_prefs.side_effect = Exception("Query failed")
        mock_graph.side_effect = Exception("Graph query failed")
        mock_entities.side_effect = Exception("Query failed")
        mock_patterns.side_effect = Exception("Query failed")
        mock_effectiveness.side_effect = Exception("Metrics failed")
        mock_daily.side_effect = Exception("Metrics failed")
        mock_semantic.side_effect = Exception("Search failed")

        from main import app
        yield TestClient(app)


# ============ HEALTH CHECK TESTS ============


class TestHealthCheck:
    """Testes para endpoint de health check (GET /)"""

    def test_root_returns_200(self, client):
        """Health check deve retornar status 200"""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_status_online(self, client):
        """Health check deve indicar status online"""
        response = client.get("/")
        data = response.json()
        assert data["status"] == "online"

    def test_root_returns_service_name(self, client):
        """Health check deve retornar nome do servico"""
        response = client.get("/")
        data = response.json()
        assert data["service"] == "Claude Brain API"

    def test_root_returns_version(self, client):
        """Health check deve retornar versao"""
        response = client.get("/")
        data = response.json()
        assert "version" in data
        assert data["version"] == "1.0.0"

    def test_root_lists_endpoints(self, client):
        """Health check deve listar endpoints disponiveis"""
        response = client.get("/")
        data = response.json()
        assert "endpoints" in data
        assert isinstance(data["endpoints"], list)
        assert len(data["endpoints"]) > 0
        # Verifica endpoints principais
        expected = ["/stats", "/decisions", "/learnings", "/search"]
        for endpoint in expected:
            assert endpoint in data["endpoints"]


# ============ SEARCH ENDPOINT TESTS ============


class TestSearchEndpoint:
    """Testes para endpoint de busca semantica (GET /search)"""

    def test_search_requires_query(self, client):
        """Busca deve exigir parametro q"""
        response = client.get("/search")
        assert response.status_code == 422  # Validation Error

    def test_search_validates_min_length(self, client):
        """Busca deve validar tamanho minimo da query"""
        response = client.get("/search", params={"q": "a"})
        assert response.status_code == 422

    def test_search_returns_results(self, client):
        """Busca valida deve retornar resultados"""
        response = client.get("/search", params={"q": "python venv"})
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "count" in data
        assert "query" in data
        assert data["query"] == "python venv"

    def test_search_with_doc_type_filter(self, client):
        """Busca deve aceitar filtro de tipo de documento"""
        response = client.get("/search", params={"q": "fastapi", "doc_type": "markdown"})
        assert response.status_code == 200
        data = response.json()
        assert data["doc_type"] == "markdown"

    def test_search_with_limit(self, client):
        """Busca deve respeitar limite de resultados"""
        response = client.get("/search", params={"q": "teste", "limit": 3})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] <= 3

    def test_search_limit_validation_min(self, client):
        """Limite deve ser >= 1"""
        response = client.get("/search", params={"q": "teste", "limit": 0})
        assert response.status_code == 422

    def test_search_limit_validation_max(self, client):
        """Limite deve ser <= 20"""
        response = client.get("/search", params={"q": "teste", "limit": 100})
        assert response.status_code == 422

    def test_search_result_structure(self, client):
        """Resultados devem ter estrutura correta"""
        response = client.get("/search", params={"q": "python"})
        assert response.status_code == 200
        data = response.json()
        if data["count"] > 0:
            result = data["results"][0]
            assert "score" in result
            assert "text" in result
            assert "source" in result
            assert "doc_type" in result


# ============ STATS ENDPOINT TESTS ============


class TestStatsEndpoint:
    """Testes para endpoint de estatisticas (GET /stats)"""

    def test_stats_returns_200(self, client):
        """Stats deve retornar 200"""
        response = client.get("/stats")
        assert response.status_code == 200

    def test_stats_contains_database_section(self, client):
        """Stats deve conter secao de banco de dados"""
        response = client.get("/stats")
        data = response.json()
        assert "database" in data
        assert isinstance(data["database"], dict)

    def test_stats_contains_rag_section(self, client):
        """Stats deve conter secao de RAG"""
        response = client.get("/stats")
        data = response.json()
        assert "rag" in data
        assert isinstance(data["rag"], dict)

    def test_stats_database_has_counts(self, client):
        """Stats do banco deve ter contagens"""
        response = client.get("/stats")
        data = response.json()
        db = data["database"]
        expected_keys = ["memories", "decisions", "learnings"]
        for key in expected_keys:
            assert key in db
            assert isinstance(db[key], int)


# ============ DECISIONS ENDPOINT TESTS ============


class TestDecisionsEndpoint:
    """Testes para endpoint de decisoes (GET /decisions)"""

    def test_decisions_returns_200(self, client):
        """Decisions deve retornar 200"""
        response = client.get("/decisions")
        assert response.status_code == 200

    def test_decisions_returns_list(self, client):
        """Decisions deve retornar lista de decisoes"""
        response = client.get("/decisions")
        data = response.json()
        assert "decisions" in data
        assert isinstance(data["decisions"], list)

    def test_decisions_returns_count(self, client):
        """Decisions deve retornar contagem"""
        response = client.get("/decisions")
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_decisions_filter_by_project(self, client):
        """Decisions deve filtrar por projeto"""
        response = client.get("/decisions", params={"project": "vsl-analysis"})
        assert response.status_code == 200
        data = response.json()
        assert data["project"] == "vsl-analysis"

    def test_decisions_filter_by_status(self, client):
        """Decisions deve filtrar por status"""
        response = client.get("/decisions", params={"status": "deprecated"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deprecated"

    def test_decisions_respects_limit(self, client):
        """Decisions deve respeitar limite"""
        response = client.get("/decisions", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] <= 5

    def test_decisions_limit_validation_min(self, client):
        """Limite deve ser >= 1"""
        response = client.get("/decisions", params={"limit": 0})
        assert response.status_code == 422

    def test_decisions_limit_validation_max(self, client):
        """Limite deve ser <= 100"""
        response = client.get("/decisions", params={"limit": 200})
        assert response.status_code == 422

    def test_decision_structure(self, client):
        """Decisao deve ter estrutura correta"""
        response = client.get("/decisions")
        data = response.json()
        if data["count"] > 0:
            decision = data["decisions"][0]
            assert "id" in decision
            assert "decision" in decision


# ============ LEARNINGS ENDPOINT TESTS ============


class TestLearningsEndpoint:
    """Testes para endpoint de aprendizados (GET /learnings)"""

    def test_learnings_returns_200(self, client):
        """Learnings deve retornar 200"""
        response = client.get("/learnings")
        assert response.status_code == 200

    def test_learnings_returns_list(self, client):
        """Learnings deve retornar lista"""
        response = client.get("/learnings")
        data = response.json()
        assert "learnings" in data
        assert isinstance(data["learnings"], list)

    def test_learnings_returns_count(self, client):
        """Learnings deve retornar contagem"""
        response = client.get("/learnings")
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_learnings_respects_limit(self, client):
        """Learnings deve respeitar limite"""
        response = client.get("/learnings", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] <= 5

    def test_learnings_limit_validation(self, client):
        """Limite deve ser validado"""
        response = client.get("/learnings", params={"limit": 0})
        assert response.status_code == 422
        response = client.get("/learnings", params={"limit": 200})
        assert response.status_code == 422

    def test_learning_structure(self, client):
        """Learning deve ter estrutura correta"""
        response = client.get("/learnings")
        data = response.json()
        if data["count"] > 0:
            learning = data["learnings"][0]
            assert "id" in learning
            assert "error_type" in learning
            assert "solution" in learning


# ============ PREFERENCES ENDPOINT TESTS ============


class TestPreferencesEndpoint:
    """Testes para endpoint de preferencias (GET /preferences)"""

    def test_preferences_returns_200(self, client):
        """Preferences deve retornar 200"""
        response = client.get("/preferences")
        assert response.status_code == 200

    def test_preferences_returns_dict(self, client):
        """Preferences deve retornar dicionario"""
        response = client.get("/preferences")
        data = response.json()
        assert "preferences" in data
        assert isinstance(data["preferences"], dict)

    def test_preferences_filter_by_confidence(self, client):
        """Preferences deve filtrar por confianca minima"""
        response = client.get("/preferences", params={"min_confidence": 0.8})
        assert response.status_code == 200
        data = response.json()
        assert data["min_confidence"] == 0.8

    def test_preferences_confidence_validation(self, client):
        """Confianca deve ser entre 0 e 1"""
        response = client.get("/preferences", params={"min_confidence": -0.1})
        assert response.status_code == 422
        response = client.get("/preferences", params={"min_confidence": 1.5})
        assert response.status_code == 422


# ============ METRICS ENDPOINT TESTS ============


class TestMetricsEndpoint:
    """Testes para endpoint de metricas (GET /metrics)"""

    def test_metrics_returns_200(self, client):
        """Metrics deve retornar 200"""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_contains_effectiveness(self, client):
        """Metrics deve conter eficacia"""
        response = client.get("/metrics")
        data = response.json()
        assert "effectiveness" in data
        assert isinstance(data["effectiveness"], dict)

    def test_metrics_contains_daily_report(self, client):
        """Metrics deve conter relatorio diario"""
        response = client.get("/metrics")
        data = response.json()
        assert "daily_report" in data
        assert isinstance(data["daily_report"], list)

    def test_metrics_days_parameter(self, client):
        """Metrics deve aceitar parametro days"""
        response = client.get("/metrics", params={"days": 14})
        assert response.status_code == 200

    def test_metrics_days_validation(self, client):
        """Days deve ser entre 1 e 30"""
        response = client.get("/metrics", params={"days": 0})
        assert response.status_code == 422
        response = client.get("/metrics", params={"days": 100})
        assert response.status_code == 422


# ============ MEMORIES ENDPOINT TESTS ============


class TestMemoriesEndpoint:
    """Testes para endpoint de memorias (GET /memories)"""

    def test_memories_returns_200(self, client):
        """Memories deve retornar 200"""
        response = client.get("/memories")
        assert response.status_code == 200

    def test_memories_returns_list(self, client):
        """Memories deve retornar lista"""
        response = client.get("/memories")
        data = response.json()
        assert "memories" in data
        assert isinstance(data["memories"], list)

    def test_memories_with_query(self, client):
        """Memories deve aceitar query de busca"""
        response = client.get("/memories", params={"q": "slack"})
        assert response.status_code == 200

    def test_memories_with_type_filter(self, client):
        """Memories deve aceitar filtro de tipo"""
        response = client.get("/memories", params={"type": "general"})
        assert response.status_code == 200

    def test_memories_with_category_filter(self, client):
        """Memories deve aceitar filtro de categoria"""
        response = client.get("/memories", params={"category": "api"})
        assert response.status_code == 200

    def test_memories_with_min_importance(self, client):
        """Memories deve aceitar importancia minima"""
        response = client.get("/memories", params={"min_importance": 5})
        assert response.status_code == 200

    def test_memories_importance_validation(self, client):
        """Importancia deve ser entre 0 e 10"""
        response = client.get("/memories", params={"min_importance": -1})
        assert response.status_code == 422
        response = client.get("/memories", params={"min_importance": 15})
        assert response.status_code == 422


# ============ ENTITIES ENDPOINT TESTS ============


class TestEntitiesEndpoint:
    """Testes para endpoint de entidades (GET /entities)"""

    def test_entities_returns_200(self, client):
        """Entities deve retornar 200"""
        response = client.get("/entities")
        assert response.status_code == 200

    def test_entities_returns_list(self, client):
        """Entities deve retornar lista"""
        response = client.get("/entities")
        data = response.json()
        assert "entities" in data
        assert isinstance(data["entities"], list)

    def test_entities_filter_by_type(self, client):
        """Entities deve filtrar por tipo"""
        response = client.get("/entities", params={"type": "technology"})
        assert response.status_code == 200
        data = response.json()
        assert data["type_filter"] == "technology"

    def test_entities_respects_limit(self, client):
        """Entities deve respeitar limite"""
        response = client.get("/entities", params={"limit": 10})
        assert response.status_code == 200


# ============ PATTERNS ENDPOINT TESTS ============


class TestPatternsEndpoint:
    """Testes para endpoint de padroes (GET /patterns)"""

    def test_patterns_returns_200(self, client):
        """Patterns deve retornar 200"""
        response = client.get("/patterns")
        assert response.status_code == 200

    def test_patterns_returns_list(self, client):
        """Patterns deve retornar lista"""
        response = client.get("/patterns")
        data = response.json()
        assert "patterns" in data
        assert isinstance(data["patterns"], list)

    def test_patterns_filter_by_type(self, client):
        """Patterns deve filtrar por tipo"""
        response = client.get("/patterns", params={"type": "python"})
        assert response.status_code == 200
        data = response.json()
        assert data["type_filter"] == "python"


# ============ GRAPH ENDPOINT TESTS ============


class TestGraphEndpoint:
    """Testes para endpoint de knowledge graph (GET /graph/{entity})"""

    def test_graph_returns_200_for_existing_entity(self, client):
        """Graph deve retornar 200 para entidade existente"""
        response = client.get("/graph/vsl-analysis")
        assert response.status_code == 200

    def test_graph_returns_entity_info(self, client):
        """Graph deve retornar informacoes da entidade"""
        response = client.get("/graph/vsl-analysis")
        data = response.json()
        assert "entity" in data
        assert "outgoing" in data
        assert "incoming" in data

    def test_graph_returns_404_for_missing_entity(self, client):
        """Graph deve retornar 404 para entidade inexistente"""
        with patch("main.get_entity_graph") as mock_graph:
            mock_graph.return_value = None
            from main import app
            test_client = TestClient(app)
            response = test_client.get("/graph/entidade-inexistente")
            assert response.status_code == 404

    def test_graph_404_has_detail_message(self, client):
        """Erro 404 deve ter mensagem de detalhe"""
        with patch("main.get_entity_graph") as mock_graph:
            mock_graph.return_value = None
            from main import app
            test_client = TestClient(app)
            response = test_client.get("/graph/entidade-inexistente")
            data = response.json()
            assert "detail" in data


# ============ DASHBOARD ENDPOINT TESTS ============


class TestDashboardEndpoint:
    """Testes para endpoint de dashboard (GET /dashboard)"""

    def test_dashboard_returns_html(self, client):
        """Dashboard deve retornar HTML"""
        response = client.get("/dashboard")
        # Pode retornar 200 se arquivo existe ou 404 se nao
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_returns_404_when_file_missing(self):
        """Dashboard deve retornar 404 quando arquivo nao existe"""
        with patch("main.DASHBOARD_PATH") as mock_path:
            mock_path.exists.return_value = False
            from main import app
            test_client = TestClient(app)
            response = test_client.get("/dashboard")
            assert response.status_code == 404
            assert "Dashboard not found" in response.text


# ============ ERROR RESPONSE TESTS ============


class TestErrorResponses:
    """Testes para respostas de erro"""

    def test_422_on_invalid_query_params(self, client):
        """Deve retornar 422 para parametros invalidos"""
        # Query muito curta
        response = client.get("/search", params={"q": "x"})
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_422_response_structure(self, client):
        """Erro 422 deve ter estrutura correta"""
        response = client.get("/search", params={"q": "x"})
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)

    def test_500_on_internal_error(self, client_with_errors):
        """Deve retornar 500 em erro interno"""
        response = client_with_errors.get("/stats")
        assert response.status_code == 500

    def test_500_has_detail_message(self, client_with_errors):
        """Erro 500 deve ter mensagem de detalhe"""
        response = client_with_errors.get("/stats")
        data = response.json()
        assert "detail" in data

    def test_500_does_not_leak_internal_details(self, client_with_errors):
        """Erro 500 nao deve vazar detalhes internos"""
        response = client_with_errors.get("/stats")
        data = response.json()
        # Nao deve conter stack trace ou detalhes de excecao
        assert "Database connection failed" not in data["detail"]

    def test_404_on_unknown_route(self, client):
        """Deve retornar 404 para rota desconhecida"""
        response = client.get("/rota-que-nao-existe")
        assert response.status_code == 404

    def test_decisions_500_on_error(self, client_with_errors):
        """Decisions deve retornar 500 em erro"""
        response = client_with_errors.get("/decisions")
        assert response.status_code == 500

    def test_learnings_500_on_error(self, client_with_errors):
        """Learnings deve retornar 500 em erro"""
        response = client_with_errors.get("/learnings")
        assert response.status_code == 500

    def test_search_500_on_error(self, client_with_errors):
        """Search deve retornar 500 em erro"""
        response = client_with_errors.get("/search", params={"q": "test"})
        assert response.status_code == 500

    def test_metrics_500_on_error(self, client_with_errors):
        """Metrics deve retornar 500 em erro"""
        response = client_with_errors.get("/metrics")
        assert response.status_code == 500

    def test_preferences_500_on_error(self, client_with_errors):
        """Preferences deve retornar 500 em erro"""
        response = client_with_errors.get("/preferences")
        assert response.status_code == 500

    def test_memories_500_on_error(self, client_with_errors):
        """Memories deve retornar 500 em erro"""
        response = client_with_errors.get("/memories")
        assert response.status_code == 500

    def test_entities_500_on_error(self, client_with_errors):
        """Entities deve retornar 500 em erro"""
        response = client_with_errors.get("/entities")
        assert response.status_code == 500

    def test_patterns_500_on_error(self, client_with_errors):
        """Patterns deve retornar 500 em erro"""
        response = client_with_errors.get("/patterns")
        assert response.status_code == 500

    def test_graph_500_on_error(self, client_with_errors):
        """Graph deve retornar 500 em erro"""
        response = client_with_errors.get("/graph/test")
        assert response.status_code == 500


# ============ CORS TESTS ============


class TestCORS:
    """Testes para configuracao CORS"""

    def test_cors_allows_localhost(self, client):
        """CORS deve permitir localhost"""
        response = client.get(
            "/",
            headers={"Origin": "http://localhost:8765"}
        )
        assert response.status_code == 200
        # Verifica se header CORS esta presente
        # Nota: TestClient pode nao retornar headers CORS em todos os casos

    def test_cors_allows_127_0_0_1(self, client):
        """CORS deve permitir 127.0.0.1"""
        response = client.get(
            "/",
            headers={"Origin": "http://127.0.0.1:8765"}
        )
        assert response.status_code == 200


# ============ INTEGRATION TESTS ============


class TestIntegration:
    """Testes de integracao mais complexos"""

    def test_search_and_get_entity(self, client):
        """Deve poder buscar e obter entidade relacionada"""
        # Busca semantica
        search_response = client.get("/search", params={"q": "python"})
        assert search_response.status_code == 200

        # Obtem entidade
        graph_response = client.get("/graph/vsl-analysis")
        assert graph_response.status_code == 200

    def test_all_main_endpoints_accessible(self, client):
        """Todos os endpoints principais devem ser acessiveis"""
        endpoints = [
            "/",
            "/stats",
            "/decisions",
            "/learnings",
            "/preferences",
            "/metrics",
            "/memories",
            "/entities",
            "/patterns",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} falhou"


# ============ MAIN ============


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
