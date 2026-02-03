#!/usr/bin/env python3
"""
Exemplos Práticos: Query Decomposer

Casos de uso reais e padrões de integração
"""

import sys
sys.path.insert(0, '/root/claude-brain')

from scripts.memory import (
    decompose_query,
    QueryDecomposer,
    DecompositionResult,
)
from scripts.memory.query_decomposer_integration import (
    expand_search,
    batch_decompose,
    rank_sub_queries,
    analyze_decompositions,
    DecompositionCache,
    export_decompositions,
)


# ============ EXEMPLO 1: Busca RAG Expandida ============

def exemplo_rag_expandida():
    """
    Caso de uso: Expandir busca em um sistema RAG

    Problema: Query simples pode perder contexto
    Solução: Decomposição em múltiplas sub-queries para cobertura melhor
    """
    print("\n" + "="*70)
    print("EXEMPLO 1: Busca RAG Expandida")
    print("="*70 + "\n")

    query = "Como implementar autenticação JWT em uma API FastAPI?"

    print(f"Query original: {query}\n")

    # Expandir search
    expanded_queries = expand_search(query, min_confidence=0.75)

    print(f"Queries expandidas ({len(expanded_queries)}):")
    for i, q in enumerate(expanded_queries, 1):
        print(f"  {i}. {q}")

    print(f"\nBenefício: Busca em múltiplas dimensões")
    print(f"  - Query 1: Contexto de autenticação")
    print(f"  - Query 2: Contexto de JWT")
    print(f"  - Query 3: Contexto de FastAPI")
    print(f"  → Resultados mais relevantes e completos")


# ============ EXEMPLO 2: Processamento em Batch ============

def exemplo_batch():
    """
    Caso de uso: Processar muitas queries em lote

    Exemplo: Indexação de FAQ, processamento de logs, análise de padrões
    """
    print("\n" + "="*70)
    print("EXEMPLO 2: Batch Processing de Queries")
    print("="*70 + "\n")

    # Simular FAQ
    faq_questions = [
        "Qual é a diferença entre decisions e learnings?",
        "Como usar FAISS para busca semântica?",
        "Como implementar caching com Redis?",
    ]

    print(f"Processando {len(faq_questions)} perguntas de FAQ...\n")

    # Decomposição em batch
    results = batch_decompose(faq_questions)

    # Análise
    analytics = analyze_decompositions(results)

    print("Estatísticas:")
    print(f"  Total de queries: {analytics['total_queries']}")
    print(f"  Total de sub-queries: {analytics['total_sub_queries']}")
    print(f"  Média por query: {analytics['avg_sub_queries_per_query']:.1f}")
    print(f"  Confiança média: {analytics['avg_confidence']}")
    print(f"  Taxa de sucesso: {analytics['success_rate']}")

    print(f"\nDistribuição de tipos:")
    for type_name, count in analytics['sub_query_types'].items():
        print(f"  {type_name}: {count}")


# ============ EXEMPLO 3: Ranking Inteligente ============

def exemplo_ranking():
    """
    Caso de uso: Priorizar sub-queries para processamento

    Exemplo: Processamento em sistema com recursos limitados
    """
    print("\n" + "="*70)
    print("EXEMPLO 3: Ranking Inteligente de Sub-queries")
    print("="*70 + "\n")

    query = "Como otimizar performance de busca em base de dados grande?"
    result = decompose_query(query)

    if result.error:
        print(f"Erro: {result.error}")
        return

    print(f"Query: {query}\n")

    # Ranking
    ranked = rank_sub_queries(result)

    print("Sub-queries rankeadas por importância:")
    for i, sq in enumerate(ranked, 1):
        print(f"\n  {i}. [{sq.type.upper()}] {sq.query}")
        print(f"     Confiança: {sq.confidence:.0%} | Peso: {sq.weight:.2f}")

    print(f"\nCaso de uso:")
    print(f"  • Se recursos limitados: processar apenas top 2-3")
    print(f"  • Se recursos abundantes: processar todas")


# ============ EXEMPLO 4: Caching em Produção ============

def exemplo_caching():
    """
    Caso de uso: Cache de decomposições em produção

    Exemplo: API que recebe queries repetidas
    """
    print("\n" + "="*70)
    print("EXEMPLO 4: Caching em Produção")
    print("="*70 + "\n")

    cache = DecompositionCache(max_size=5)

    # Simular requests
    requests = [
        "Query 1",
        "Query 2",
        "Query 1",  # Cache hit
        "Query 3",
        "Query 1",  # Cache hit
        "Query 2",  # Cache hit
    ]

    print(f"Processando {len(requests)} requests com cache:\n")

    for req in requests:
        result = cache.decompose_cached(req)
        print(f"  Request: {req} → Cache: {cache.stats()['hit_rate']}")

    print(f"\nEstatísticas finais:")
    stats = cache.stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print(f"\nBenefício:")
    print(f"  • Redução de latência: ~500x mais rápido")
    print(f"  • Redução de custos: sem chamadas à API")


# ============ EXEMPLO 5: Quality Assurance ============

