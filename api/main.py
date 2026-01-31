#!/usr/bin/env python3
"""
Claude Brain - FastAPI REST API
Expoe funcionalidades do brain via HTTP
"""

import sys
from pathlib import Path

# Adiciona scripts ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from fastapi import FastAPI, Query, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List, Dict, Any
import uvicorn
import logging

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS protection (legacy, but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (restrict browser features)
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Content Security Policy (basic)
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"

        # Cache control for API responses
        if request.url.path.startswith("/api") or not request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-store, max-age=0"

        return response

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Imports dos modulos do brain
from memory_store import (
    get_stats as db_get_stats,
    get_decisions,
    get_all_learnings,
    search_memories,
    get_all_preferences,
    get_entity_graph,
    get_all_entities,
    get_all_patterns,
)
from metrics import get_effectiveness, get_daily_report
from faiss_rag import semantic_search, get_stats as rag_get_stats


def _handle_error(e: Exception, operation: str) -> HTTPException:
    """Loga erro interno e retorna mensagem genérica para o usuário."""
    logger.error(f"Erro em {operation}: {type(e).__name__}: {e}")
    return HTTPException(status_code=500, detail=f"Erro interno em {operation}")


# Inicializa FastAPI
app = FastAPI(
    title="Claude Brain API",
    description="API REST para o sistema de memoria inteligente Claude Brain",
    version="1.0.0",
)

# Attach rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Configura CORS para frontend (restrito a localhost por seguranca)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8765", "http://127.0.0.1:8765"],
    allow_credentials=False,
    allow_methods=["GET"],  # API somente leitura
    allow_headers=["*"],
)


# ============ ENDPOINTS ============


@app.get("/", tags=["Health"])
def root():
    """Health check e info basica da API"""
    return {
        "status": "online",
        "service": "Claude Brain API",
        "version": "1.0.0",
        "api_version": "v1",
        "endpoints": [
            "/v1/stats",
            "/v1/decisions",
            "/v1/learnings",
            "/v1/preferences",
            "/v1/metrics",
            "/v1/search",
            "/v1/memories",
            "/v1/entities",
            "/v1/patterns",
            "/v1/graph/{entity}",
        ],
        "dashboard": "/dashboard",
    }


@app.get("/v1/stats", tags=["Stats"])
@limiter.limit("60/minute")
def get_stats(request: Request):
    """
    Retorna estatisticas gerais do brain.

    Inclui contagem de memorias, decisoes, aprendizados, entidades, etc.
    Tambem retorna stats do indice FAISS (RAG).
    """
    try:
        db_stats = db_get_stats()
        rag_stats = rag_get_stats()

        return {
            "database": db_stats,
            "rag": rag_stats,
        }
    except Exception as e:
        raise _handle_error(e, "stats")


@app.get("/v1/decisions", tags=["Memory"])
def list_decisions(
    project: Optional[str] = Query(None, description="Filtrar por projeto"),
    status: str = Query("active", description="Status das decisoes (active, deprecated, etc)"),
    limit: int = Query(20, ge=1, le=100, description="Numero maximo de resultados"),
):
    """
    Lista decisoes arquiteturais armazenadas.

    Decisoes sao escolhas importantes feitas durante desenvolvimento,
    como tecnologias, padroes de design, abordagens, etc.
    """
    try:
        decisions = get_decisions(project=project, status=status, limit=limit)
        return {
            "count": len(decisions),
            "project": project,
            "status": status,
            "decisions": decisions,
        }
    except Exception as e:
        raise _handle_error(e, "decisions")


@app.get("/v1/learnings", tags=["Memory"])
def list_learnings(
    limit: int = Query(20, ge=1, le=100, description="Numero maximo de resultados"),
):
    """
    Lista aprendizados de erros.

    Aprendizados sao solucoes para problemas encontrados,
    armazenadas para evitar repetir os mesmos erros.
    """
    try:
        learnings = get_all_learnings(limit=limit)
        return {
            "count": len(learnings),
            "learnings": learnings,
        }
    except Exception as e:
        raise _handle_error(e, "learnings")


@app.get("/v1/preferences", tags=["Memory"])
def list_preferences(
    min_confidence: float = Query(0.3, ge=0.0, le=1.0, description="Confianca minima"),
):
    """
    Lista preferencias do usuario.

    Preferencias sao detectadas automaticamente baseadas em padroes de uso,
    como frameworks preferidos, estilo de codigo, etc.
    """
    try:
        preferences = get_all_preferences(min_confidence=min_confidence)
        return {
            "count": len(preferences),
            "min_confidence": min_confidence,
            "preferences": preferences,
        }
    except Exception as e:
        raise _handle_error(e, "preferences")


