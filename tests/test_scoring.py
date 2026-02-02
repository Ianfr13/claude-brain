#!/usr/bin/env python3
"""
Testes para o modulo de scoring e resolução de conflitos
"""

import pytest
from scripts.memory.scoring import (
    calculate_relevance_score,
    calculate_specificity_score,
    calculate_recency_score,
    calculate_usage_score,
    calculate_validation_score,
    rank_results,
    detect_conflicts,
    get_decision_score_components,
)
from datetime import datetime, timedelta


class TestSpecificityScore:
    """Testa cálculo de especificidade"""

    def test_project_exact_with_context(self):
        record = {'project': 'vsl-analysis', 'context': 'algo'}
        score = calculate_specificity_score(record, 'vsl-analysis')
        assert score == 1.0

    def test_project_exact_no_context(self):
        record = {'project': 'vsl-analysis'}
        score = calculate_specificity_score(record, 'vsl-analysis')
        assert score == 0.8

    def test_general_knowledge(self):
        record = {'project': None}
        score = calculate_specificity_score(record, 'vsl-analysis')
        assert score == 0.5

    def test_other_project(self):
        record = {'project': 'api-nova'}
        score = calculate_specificity_score(record, 'vsl-analysis')
        assert score == 0.3

    def test_no_project_specified(self):
        record = {'project': None}
        score = calculate_specificity_score(record, None)
        assert score == 0.5


