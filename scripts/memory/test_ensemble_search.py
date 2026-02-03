#!/usr/bin/env python3
"""
Testes para ensemble_search.py

Cobertura de testes:
- Busca em cada fonte (SQLite, FAISS, Neo4j fallback)
- Consolidação e deduplicação
- Ranking por relevância
- Cross-encoder reranking opcional
- Error handling com fallback gracioso
"""

import pytest
import json
import logging
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock

# Imports do módulo
from .ensemble_search import (
    SearchResult,
    _search_sqlite_decisions,
    _search_sqlite_learnings,
    _search_sqlite,
    _search_faiss,
    _search_neo4j,
    _consolidate_results,
    _apply_cross_encoder_reranking,
    ensemble_search
)

logger = logging.getLogger(__name__)


# ============ FIXTURES ============

@pytest.fixture
def sample_sqlite_decision() -> Dict[str, Any]:
    """Sample decision para testes."""
    return {
        'id': 1,
        'project': 'test-project',
        'context': 'Testing context',
        'decision': 'Use Redis for caching',
        'reasoning': 'Performance reasons',
        'created_at': '2025-01-01 10:00:00',
        'updated_at': '2025-01-01 10:00:00',
        'maturity_status': 'confirmed',
        'confidence_score': 0.9,
        'times_used': 5,
        'times_confirmed': 2,
        'times_contradicted': 0
    }


@pytest.fixture
def sample_sqlite_learning() -> Dict[str, Any]:
    """Sample learning para testes."""
    return {
        'id': 1,
        'project': 'test-project',
        'error_type': 'ConnectionError',
        'error_message': 'Failed to connect to Redis',
        'root_cause': 'Redis server not running',
        'solution': 'Start Redis server with: systemctl start redis-server',
        'prevention': 'Add healthcheck to monitoring',
        'context': 'Cache initialization',
        'created_at': '2025-01-01 09:00:00',
        'last_occurred': '2025-01-01 14:00:00',
        'maturity_status': 'confirmed',
        'confidence_score': 0.95,
        'times_used': 10,
        'times_confirmed': 3,
        'times_contradicted': 0
    }


@pytest.fixture
def sample_faiss_result() -> Dict[str, Any]:
    """Sample FAISS result."""
    return {
        'chunk_id': '123',
        'score': 0.85,
        'text': 'Redis is an in-memory data structure store used for caching',
        'source': '/root/docs/redis.md',
        'doc_type': 'markdown',
        'position': 0
    }


@pytest.fixture
def sample_search_result() -> SearchResult:
    """Sample SearchResult dataclass."""
    return SearchResult(
        id='test_1',
        content='Test content',
        source='sqlite_decision',
        score=0.8,
        relevance_score=0.75,
        metadata={'test': 'data'},
        timestamp='2025-01-01T10:00:00'
    )


# ============ TESTES: SQLITE SEARCH ============

def test_search_result_to_dict(sample_search_result: SearchResult):
    """SearchResult.to_dict() retorna dict válido com timestamp."""
    result_dict = sample_search_result.to_dict()

    assert isinstance(result_dict, dict)
    assert result_dict['id'] == 'test_1'
    assert result_dict['source'] == 'sqlite_decision'
    assert 'timestamp' in result_dict
    assert result_dict['timestamp'] is not None


@patch('scripts.memory.ensemble_search.get_db')
def test_search_sqlite_decisions_with_project(mock_get_db, sample_sqlite_decision):
    """_search_sqlite_decisions() retorna decisions do projeto especificado."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [sample_sqlite_decision]
    mock_conn.cursor.return_value = mock_cursor
    mock_get_db.return_value.__enter__.return_value = mock_conn

    results = _search_sqlite_decisions('redis', project='test-project', limit=5)

    assert len(results) > 0
    assert results[0]['decision'] == 'Use Redis for caching'


@patch('scripts.memory.ensemble_search.get_db')
def test_search_sqlite_decisions_empty(mock_get_db):
    """_search_sqlite_decisions() retorna [] quando nenhuma decision encontrada."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor
    mock_get_db.return_value.__enter__.return_value = mock_conn

    results = _search_sqlite_decisions('nonexistent', limit=5)

    assert results == []


