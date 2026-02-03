#!/usr/bin/env python3
"""
Integração: Query Decomposer com o sistema de Memory/Brain

Padrões de integração:
1. Usar para expandir buscas semânticas
2. Log de decomposições no memory
3. Ranking automático de sub-queries
4. Cache de decomposições frequentes

Este módulo fornece helpers para integração com o resto do brain.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from .query_decomposer import (
    DecompositionResult,
    SubQuery,
    decompose_query,
)
from .base import get_db

logger = logging.getLogger(__name__)


# ============ DATABASE STORAGE ============

def save_decomposition(
    result: DecompositionResult,
    context: Optional[str] = None,
    project: Optional[str] = None
) -> bool:
    """
    Salva decomposição no database para análise posterior

    Args:
        result: DecompositionResult
        context: Contexto adicional
        project: Projeto associado

    Returns:
        True se salvo com sucesso
    """
    try:
        db = get_db()
        cursor = db.cursor()

        # Serializa sub-queries
        sub_queries_json = json.dumps([sq.to_dict() for sq in result.sub_queries])

        # Insere record
        cursor.execute("""
            INSERT INTO memories (
                title, content, tags, project, source, created_at, modified_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            f"Query Decomposition: {result.original_query[:50]}",
            json.dumps(result.to_dict()),
            json.dumps(["decomposition", result.provider, result.model_used]),
            project or "general",
            "query_decomposer",
            datetime.now().isoformat(),
            datetime.now().isoformat(),
        ))

        db.commit()
        logger.info(f"Decomposição salva: {result.original_query[:50]}")
        return True

    except Exception as e:
        logger.error(f"Erro ao salvar decomposição: {e}")
        return False


# ============ SEARCH EXPANSION ============

def expand_search(
    query: str,
    min_confidence: float = 0.7,
    max_sub_queries: int = None
) -> List[str]:
    """
    Expande query inicial em múltiplas buscas

    Útil para RAG: usa sub-queries para fazer múltiplas buscas
    em paralelo e consolidar resultados

    Args:
        query: Query original
        min_confidence: Confiança mínima para incluir
        max_sub_queries: Máximo de sub-queries (None = todas)

    Returns:
        Lista de queries expandidas (incluindo original)
    """
    logger.info(f"Expandindo query: {query}")

    result = decompose_query(query)

    if result.error:
        logger.warning(f"Decomposição falhou: {result.error}")
        return [query]  # Fallback: retorna query original

    # Filtra por confiança
    filtered = [sq for sq in result.sub_queries if sq.confidence >= min_confidence]

    # Limita quantidade
    if max_sub_queries:
        filtered = filtered[:max_sub_queries]

    # Inclui query original
    queries = [query] + [sq.query for sq in filtered]

    logger.info(f"Query expandida: {len(queries)} queries ({len(filtered)} sub-queries)")

    return queries


# ============ RANKING & SCORING ============

def rank_sub_queries(
    result: DecompositionResult,
    weight_confidence: float = 0.6,
    weight_type: Dict[str, float] = None
) -> List[SubQuery]:
    """
    Rankeia sub-queries por importância

    Args:
        result: DecompositionResult
        weight_confidence: Peso da confiança (0.0-1.0)
        weight_type: Pesos por tipo {'semantic': 1.0, ...}

    Returns:
        Sub-queries ordenadas por score
    """
    if weight_type is None:
        weight_type = {
            "semantic": 1.2,      # Mais importante
            "entity": 1.0,
            "relational": 0.9,
            "temporal": 0.8,
        }

    def calculate_score(sq: SubQuery) -> float:
        """Calcula score de ranking"""
        type_weight = weight_type.get(sq.type, 1.0)
        confidence_score = sq.confidence * weight_confidence
        return (confidence_score + sq.weight) * type_weight

    # Add score temporary
    scored = [(sq, calculate_score(sq)) for sq in result.sub_queries]
    scored.sort(key=lambda x: x[1], reverse=True)

    ranked = [sq for sq, score in scored]

    logger.info(f"Sub-queries rankeadas: {len(ranked)} total")

    return ranked


# ============ BATCHING & PARALLEL SEARCH ============

def batch_decompose(
    queries: List[str],
    save_to_db: bool = False
) -> List[DecompositionResult]:
    """
    Decomposição em batch para múltiplas queries

    Útil para processar muitas queries de uma vez
    (e.g., durante indexação RAG ou análise de padrões)

    Args:
        queries: Lista de queries
        save_to_db: Salvar resultados no database?

    Returns:
        Lista de DecompositionResult
    """
    logger.info(f"Processando {len(queries)} queries em batch")

    results = []
    for i, query in enumerate(queries, 1):
        logger.debug(f"  [{i}/{len(queries)}] {query[:50]}")
        result = decompose_query(query)
        results.append(result)

        if save_to_db:
            save_decomposition(result)

    logger.info(f"Batch completo: {len(results)} decomposições")

    return results


# ============ CACHING ============

