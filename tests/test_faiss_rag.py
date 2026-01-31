#!/usr/bin/env python3
"""
Testes unitarios para faiss_rag.py

Cobertura alvo: >=70% do modulo faiss_rag.py

Funcoes testadas:
- semantic_search() - busca basica, com cache, com filtro doc_type, com limite
- build_faiss_index() - construcao do indice
- is_index_stale() - deteccao de indice obsoleto
- load_query_cache() - cache com TTL, expiracao
- Cache invalidation - invalidacao apos rebuild
"""

import sys
import json
import time
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import numpy as np

# Adiciona scripts ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Mock faiss antes de importar faiss_rag (faiss e importado lazy dentro das funcoes)
mock_faiss_module = MagicMock()
sys.modules['faiss'] = mock_faiss_module


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_brain_dir(tmp_path):
    """Cria estrutura temporaria do brain para testes."""
    brain_dir = tmp_path / "claude-brain"
    rag_dir = brain_dir / "rag"
    faiss_dir = rag_dir / "faiss"
    faiss_dir.mkdir(parents=True)

    return {
        "brain_dir": brain_dir,
        "rag_dir": rag_dir,
        "faiss_dir": faiss_dir,
        "index_file": rag_dir / "index.json",
        "faiss_index_file": faiss_dir / "index.faiss",
        "faiss_meta_file": faiss_dir / "metadata.json",
        "cache_file": rag_dir / "query_cache.json",
        "rebuild_state_file": faiss_dir / "rebuild_state.json",
    }


@pytest.fixture
def mock_faiss():
    """Mock do modulo FAISS."""
    # Mock do indice FAISS
    mock_index = MagicMock()
    mock_index.ntotal = 10
    mock_index.search.return_value = (
        np.array([[0.95, 0.85, 0.75, 0.65, 0.55]], dtype=np.float32),
        np.array([[0, 1, 2, 3, 4]], dtype=np.int64)
    )

    mock_faiss_module.IndexFlatIP.return_value = mock_index
    mock_faiss_module.read_index.return_value = mock_index
    mock_faiss_module.normalize_L2 = MagicMock()
    mock_faiss_module.write_index = MagicMock()

    yield mock_faiss_module, mock_index


@pytest.fixture
def mock_model():
    """Mock do modelo de embeddings."""
    mock = MagicMock()
    mock.encode.return_value = np.random.rand(1, 384).astype('float32')
    return mock


@pytest.fixture
def sample_doc_index():
    """Indice de documentos de exemplo."""
    return {
        "documents": {
            "abc123": {
                "source": "/tmp/test_doc1.md",
                "doc_type": "markdown"
            },
            "def456": {
                "source": "/tmp/test_doc2.py",
                "doc_type": "python"
            },
            "ghi789": {
                "source": "/tmp/test_doc3.yaml",
                "doc_type": "yaml"
            }
        }
    }


@pytest.fixture
def sample_faiss_metadata():
    """Metadados FAISS de exemplo."""
    return {
        "texts": [
            "Texto do chunk 0 sobre Python",
            "Texto do chunk 1 sobre cache",
            "Texto do chunk 2 sobre FAISS",
            "Texto do chunk 3 sobre testes",
            "Texto do chunk 4 sobre embeddings"
        ],
        "meta": [
            {"source": "/tmp/test_doc1.md", "doc_type": "markdown", "position": 0},
            {"source": "/tmp/test_doc2.py", "doc_type": "python", "position": 0},
            {"source": "/tmp/test_doc1.md", "doc_type": "markdown", "position": 1500},
            {"source": "/tmp/test_doc2.py", "doc_type": "python", "position": 1500},
            {"source": "/tmp/test_doc3.yaml", "doc_type": "yaml", "position": 0}
        ]
    }


# =============================================================================
# Tests: load_query_cache()
# =============================================================================

