#!/usr/bin/env python3
"""
Testes unitários para memory_store.py
"""

import sys
from pathlib import Path

# Adiciona scripts ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from memory_store import (
    save_memory, search_memories, save_decision, get_decisions,
    save_learning, get_all_learnings
)
# Funcoes utilitarias movidas para scripts/memory/base.py
from scripts.memory.base import _hash, _escape_like, _similarity


class TestHashFunctions:
    """Testes para funções de hash e escape"""

    def test_hash_returns_32_chars(self):
        """Hash deve retornar 32 caracteres (128 bits)"""
        result = _hash("test content")
        assert len(result) == 32

    def test_hash_is_deterministic(self):
        """Mesmo conteúdo deve gerar mesmo hash"""
        h1 = _hash("test")
        h2 = _hash("test")
        assert h1 == h2

    def test_hash_different_for_different_content(self):
        """Conteúdos diferentes devem gerar hashes diferentes"""
        h1 = _hash("test1")
        h2 = _hash("test2")
        assert h1 != h2

    def test_escape_like_escapes_percent(self):
        """_escape_like deve escapar %"""
        result = _escape_like("100%")
        assert r"\%" in result

    def test_escape_like_escapes_underscore(self):
        """_escape_like deve escapar _"""
        result = _escape_like("test_value")
        assert r"\_" in result

    def test_escape_like_preserves_normal_text(self):
        """_escape_like não deve alterar texto normal"""
        result = _escape_like("normal text")
        assert result == "normal text"


class TestSimilarity:
    """Testes para função de similaridade"""

    def test_identical_strings_return_1(self):
        """Strings idênticas devem retornar similaridade 1.0"""
        result = _similarity("test", "test")
        assert result == 1.0

    def test_completely_different_returns_0(self):
        """Strings completamente diferentes devem retornar ~0"""
        result = _similarity("abc", "xyz")
        assert result < 0.5

    def test_similar_strings_return_high_score(self):
        """Strings similares devem retornar score alto"""
        result = _similarity("ModuleNotFoundError", "ModuleNotFound")
        assert result > 0.8


class TestMemorySave:
    """Testes para save_memory"""

    def test_save_memory_returns_id(self):
        """save_memory deve retornar um ID inteiro"""
        mem_id = save_memory("test", "Test memory content for unit test")
        assert isinstance(mem_id, int)
        assert mem_id > 0

    def test_save_memory_deduplicates(self):
        """save_memory deve retornar mesmo ID para conteúdo duplicado"""
        content = "Unique test content for dedup test 12345"
        id1 = save_memory("test", content)
        id2 = save_memory("test", content)
        assert id1 == id2


class TestSearchMemories:
    """Testes para search_memories"""

    def test_search_returns_list(self):
        """search_memories deve retornar uma lista"""
        results = search_memories(query="test")
        assert isinstance(results, list)

    def test_search_with_limit(self):
        """search_memories deve respeitar o limite"""
        results = search_memories(limit=2)
        assert len(results) <= 2


class TestDecisions:
    """Testes para decisões"""

    def test_save_decision_returns_id(self):
        """save_decision deve retornar um ID"""
        dec_id = save_decision("Test decision", reasoning="Test reason")
        assert isinstance(dec_id, int)

    def test_get_decisions_returns_list(self):
        """get_decisions deve retornar uma lista"""
        decisions = get_decisions(limit=5)
        assert isinstance(decisions, list)


class TestLearnings:
    """Testes para learnings"""

    def test_save_learning_returns_id(self):
        """save_learning deve retornar um ID"""
        learn_id = save_learning("TestError", "Test solution")
        assert isinstance(learn_id, int)

    def test_get_all_learnings_returns_list(self):
        """get_all_learnings deve retornar uma lista"""
        learnings = get_all_learnings(limit=5)
        assert isinstance(learnings, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