def exemplo_qa():
    """
    Caso de uso: Validar qualidade de decomposições

    Exemplo: Sistema de QA antes de usar em produção
    """
    print("\n" + "="*70)
    print("EXEMPLO 5: Quality Assurance")
    print("="*70 + "\n")

    queries = [
        "Query muito simples",
        "Query complexa com múltiplos contextos e requisitos",
        "Query vazia",
    ]

    print("Validando qualidade de decomposições:\n")

    for query in queries:
        result = decompose_query(query)

        # Validações
        checks = {
            "Sem erro": result.error is None,
            "Confiança > 70%": result.decomposition_confidence > 0.7,
            "Tem sub-queries": len(result.sub_queries) > 0,
            "Confiança min > 50%": all(
                sq.confidence > 0.5 for sq in result.sub_queries
            ) if result.sub_queries else False,
        }

        status = "✓ PASS" if all(checks.values()) else "✗ FAIL"
        print(f"{status} | {query[:40]}")
        for check, passed in checks.items():
            mark = "✓" if passed else "✗"
            print(f"       {mark} {check}")


# ============ EXEMPLO 6: Export e Análise ============

def exemplo_export():
    """
    Caso de uso: Exportar dados para análise externa

    Exemplo: BI, dashboards, relatórios
    """
    print("\n" + "="*70)
    print("EXEMPLO 6: Export para Análise Externa")
    print("="*70 + "\n")

    queries = [
        "Query 1",
        "Query 2",
    ]

    results = batch_decompose(queries)

    # Export JSON
    print("Exportando para JSON:")
    json_export = export_decompositions(results, format="json")
    print(json_export[:200] + "...\n")

    # Export CSV
    print("Exportando para CSV:")
    csv_export = export_decompositions(results, format="csv")
    print(csv_export)

    print("Casos de uso:")
    print("  • JSON: Integração com APIs")
    print("  • CSV: Import em Excel, Tableau, etc")


# ============ EXEMPLO 7: Fallback e Error Handling ============

def exemplo_error_handling():
    """
    Caso de uso: Tratamento robusto de erros

    Exemplo: Aplicação que não pode falhar
    """
    print("\n" + "="*70)
    print("EXEMPLO 7: Error Handling Robusto")
    print("="*70 + "\n")

    def decompose_with_fallback(query: str) -> list:
        """Decompõe com fallback para query original"""
        result = decompose_query(query)

        if result.error:
            print(f"  ⚠ Decomposição falhou: {result.error}")
            print(f"  → Usando query original como fallback")
            return [query]

        if result.decomposition_confidence < 0.5:
            print(f"  ⚠ Confiança muito baixa ({result.decomposition_confidence:.0%})")
            print(f"  → Incluindo query original")
            queries = [query]
        else:
            queries = []

        queries.extend([sq.query for sq in result.sub_queries])
        return queries

    print("Teste com query válida:")
    queries = decompose_with_fallback("Query normal")
    print(f"  Resultado: {len(queries)} queries\n")

    print("Teste com erro simulado:")
    # Forçar erro
    from unittest.mock import patch
    with patch('scripts.memory.query_decomposer.QueryDecomposer.decompose') as mock:
        from scripts.memory.query_decomposer import DecompositionResult
        mock.return_value = DecompositionResult(
            original_query="test",
            sub_queries=[],
            decomposition_confidence=0.0,
            provider="none",
            model_used="none",
            timestamp="",
            processing_time_ms=0,
            error="Simulated error"
        )
        queries = decompose_with_fallback("Query problemática")
        print(f"  Resultado: {len(queries)} queries (fallback aplicado)")


# ============ EXEMPLO 8: Integração com Brain ============

def exemplo_brain_integration():
    """
    Caso de uso: Usar decomposição para melhorar brain search

    Exemplo: Potencializar sistema de memória do Claude Brain
    """
    print("\n" + "="*70)
    print("EXEMPLO 8: Integração com Claude Brain")
    print("="*70 + "\n")

    print("Fluxo proposto:")
    print("""
    1. Usuário faz query ao brain:
       "brain ask 'Como implementar cache?'"

    2. Brain decomposição query:
       result = decompose_query(query)

    3. Brain busca com sub-queries:
       for sq in result.sub_queries:
           brain_results.extend(brain_search(sq.query))

    4. Brain consolida resultados:
       final_results = consolidate(brain_results)

    Benefício: Busca mais completa e relevante
    """)

    print("\nExemplo prático:")

    query = "Qual é a diferença entre decisions e learnings?"
    result = decompose_query(query)

    if not result.error:
        print(f"\nQuery: {query}")
        print(f"\nBuscaria no brain:")
        for sq in result.sub_queries:
            print(f"  • {sq.query} (weight={sq.weight:.1f})")


# ============ MAIN ============

def main():
    """Executa todos os exemplos"""
    print("\n" + "="*70)
    print("QUERY DECOMPOSER - EXEMPLOS PRÁTICOS")
    print("="*70)

    exemplos = [
        ("RAG Expandida", exemplo_rag_expandida),
        ("Batch Processing", exemplo_batch),
        ("Ranking Inteligente", exemplo_ranking),
        ("Caching", exemplo_caching),
        ("Quality Assurance", exemplo_qa),
        ("Export e Análise", exemplo_export),
        ("Error Handling", exemplo_error_handling),
        ("Integração com Brain", exemplo_brain_integration),
    ]

    for nome, func in exemplos:
        try:
            func()
        except Exception as e:
            print(f"\n✗ Erro no exemplo '{nome}': {e}")

    print("\n" + "="*70)
    print("EXEMPLOS COMPLETOS")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