class TestLoadQueryCache:
    """Testes para load_query_cache() - cache com TTL e expiracao."""

    def test_load_empty_cache_when_file_not_exists(self, temp_brain_dir):
        """Retorna dict vazio quando arquivo de cache nao existe."""
        import faiss_rag

        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]):
            result = faiss_rag.load_query_cache()
            assert result == {}

    def test_load_cache_with_valid_entries(self, temp_brain_dir):
        """Carrega entradas validas do cache."""
        import faiss_rag

        current_time = time.time()
        cache_data = {
            "query1:None:5": {"data": [{"score": 0.9}], "timestamp": current_time}
        }
        temp_brain_dir["cache_file"].write_text(json.dumps(cache_data))

        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]):
            result = faiss_rag.load_query_cache()
            assert "query1:None:5" in result
            assert result["query1:None:5"]["data"] == [{"score": 0.9}]

    def test_cache_ttl_expiration(self, temp_brain_dir):
        """Entradas expiradas sao removidas do cache."""
        import faiss_rag

        old_timestamp = time.time() - (faiss_rag.CACHE_TTL_SECONDS + 100)
        cache_data = {
            "expired_query:None:5": {"data": [{"score": 0.5}], "timestamp": old_timestamp}
        }
        temp_brain_dir["cache_file"].write_text(json.dumps(cache_data))

        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]):
            result = faiss_rag.load_query_cache()
            assert "expired_query:None:5" not in result

    def test_cache_converts_old_format(self, temp_brain_dir):
        """Formato antigo (lista direta) e convertido para novo formato."""
        import faiss_rag

        # Formato antigo: valor e lista diretamente
        cache_data = {
            "old_query:None:5": [{"score": 0.8}]
        }
        temp_brain_dir["cache_file"].write_text(json.dumps(cache_data))

        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]):
            result = faiss_rag.load_query_cache()
            assert "old_query:None:5" in result
            assert "data" in result["old_query:None:5"]
            assert "timestamp" in result["old_query:None:5"]

    def test_cache_handles_invalid_json(self, temp_brain_dir):
        """Retorna dict vazio quando JSON e invalido."""
        import faiss_rag

        temp_brain_dir["cache_file"].write_text("invalid json {{{")

        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]):
            result = faiss_rag.load_query_cache()
            assert result == {}


# =============================================================================
# Tests: is_index_stale()
# =============================================================================

