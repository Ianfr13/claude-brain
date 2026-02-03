#!/usr/bin/env python3
"""
Testes para o sistema de Job Queue do Claude Brain.

Executa testes unitarios das funcoes de jobs:
- create_job: Criacao de jobs com TTL
- get_job: Recuperacao de jobs
- list_jobs: Listagem de jobs ativos/expirados
- delete_job: Delecao manual
- cleanup_jobs: Remocao automatica de expirados
- get_job_count: Estatisticas

Uso:
    python3 tests/test_jobs.py
    pytest tests/test_jobs.py -v
"""

import json
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# Adiciona o diretorio raiz ao path para imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock pytest se nao disponivel
try:
    import pytest
except ImportError:
    class pytest:
        @staticmethod
        def raises(exc, match=None):
            class RaisesContext:
                def __init__(self, exc, match):
                    self.exc = exc
                    self.match = match
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    if exc_type is None:
                        raise AssertionError(f"Expected {self.exc.__name__} but nothing was raised")
                    if not issubclass(exc_type, self.exc):
                        return False
                    if self.match and self.match not in str(exc_val):
                        raise AssertionError(f"Expected match '{self.match}' in '{exc_val}'")
                    return True
            return RaisesContext(exc, match)

from scripts.memory.jobs import (
    create_job,
    get_job,
    list_jobs,
    delete_job,
    cleanup_jobs,
    get_job_count,
)


class TestJobCreation(unittest.TestCase):
    """Testes de criacao de jobs."""

    def test_create_job_basic(self):
        """Testa criacao basica de job."""
        data = {
            "prompt": "Teste basico",
            "skills": ["python-pro-skill"],
            "brain_queries": [],
            "files": [],
            "context": {}
        }

        job_id = create_job(ttl=60, data=data)

        assert job_id is not None
        assert len(job_id) == 36  # UUID format

        # Verifica se pode recuperar
        job = get_job(job_id)
        assert job is not None
        assert job["data"]["prompt"] == "Teste basico"

        # Cleanup
        delete_job(job_id)

    def test_create_job_full(self):
        """Testa criacao de job com todos os campos."""
        data = {
            "prompt": "Implementar feature X",
            "skills": ["python-pro-skill", "sql-pro-skill"],
            "brain_queries": [
                {"query": "redis", "project": "vsl-analysis"},
                {"query": "cache"}
            ],
            "files": ["/root/test.py", "/root/test2.py"],
            "context": {"priority": "high", "deadline": "2026-02-05"}
        }

        job_id = create_job(ttl=3600, data=data)
        job = get_job(job_id)

        assert job["data"]["prompt"] == "Implementar feature X"
        assert len(job["data"]["skills"]) == 2
        assert len(job["data"]["brain_queries"]) == 2
        assert job["data"]["brain_queries"][0]["project"] == "vsl-analysis"
        assert len(job["data"]["files"]) == 2
        assert job["data"]["context"]["priority"] == "high"

        # Cleanup
        delete_job(job_id)

    def test_create_job_minimal(self):
        """Testa criacao de job apenas com prompt."""
        data = {"prompt": "Tarefa simples"}

        job_id = create_job(ttl=60, data=data)
        job = get_job(job_id)

        assert job["data"]["prompt"] == "Tarefa simples"
        assert job["data"]["skills"] == []
        assert job["data"]["brain_queries"] == []
        assert job["data"]["files"] == []
        assert job["data"]["context"] == {}

        # Cleanup
        delete_job(job_id)

    def test_create_job_invalid_data(self):
        """Testa validacao de dados invalidos."""
        # Sem prompt
        with pytest.raises(ValueError, match="prompt"):
            create_job(ttl=60, data={})

        # TTL invalido
        with pytest.raises(ValueError, match="ttl"):
            create_job(ttl=-10, data={"prompt": "teste"})

        with pytest.raises(ValueError, match="ttl"):
            create_job(ttl=0, data={"prompt": "teste"})

        # Data nao e dict
        with pytest.raises(ValueError, match="dicionario"):
            create_job(ttl=60, data="string")


class TestJobRetrieval(unittest.TestCase):
    """Testes de recuperacao de jobs."""

    def test_get_job_exists(self):
        """Testa recuperacao de job existente."""
        data = {"prompt": "Teste get"}
        job_id = create_job(ttl=60, data=data)

        job = get_job(job_id)

        assert job is not None
        assert job["job_id"] == job_id
        assert "created_at" in job
        assert "expires_at" in job
        assert job["ttl"] == 60
        assert job["data"]["prompt"] == "Teste get"

        # Cleanup
        delete_job(job_id)

    def test_get_job_not_found(self):
        """Testa recuperacao de job inexistente."""
        job = get_job("00000000-0000-0000-0000-000000000000")
        assert job is None

    def test_get_job_expired(self):
        """Testa que job expirado nao e retornado."""
        data = {"prompt": "Teste expiracao"}
        job_id = create_job(ttl=1, data=data)

        # Verifica que existe
        job = get_job(job_id)
        assert job is not None

        # Aguarda expirar
        time.sleep(2)

        # Verifica que foi removido automaticamente
        job = get_job(job_id)
        assert job is None