class TestRecencyScore:
    """Testa cálculo de recência"""

    def test_last_week(self):
        today = datetime.now()
        record = {'created_at': (today - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')}
        score = calculate_recency_score(record)
        assert score == 1.0

    def test_last_month(self):
        today = datetime.now()
        record = {'created_at': (today - timedelta(days=15)).strftime('%Y-%m-%d %H:%M:%S')}
        score = calculate_recency_score(record)
        assert score == 0.8

    def test_three_months(self):
        today = datetime.now()
        record = {'created_at': (today - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')}
        score = calculate_recency_score(record)
        assert score == 0.6

    def test_no_timestamp(self):
        record = {}
        score = calculate_recency_score(record)
        assert score == 0.5  # padrão


class TestUsageScore:
    """Testa cálculo de uso"""

    def test_no_usage(self):
        record = {'access_count': 0}
        score = calculate_usage_score(record)
        assert score == 0.0

    def test_10_accesses(self):
        record = {'access_count': 10}
        score = calculate_usage_score(record)
        assert score == 1.0

    def test_5_accesses(self):
        record = {'access_count': 5}
        score = calculate_usage_score(record)
        assert score == 0.5

    def test_frequency_field(self):
        record = {'frequency': 8}
        score = calculate_usage_score(record)
        assert score == 0.8


class TestValidationScore:
    """Testa cálculo de validação"""

    def test_confirmed(self):
        record = {'maturity_status': 'confirmed'}
        score = calculate_validation_score(record)
        assert score == 1.0

    def test_testing(self):
        record = {'maturity_status': 'testing'}
        score = calculate_validation_score(record)
        assert score == 0.6

    def test_hypothesis(self):
        record = {'maturity_status': 'hypothesis'}
        score = calculate_validation_score(record)
        assert score == 0.4

    def test_deprecated(self):
        record = {'maturity_status': 'deprecated'}
        score = calculate_validation_score(record)
        assert score == 0.2

    def test_contradicted(self):
        record = {'maturity_status': 'contradicted'}
        score = calculate_validation_score(record)
        assert score == 0.0


class TestRelevanceScore:
    """Testa score composto"""

    def test_perfect_result(self):
        """Score máximo: projeto exato + recente + confirmado + usado"""
        record = {
            'project': 'vsl-analysis',
            'context': 'algo',
            'confidence_score': 1.0,
            'maturity_status': 'confirmed',
            'access_count': 20,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        score = calculate_relevance_score(record, '', 'vsl-analysis')
        assert 0.95 < score <= 1.0

    def test_poor_result(self):
        """Score baixo: outro projeto + antigo + hypothesis + não usado"""
        record = {
            'project': 'outro',
            'confidence_score': 0.3,
            'maturity_status': 'hypothesis',
            'access_count': 0,
            'created_at': (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S')
        }
        score = calculate_relevance_score(record, '', 'vsl-analysis')
        assert score < 0.4

    def test_general_knowledge_decent(self):
        """Conhecimento geral com boa confiança"""
        record = {
            'project': None,
            'confidence_score': 0.9,
            'maturity_status': 'confirmed',
            'access_count': 5,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        score = calculate_relevance_score(record, '', 'vsl-analysis')
        assert 0.6 < score < 0.8


class TestRanking:
    """Testa ranking automático"""

    def test_rank_by_score(self):
        """Verifica se ranking ordena por score DESC"""
        results = [
            {
                'id': 1,
                'decision': 'A',
                'project': 'vsl-analysis',
                'confidence_score': 0.5,
                'maturity_status': 'hypothesis',
                'access_count': 0,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            {
                'id': 2,
                'decision': 'B',
                'project': 'vsl-analysis',
                'confidence_score': 0.9,
                'maturity_status': 'confirmed',
                'access_count': 10,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        ]

        ranked = rank_results(results, 'test', 'vsl-analysis')

        # Segundo resultado deve ter score maior
        assert ranked[0]['relevance_score'] > ranked[1]['relevance_score']

        # Deve ter 'relevance_score' em cada um
        assert 'relevance_score' in ranked[0]
        assert 'relevance_score' in ranked[1]

    def test_rank_adds_scores(self):
        """Verifica se rank_results adiciona relevance_score"""
        results = [{'id': 1, 'decision': 'Test'}]
        ranked = rank_results(results, '', None)
        assert 'relevance_score' in ranked[0]


class TestConflictDetection:
    """Testa detecção de conflitos"""

    def test_detect_close_scores(self):
        """Detecta scores muito próximos"""
        results = [
            {'id': 1, 'relevance_score': 0.85},
            {'id': 2, 'relevance_score': 0.84},  # Diferença de 0.01
            {'id': 3, 'relevance_score': 0.70},
        ]

        conflicts = detect_conflicts(results, threshold=0.05)

        # Deve detectar conflito entre 1 e 2
        assert len(conflicts) == 1
        assert conflicts[0][0]['id'] == 1
        assert conflicts[0][1]['id'] == 2

    def test_no_conflicts_with_gap(self):
        """Sem conflitos quando há gap maior que threshold"""
        results = [
            {'id': 1, 'relevance_score': 0.85},
            {'id': 2, 'relevance_score': 0.70},  # Diferença de 0.15
        ]

        conflicts = detect_conflicts(results, threshold=0.10)

        assert len(conflicts) == 0

    def test_multiple_conflicts(self):
        """Detecta múltiplos conflitos"""
        results = [
            {'id': 1, 'relevance_score': 0.80},
            {'id': 2, 'relevance_score': 0.79},  # Conflito com 1
            {'id': 3, 'relevance_score': 0.78},  # Conflito com 2
        ]

        conflicts = detect_conflicts(results, threshold=0.05)

        assert len(conflicts) == 2


class TestScoreComponents:
    """Testa breakdown de componentes de score"""

    def test_component_breakdown(self):
        """Verifica se breakdown retorna todos os componentes"""
        record = {
            'project': 'vsl-analysis',
            'context': 'algo',
            'confidence_score': 0.8,
            'maturity_status': 'confirmed',
            'access_count': 5,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        components = get_decision_score_components(record, 'vsl-analysis')

        assert 'specificity' in components
        assert 'recency' in components
        assert 'confidence' in components
        assert 'usage' in components
        assert 'validation' in components
        assert 'score_total' in components
        assert 'weighted' in components

        # Score total deve ser a soma dos pesos
        weighted_sum = (
            components['weighted']['specificity'] +
            components['weighted']['recency'] +
            components['weighted']['confidence'] +
            components['weighted']['usage'] +
            components['weighted']['validation']
        )

        assert abs(weighted_sum - components['score_total']) < 0.001


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