class TestIsIndexStale:
    """Testes para is_index_stale() - deteccao de indice obsoleto."""

    def test_stale_when_index_not_exists(self, temp_brain_dir):
        """Indice e obsoleto quando arquivos FAISS nao existem."""
        import faiss_rag

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]):

            is_stale, reason = faiss_rag.is_index_stale()
            assert is_stale is True
            assert "nao existe" in reason.lower() or "não existe" in reason.lower()

    def test_stale_when_index_json_modified(self, temp_brain_dir):
        """Indice e obsoleto quando index.json foi modificado apos o indice."""
        import faiss_rag

        # Cria arquivos FAISS
        temp_brain_dir["faiss_index_file"].write_bytes(b"fake faiss index")
        temp_brain_dir["faiss_meta_file"].write_text('{}')
        time.sleep(0.1)  # Garante timestamps diferentes

        # Cria index.json mais novo
        temp_brain_dir["index_file"].write_text('{"documents": {}}')

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]):

            is_stale, reason = faiss_rag.is_index_stale()
            assert is_stale is True
            assert "index.json" in reason.lower()

    def test_stale_when_documents_hash_changed(self, temp_brain_dir, sample_doc_index):
        """Indice e obsoleto quando hash dos documentos mudou."""
        import faiss_rag

        # Cria arquivos com mesmo timestamp (index.json primeiro)
        temp_brain_dir["index_file"].write_text(json.dumps(sample_doc_index))
        time.sleep(0.1)
        temp_brain_dir["faiss_index_file"].write_bytes(b"fake faiss index")
        temp_brain_dir["faiss_meta_file"].write_text('{}')

        # Estado de rebuild com hash diferente
        rebuild_state = {"documents_hash": "old_hash_that_does_not_match"}
        temp_brain_dir["rebuild_state_file"].write_text(json.dumps(rebuild_state))

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]):

            is_stale, reason = faiss_rag.is_index_stale()
            assert is_stale is True
            assert "hash" in reason.lower()

    def test_not_stale_when_up_to_date(self, temp_brain_dir):
        """Indice nao e obsoleto quando esta atualizado."""
        import faiss_rag

        # Cria index.json primeiro
        temp_brain_dir["index_file"].write_text('{"documents": {}}')
        time.sleep(0.1)

        # Depois cria arquivos FAISS
        temp_brain_dir["faiss_index_file"].write_bytes(b"fake faiss index")
        temp_brain_dir["faiss_meta_file"].write_text('{}')

        # Hash correspondente (vazio pois nao tem documentos)
        current_hash = faiss_rag.compute_documents_hash({"documents": {}})
        rebuild_state = {"documents_hash": current_hash}
        temp_brain_dir["rebuild_state_file"].write_text(json.dumps(rebuild_state))

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]):

            is_stale, reason = faiss_rag.is_index_stale()
            assert is_stale is False
            assert "atualizado" in reason.lower()

    def test_stale_when_source_file_modified(self, temp_brain_dir):
        """Indice e obsoleto quando arquivo fonte foi modificado apos o indice."""
        import faiss_rag

        # Cria arquivo fonte ANTES do indice
        source_file = temp_brain_dir["brain_dir"] / "doc.md"
        source_file.write_text("initial content")
        time.sleep(0.1)

        # Cria index.json com referencia ao arquivo
        doc_index = {"documents": {"abc": {"source": str(source_file)}}}
        temp_brain_dir["index_file"].write_text(json.dumps(doc_index))
        time.sleep(0.1)

        # Cria arquivos FAISS
        temp_brain_dir["faiss_index_file"].write_bytes(b"fake faiss index")
        temp_brain_dir["faiss_meta_file"].write_text('{}')
        time.sleep(0.1)

        # Modifica arquivo fonte DEPOIS do indice
        source_file.write_text("modified content")

        # Hash correspondente
        current_hash = faiss_rag.compute_documents_hash(doc_index)
        rebuild_state = {"documents_hash": current_hash}
        temp_brain_dir["rebuild_state_file"].write_text(json.dumps(rebuild_state))

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]):

            is_stale, reason = faiss_rag.is_index_stale()
            assert is_stale is True
            assert "arquivo modificado" in reason.lower()


# =============================================================================
# Tests: build_faiss_index()
# =============================================================================

class TestBuildFaissIndex:
    """Testes para build_faiss_index() - construcao do indice."""

    def test_build_returns_exists_when_index_exists(self, temp_brain_dir, mock_faiss, sample_faiss_metadata):
        """Retorna status 'exists' quando indice ja existe e force=False."""
        import faiss_rag

        mock_faiss_module, mock_index = mock_faiss

        # Cria arquivos de indice
        temp_brain_dir["faiss_index_file"].write_bytes(b"fake faiss index")
        temp_brain_dir["faiss_meta_file"].write_text(json.dumps(sample_faiss_metadata))

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            result = faiss_rag.build_faiss_index(force=False)
            assert result["status"] == "exists"
            assert result["count"] == 10  # mock_index.ntotal

    def test_build_error_when_no_documents(self, temp_brain_dir, mock_faiss):
        """Retorna erro quando nao ha documentos para indexar."""
        import faiss_rag

        # Cria index.json vazio
        temp_brain_dir["index_file"].write_text('{"documents": {}}')

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None):

            result = faiss_rag.build_faiss_index(force=True)
            assert result["status"] == "error"
            assert "nenhum documento" in result["message"].lower()

    def test_build_creates_index_with_documents(self, temp_brain_dir, mock_faiss, mock_model, sample_doc_index):
        """Cria indice quando ha documentos validos."""
        import faiss_rag

        # Cria documentos de teste
        doc1 = temp_brain_dir["brain_dir"] / "test_doc1.md"
        doc1.write_text("# Documento de teste\n\nConteudo extenso para testar embeddings. " * 20)

        sample_doc_index["documents"]["abc123"]["source"] = str(doc1)
        temp_brain_dir["index_file"].write_text(json.dumps(sample_doc_index))

        # Mock encode para retornar embeddings do tamanho correto
        mock_model.encode.return_value = np.random.rand(5, 384).astype('float32')

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]), \
             patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, '_model', mock_model):

            result = faiss_rag.build_faiss_index(force=True, log_rebuild=True)
            assert result["status"] == "rebuilt"
            assert "count" in result
            assert "elapsed_seconds" in result

    def test_build_logs_rebuild_info(self, temp_brain_dir, mock_faiss, mock_model, caplog):
        """Log de rebuild e gravado quando log_rebuild=True."""
        import faiss_rag
        import logging

        # Cria documento de teste
        doc1 = temp_brain_dir["brain_dir"] / "test_doc.md"
        doc1.write_text("Conteudo de teste para logging. " * 50)

        doc_index = {
            "documents": {
                "abc123": {"source": str(doc1), "doc_type": "markdown"}
            }
        }
        temp_brain_dir["index_file"].write_text(json.dumps(doc_index))

        mock_model.encode.return_value = np.random.rand(1, 384).astype('float32')

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]), \
             patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, '_model', mock_model), \
             caplog.at_level(logging.INFO, logger="faiss_rag"):

            faiss_rag.build_faiss_index(force=True, log_rebuild=True)

            # Verifica que logs foram emitidos
            assert any("INICIANDO REBUILD" in record.message for record in caplog.records)


