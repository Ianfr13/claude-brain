#!/usr/bin/env python3
"""
Demo: Query Decomposer em ação

Demonstra:
1. Importação e inicialização
2. Decomposição com logging detalhado
3. Acesso aos resultados
4. Export para JSON
"""

import sys
import json
import logging

# Add path
sys.path.insert(0, '/root/claude-brain')

from scripts.memory.query_decomposer import (
    decompose_query,
    QueryDecomposer,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def demo_simple():
    """Demo simples com função de conveniência"""
    print("\n" + "="*70)
    print("DEMO 1: Usando decompose_query() (função de conveniência)")
    print("="*70 + "\n")

    query = "Como implementar cache Redis com TTL de 24 horas em FastAPI?"

    print(f"Query: {query}\n")
    print("Chamando: result = decompose_query(query)")
    print("-" * 70)

    result = decompose_query(query)

    print(f"\nResultado:")
    print(f"  Provider: {result.provider}")
    print(f"  Modelo: {result.model_used}")
    print(f"  Tempo: {result.processing_time_ms:.2f}ms")
    print(f"  Confiança: {result.decomposition_confidence:.2%}")
    print(f"  Sub-queries: {len(result.sub_queries)}")

    if result.error:
        print(f"  Erro: {result.error}")
    else:
        print(f"\n  Sub-queries detectadas:")
        for i, sq in enumerate(result.sub_queries, 1):
            print(f"    {i}. [{sq.type.upper()}] {sq.query}")
            print(f"       - Confiança: {sq.confidence:.2%}")
            print(f"       - Peso: {sq.weight:.1f}")
            print(f"       - Tags: {', '.join(sq.tags)}")


def demo_advanced():
    """Demo avançada com QueryDecomposer direto"""
    print("\n" + "="*70)
    print("DEMO 2: Usando QueryDecomposer() (controle direto)")
    print("="*70 + "\n")

    queries = [
        "Qual é a diferença entre decisions e learnings?",
        "Como usar FAISS para busca semântica?",
        "Implementar autenticação JWT",
    ]

    decomposer = QueryDecomposer()

    print(f"Providers disponíveis:")
    print(f"  - OpenRouter: {decomposer.openrouter.available}")
    print(f"  - Anthropic: {decomposer.anthropic.available}\n")

    for i, query in enumerate(queries, 1):
        print(f"\n[Query {i}] {query}")
        print("-" * 70)

        result = decomposer.decompose(query)

        print(f"Provider usado: {result.provider}")
        print(f"Sub-queries: {len(result.sub_queries)}")

        if result.sub_queries:
            for sq in result.sub_queries[:2]:  # Show first 2
                print(f"  • [{sq.type}] {sq.query} (conf: {sq.confidence:.0%})")
        else:
            print(f"Erro: {result.error}")


def demo_json_export():
    """Demo de export JSON"""
    print("\n" + "="*70)
    print("DEMO 3: JSON Export")
    print("="*70 + "\n")

    query = "Implementar sistema de fila de jobs com TTL"

    result = decompose_query(query)

    result_dict = result.to_dict()
    json_output = json.dumps(result_dict, indent=2, ensure_ascii=False)

    print(f"Query: {query}\n")
    print("JSON Output:")
    print(json_output)

    # Também salva em arquivo
    output_file = "/tmp/decomposition_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(json_output)

    print(f"\n✓ Salvo em: {output_file}")


def demo_usage_patterns():
    """Demonstra padrões de uso"""
    print("\n" + "="*70)
    print("DEMO 4: Padrões de Uso")
    print("="*70 + "\n")

    print("Padrão 1: Usar resultado para busca RAG")
    print("-" * 70)
    result = decompose_query("Como usar Redis para caching?")

    print(f"# Pseudo-código para integração com RAG:")
    print(f"""
# 1. Decomposição
result = decompose_query("Como usar Redis para caching?")

# 2. Validar resultado
if result.error:
    print(f"Erro: {{result.error}}")
else:
    # 3. Usar sub-queries para busca
    for sq in result.sub_queries:
        # Buscar no RAG com menor confiança
        if sq.confidence > 0.7:
            search_results = rag.search(sq.query, weight=sq.weight)
            # Consolidar resultados...
""")

    print(f"\nParâmetros disponíveis para usar:")
    print(f"""
DecompositionResult:
  - original_query: str (query original)
  - sub_queries: List[SubQuery] (sub-queries)
  - decomposition_confidence: float (confiança geral)
  - provider: str ('openrouter' ou 'anthropic')
  - model_used: str (nome do modelo)
  - timestamp: str (ISO 8601)
  - processing_time_ms: float (tempo de processamento)
  - error: Optional[str] (erro se houver)

SubQuery:
  - query: str (sub-query)
  - type: str ('semantic', 'entity', 'temporal', 'relational')
  - confidence: float (0.0-1.0)
  - weight: float (importância)
  - tags: List[str] (categorização)
""")


def main():
    """Executa demos"""
    print("\n" + "="*70)
    print("CLAUDE BRAIN - QUERY DECOMPOSER DEMO")
    print("="*70)

    try:
        demo_simple()
    except Exception as e:
        print(f"\n✗ Demo 1 error: {e}")

    try:
        demo_advanced()
    except Exception as e:
        print(f"\n✗ Demo 2 error: {e}")

    try:
        demo_json_export()
    except Exception as e:
        print(f"\n✗ Demo 3 error: {e}")

    try:
        demo_usage_patterns()
    except Exception as e:
        print(f"\n✗ Demo 4 error: {e}")

    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
