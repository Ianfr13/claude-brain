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
    iterate_job,
    check_cli_tools,
    update_job_status,
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


class TestListJobsSecurityValidation(unittest.TestCase):
    """Testes de validacao de seguranca em list_jobs - SECURITY FIX #1."""

    def setUp(self):
        """Limpa banco antes de cada teste."""
        cleanup_jobs()
        # Deleta todos os jobs manualmente (incluindo expirados)
        from scripts.memory.base import get_db
        with get_db() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM jobs')

    def test_list_jobs_valid_status_filter(self):
        """Testa que status_filter valido funciona."""
        # Cria job com status pendente
        job_id = create_job(ttl=3600, data={"prompt": "Teste"})

        # Filtra por status valido (deve funcionar)
        jobs = list_jobs(status_filter='pending')
        assert len(jobs) == 1
        assert jobs[0]['status'] == 'pending'

        # Cleanup
        delete_job(job_id)

    def test_list_jobs_invalid_status_filter_raises_error(self):
        """Testa que status_filter invalido levanta ValueError."""
        with pytest.raises(ValueError, match="Status invalido"):
            list_jobs(status_filter='invalid_status')

    def test_list_jobs_sql_injection_attempt_blocked(self):
        """Testa que tentativas de SQL injection sao bloqueadas."""
        # Tentativas maliciosas devem ser rejeitadas
        malicious_inputs = [
            "pending' OR '1'='1",
            "pending; DROP TABLE jobs;--",
            "pending' UNION SELECT * FROM jobs--",
        ]

        for malicious_input in malicious_inputs:
            with pytest.raises(ValueError, match="Status invalido"):
                list_jobs(status_filter=malicious_input)


class TestIterateJobSecurityRaceCondition(unittest.TestCase):
    """Testes de race condition em iterate_job - SECURITY FIX #2."""

    def setUp(self):
        """Limpa banco antes de cada teste."""
        cleanup_jobs()
        from scripts.memory.base import get_db
        with get_db() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM jobs')

    def test_iterate_job_valid_execution(self):
        """Testa iteracao valida de job."""
        data = {"prompt": "Teste iteracao"}
        job_id = create_job(ttl=3600, data=data)

        # Get job inicial para saber o iteration number
        job_before = get_job(job_id)
        initial_iteration = job_before['iteration']

        # Itera com execution
        success = iterate_job(job_id, 'execution', 'haiku', 'Resultado da execucao')
        assert success is True

        # Verifica que job foi atualizado
        job = get_job(job_id)
        assert job['iteration'] == initial_iteration + 1
        assert job['status'] == 'executing'
        assert len(job['history']) == 1
        assert job['history'][0]['type'] == 'execution'
        assert job['history'][0]['agent'] == 'haiku'

        # Cleanup
        delete_job(job_id)

    def test_iterate_job_multiple_iterations(self):
        """Testa multiplas iteracoes de um job."""
        data = {"prompt": "Teste multiplas iteracoes"}
        job_id = create_job(ttl=3600, data=data)

        # Get inicial
        job_initial = get_job(job_id)
        initial_iter = job_initial['iteration']

        # Iteracao 1: execution
        iterate_job(job_id, 'execution', 'haiku', 'Resultado haiku')
        job = get_job(job_id)
        assert job['iteration'] == initial_iter + 1
        assert job['status'] == 'executing'

        # Iteracao 2: review
        iterate_job(job_id, 'review', 'opus', 'Review do opus')
        job = get_job(job_id)
        assert job['iteration'] == initial_iter + 2
        assert job['status'] == 'in_review'
        assert len(job['history']) == 2

        # Cleanup
        delete_job(job_id)

    def test_iterate_job_cannot_iterate_terminal_state(self):
        """Testa que nao pode iterar job em estado terminal."""
        data = {"prompt": "Teste estado terminal"}
        job_id = create_job(ttl=3600, data=data)

        job_initial = get_job(job_id)
        initial_iter = job_initial['iteration']

        # Tenta mudar para completed primeiro
        # pending pode ir para executing, in_review, ou failed
        # Então vamos para executing primeiro, depois failed (terminal)
        update_job_status(job_id, 'executing')
        update_job_status(job_id, 'failed')  # Terminal

        # Tenta iterar (deve falhar)
        success = iterate_job(job_id, 'execution', 'haiku', 'Nao deve funcionar')
        assert success is False

        # Verifica que job nao foi atualizado
        job = get_job(job_id)
        assert job['iteration'] == initial_iter  # Nao deve ter mudado
        assert len(job['history']) == 0

        # Cleanup
        delete_job(job_id)

    def test_iterate_job_invalid_iteration_type(self):
        """Testa validacao de iteration_type."""
        data = {"prompt": "Teste"}
        job_id = create_job(ttl=3600, data=data)

        with pytest.raises(ValueError, match="iteration_type"):
            iterate_job(job_id, 'invalid_type', 'haiku', 'Result')

        # Cleanup
        delete_job(job_id)

    def test_iterate_job_invalid_agent(self):
        """Testa validacao de agent."""
        data = {"prompt": "Teste"}
        job_id = create_job(ttl=3600, data=data)

        with pytest.raises(ValueError, match="agent"):
            iterate_job(job_id, 'execution', 'invalid_agent', 'Result')

        # Cleanup
        delete_job(job_id)


class TestCheckCliToolsSecurityPathTraversal(unittest.TestCase):
    """Testes de path traversal em check_cli_tools - SECURITY FIX #3."""

    def setUp(self):
        """Limpa banco antes de cada teste (se necessario)."""
        # check_cli_tools nao usa banco, mas mantemos setUp por consistencia
        pass

    def test_check_cli_tools_valid_names(self):
        """Testa que nomes validos de ferramentas funcionam."""
        # Nomes validos nao devem gerar erro
        result = check_cli_tools(['gdrive', 'elevenlabs-cli', 'my_tool_123'])

        # Tudo deve ser False (nao existem) mas nao deve haver erro
        assert isinstance(result, dict)
        assert 'gdrive' in result
        assert 'elevenlabs-cli' in result
        assert 'my_tool_123' in result

    def test_check_cli_tools_path_traversal_blocked(self):
        """Testa que tentativas de path traversal sao bloqueadas."""
        malicious_names = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32',
            'tool/../../../etc/passwd',
            'tool\\..\\..',
            '/etc/passwd',
            '\\windows\\system32',
        ]

        result = check_cli_tools(malicious_names)

        # Todos devem retornar False (bloqueados)
        for name in malicious_names:
            assert result[name] is False

    def test_check_cli_tools_null_bytes_blocked(self):
        """Testa que null bytes sao bloqueados."""
        malicious_names = [
            'tool\x00.exe',
            'tool\x00',
        ]

        result = check_cli_tools(malicious_names)

        # Todos devem retornar False
        for name in malicious_names:
            assert result[name] is False

    def test_check_cli_tools_empty_name_blocked(self):
        """Testa que nomes vazios sao bloqueados."""
        result = check_cli_tools([''])

        # Deve retornar False para nome vazio
        assert result[''] is False

    def test_check_cli_tools_double_dots_blocked(self):
        """Testa que '..' em nomes e bloqueado."""
        malicious_names = [
            '..',
            'tool..name',
            '..tool',
            'tool..',
        ]

        result = check_cli_tools(malicious_names)

        # Todos devem retornar False
        for name in malicious_names:
            assert result[name] is False


if __name__ == "__main__":
    # Executa testes com unittest
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