class DecompositionCache:
    """Cache simples em memória para decomposições"""

    def __init__(self, max_size: int = 100):
        self.cache: Dict[str, DecompositionResult] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, query: str) -> Optional[DecompositionResult]:
        """Busca do cache"""
        if query in self.cache:
            self.hits += 1
            logger.debug(f"Cache HIT: {query[:30]}")
            return self.cache[query]
        self.misses += 1
        return None

    def put(self, query: str, result: DecompositionResult) -> None:
        """Salva no cache"""
        if len(self.cache) >= self.max_size:
            # Remove primeira entrada (FIFO simples)
            self.cache.pop(next(iter(self.cache)))

        self.cache[query] = result
        logger.debug(f"Cache PUT: {query[:30]}")

    def decompose_cached(self, query: str) -> DecompositionResult:
        """Decomposição com cache automático"""
        # Tenta cache
        cached = self.get(query)
        if cached:
            return cached

        # Cache miss: faz decomposição
        result = decompose_query(query)
        self.put(query, result)
        return result

    def stats(self) -> Dict[str, Any]:
        """Estatísticas de cache"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "total": total,
            "hit_rate": f"{hit_rate:.1f}%"
        }


# ============ EXPORT & ANALYTICS ============

def export_decompositions(
    results: List[DecompositionResult],
    format: str = "json"
) -> str:
    """
    Exporta múltiplas decomposições

    Args:
        results: Lista de DecompositionResult
        format: "json" ou "csv"

    Returns:
        String com dados exportados
    """
    if format == "json":
        data = [r.to_dict() for r in results]
        return json.dumps(data, indent=2, ensure_ascii=False)

    elif format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "original_query",
            "sub_queries_count",
            "confidence",
            "provider",
            "model",
            "time_ms"
        ])

        # Rows
        for r in results:
            writer.writerow([
                r.original_query,
                len(r.sub_queries),
                f"{r.decomposition_confidence:.2f}",
                r.provider,
                r.model_used,
                f"{r.processing_time_ms:.1f}"
            ])

        return output.getvalue()

    else:
        raise ValueError(f"Format unknown: {format}")


def analyze_decompositions(results: List[DecompositionResult]) -> Dict[str, Any]:
    """
    Análise agregada de decomposições

    Args:
        results: Lista de DecompositionResult

    Returns:
        Dicionário com análises
    """
    if not results:
        return {}

    # Coleta estatísticas
    total_sub_queries = sum(len(r.sub_queries) for r in results)
    avg_confidence = sum(r.decomposition_confidence for r in results) / len(results)
    avg_time = sum(r.processing_time_ms for r in results) / len(results)

    # Conta por provider
    provider_counts = {}
    for r in results:
        provider_counts[r.provider] = provider_counts.get(r.provider, 0) + 1

    # Conta por type de sub-query
    type_counts = {}
    for r in results:
        for sq in r.sub_queries:
            type_counts[sq.type] = type_counts.get(sq.type, 0) + 1

    # Erro
    error_count = sum(1 for r in results if r.error)

    return {
        "total_queries": len(results),
        "total_sub_queries": total_sub_queries,
        "avg_sub_queries_per_query": total_sub_queries / len(results),
        "avg_confidence": f"{avg_confidence:.2f}",
        "avg_processing_time_ms": f"{avg_time:.2f}",
        "providers": provider_counts,
        "sub_query_types": type_counts,
        "errors": error_count,
        "success_rate": f"{((len(results) - error_count) / len(results) * 100):.1f}%"
    }


# ============ EXAMPLES ============

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    print("\n" + "="*70)
    print("QUERY DECOMPOSER INTEGRATION - EXAMPLES")
    print("="*70 + "\n")

    # Example 1: Search expansion
    print("EXAMPLE 1: Search Expansion")
    print("-" * 70)
    expanded = expand_search("Como implementar cache?")
    print(f"Original: 'Como implementar cache?'")
    print(f"Expandida em {len(expanded)} queries:")
    for q in expanded:
        print(f"  • {q}")

    # Example 2: Batching
    print("\n\nEXAMPLE 2: Batch Decomposition")
    print("-" * 70)
    batch_queries = [
        "Query 1",
        "Query 2",
        "Query 3",
    ]
    results = batch_decompose(batch_queries)
    print(f"Processadas {len(results)} queries")

    # Example 3: Analytics
    print("\n\nEXAMPLE 3: Analytics")
    print("-" * 70)
    analytics = analyze_decompositions(results)
    print(f"Analytics: {json.dumps(analytics, indent=2, ensure_ascii=False)}")

    # Example 4: Caching
    print("\n\nEXAMPLE 4: Caching")
    print("-" * 70)
    cache = DecompositionCache(max_size=10)

    # First call (miss)
    r1 = cache.decompose_cached("Query teste")
    print(f"Cache stats: {cache.stats()}")

    # Second call (hit)
    r2 = cache.decompose_cached("Query teste")
    print(f"Cache stats: {cache.stats()}")

    print("\n" + "="*70 + "\n")