# =============================================================================
# Tests: semantic_search()
# =============================================================================

class TestSemanticSearch:
    """Testes para semantic_search() - busca semantica."""

    def test_search_returns_results_from_cache(self, temp_brain_dir):
        """Retorna resultados do cache quando disponivel."""
        import faiss_rag

        cached_results = [{"chunk_id": "0", "score": 0.95, "text": "cached result"}]
        cache_data = {
            "test query:None:5": {"data": cached_results, "timestamp": time.time()}
        }
        temp_brain_dir["cache_file"].write_text(json.dumps(cache_data))

        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]):
            result = faiss_rag.semantic_search("test query", limit=5)
            assert result == cached_results

    def test_search_basic_query(self, temp_brain_dir, mock_faiss, mock_model, sample_faiss_metadata):
        """Busca basica retorna resultados ordenados por score."""
        import faiss_rag

        # Configura metadados
        temp_brain_dir["faiss_index_file"].write_bytes(b"fake")
        temp_brain_dir["faiss_meta_file"].write_text(json.dumps(sample_faiss_metadata))

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, '_model', mock_model), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            results = faiss_rag.semantic_search("Python embeddings", limit=3)

            assert isinstance(results, list)
            assert len(results) <= 3
            if results:
                assert "score" in results[0]
                assert "text" in results[0]
                assert "source" in results[0]

    def test_search_with_doc_type_filter(self, temp_brain_dir, mock_faiss, mock_model, sample_faiss_metadata):
        """Busca com filtro doc_type retorna apenas documentos do tipo especificado."""
        import faiss_rag

        temp_brain_dir["faiss_index_file"].write_bytes(b"fake")
        temp_brain_dir["faiss_meta_file"].write_text(json.dumps(sample_faiss_metadata))

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, '_model', mock_model), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            results = faiss_rag.semantic_search("query", doc_type="markdown", limit=5)

            for r in results:
                assert r["doc_type"] == "markdown"

    def test_search_respects_limit(self, temp_brain_dir, mock_faiss, mock_model, sample_faiss_metadata):
        """Busca respeita o limite de resultados."""
        import faiss_rag

        temp_brain_dir["faiss_index_file"].write_bytes(b"fake")
        temp_brain_dir["faiss_meta_file"].write_text(json.dumps(sample_faiss_metadata))

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, '_model', mock_model), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            results = faiss_rag.semantic_search("query", limit=2)
            assert len(results) <= 2

    def test_search_builds_index_if_not_exists(self, temp_brain_dir, mock_faiss, mock_model):
        """Busca constroi indice automaticamente se nao existir."""
        import faiss_rag

        # Nao cria arquivos de indice - devera tentar construir
        temp_brain_dir["index_file"].write_text('{"documents": {}}')

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, '_model', mock_model), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            # Sem documentos, build retorna erro e search retorna lista vazia
            results = faiss_rag.semantic_search("query")
            assert results == []

    def test_search_saves_to_cache(self, temp_brain_dir, mock_faiss, mock_model, sample_faiss_metadata):
        """Busca salva resultados no cache."""
        import faiss_rag

        temp_brain_dir["faiss_index_file"].write_bytes(b"fake")
        temp_brain_dir["faiss_meta_file"].write_text(json.dumps(sample_faiss_metadata))

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, '_model', mock_model), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            # Primeira busca - nao esta no cache
            faiss_rag.semantic_search("new unique query xyz", limit=3)

            # Verifica que foi salvo no cache
            assert temp_brain_dir["cache_file"].exists()
            cache = json.loads(temp_brain_dir["cache_file"].read_text())
            assert "new unique query xyz:None:3" in cache