@app.get("/v1/metrics", tags=["Metrics"])
def get_metrics(
    days: int = Query(7, ge=1, le=30, description="Numero de dias para relatorio diario"),
):
    """
    Retorna metricas de eficacia do brain.

    Inclui taxa de acertos, acoes uteis vs inuteis,
    score medio de buscas, e relatorio diario.
    """
    try:
        effectiveness = get_effectiveness()
        daily_report = get_daily_report(days=days)

        return {
            "effectiveness": effectiveness,
            "daily_report": daily_report,
        }
    except Exception as e:
        raise _handle_error(e, "metrics")


@app.get("/v1/search", tags=["Search"])
@limiter.limit("30/minute")
def search(
    request: Request,
    q: str = Query(..., min_length=2, description="Query de busca"),
    doc_type: Optional[str] = Query(None, description="Filtrar por tipo de documento"),
    limit: int = Query(5, ge=1, le=20, description="Numero maximo de resultados"),
):
    """
    Busca semantica nos documentos indexados.

    Usa FAISS com embeddings para encontrar documentos
    semanticamente similares a query.
    """
    try:
        results = semantic_search(query=q, doc_type=doc_type, limit=limit)

        return {
            "query": q,
            "doc_type": doc_type,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        raise _handle_error(e, "search")


@app.get("/v1/memories", tags=["Memory"])
def search_in_memories(
    q: Optional[str] = Query(None, description="Query de busca"),
    type: Optional[str] = Query(None, description="Tipo de memoria"),
    category: Optional[str] = Query(None, description="Categoria"),
    min_importance: int = Query(0, ge=0, le=10, description="Importancia minima"),
    limit: int = Query(10, ge=1, le=50, description="Numero maximo de resultados"),
):
    """
    Busca nas memorias do banco SQLite.

    Diferente de /search que usa busca semantica,
    este endpoint faz busca por texto e filtros.
    """
    try:
        memories = search_memories(
            query=q,
            type=type,
            category=category,
            min_importance=min_importance,
            limit=limit,
        )

        return {
            "count": len(memories),
            "filters": {
                "query": q,
                "type": type,
                "category": category,
                "min_importance": min_importance,
            },
            "memories": memories,
        }
    except Exception as e:
        raise _handle_error(e, "memories")


@app.get("/v1/entities", tags=["Knowledge Graph"])
def list_entities(
    type: Optional[str] = Query(None, description="Filtrar por tipo (project, technology, etc)"),
    limit: int = Query(100, ge=1, le=200, description="Numero maximo de resultados"),
):
    """
    Lista todas as entidades do knowledge graph.
    """
    try:
        entities = get_all_entities(type=type, limit=limit)
        return {
            "count": len(entities),
            "type_filter": type,
            "entities": entities,
        }
    except Exception as e:
        raise _handle_error(e, "entities")


@app.get("/v1/patterns", tags=["Memory"])
def list_patterns(
    type: Optional[str] = Query(None, description="Filtrar por tipo de pattern"),
    limit: int = Query(100, ge=1, le=200, description="Numero maximo de resultados"),
):
    """
    Lista todos os padrões de código salvos.
    """
    try:
        patterns = get_all_patterns(pattern_type=type, limit=limit)
        return {
            "count": len(patterns),
            "type_filter": type,
            "patterns": patterns,
        }
    except Exception as e:
        raise _handle_error(e, "patterns")


@app.get("/v1/graph/{entity}", tags=["Knowledge Graph"])
@limiter.limit("30/minute")
def get_graph(request: Request, entity: str):
    """
    Retorna knowledge graph de uma entidade.

    Inclui a entidade, suas relacoes de saida (para outras entidades),
    e relacoes de entrada (de outras entidades para ela).
    """
    try:
        graph = get_entity_graph(entity)

        if graph is None:
            raise HTTPException(
                status_code=404,
                detail=f"Entidade '{entity}' nao encontrada",
            )

        return graph
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_error(e, "graph")


# ============ DASHBOARD ============

DASHBOARD_PATH = Path(__file__).parent.parent / "dashboard" / "index.html"

@app.get("/dashboard", tags=["Dashboard"], response_class=HTMLResponse)
def dashboard():
    """Serve o dashboard HTML"""
    if DASHBOARD_PATH.exists():
        return HTMLResponse(content=DASHBOARD_PATH.read_text(), status_code=200)
    return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)


# ============ MAIN ============

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",  # Apenas localhost, nao expor externamente
        port=8765,
    )
