# Claude Brain - API REST Completa

**FastAPI Documentation**

Documentação completa dos endpoints REST para Claude Brain.

## Sumário

1. [Health & Info](#health--info)
2. [Search Endpoints](#search-endpoints)
3. [Decision Management](#decision-management)
4. [Learning Management](#learning-management)
5. [Memory Management](#memory-management)
6. [Graph Operations](#graph-operations)
7. [Job Queue](#job-queue)
8. [Rate Limiting](#rate-limiting)
9. [Authentication](#authentication)

---

## Health & Info

### GET /health

Health check do sistema.

**Request:**
```bash
curl http://localhost:8765/health
```

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-04T10:00:00Z",
  "version": "1.2.0",
  "components": {
    "sqlite": "ok",
    "faiss": "ok",
    "neo4j": "ok",
    "redis": "ok"
  },
  "uptime_seconds": 3600
}
```

---

### GET /stats

Estatísticas do sistema.

**Request:**
```bash
curl http://localhost:8765/stats
```

**Response (200):**
```json
{
  "decisions_count": 112,
  "learnings_count": 45,
  "memories_count": 28,
  "faiss_vectors": 3421,
  "neo4j_nodes": 150,
  "neo4j_edges": 280,
  "cache_hit_rate": 0.62,
  "avg_search_time_ms": 1234,
  "storage_mb": 150
}
```

---

## Search Endpoints

### POST /search

Busca simples em SQLite + FAISS (sem LLM decomposition).

**Request:**
```bash
curl -X POST http://localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "redis cache",
    "project": "vsl-analysis",
    "limit": 10
  }'
```

**Parameters:**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| query | string | ✅ | - | Texto da busca |
| project | string | ❌ | null | Filtrar por projeto |
| limit | int | ❌ | 10 | Max resultados (1-100) |
| use_graph | bool | ❌ | true | Incluir Neo4j |
| enable_cross_encoder | bool | ❌ | true | Reranking final |

**Response (200):**
```json
{
  "query": "redis cache",
  "project": "vsl-analysis",
  "results": [
    {
      "id": "sqlite_decision_45",
      "rank": 1,
      "relevance_score": 0.92,
      "source": "sqlite_decision",
      "content": "Use Redis with TTL 24h for performance",
      "metadata": {
        "project": "vsl-analysis",
        "confidence": 0.9,
        "maturity": "confirmed",
        "usage_count": 23,
        "created_at": "2025-11-15T09:30:00Z"
      }
    }
  ],
  "execution_time_ms": 245,
  "timestamp": "2026-02-04T10:00:00Z"
}
```

---

### POST /agentic-search

Busca inteligente com Query Decomposer + Ensemble Search.

**Request:**
```bash
curl -X POST http://localhost:8765/agentic-search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Como resolver erro de conexão Redis no vsl-analysis?",
    "project": "vsl-analysis"
  }'
```

**Parameters:**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| query | string | ✅ | - | Pergunta em linguagem natural |
| project | string | ❌ | null | Contexto do projeto |
| decomposition_depth | int | ❌ | 3 | Num sub-queries (2-5) |
| timeout_seconds | int | ❌ | 10 | Timeout máximo |

**Response (200):**
```json
{
  "original_query": "Como resolver erro de conexão Redis no vsl-analysis?",
  "decomposition": {
    "provider": "nvidia/nemotron-nano:free",
    "confidence": 0.88,
    "sub_queries": [
      {
        "type": "CONCEPTUAL",
        "query": "Redis connection troubleshooting",
        "confidence": 0.92
      },
      {
        "type": "TECHNICAL",
        "query": "systemctl redis-server error handling",
        "confidence": 0.85
      },
      {
        "type": "PROJECT_SPECIFIC",
        "query": "vsl-analysis Redis configuration",
        "confidence": 0.78
      }
    ]
  },
  "consolidated_results": [
    {
      "rank": 1,
      "relevance_score": 0.95,
      "content": "ConnectionError: Verify redis-server is running via systemctl status redis-server",
      "sources": ["sqlite_learning", "neo4j"],
      "metadata": {
        "error_category": "connectivity",
        "solution_type": "troubleshooting",
        "project": "vsl-analysis"
      }
    }
  ],
  "execution_time_ms": 2345,
  "timestamp": "2026-02-04T10:00:00Z"
}
```

---

## Decision Management

### POST /decisions

Criar nova decisão.

**Request:**
```bash
curl -X POST http://localhost:8765/decisions \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Use Redis for caching",
    "description": "Redis improves performance by 50%",
    "project": "vsl-analysis",
    "reasoning": "Tested with 10k req/s benchmark",
    "confidence": 0.9
  }'
```

**Response (201):**
```json
{
  "id": 45,
  "title": "Use Redis for caching",
  "project": "vsl-analysis",
  "confidence": 0.9,
  "maturity_status": "hypothesis",
  "created_at": "2026-02-04T10:00:00Z"
}
```

---

### GET /decisions

Listar decisões.

**Request:**
```bash
curl "http://localhost:8765/decisions?project=vsl-analysis&limit=10"
```

**Response (200):**
```json
{
  "decisions": [
    {
      "id": 45,
      "title": "Use Redis for caching",
      "project": "vsl-analysis",
      "confidence": 0.9,
      "maturity_status": "confirmed",
      "usage_count": 23,
      "created_at": "2025-11-15T09:30:00Z"
    }
  ],
  "total": 112,
  "limit": 10
}
```

---

### PATCH /decisions/{id}

Atualizar decisão.

**Request:**
```bash
curl -X PATCH http://localhost:8765/decisions/45 \
  -H "Content-Type: application/json" \
  -d '{
    "confidence": 0.95,
    "maturity_status": "confirmed"
  }'
```

**Response (200):**
```json
{
  "id": 45,
  "title": "Use Redis for caching",
  "confidence": 0.95,
  "maturity_status": "confirmed",
  "updated_at": "2026-02-04T10:05:00Z"
}
```

---

### DELETE /decisions/{id}

Deletar decisão.

**Request:**
```bash
curl -X DELETE http://localhost:8765/decisions/45
```

**Response (204):** (No content)

---

## Learning Management

### POST /learnings

Salvar novo learning (erro + solução).

**Request:**
```bash
curl -X POST http://localhost:8765/learnings \
  -H "Content-Type: application/json" \
  -d '{
    "error": "ConnectionError: redis-server not running",
    "solution": "Run: systemctl restart redis-server",
    "project": "vsl-analysis",
    "category": "infrastructure"
  }'
```

**Response (201):**
```json
{
  "id": 23,
  "error": "ConnectionError: redis-server not running",
  "solution": "Run: systemctl restart redis-server",
  "project": "vsl-analysis",
  "category": "infrastructure",
  "created_at": "2026-02-04T10:00:00Z"
}
```

---

### GET /learnings

Listar learnings.

**Request:**
```bash
curl "http://localhost:8765/learnings?project=vsl-analysis&limit=20"
```

**Response (200):**
```json
{
  "learnings": [
    {
      "id": 23,
      "error": "ConnectionError: redis-server not running",
      "solution": "Run: systemctl restart redis-server",
      "project": "vsl-analysis",
      "category": "infrastructure",
      "confidence": 0.95,
      "usage_count": 5,
      "created_at": "2025-11-15T09:30:00Z"
    }
  ],
  "total": 45,
  "limit": 20
}
```

---

## Memory Management

### POST /memories

Salvar memória geral.

**Request:**
```bash
curl -X POST http://localhost:8765/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "FastAPI supports async/await for high performance",
    "category": "technology"
  }'
```

**Response (201):**
```json
{
  "id": 128,
  "content": "FastAPI supports async/await for high performance",
  "category": "technology",
  "created_at": "2026-02-04T10:00:00Z"
}
```

---

### GET /memories

Listar memórias.

**Request:**
```bash
curl "http://localhost:8765/memories?category=technology&limit=10"
```

**Response (200):**
```json
{
  "memories": [
    {
      "id": 128,
      "content": "FastAPI supports async/await for high performance",
      "category": "technology",
      "relevance_score": 0.8,
      "created_at": "2025-11-15T09:30:00Z"
    }
  ],
  "total": 28
}
```

---

## Graph Operations

### GET /graph/stats

Estatísticas do Neo4j.

**Request:**
```bash
curl http://localhost:8765/graph/stats
```

**Response (200):**
```json
{
  "nodes": 150,
  "edges": 280,
  "labels": ["Decision", "Learning", "Memory", "Project", "Technology"],
  "relation_types": ["RELATES_TO", "VALIDATES", "CONTRADICTS", "USES"],
  "pagerank_ready": true,
  "last_sync": "2026-02-04T09:55:00Z"
}
```

---

### GET /graph/pagerank

Top conceitos por importância (PageRank).

**Request:**
```bash
curl "http://localhost:8765/graph/pagerank?limit=10"
```

**Response (200):**
```json
{
  "top_concepts": [
    {
      "rank": 1,
      "label": "Decision",
      "content": "Use Redis for caching",
      "score": 0.85,
      "connections": 23
    },
    {
      "rank": 2,
      "label": "Technology",
      "content": "Redis",
      "score": 0.78,
      "connections": 15
    }
  ]
}
```

---

### POST /graph/sync

Sincronizar SQLite → Neo4j manualmente.

**Request:**
```bash
curl -X POST http://localhost:8765/graph/sync \
  -H "Content-Type: application/json" \
  -d '{
    "force_full_sync": false
  }'
```

**Response (200):**
```json
{
  "status": "synced",
  "decisions_synced": 112,
  "learnings_synced": 45,
  "execution_time_ms": 2341,
  "timestamp": "2026-02-04T10:00:00Z"
}
```

---

## Job Queue

### POST /jobs

Criar novo job (para sub-tasks distribuídos).

**Request:**
```bash
curl -X POST http://localhost:8765/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Implementar cache Redis",
    "skills": ["python-pro-skill", "devops-engineer-skill"],
    "ttl_seconds": 43200,
    "distributed": true
  }'