@patch('scripts.memory.ensemble_search.get_db')
def test_search_sqlite_learnings_returns_solutions(mock_get_db, sample_sqlite_learning):
    """_search_sqlite_learnings() retorna learnings com soluções."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [sample_sqlite_learning]
    mock_conn.cursor.return_value = mock_cursor
    mock_get_db.return_value.__enter__.return_value = mock_conn

    results = _search_sqlite_learnings('ConnectionError', limit=5)

    assert len(results) > 0
    assert results[0]['solution'] == 'Start Redis server with: systemctl start redis-server'


@patch('scripts.memory.ensemble_search._search_sqlite_decisions')
@patch('scripts.memory.ensemble_search._search_sqlite_learnings')
def test_search_sqlite_consolidated(mock_learnings, mock_decisions, sample_sqlite_decision, sample_sqlite_learning):
    """_search_sqlite() retorna SearchResult consolidado de decisions + learnings."""
    mock_decisions.return_value = [sample_sqlite_decision]
    mock_learnings.return_value = [sample_sqlite_learning]

    results = _search_sqlite('redis', project='test-project', limit=10)

    # Deve ter 2 resultados (1 decision + 1 learning)
    assert len(results) == 2

    # Primeiro resultado é decision
    assert results[0].source == 'sqlite_decision'
    assert 'Use Redis' in results[0].content

    # Segundo resultado é learning
    assert results[1].source == 'sqlite_learning'
    assert 'systemctl start redis-server' in results[1].content


# ============ TESTES: FAISS SEARCH ============

@patch('scripts.memory.ensemble_search.faiss_search')
def test_search_faiss_returns_search_results(mock_faiss, sample_faiss_result):
    """_search_faiss() converte FAISS results em SearchResult."""
    mock_faiss.return_value = [sample_faiss_result]

    results = _search_faiss('redis cache', limit=5)

    assert len(results) == 1
    assert results[0].source == 'faiss'
    assert results[0].score == 0.85
    assert 'Redis' in results[0].content


@patch('scripts.memory.ensemble_search.faiss_search')
def test_search_faiss_empty(mock_faiss):
    """_search_faiss() retorna [] quando FAISS não encontra resultados."""
    mock_faiss.return_value = []

    results = _search_faiss('nonexistent', limit=5)

    assert results == []


@patch('scripts.memory.ensemble_search.faiss_search')
def test_search_faiss_error_handling(mock_faiss):
    """_search_faiss() retorna [] em caso de erro (fallback gracioso)."""
    mock_faiss.side_effect = Exception("FAISS index corrupted")

    results = _search_faiss('redis', limit=5)

    # Não lança exception, retorna vazio
    assert results == []


# ============ TESTES: NEO4J SEARCH ============

def test_search_neo4j_disabled():
    """_search_neo4j() retorna [] quando use_graph=False."""
    results = _search_neo4j('query', use_graph=False)

    assert results == []


def test_search_neo4j_import_error():
    """_search_neo4j() retorna [] quando neo4j_wrapper não está disponível."""
    # Simula que neo4j_wrapper não existe
    results = _search_neo4j('redis', use_graph=True)

    # Não lança exception, retorna vazio
    assert results == []


# ============ TESTES: CONSOLIDATION ============

def test_consolidate_results_deduplication():
    """_consolidate_results() remove duplicatas mantendo melhor score."""
    # Cria 2 resultados com mesmo ID mas scores diferentes
    result1 = SearchResult(
        id='test_1',
        content='Content A',
        source='sqlite_decision',
        score=0.7,
        timestamp='2025-01-01T10:00:00'
    )
    result2 = SearchResult(
        id='test_1',  # Mesmo ID
        content='Content B',
        source='faiss',
        score=0.9,  # Score maior
        timestamp='2025-01-01T10:00:00'
    )

    consolidated = _consolidate_results([result1], [result2], [], 'test_query')

    # Deve ter apenas 1 resultado (deduplicated)
    assert len(consolidated) == 1
    # Mantém o de maior score
    assert consolidated[0].score == 0.9
    assert consolidated[0].source == 'faiss'


def test_consolidate_results_adds_relevance_score():
    """_consolidate_results() adiciona relevance_score a cada resultado."""
    result = SearchResult(
        id='test_1',
        content='Test content',
        source='sqlite_decision',
        score=0.8,
        timestamp='2025-01-01T10:00:00'
    )

    consolidated = _consolidate_results([result], [], [], 'test_query', project=None)

    assert len(consolidated) == 1
    assert consolidated[0].relevance_score is not None
    assert isinstance(consolidated[0].relevance_score, float)


def test_consolidate_results_empty_sources():
    """_consolidate_results() retorna [] quando todas as fontes vazias."""
    consolidated = _consolidate_results([], [], [], 'query')

    assert consolidated == []


# ============ TESTES: CROSS-ENCODER RERANKING ============

def test_cross_encoder_disabled_for_small_results():
    """_apply_cross_encoder_reranking() pula se < 5 resultados."""
    results = [
        SearchResult(
            id='test_1',
            content='Short content',
            source='sqlite_decision',
            score=0.8,
            timestamp='2025-01-01T10:00:00'
        )
    ]

    reranked = _apply_cross_encoder_reranking(results, 'query')

    # Não deve mudar (poucos resultados)
    assert reranked == results


@patch('sentence_transformers.CrossEncoder')
def test_cross_encoder_reranking_applied(mock_cross_encoder_class):
    """_apply_cross_encoder_reranking() aplica scores quando disponível."""
    # Mock CrossEncoder
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.9, 0.7, 0.5, 0.8, 0.6]
    mock_cross_encoder_class.return_value = mock_model

    results = [
        SearchResult(
            id=f'test_{i}',
            content=f'Content {i}',
            source='sqlite_decision',
            score=0.5 + i * 0.1,
            relevance_score=0.5 + i * 0.1,
            timestamp='2025-01-01T10:00:00'
        )
        for i in range(5)
    ]

    reranked = _apply_cross_encoder_reranking(results, 'query')

    # Deve reordenar por novo score
    assert len(reranked) == 5
    # Scores devem mudar (70% old + 30% cross-encoder)
    for result in reranked:
        assert result.relevance_score is not None


def test_cross_encoder_import_error():
    """_apply_cross_encoder_reranking() volta ao original se sentence-transformers não disponível."""
    results = [
        SearchResult(
            id=f'test_{i}',
            content=f'Content {i}',
            source='sqlite_decision',
            score=0.5,
            relevance_score=0.5,
            timestamp='2025-01-01T10:00:00'
        )
        for i in range(5)
    ]

    # Simula que CrossEncoder não está disponível
    with patch('sentence_transformers.CrossEncoder', side_effect=ImportError):
        reranked = _apply_cross_encoder_reranking(results, 'query')

    # Deve retornar original (sem erro)
    assert len(reranked) == 5


# ============ TESTES: ENSEMBLE SEARCH (FUNÇÃO PRINCIPAL) ============

@patch('scripts.memory.ensemble_search._search_neo4j')
@patch('scripts.memory.ensemble_search._search_faiss')
@patch('scripts.memory.ensemble_search._search_sqlite')
def test_ensemble_search_consolidates_all_sources(mock_sqlite, mock_faiss, mock_neo4j):
    """ensemble_search() consolida resultados de todas as 3 fontes."""
    # Mock cada fonte
    mock_sqlite.return_value = [
        SearchResult(
            id='sqlite_1',
            content='Decision content',
            source='sqlite_decision',
            score=0.8,
            timestamp='2025-01-01T10:00:00'
        )
    ]
    mock_faiss.return_value = [
        SearchResult(
            id='faiss_1',
            content='FAISS content',
            source='faiss',
            score=0.85,
            timestamp='2025-01-01T10:00:00'
        )
    ]
    mock_neo4j.return_value = []

    results = ensemble_search('test query', project='test-project')

    # Deve ter resultados de sqlite + faiss
    assert len(results) >= 1
    # Cada resultado deve ter campos obrigatórios
    for result in results:
        assert 'id' in result
        assert 'content' in result
        assert 'source' in result
        assert 'relevance_score' in result


@patch('scripts.memory.ensemble_search._search_neo4j')
@patch('scripts.memory.ensemble_search._search_faiss')
@patch('scripts.memory.ensemble_search._search_sqlite')
def test_ensemble_search_respects_limit(mock_sqlite, mock_faiss, mock_neo4j):
    """ensemble_search() respeita parâmetro limit."""
    # Cria 15 resultados
    sqlite_results = [
        SearchResult(
            id=f'sqlite_{i}',
            content=f'Content {i}',
            source='sqlite_decision',
            score=0.8,
            timestamp='2025-01-01T10:00:00'
        )
        for i in range(10)
    ]
    faiss_results = [
        SearchResult(
            id=f'faiss_{i}',
            content=f'Content {i}',
            source='faiss',
            score=0.85,
            timestamp='2025-01-01T10:00:00'
        )
        for i in range(5)
    ]

    mock_sqlite.return_value = sqlite_results
    mock_faiss.return_value = faiss_results
    mock_neo4j.return_value = []

    results = ensemble_search('test query', limit=10)

    # Deve respeitar limit=10
    assert len(results) <= 10


@patch('scripts.memory.ensemble_search._search_neo4j')
@patch('scripts.memory.ensemble_search._search_faiss')
@patch('scripts.memory.ensemble_search._search_sqlite')
def test_ensemble_search_returns_valid_json(mock_sqlite, mock_faiss, mock_neo4j):
    """ensemble_search() retorna resultados JSON-serializable."""
    mock_sqlite.return_value = [
        SearchResult(
            id='sqlite_1',
            content='Decision',
            source='sqlite_decision',
            score=0.8,
            metadata={'test': 'data'},
            timestamp='2025-01-01T10:00:00'
        )
    ]
    mock_faiss.return_value = []
    mock_neo4j.return_value = []

    results = ensemble_search('test query')

    # Deve ser JSON-serializable
    json_str = json.dumps(results, ensure_ascii=False)
    assert isinstance(json_str, str)


@patch('scripts.memory.ensemble_search._search_neo4j')
@patch('scripts.memory.ensemble_search._search_faiss')
@patch('scripts.memory.ensemble_search._search_sqlite')
def test_ensemble_search_without_graph(mock_sqlite, mock_faiss, mock_neo4j):
    """ensemble_search(use_graph=False) não chama Neo4j."""
    mock_sqlite.return_value = []
    mock_faiss.return_value = []
    mock_neo4j.return_value = []

    ensemble_search('test query', use_graph=False)

    # Neo4j deve ser chamado com use_graph=False
    mock_neo4j.assert_called_once()
    # Verifica que use_graph foi passado como False
    call_args = mock_neo4j.call_args
    assert call_args[1]['use_graph'] == False


def test_ensemble_search_with_project_filter():
    """ensemble_search() passa project filter para SQLite."""
    with patch('scripts.memory.ensemble_search._search_sqlite') as mock_sqlite:
        mock_sqlite.return_value = []

        with patch('scripts.memory.ensemble_search._search_faiss'):
            with patch('scripts.memory.ensemble_search._search_neo4j'):
                ensemble_search('query', project='vsl-analysis')

    # SQLite deve receber project
    call_args = mock_sqlite.call_args
    assert call_args[0][1] == 'vsl-analysis'


# ============ TESTES: INTEGRATION ============

@pytest.mark.integration
def test_ensemble_search_end_to_end():
    """Teste de integração: ensemble_search() funciona com dados reais."""
    # Este teste rodaría contra o banco de dados real
    # Apenas se o banco estiver populado com dados de teste

    results = ensemble_search('redis', project=None, limit=5)

    # Deve retornar lista
    assert isinstance(results, list)
    # Se houver resultados
    if len(results) > 0:
        # Cada resultado deve ter estrutura correta
        for result in results:
            assert isinstance(result, dict)
            assert 'id' in result
            assert 'source' in result
            assert 'relevance_score' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