class TestJobListing(unittest.TestCase):
    """Testes de listagem de jobs."""

    def test_list_jobs_empty(self):
        """Testa listagem com fila vazia."""
        cleanup_jobs()
        jobs = list_jobs()
        assert len(jobs) == 0

    def test_list_jobs_active(self):
        """Testa listagem de jobs ativos."""
        cleanup_jobs()

        # Cria 3 jobs
        ids = []
        for i in range(3):
            job_id = create_job(ttl=3600, data={"prompt": f"Job {i}"})
            ids.append(job_id)

        jobs = list_jobs()
        assert len(jobs) == 3

        # Cleanup
        for job_id in ids:
            delete_job(job_id)

    def test_list_jobs_excludes_expired(self):
        """Testa que jobs expirados nao aparecem na lista."""
        cleanup_jobs()

        # Cria job com TTL curto
        job_id_short = create_job(ttl=1, data={"prompt": "Expira rapido"})

        # Cria job com TTL longo
        job_id_long = create_job(ttl=3600, data={"prompt": "Expira tarde"})

        # Verifica que ambos existem
        jobs = list_jobs()
        assert len(jobs) == 2

        # Aguarda expiracao do primeiro
        time.sleep(2)

        # Verifica que so resta um
        jobs = list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == job_id_long

        # Cleanup
        delete_job(job_id_long)

    def test_list_jobs_include_expired(self):
        """Testa listagem incluindo expirados."""
        cleanup_jobs()

        # Cria job expirado
        job_id = create_job(ttl=1, data={"prompt": "Expira"})
        time.sleep(2)

        # Lista com expirados primeiro (antes de cleanup remover)
        jobs = list_jobs(include_expired=True)
        assert len(jobs) == 1

        # Lista sem expirados (faz cleanup automatico)
        jobs = list_jobs(include_expired=False)
        assert len(jobs) == 0

        # Lista com expirados novamente (agora vazio porque foi limpo)
        jobs = list_jobs(include_expired=True)
        assert len(jobs) == 0


class TestJobDeletion(unittest.TestCase):
    """Testes de delecao de jobs."""

    def test_delete_job_exists(self):
        """Testa delecao de job existente."""
        data = {"prompt": "Teste delete"}
        job_id = create_job(ttl=60, data=data)

        # Verifica que existe
        assert get_job(job_id) is not None

        # Deleta
        deleted = delete_job(job_id)
        assert deleted is True

        # Verifica que nao existe mais
        assert get_job(job_id) is None

    def test_delete_job_not_found(self):
        """Testa delecao de job inexistente."""
        deleted = delete_job("00000000-0000-0000-0000-000000000000")
        assert deleted is False


class TestJobCleanup(unittest.TestCase):
    """Testes de cleanup automatico."""

    def test_cleanup_removes_expired(self):
        """Testa que cleanup remove jobs expirados."""
        cleanup_jobs()

        # Cria jobs expirados
        for i in range(3):
            create_job(ttl=1, data={"prompt": f"Expira {i}"})

        # Aguarda expiracao
        time.sleep(2)

        # Executa cleanup
        removed = cleanup_jobs()
        assert removed == 3

        # Verifica que fila esta vazia
        jobs = list_jobs()
        assert len(jobs) == 0

    def test_cleanup_preserves_active(self):
        """Testa que cleanup preserva jobs ativos."""
        cleanup_jobs()

        # Cria job ativo
        job_id = create_job(ttl=3600, data={"prompt": "Ativo"})

        # Executa cleanup
        removed = cleanup_jobs()
        assert removed == 0

        # Verifica que job ainda existe
        job = get_job(job_id)
        assert job is not None

        # Cleanup
        delete_job(job_id)


class TestJobStats(unittest.TestCase):
    """Testes de estatisticas."""

    def test_job_count_active_only(self):
        """Testa contagem de jobs ativos."""
        cleanup_jobs()

        # Cria jobs
        ids = []
        for i in range(3):
            job_id = create_job(ttl=3600, data={"prompt": f"Job {i}"})
            ids.append(job_id)

        stats = get_job_count(active_only=True)
        assert stats["total"] == 3

        # Cleanup
        for job_id in ids:
            delete_job(job_id)

    def test_job_count_with_expired(self):
        """Testa contagem incluindo expirados."""
        cleanup_jobs()

        # Cria job ativo
        job_id_active = create_job(ttl=3600, data={"prompt": "Ativo"})

        # Cria job expirado
        job_id_expired = create_job(ttl=1, data={"prompt": "Expira"})
        time.sleep(2)

        stats = get_job_count(active_only=False)
        assert stats["active"] == 1
        assert stats["expired"] == 1
        assert stats["total"] == 2

        # Cleanup
        delete_job(job_id_active)
        delete_job(job_id_expired)


if __name__ == "__main__":
    # Executa testes com unittest
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