# =============================================================================
# Tests: Cache Invalidation
# =============================================================================

class TestCacheInvalidation:
    """Testes para invalidacao de cache apos rebuild."""

    def test_invalidate_removes_cache_file(self, temp_brain_dir):
        """invalidate_query_cache() remove arquivo de cache."""
        import faiss_rag

        # Cria cache
        temp_brain_dir["cache_file"].write_text('{"test": {"data": [], "timestamp": 0}}')
        assert temp_brain_dir["cache_file"].exists()

        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]):
            faiss_rag.invalidate_query_cache()
            assert not temp_brain_dir["cache_file"].exists()

    def test_invalidate_handles_missing_file(self, temp_brain_dir):
        """invalidate_query_cache() nao falha se arquivo nao existe."""
        import faiss_rag

        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]):
            # Nao deve lancar excecao
            faiss_rag.invalidate_query_cache()

    def test_invalidate_handles_unlink_error(self, temp_brain_dir, caplog):
        """invalidate_query_cache() loga warning se erro ao remover arquivo."""
        import faiss_rag
        import logging

        # Cria arquivo de cache
        temp_brain_dir["cache_file"].write_text('{}')

        # Mock unlink para lancar excecao
        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]), \
             patch.object(Path, 'unlink', side_effect=PermissionError("Permission denied")), \
             caplog.at_level(logging.WARNING, logger="faiss_rag"):

            faiss_rag.invalidate_query_cache()

            # Verifica que warning foi logado
            assert any("Erro ao invalidar cache" in record.message for record in caplog.records)

    def test_build_invalidates_cache(self, temp_brain_dir, mock_faiss, mock_model):
        """build_faiss_index() invalida cache apos rebuild."""
        import faiss_rag

        # Cria documento de teste
        doc1 = temp_brain_dir["brain_dir"] / "test_doc.md"
        doc1.write_text("Conteudo de teste. " * 50)

        doc_index = {
            "documents": {
                "abc123": {"source": str(doc1), "doc_type": "markdown"}
            }
        }
        temp_brain_dir["index_file"].write_text(json.dumps(doc_index))

        # Cria cache existente
        temp_brain_dir["cache_file"].write_text('{"old_query": {"data": [], "timestamp": 0}}')

        mock_model.encode.return_value = np.random.rand(1, 384).astype('float32')

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]), \
             patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, '_model', mock_model):

            faiss_rag.build_faiss_index(force=True)

            # Cache deve ter sido removido
            assert not temp_brain_dir["cache_file"].exists()


# =============================================================================
# Tests: save_query_cache()
# =============================================================================

class TestSaveQueryCache:
    """Testes para save_query_cache() - salvar cache no disco."""

    def test_save_creates_file(self, temp_brain_dir):
        """save_query_cache() cria arquivo de cache."""
        import faiss_rag

        cache = {"query1:None:5": {"data": [{"score": 0.9}], "timestamp": time.time()}}

        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]):
            faiss_rag.save_query_cache(cache)

            assert temp_brain_dir["cache_file"].exists()
            saved = json.loads(temp_brain_dir["cache_file"].read_text())
            assert "query1:None:5" in saved

    def test_save_limits_cache_size(self, temp_brain_dir):
        """save_query_cache() limita tamanho do cache."""
        import faiss_rag

        # Cria cache maior que o limite
        cache = {}
        current_time = time.time()
        for i in range(faiss_rag.CACHE_MAX_SIZE + 20):
            cache[f"query{i}:None:5"] = {"data": [], "timestamp": current_time - i}

        with patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]):
            faiss_rag.save_query_cache(cache)

            saved = json.loads(temp_brain_dir["cache_file"].read_text())
            assert len(saved) <= faiss_rag.CACHE_MAX_SIZE


