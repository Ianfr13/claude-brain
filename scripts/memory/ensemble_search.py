#!/usr/bin/env python3
"""
Claude Brain - Ensemble Search Engine

Sistema de busca multi-fonte consolidada para o Claude Brain.

Implementa busca paralela em 3 fontes com consolidação, deduplicação e ranking:
1. SQLite: decisions, learnings, memories
2. FAISS: semantic search (RAG)
3. Neo4j: graph traversal (com fallback se offline)

Fluxo:
    query → [SQLite, FAISS, Neo4j] → consolidate → dedupe → rank → rerank → top 10

Features:
- Type hints completos
- Logging detalhado por fonte
- Error handling com fallback gracioso
- Cross-encoder reranking opcional
- Deduplicação por ID
- Resultado consolidado com source tracking
"""

import logging
import time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# Imports do claude-brain
from .base import get_db
from .scoring import rank_results, calculate_relevance_score
from ..faiss_rag import semantic_search as faiss_search

logger = logging.getLogger(__name__)


# ============ TIPOS E DATACLASSES ============

@dataclass
class SearchResult:
    """Resultado consolidado de busca com metadata completa."""
    id: str
    content: str
    source: str  # 'sqlite_decision', 'sqlite_learning', 'faiss', 'neo4j'
    score: float  # 0.0 - 1.0
    relevance_score: Optional[float] = None  # Score final após ranking
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dict (compatível com JSON)."""
        data = asdict(self)
        data['timestamp'] = data.get('timestamp') or datetime.now().isoformat()
        return data


# ============ SQLITE SEARCH ============

def _search_sqlite_decisions(
    query: str,
    project: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Busca em decisões por similarity de texto.

    Args:
        query: Termo de busca
        project: Filtrar por projeto (opcional)
        limit: Número máximo de resultados

    Returns:
        Lista de decisions como dicts
    """
    with get_db() as conn:
        c = conn.cursor()

        # Busca por LIKE case-insensitive
        pattern = f"%{query}%"

        if project:
            c.execute('''
                SELECT id, project, context, decision, reasoning,
                       created_at, updated_at, maturity_status,
                       confidence_score, times_used, times_confirmed, times_contradicted
                FROM decisions
                WHERE project = ? AND (
                    decision LIKE ? OR
                    reasoning LIKE ? OR
                    context LIKE ?
                )
                ORDER BY created_at DESC
                LIMIT ?
            ''', (project, pattern, pattern, pattern, limit))
        else:
            c.execute('''
                SELECT id, project, context, decision, reasoning,
                       created_at, updated_at, maturity_status,
                       confidence_score, times_used, times_confirmed, times_contradicted
                FROM decisions
                WHERE decision LIKE ? OR reasoning LIKE ? OR context LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (pattern, pattern, pattern, limit))

        return [dict(row) for row in c.fetchall()]


def _search_sqlite_learnings(
    query: str,
    project: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Busca em learnings por similarity de texto.

    Args:
        query: Termo de busca
        project: Filtrar por projeto (opcional)
        limit: Número máximo de resultados

    Returns:
        Lista de learnings como dicts
    """
    with get_db() as conn:
        c = conn.cursor()

        pattern = f"%{query}%"

        if project:
            c.execute('''
                SELECT id, project, error_type, error_pattern, error_message,
                       root_cause, solution, prevention, context,
                       created_at, last_occurred, maturity_status,
                       confidence_score, times_used, times_confirmed, times_contradicted
                FROM learnings
                WHERE project = ? AND (
                    error_type LIKE ? OR
                    error_message LIKE ? OR
                    solution LIKE ? OR
                    context LIKE ?
                )
                ORDER BY last_occurred DESC
                LIMIT ?
            ''', (project, pattern, pattern, pattern, pattern, limit))
        else:
            c.execute('''
                SELECT id, project, error_type, error_pattern, error_message,
                       root_cause, solution, prevention, context,
                       created_at, last_occurred, maturity_status,
                       confidence_score, times_used, times_confirmed, times_contradicted
                FROM learnings
                WHERE error_type LIKE ? OR error_message LIKE ? OR
                      solution LIKE ? OR context LIKE ?
                ORDER BY last_occurred DESC
                LIMIT ?
            ''', (pattern, pattern, pattern, pattern, limit))

        return [dict(row) for row in c.fetchall()]


def _search_sqlite(
    query: str,
    project: Optional[str] = None,
    limit: int = 10
) -> List[SearchResult]:
    """Busca consolidada em SQLite (decisions + learnings).

    Args:
        query: Termo de busca
        project: Filtrar por projeto (opcional)
        limit: Número máximo de resultados

    Returns:
        Lista de SearchResult consolidados
    """
    start_time = time.time()
    results = []

    try:
        # Busca decisions
        decisions = _search_sqlite_decisions(query, project, limit=limit // 2)
        logger.info(f"SQLite decisions: {len(decisions)} resultados encontrados")

        for dec in decisions:
            # Usa 'decision' como conteúdo principal
            content = dec.get('decision', '')
            result = SearchResult(
                id=f"decision_{dec['id']}",
                content=content,
                source='sqlite_decision',
                score=float(dec.get('confidence_score', 0.5)),
                metadata={
                    'record_id': dec['id'],
                    'project': dec.get('project'),
                    'context': dec.get('context'),
                    'reasoning': dec.get('reasoning'),
                    'maturity_status': dec.get('maturity_status'),
                    'table': 'decisions'
                },
                timestamp=dec.get('updated_at') or dec.get('created_at')
            )
            results.append(result)

        # Busca learnings
        learnings = _search_sqlite_learnings(query, project, limit=limit // 2)
        logger.info(f"SQLite learnings: {len(learnings)} resultados encontrados")

        for learn in learnings:
            # Usa 'solution' como conteúdo principal
            content = learn.get('solution', '')
            result = SearchResult(
                id=f"learning_{learn['id']}",
                content=content,
                source='sqlite_learning',
                score=float(learn.get('confidence_score', 0.5)),
                metadata={
                    'record_id': learn['id'],
                    'project': learn.get('project'),
                    'error_type': learn.get('error_type'),
                    'error_message': learn.get('error_message'),
                    'root_cause': learn.get('root_cause'),
                    'maturity_status': learn.get('maturity_status'),
                    'table': 'learnings'
                },
                timestamp=learn.get('last_occurred') or learn.get('created_at')
            )
            results.append(result)

        elapsed = time.time() - start_time
        logger.debug(f"SQLite search completed in {elapsed:.2f}s")

    except Exception as e:
        logger.error(f"Erro ao buscar em SQLite: {e}", exc_info=True)

    return results


# ============ FAISS SEARCH ============

def _search_faiss(
    query: str,
    limit: int = 10
) -> List[SearchResult]:
    """Busca semântica usando FAISS.

    Args:
        query: Termo de busca
        limit: Número máximo de resultados

    Returns:
        Lista de SearchResult do FAISS
    """
    start_time = time.time()
    results = []

    try:
        # Usa função existente do faiss_rag.py
        faiss_results = faiss_search(query, limit=limit)
        logger.info(f"FAISS: {len(faiss_results)} resultados encontrados")

        for i, faiss_result in enumerate(faiss_results):
            result = SearchResult(
                id=f"faiss_{faiss_result.get('chunk_id', i)}",
                content=faiss_result.get('text', ''),
                source='faiss',
                score=float(faiss_result.get('score', 0.0)),
                metadata={
                    'chunk_id': faiss_result.get('chunk_id'),
                    'doc_type': faiss_result.get('doc_type'),
                    'source_file': faiss_result.get('source'),
                    'position': faiss_result.get('position')
                },
                timestamp=datetime.now().isoformat()
            )
            results.append(result)

        elapsed = time.time() - start_time
        logger.debug(f"FAISS search completed in {elapsed:.2f}s")

    except Exception as e:
        logger.error(f"Erro ao buscar em FAISS: {e}", exc_info=True)

    return results


# ============ NEO4J SEARCH (COM FALLBACK) ============

def _search_neo4j(
    query: str,
    project: Optional[str] = None,
    limit: int = 10,
    use_graph: bool = True
) -> List[SearchResult]:
    """Busca em Neo4j com fallback gracioso se offline.

    Args:
        query: Termo de busca
        project: Filtrar por projeto (opcional)
        limit: Número máximo de resultados
        use_graph: Se False, pula Neo4j e retorna []

    Returns:
        Lista de SearchResult do Neo4j (vazio se offline ou use_graph=False)
    """
    if not use_graph:
        logger.debug("Neo4j busca desabilitada (use_graph=False)")
        return []

    start_time = time.time()
    results = []

    try:
        # Importação local para evitar erro se neo4j_wrapper não existir
        from .neo4j_wrapper import Neo4jGraph
        import os

        # Inicializa com parâmetros do ambiente
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD")

        if not password:
            logger.warning("NEO4J_PASSWORD não configurada, pulando Neo4j")
            return []

        graph = Neo4jGraph(uri=uri, user=user, password=password)

        # Tenta busca graph (ex: graph traversal, relationship search)
        graph_results = graph.search_with_relationships(query, project, limit)
        logger.info(f"Neo4j: {len(graph_results)} resultados encontrados")

        for i, graph_result in enumerate(graph_results):
            result = SearchResult(
                id=f"neo4j_{graph_result.get('node_id', i)}",
                content=graph_result.get('name') or graph_result.get('description', ''),
                source='neo4j',
                score=float(graph_result.get('score', 0.5)),
                metadata={
                    'node_id': graph_result.get('node_id'),
                    'node_type': graph_result.get('node_type'),
                    'relationships': graph_result.get('relationships', []),
                    'properties': graph_result.get('properties', {})
                },
                timestamp=graph_result.get('updated_at', datetime.now().isoformat())
            )
            results.append(result)

        elapsed = time.time() - start_time
        logger.debug(f"Neo4j search completed in {elapsed:.2f}s")

    except ImportError:
        logger.warning("neo4j_wrapper não disponível (módulo não encontrado)")
    except Exception as e:
        logger.warning(f"Neo4j offline ou erro ao buscar: {e}")
        logger.debug("Continuando com fallback (sem Neo4j)")

    return results


# ============ CONSOLIDAÇÃO E RANKING ============

def _consolidate_results(
    sqlite_results: List[SearchResult],
    faiss_results: List[SearchResult],
    neo4j_results: List[SearchResult],
    query: str,
    project: Optional[str] = None
) -> List[SearchResult]:
    """Consolida resultados de múltiplas fontes com deduplicação.

    Args:
        sqlite_results: Resultados do SQLite
        faiss_results: Resultados do FAISS
        neo4j_results: Resultados do Neo4j
        query: Query original (para context)
        project: Projeto (para context)

    Returns:
        Lista consolidada de SearchResult com scores recalculados
    """
    # Combina todos os resultados
    all_results = sqlite_results + faiss_results + neo4j_results

    if not all_results:
        logger.warning("Nenhum resultado encontrado em nenhuma fonte")
        return []

    # Deduplicação por ID (evita duplicatas entre fontes)
    seen_ids: Dict[str, SearchResult] = {}
    for result in all_results:
        if result.id not in seen_ids:
            seen_ids[result.id] = result
        else:
            # Se duplicate, mantém o de melhor score
            if result.score > seen_ids[result.id].score:
                seen_ids[result.id] = result

    deduplicated = list(seen_ids.values())
    logger.info(f"Deduplicação: {len(all_results)} → {len(deduplicated)} resultados")

    # Converte para dicts para usar scoring.rank_results()
    result_dicts = []
    for result in deduplicated:
        # Prepara dict com campos esperados pelo rank_results()
        record = {
            'id': result.id,
            'content': result.content,
            'source': result.source,
            'confidence_score': result.score,
            'project': project,
            'created_at': result.timestamp,
            'updated_at': result.timestamp
        }
        result_dicts.append(record)

    # Usa scoring.rank_results() para ranking composto
    ranked_dicts = rank_results(result_dicts, query, project)

    # Reconverte para SearchResult com relevance_score adicionado
    final_results = []
    for ranked_dict in ranked_dicts:
        # Encontra o SearchResult original
        original = next((r for r in deduplicated if r.id == ranked_dict['id']), None)
        if original:
            original.relevance_score = ranked_dict.get('relevance_score', 0.0)
            final_results.append(original)

    return final_results


def _apply_cross_encoder_reranking(
    results: List[SearchResult],
    query: str
) -> List[SearchResult]:
    """Aplica reranking com cross-encoder se houver muitos resultados.

    Args:
        results: Resultados para reranking
        query: Query original

    Returns:
        Resultados rerankeados ou originais se < 5 resultados
    """
    if len(results) <= 5:
        logger.debug("Poucos resultados (<5), pulando cross-encoder reranking")
        return results

    try:
        from sentence_transformers import CrossEncoder
        logger.info("Aplicando cross-encoder reranking...")

        # Carrega modelo cross-encoder (compatível com MS MARCO)
        model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

        # Prepara pares query-documento
        pairs = [[query, result.content] for result in results]

        # Calcula scores
        scores = model.predict(pairs)

        # Atualiza relevance_score com cross-encoder scores
        for result, score in zip(results, scores):
            # Combina score anterior (70%) com cross-encoder (30%)
            old_score = result.relevance_score or result.score
            result.relevance_score = (old_score * 0.7) + (float(score) * 0.3)

        # Re-ordena por novo score
        results = sorted(results, key=lambda r: r.relevance_score or 0.0, reverse=True)

        logger.info(f"Cross-encoder reranking aplicado a {len(results)} resultados")

    except ImportError:
        logger.debug("sentence-transformers não disponível, pulando cross-encoder")
    except Exception as e:
        logger.warning(f"Erro no cross-encoder reranking: {e}")

    return results


# ============ FUNÇÃO PRINCIPAL ============

def ensemble_search(
    query: str,
    project: Optional[str] = None,
    use_graph: bool = True,
    limit: int = 10,
    enable_cross_encoder: bool = True
) -> List[Dict[str, Any]]:
    """Busca ensemble multi-fonte consolidada.

    Implementa busca paralela em 3 fontes:
    1. SQLite (decisions + learnings)
    2. FAISS (semantic search)
    3. Neo4j (graph traversal, com fallback se offline)

    Fluxo:
        query → [SQLite, FAISS, Neo4j] → consolidate → dedupe → rank
                 → cross-encoder rerank (opcional) → top 10

    Args:
        query: Termo de busca
        project: Filtrar por projeto (opcional)
        use_graph: Se True, tenta buscar em Neo4j (com fallback)
        limit: Número máximo de resultados finais (default: 10)
        enable_cross_encoder: Se True, aplica reranking com cross-encoder (opcional)

    Returns:
        Lista de dicts com resultados consolidados, ordenados por relevância:
        {
            'id': str,
            'content': str,
            'source': str,  # 'sqlite_decision', 'sqlite_learning', 'faiss', 'neo4j'
            'relevance_score': float,  # Score final 0.0-1.0
            'metadata': dict,
            'timestamp': str
        }

    Examples:
        >>> results = ensemble_search("redis cache", project="vsl-analysis")
        >>> for r in results:
        ...     print(f"{r['relevance_score']:.2f} | {r['source']}: {r['content'][:50]}")

        >>> results = ensemble_search("ConnectionError", use_graph=False)
        >>> # Busca só em SQLite + FAISS, pula Neo4j
    """
    start_time = time.time()
    logger.info(f"Iniciando ensemble search: '{query}' (project={project})")

    # Busca paralela em 3 fontes
    logger.debug("Buscando em SQLite...")
    sqlite_results = _search_sqlite(query, project, limit=limit)

    logger.debug("Buscando em FAISS...")
    faiss_results = _search_faiss(query, limit=limit)

    logger.debug(f"Buscando em Neo4j (use_graph={use_graph})...")
    neo4j_results = _search_neo4j(query, project, limit=limit, use_graph=use_graph)

    # Consolida resultados
    logger.debug("Consolidando resultados...")
    consolidated = _consolidate_results(
        sqlite_results, faiss_results, neo4j_results, query, project
    )

    # Limita a TOP K
    consolidated = consolidated[:limit]

    # Cross-encoder reranking opcional
    if enable_cross_encoder and len(consolidated) > 5:
        logger.debug("Aplicando cross-encoder reranking...")
        consolidated = _apply_cross_encoder_reranking(consolidated, query)

    # Converte para dicts para retorno
    final_results = [result.to_dict() for result in consolidated]

    elapsed = time.time() - start_time
    logger.info(
        f"Ensemble search concluído: {len(final_results)} resultados em {elapsed:.2f}s"
    )

    # Log summary
    sources_count = {}
    for result in final_results:
        source = result['source']
        sources_count[source] = sources_count.get(source, 0) + 1

    logger.info(f"Distribuição de fontes: {sources_count}")

    return final_results


# ============ CLI TESTING ============

if __name__ == "__main__":
    import sys
    import json

    # Configure logging para CLI
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 2:
        print("Uso: ensemble_search.py <query> [project] [--no-graph] [--no-cross-encoder]")
        print("\nExemplos:")
        print("  python ensemble_search.py 'redis cache'")
        print("  python ensemble_search.py 'ConnectionError' vsl-analysis")
        print("  python ensemble_search.py 'FastAPI' --no-graph")
        sys.exit(1)

    query = sys.argv[1]
    project = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    use_graph = '--no-graph' not in sys.argv
    enable_cross_encoder = '--no-cross-encoder' not in sys.argv

    print(f"\nBuscando: '{query}'")
    if project:
        print(f"Projeto: {project}")
    print(f"Use graph: {use_graph}, Cross-encoder: {enable_cross_encoder}")
    print("-" * 80)

    results = ensemble_search(
        query,
        project=project,
        use_graph=use_graph,
        enable_cross_encoder=enable_cross_encoder
    )

    print(f"\nResultados ({len(results)}):\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. [{result['relevance_score']:.3f}] {result['source']}")
        print(f"   {result['content'][:100]}...")
        print(f"   Timestamp: {result['timestamp']}\n")

    print("\nJSON completo:")
    print(json.dumps(results, indent=2, ensure_ascii=False))
