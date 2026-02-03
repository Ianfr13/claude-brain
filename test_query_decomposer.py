#!/usr/bin/env python3
"""
Test suite para Query Decomposer Module

Testa:
1. Estruturas de dados (SubQuery, DecompositionResult)
2. Logging
3. Simulação de providers
4. Fallback automático
5. JSON serialization
"""

import sys
import json
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime

# Adicionar path
sys.path.insert(0, '/root/claude-brain')

from scripts.memory.query_decomposer import (
    SubQuery,
    DecompositionResult,
    QueryDecomposer,
    decompose_query,
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ============ MOCK DATA ============

MOCK_DECOMPOSITION_RESULT = {
    "sub_queries": [
        {
            "query": "Como implementar cache com TTL?",
            "type": "semantic",
            "confidence": 0.95,
            "weight": 1.5,
            "tags": ["cache", "redis", "ttl"]
        },
        {
            "query": "Redis Python client",
            "type": "entity",
            "confidence": 0.88,
            "weight": 1.0,
            "tags": ["redis", "python", "client"]
        },
        {
            "query": "24 horas em segundos",
            "type": "temporal",
            "confidence": 0.99,
            "weight": 0.5,
            "tags": ["temporal", "conversion"]
        }
    ],
    "decomposition_confidence": 0.87,
    "reasoning": "Query decomposta em 3 sub-queries: semântica (cache), entidade (Redis), temporal (TTL)"
}


# ============ TEST CASES ============

def test_subquery_structure():
    """Testa estrutura de SubQuery"""
    print("\n" + "="*70)
    print("TEST 1: SubQuery Structure")
    print("="*70)

    sq = SubQuery(
        query="Test query",
        type="semantic",
        confidence=0.95,
        weight=1.0,
        tags=["tag1", "tag2"]
    )

    print(f"✓ SubQuery criada: {sq}")
    assert sq.query == "Test query"
    assert sq.type == "semantic"
    assert sq.confidence == 0.95
    assert sq.weight == 1.0
    assert len(sq.tags) == 2

    # Test to_dict
    sq_dict = sq.to_dict()
    print(f"✓ to_dict(): {json.dumps(sq_dict, indent=2, ensure_ascii=False)}")
    assert isinstance(sq_dict, dict)
    assert sq_dict["query"] == "Test query"

    print("✓ SubQuery tests passed\n")


def test_decomposition_result():
    """Testa estrutura de DecompositionResult"""
    print("="*70)
    print("TEST 2: DecompositionResult Structure")
    print("="*70)

    sub_queries = [
        SubQuery("Query 1", "semantic", 0.9, 1.0, ["tag1"]),
        SubQuery("Query 2", "entity", 0.85, 1.0, ["tag2"]),
    ]

    result = DecompositionResult(
        original_query="Test query",
        sub_queries=sub_queries,
        decomposition_confidence=0.87,
        provider="test_provider",
        model_used="test_model",
        timestamp=datetime.now().isoformat(),
        processing_time_ms=125.5
    )

    print(f"✓ DecompositionResult criada")
    print(f"  - Original query: {result.original_query}")
    print(f"  - Sub-queries: {len(result.sub_queries)}")
    print(f"  - Confiança: {result.decomposition_confidence}")
    print(f"  - Provider: {result.provider}")
    print(f"  - Tempo: {result.processing_time_ms}ms")

    # Test to_dict
    result_dict = result.to_dict()
    print(f"\n✓ to_dict() serialization:")
    print(json.dumps(result_dict, indent=2, ensure_ascii=False))

    assert isinstance(result_dict, dict)
    assert len(result_dict["sub_queries"]) == 2
    assert result_dict["provider"] == "test_provider"

    print("\n✓ DecompositionResult tests passed\n")


def test_query_decomposer_mock():
    """Testa QueryDecomposer com mocks"""
    print("="*70)
    print("TEST 3: QueryDecomposer with Mocks")
    print("="*70)

    # Mock OpenRouter
    with patch('scripts.memory.query_decomposer.OpenRouterDecomposer') as MockOR:
        mock_or_instance = MagicMock()
        mock_or_instance.available = False
        MockOR.return_value = mock_or_instance

        # Mock Anthropic
        with patch('scripts.memory.query_decomposer.AnthropicDecomposer') as MockAnth:
            mock_anth_instance = MagicMock()
            mock_anth_instance.available = True
            mock_anth_instance.decompose.return_value = MOCK_DECOMPOSITION_RESULT
            MockAnth.return_value = mock_anth_instance

            decomposer = QueryDecomposer()
            print(f"✓ QueryDecomposer criada")
            print(f"  - OpenRouter disponível: {decomposer.openrouter.available}")
            print(f"  - Anthropic disponível: {decomposer.anthropic.available}")

            # Test decompose
            result = decomposer.decompose("Como implementar cache com TTL?")
            print(f"\n✓ Decomposição executada")
            print(f"  - Provider usado: {result.provider}")
            print(f"  - Modelo: {result.model_used}")
            print(f"  - Sub-queries: {len(result.sub_queries)}")
            print(f"  - Confiança: {result.decomposition_confidence}")

            assert result.provider == "anthropic"
            assert len(result.sub_queries) == 3
            assert result.sub_queries[0].query == "Como implementar cache com TTL?"

    print("\n✓ QueryDecomposer mock tests passed\n")


def test_fallback_chain():
    """Testa fallback automático"""
    print("="*70)
    print("TEST 4: Fallback Chain")
    print("="*70)

    # Cenário: OpenRouter falha, Anthropic sucede
    with patch('scripts.memory.query_decomposer.OpenRouterDecomposer') as MockOR:
        mock_or_instance = MagicMock()
        mock_or_instance.available = True
        mock_or_instance.decompose.return_value = None  # Simula falha
        MockOR.return_value = mock_or_instance

        with patch('scripts.memory.query_decomposer.AnthropicDecomposer') as MockAnth:
            mock_anth_instance = MagicMock()
            mock_anth_instance.available = True
            mock_anth_instance.decompose.return_value = MOCK_DECOMPOSITION_RESULT
            MockAnth.return_value = mock_anth_instance

            decomposer = QueryDecomposer()
            result = decomposer.decompose("Test query")

            print(f"✓ Fallback chain executado")
            print(f"  - Tentativa 1 (OpenRouter): FALHA")
            print(f"  - Tentativa 2 (Anthropic): SUCESSO")
            print(f"  - Provider final: {result.provider}")

            assert result.provider == "anthropic"
            assert len(result.sub_queries) > 0

    print("\n✓ Fallback chain tests passed\n")


def test_error_handling():
    """Testa tratamento de erros"""
    print("="*70)
    print("TEST 5: Error Handling")
    print("="*70)

    # Cenário: Ambos os providers falham
    with patch('scripts.memory.query_decomposer.OpenRouterDecomposer') as MockOR:
        mock_or_instance = MagicMock()
        mock_or_instance.available = False
        MockOR.return_value = mock_or_instance

        with patch('scripts.memory.query_decomposer.AnthropicDecomposer') as MockAnth:
            mock_anth_instance = MagicMock()
            mock_anth_instance.available = False
            MockAnth.return_value = mock_anth_instance

            decomposer = QueryDecomposer()
            result = decomposer.decompose("Test query")

            print(f"✓ Erro tratado corretamente")
            print(f"  - Provider: {result.provider}")
            print(f"  - Confiança: {result.decomposition_confidence}")
            print(f"  - Erro: {result.error}")

            assert result.provider == "none"
            assert result.decomposition_confidence == 0.0
            assert result.error is not None
            assert len(result.sub_queries) == 0

    print("\n✓ Error handling tests passed\n")


def test_json_serialization():
    """Testa serialização JSON completa"""
    print("="*70)
    print("TEST 6: JSON Serialization")
    print("="*70)

    sub_queries = [
        SubQuery("Query 1", "semantic", 0.9, 1.0, ["tag1"]),
        SubQuery("Query 2", "entity", 0.85, 1.0, ["tag2"]),
    ]

    result = DecompositionResult(
        original_query="Query com caracteres especiais: éçã",
        sub_queries=sub_queries,
        decomposition_confidence=0.87,
        provider="test",
        model_used="test-model",
        timestamp="2024-01-01T12:00:00",
        processing_time_ms=123.45
    )

    # Serialize
    result_dict = result.to_dict()
    json_str = json.dumps(result_dict, indent=2, ensure_ascii=False)

    print(f"✓ Serialização JSON bem-sucedida")
    print(f"  - Tamanho: {len(json_str)} bytes")
    print(f"  - Caracteres especiais: OK")

    # Deserialize
    loaded_dict = json.loads(json_str)
    assert loaded_dict["original_query"] == "Query com caracteres especiais: éçã"
    assert len(loaded_dict["sub_queries"]) == 2

    print(f"\n✓ Desserialização bem-sucedida")
    print(f"JSON Output:\n{json_str}\n")

    print("✓ JSON serialization tests passed\n")


def test_logging():
    """Testa logging output"""
    print("="*70)
    print("TEST 7: Logging")
    print("="*70)

    # Capture logs
    import io
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)

    logger_test = logging.getLogger('scripts.memory.query_decomposer')
    logger_test.addHandler(handler)

    # Mock and run
    with patch('scripts.memory.query_decomposer.OpenRouterDecomposer') as MockOR:
        mock_or = MagicMock()
        mock_or.available = True
        mock_or.decompose.return_value = MOCK_DECOMPOSITION_RESULT
        MockOR.return_value = mock_or

        with patch('scripts.memory.query_decomposer.AnthropicDecomposer') as MockAnth:
            mock_anth = MagicMock()
            mock_anth.available = False
            MockAnth.return_value = mock_anth

            decomposer = QueryDecomposer()
            result = decomposer.decompose("Test query")

            log_output = log_capture.getvalue()
            print(f"✓ Logging capturado:")
            print(f"{log_output}")

            assert "Iniciando decomposição" in log_output
            assert "OpenRouter" in log_output

    print("\n✓ Logging tests passed\n")


def run_all_tests():
    """Executa todos os testes"""
    print("\n" + "="*70)
    print("QUERY DECOMPOSER - TEST SUITE")
    print("="*70)

    tests = [
        test_subquery_structure,
        test_decomposition_result,
        test_query_decomposer_mock,
        test_fallback_chain,
        test_error_handling,
        test_json_serialization,
        test_logging,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ FAILED: {test_func.__name__}")
            print(f"  Error: {e}\n")
            failed += 1
        except Exception as e:
            print(f"\n✗ ERROR: {test_func.__name__}")
            print(f"  Exception: {e}\n")
            failed += 1

    print("="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    print("="*70 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