# =============================================================================
# Tests: compute_documents_hash()
# =============================================================================

class TestComputeDocumentsHash:
    """Testes para compute_documents_hash()."""

    def test_hash_is_deterministic(self):
        """Mesmo indice gera mesmo hash."""
        import faiss_rag

        doc_index = {
            "documents": {
                "abc": {"source": "/tmp/test.md"},
                "def": {"source": "/tmp/test2.py"}
            }
        }

        hash1 = faiss_rag.compute_documents_hash(doc_index)
        hash2 = faiss_rag.compute_documents_hash(doc_index)
        assert hash1 == hash2

    def test_hash_changes_with_different_docs(self):
        """Indices diferentes geram hashes diferentes."""
        import faiss_rag

        doc_index1 = {"documents": {"abc": {"source": "/tmp/test1.md"}}}
        doc_index2 = {"documents": {"xyz": {"source": "/tmp/test2.md"}}}

        hash1 = faiss_rag.compute_documents_hash(doc_index1)
        hash2 = faiss_rag.compute_documents_hash(doc_index2)
        assert hash1 != hash2

    def test_hash_empty_index(self):
        """Indice vazio gera hash valido."""
        import faiss_rag

        doc_index = {"documents": {}}
        result = faiss_rag.compute_documents_hash(doc_index)
        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 hex

    def test_hash_includes_file_mtime(self, temp_brain_dir):
        """Hash inclui mtime de arquivos existentes."""
        import faiss_rag

        # Cria arquivo de teste
        test_file = temp_brain_dir["brain_dir"] / "test.md"
        test_file.write_text("test content")

        doc_index = {"documents": {"abc": {"source": str(test_file)}}}

        hash1 = faiss_rag.compute_documents_hash(doc_index)

        # Modifica o arquivo (muda mtime)
        time.sleep(0.1)
        test_file.write_text("modified content")

        hash2 = faiss_rag.compute_documents_hash(doc_index)

        # Hashes devem ser diferentes pois mtime mudou
        assert hash1 != hash2

    def test_hash_handles_file_access_error(self, temp_brain_dir, caplog):
        """Hash trata erros de acesso a arquivos."""
        import faiss_rag
        import logging

        doc_index = {"documents": {"abc": {"source": "/nonexistent/path/file.md"}}}

        with caplog.at_level(logging.WARNING, logger="faiss_rag"):
            # Nao deve lancar excecao
            result = faiss_rag.compute_documents_hash(doc_index)
            assert isinstance(result, str)


# =============================================================================
# Tests: Helper functions
# =============================================================================