```

**Response (201):**
```json
{
  "job_id": "52445047-9d82-45d4-850b-8f76054abb68",
  "status": "created",
  "ttl_seconds": 43200,
  "expires_at": "2026-02-04T12:00:00Z",
  "created_at": "2026-02-04T00:00:00Z"
}
```

---

### GET /jobs/{job_id}

Obter status do job.

**Request:**
```bash
curl http://localhost:8765/jobs/52445047-9d82-45d4-850b-8f76054abb68
```

**Response (200):**
```json
{
  "job_id": "52445047-9d82-45d4-850b-8f76054abb68",
  "status": "running",
  "progress": 0.67,
  "sub_tasks": [
    {
      "id": "sub_1",
      "status": "completed",
      "result": "..."
    }
  ],
  "expires_at": "2026-02-04T12:00:00Z"
}
```

---

## Rate Limiting

### Headers Retornados

Toda resposta inclui:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1707000000
X-RateLimit-Retry-After: 60
```

### Limites Padrão

| Endpoint | Limite | Janela |
|----------|--------|--------|
| /search | 100 | 60s |
| /agentic-search | 20 | 60s |
| /decisions | 50 | 60s |
| /learnings | 50 | 60s |
| /graph/* | 30 | 60s |

### Response (429 Too Many Requests)

```json
{
  "error": "Rate limit exceeded",
  "retry_after_seconds": 45
}
```

---

## Authentication

### Bearer Token

**Para APIs futuras:**

```bash
curl -H "Authorization: Bearer sk_brain_..." \
  http://localhost:8765/search
```

**Header esperado:**
```
Authorization: Bearer <token>
```

---

## Error Responses

### 400 Bad Request

```json
{
  "error": "Bad Request",
  "detail": "Query cannot be empty",
  "request_id": "req_12345"
}
```

### 404 Not Found

```json
{
  "error": "Not Found",
  "detail": "Decision with ID 999 not found",
  "request_id": "req_12345"
}
```

### 500 Internal Server Error

```json
{
  "error": "Internal Server Error",
  "detail": "Database connection failed",
  "request_id": "req_12345"
}
```

---

## Exemplos End-to-End

### Fluxo Completo: Salvar + Buscar

```bash
# 1. Salvar decisão
DECISION_ID=$(curl -s -X POST http://localhost:8765/decisions \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Use FastAPI for REST API",
    "project": "claude-brain",
    "confidence": 0.9
  }' | jq .id)

echo "Decision ID: $DECISION_ID"

# 2. Sincronizar para Neo4j
curl -X POST http://localhost:8765/graph/sync

# 3. Buscar com ensemble
curl -X POST http://localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "FastAPI REST",
    "project": "claude-brain"
  }' | jq '.results | .[0]'

# 4. Ver estatísticas
curl http://localhost:8765/stats | jq '.decisions_count'
```

### Fluxo Agentic: Query → Decomposição → Busca

```bash
# Busca inteligente com LLM
curl -X POST http://localhost:8765/agentic-search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Como otimizar performance de busca no Neo4j com 150k nós?",
    "project": "claude-brain",
    "decomposition_depth": 4
  }' | jq '.'
```

---

## Swagger UI Interativo

```
http://localhost:8765/docs
```

Todos os endpoints estão disponíveis para teste interativo via Swagger UI (Redoc em `/redoc`).

---

**Última atualização**: 2026-02-04
**Versão API**: 1.2.0