class TestHelperFunctions:
    """Testes para funcoes auxiliares."""

    def test_clear_index_cache(self):
        """clear_index_cache() limpa variaveis globais."""
        import faiss_rag

        faiss_rag._faiss_index = "fake_index"
        faiss_rag._faiss_metadata = "fake_metadata"

        faiss_rag.clear_index_cache()

        assert faiss_rag._faiss_index is None
        assert faiss_rag._faiss_metadata is None

    def test_ensure_dirs_creates_faiss_dir(self, temp_brain_dir):
        """ensure_dirs() cria diretorio FAISS."""
        import faiss_rag

        new_faiss_dir = temp_brain_dir["brain_dir"] / "new_rag" / "faiss"

        with patch.object(faiss_rag, 'FAISS_DIR', new_faiss_dir):
            faiss_rag.ensure_dirs()
            assert new_faiss_dir.exists()

    def test_load_doc_index_returns_empty_when_missing(self, temp_brain_dir):
        """load_doc_index() retorna dict vazio quando arquivo nao existe."""
        import faiss_rag

        with patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]):
            result = faiss_rag.load_doc_index()
            assert result == {"documents": {}}

    def test_load_doc_index_returns_content(self, temp_brain_dir, sample_doc_index):
        """load_doc_index() retorna conteudo do arquivo."""
        import faiss_rag

        temp_brain_dir["index_file"].write_text(json.dumps(sample_doc_index))

        with patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]):
            result = faiss_rag.load_doc_index()
            assert result == sample_doc_index

    def test_load_rebuild_state_handles_invalid_json(self, temp_brain_dir, caplog):
        """load_rebuild_state() retorna dict vazio quando JSON e invalido."""
        import faiss_rag
        import logging

        temp_brain_dir["rebuild_state_file"].write_text("invalid json {{{")

        with patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]), \
             caplog.at_level(logging.WARNING, logger="faiss_rag"):

            result = faiss_rag.load_rebuild_state()
            assert result == {}
            assert any("Erro ao carregar estado de rebuild" in record.message for record in caplog.records)

    def test_save_rebuild_state(self, temp_brain_dir):
        """save_rebuild_state() salva estado no disco."""
        import faiss_rag

        state = {"documents_hash": "abc123", "last_rebuild": "2024-01-01"}

        with patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]):

            faiss_rag.save_rebuild_state(state)

            assert temp_brain_dir["rebuild_state_file"].exists()
            saved = json.loads(temp_brain_dir["rebuild_state_file"].read_text())
            assert saved["documents_hash"] == "abc123"


# =============================================================================
# Tests: check_and_rebuild()
# =============================================================================

class TestCheckAndRebuild:
    """Testes para check_and_rebuild()."""

    def test_force_rebuild(self, temp_brain_dir, mock_faiss, mock_model):
        """force=True forca rebuild."""
        import faiss_rag

        # Cria documento
        doc = temp_brain_dir["brain_dir"] / "doc.md"
        doc.write_text("Content " * 50)

        doc_index = {"documents": {"abc": {"source": str(doc), "doc_type": "markdown"}}}
        temp_brain_dir["index_file"].write_text(json.dumps(doc_index))

        mock_model.encode.return_value = np.random.rand(1, 384).astype('float32')

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]), \
             patch.object(faiss_rag, 'CACHE_FILE', temp_brain_dir["cache_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, '_model', mock_model):

            result = faiss_rag.check_and_rebuild(force=True)
            assert result["status"] in ["created", "rebuilt"]

    def test_skipped_when_auto_rebuild_disabled(self):
        """Retorna skipped quando auto-rebuild esta desabilitado."""
        import faiss_rag

        with patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):
            result = faiss_rag.check_and_rebuild(force=False)
            assert result["status"] == "skipped"

    def test_current_when_index_up_to_date(self, temp_brain_dir):
        """Retorna current quando indice esta atualizado."""
        import faiss_rag

        # Cria index.json primeiro
        temp_brain_dir["index_file"].write_text('{"documents": {}}')
        time.sleep(0.1)

        # Depois cria arquivos FAISS
        temp_brain_dir["faiss_index_file"].write_bytes(b"fake faiss index")
        temp_brain_dir["faiss_meta_file"].write_text('{}')

        # Hash correspondente
        current_hash = faiss_rag.compute_documents_hash({"documents": {}})
        rebuild_state = {"documents_hash": current_hash}
        temp_brain_dir["rebuild_state_file"].write_text(json.dumps(rebuild_state))

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', True):

            result = faiss_rag.check_and_rebuild(force=False)
            assert result["status"] == "current"


# =============================================================================
# Tests: get_context_for_query()
# =============================================================================

class TestGetContextForQuery:
    """Testes para get_context_for_query()."""

    def test_returns_no_context_message(self):
        """Retorna mensagem quando nao ha contexto."""
        import faiss_rag

        with patch.object(faiss_rag, 'semantic_search', return_value=[]):
            result = faiss_rag.get_context_for_query("test query")
            assert "nenhum" in result.lower()

    def test_formats_context_with_sources(self):
        """Formata contexto com fontes."""
        import faiss_rag

        mock_results = [
            {"source": "/tmp/test.md", "text": "Conteudo de teste", "score": 0.9}
        ]

        with patch.object(faiss_rag, 'semantic_search', return_value=mock_results):
            result = faiss_rag.get_context_for_query("test query")
            assert "Contexto Relevante" in result
            assert "/tmp/test.md" in result


# =============================================================================
# Tests: get_stats()
# =============================================================================

class TestGetStats:
    """Testes para get_stats()."""

    def test_stats_when_no_index(self, temp_brain_dir):
        """Retorna stats quando indice nao existe."""
        import faiss_rag

        temp_brain_dir["index_file"].write_text('{"documents": {"a": {}}}')

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            stats = faiss_rag.get_stats()
            assert stats["documents"] == 1
            assert stats["chunks"] == 0
            assert "nao construido" in stats["faiss_status"].lower() or "não construído" in stats["faiss_status"].lower()

    def test_stats_with_active_index(self, temp_brain_dir, mock_faiss, sample_faiss_metadata):
        """Retorna stats quando indice esta ativo."""
        import faiss_rag

        mock_faiss_module, mock_index = mock_faiss

        temp_brain_dir["index_file"].write_text('{"documents": {"a": {}, "b": {}}}')
        temp_brain_dir["faiss_index_file"].write_bytes(b"fake")
        temp_brain_dir["faiss_meta_file"].write_text(json.dumps(sample_faiss_metadata))

        # Hash correspondente
        current_hash = faiss_rag.compute_documents_hash({"documents": {}})
        rebuild_state = {"documents_hash": current_hash, "last_rebuild": "2024-01-01T12:00:00"}
        temp_brain_dir["rebuild_state_file"].write_text(json.dumps(rebuild_state))

        # Cria arquivos na ordem correta
        time.sleep(0.1)
        temp_brain_dir["faiss_index_file"].write_bytes(b"fake index updated")

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'INDEX_FILE', temp_brain_dir["index_file"]), \
             patch.object(faiss_rag, 'REBUILD_STATE_FILE', temp_brain_dir["rebuild_state_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            stats = faiss_rag.get_stats()
            assert stats["documents"] == 2
            assert stats["chunks"] == 10  # mock_index.ntotal
            assert stats["faiss_status"] == "ativo"
            assert "last_rebuild" in stats


# =============================================================================
# Tests: load_faiss_index()
# =============================================================================

class TestLoadFaissIndex:
    """Testes para load_faiss_index()."""

    def test_returns_none_when_no_index(self, temp_brain_dir):
        """Retorna None quando indice nao existe."""
        import faiss_rag

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            index, metadata = faiss_rag.load_faiss_index(auto_rebuild=False)
            assert index is None
            assert metadata is None

    def test_returns_cached_index(self, mock_faiss, sample_faiss_metadata):
        """Retorna indice cacheado se disponivel."""
        import faiss_rag

        mock_faiss_module, mock_index = mock_faiss

        with patch.object(faiss_rag, '_faiss_index', mock_index), \
             patch.object(faiss_rag, '_faiss_metadata', sample_faiss_metadata), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            index, metadata = faiss_rag.load_faiss_index(auto_rebuild=False)
            assert index == mock_index
            assert metadata == sample_faiss_metadata

    def test_loads_index_from_disk(self, temp_brain_dir, mock_faiss, sample_faiss_metadata):
        """Carrega indice do disco."""
        import faiss_rag

        mock_faiss_module, mock_index = mock_faiss

        temp_brain_dir["faiss_index_file"].write_bytes(b"fake faiss index")
        temp_brain_dir["faiss_meta_file"].write_text(json.dumps(sample_faiss_metadata))

        with patch.object(faiss_rag, 'FAISS_INDEX_FILE', temp_brain_dir["faiss_index_file"]), \
             patch.object(faiss_rag, 'FAISS_META_FILE', temp_brain_dir["faiss_meta_file"]), \
             patch.object(faiss_rag, 'FAISS_DIR', temp_brain_dir["faiss_dir"]), \
             patch.object(faiss_rag, '_faiss_index', None), \
             patch.object(faiss_rag, '_faiss_metadata', None), \
             patch.object(faiss_rag, 'AUTO_REBUILD_ENABLED', False):

            index, metadata = faiss_rag.load_faiss_index(auto_rebuild=False)
            assert index is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
