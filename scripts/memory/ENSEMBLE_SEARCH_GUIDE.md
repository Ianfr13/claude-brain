# Ensemble Search - Guia Completo

## Overview

`ensemble_search.py` implementa um sistema de busca **multi-fonte consolidada** para o Claude Brain que integra:

1. **SQLite**: decisions + learnings (busca por texto)
2. **FAISS**: semantic search (busca semântica via embeddings)
3. **Neo4j**: graph traversal (busca por relacionamentos, com fallback se offline)

O sistema consolida resultados de todas as 3 fontes, deduplicação, ranking inteligente e reranking opcional com cross-encoder.

---

## Uso Básico

### Importar

```python
from scripts.memory import ensemble_search, SearchResult

# Ou diretamente:
from scripts.memory.ensemble_search import ensemble_search
```

### Busca Simples

```python
# Busca básica
results = ensemble_search("redis cache")

for result in results:
    print(f"[{result['relevance_score']:.2f}] {result['source']}")
    print(f"  {result['content'][:100]}...")
    print(f"  ID: {result['id']}\n")
```

### Com Filtro de Projeto

```python
# Busca específica para projeto
results = ensemble_search(
    "ConnectionError",
    project="vsl-analysis"
)
```

### Desabilitar Neo4j

```python
# Se Neo4j não está disponível ou quer evitar overhead:
results = ensemble_search(
    "FastAPI",
    use_graph=False  # Pula Neo4j, busca só SQLite + FAISS
)
```

### Desabilitar Cross-Encoder Reranking

```python
# Para performance (default=True):
results = ensemble_search(
    "query",
    enable_cross_encoder=False
)
```

### Ajustar Limite de Resultados

```python
# Default: 10 resultados
results = ensemble_search("query", limit=20)
```

---

## Estructura de Resultado

```python
{
    'id': 'sqlite_decision_1',           # ID único: source + ID
    'content': 'Use Redis for caching',  # Conteúdo principal
    'source': 'sqlite_decision',         # 'sqlite_decision', 'sqlite_learning', 'faiss', 'neo4j'
    'relevance_score': 0.85,             # Score final (0.0-1.0)
    'score': 0.9,                        # Score original da fonte
    'metadata': {                        # Dados específicos da fonte
        'record_id': 1,
        'project': 'vsl-analysis',
        'context': 'Caching layer design',
        'maturity_status': 'confirmed'
    },
    'timestamp': '2025-01-01T10:00:00'   # ISO format timestamp
}
```

---

## Fluxo Interno

### 1. Busca Paralela (3 Fontes)

```
SQLite:     query LIKE search (pattern matching)
            ├─ Decisions: decision + reasoning + context
            └─ Learnings: error_type + solution + prevention

FAISS:      semantic_search(query) - embeddings similarity
            └─ Return: score + text + source + doc_type

Neo4j:      graph search by relationships (com fallback)
            └─ Return: node properties + relationships
```

### 2. Consolidação

```
[SQLite Results] + [FAISS Results] + [Neo4j Results]
        ↓
    Deduplicação (por ID)
        ↓
    Conversão para dicts com campos padrão
        ↓
    Ranking com scoring.rank_results()
    (Especificidade + Recência + Confiança + Uso + Validação)
```

### 3. Reranking (Opcional)

```
Se len(results) > 5:
    Cross-Encoder Model: ms-marco-MiniLM-L-6-v2
    ├─ Calcula score query-document
    └─ Combina: 70% old_score + 30% cross_encoder_score

Re-ordena por novo score
```

---

## Exemplos Práticos

### Buscar Decisão Arquitetural

```python
results = ensemble_search(
    "cache strategy",
    project="vsl-analysis",
    limit=5
)

# Retorna decisions + learnings + documentação
for r in results:
    if r['source'].startswith('sqlite_decision'):
        print(f"Decisão: {r['content']}")
        print(f"Projeto: {r['metadata'].get('project')}")
        print(f"Status: {r['metadata'].get('maturity_status')}\n")
```

### Buscar Solução para Erro

```python
results = ensemble_search(
    "ConnectionError redis",
    use_graph=False  # Sem Neo4j, mais rápido
)

# Primeiro resultado deve ser learning com solução
if results:
    best = results[0]
    print(f"Problema: {best['metadata'].get('error_type')}")
    print(f"Solução: {best['content']}")
    print(f"Confiança: {best['relevance_score']:.0%}")
```

### Buscar com Contexto RAG

```python
# Combina documentação + decisions + learnings
results = ensemble_search(
    "FastAPI async patterns",
    limit=10
)

# Filtra por fonte
faiss_results = [r for r in results if r['source'] == 'faiss']
decision_results = [r for r in results if r['source'].startswith('sqlite_decision')]

print(f"Documentação: {len(faiss_results)} chunks")
print(f"Decisões: {len(decision_results)} records")
```

---

## Logging e Debug

### Ver Logs

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('scripts.memory.ensemble_search')

results = ensemble_search("query")
# Vai printar:
# DEBUG: Buscando em SQLite...
# INFO: SQLite decisions: 3 resultados encontrados
# INFO: SQLite learnings: 1 resultados encontrados
# DEBUG: Buscando em FAISS...
# INFO: FAISS: 2 resultados encontrados
# INFO: Deduplicação: 6 → 5 resultados
# INFO: Distribuição de fontes: {'sqlite_decision': 3, 'sqlite_learning': 1, 'faiss': 2}
```

### CLI Testing

```bash
# Via CLI
python scripts/memory/ensemble_search.py "redis cache"

# Com projeto específico
python scripts/memory/ensemble_search.py "ConnectionError" vsl-analysis

# Sem Neo4j
python scripts/memory/ensemble_search.py "FastAPI" --no-graph

# Sem cross-encoder
python scripts/memory/ensemble_search.py "query" --no-cross-encoder
```

---

## Performance

### Tempos Típicos (ms)

| Operação | Tempo | Cache |
|----------|-------|-------|
| SQLite busca | 10-50ms | N/A |
| FAISS busca (cold) | 200-500ms | Memória |
| FAISS busca (warm) | 1-5ms | Cache |
| Neo4j busca | 50-200ms | Memória |
| Consolidação | 5-20ms | N/A |
| Cross-encoder | 100-300ms | Opcional |
| **Total (end-to-end)** | **300-1000ms** | Com cache |

### Otimizações

1. **Desabilitar Neo4j**: `use_graph=False` → ~50% mais rápido
2. **Desabilitar Cross-Encoder**: `enable_cross_encoder=False` → ~30% mais rápido
3. **Limitar resultados**: `limit=5` em vez de 10 → menos processamento
4. **Cache FAISS**: Query cache automático (24h) → 100-1000x mais rápido

---

## Tratamento de Erros

### Fallback Gracioso

```python
# Mesmo que Neo4j esteja offline:
results = ensemble_search("query", use_graph=True)
# Retorna SQLite + FAISS, pula Neo4j sem erro

# Mesmo que sentence-transformers não esteja instalado:
results = ensemble_search("query", enable_cross_encoder=True)
# Aplica cross-encoder se disponível, senão usa score original
```

### Exceções

```python
try:
    results = ensemble_search("query")
except Exception as e:
    logger.error(f"Ensemble search failed: {e}")
    # Sempre retorna algo (lista vazia no pior caso)
    results = []
```

---

## Integração com Sistema

### Em brain ask

```python
# scripts/cli/memory.py ou similar
def ask(query: str, project: str = None):
    from scripts.memory import ensemble_search

    results = ensemble_search(
        query,
        project=project,
        limit=10
    )

    # Formata para exibição
    for r in results:
        print(f"[{r['relevance_score']:.1%}] {r['source']}: {r['content'][:80]}...")
```

### Em brain job create

```python
# Salva query decomposition junto com job
job_data = {
    "prompt": "...",
    "brain_queries": [
        {"query": "redis", "source": "ensemble_search", "project": "vsl-analysis"}
    ]
}
```

---

## Componentes Relacionados

### Entradas de ensemble_search

- **SQLite**: `scripts/memory/decisions.py`, `scripts/memory/learnings.py`
- **FAISS**: `scripts/faiss_rag.py`
- **Neo4j**: `scripts/memory/neo4j_wrapper.py` (fallback se não existir)

### Ranking

- `scripts/memory/scoring.py`: `rank_results()` - Score composto
  - Especificidade (0.25x): Projeto exato vs geral
  - Recência (0.20x): Últimas semanas
  - Confiança (0.25x): confidence_score
  - Uso (0.15x): access_count
  - Validação (0.15x): maturity_status

### Cross-Encoder (Opcional)

- `sentence-transformers`: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Reranking de pares query-documento

---

## Testes

### Rodar Testes

```bash
# Todos os testes (exceto integration)
python -m pytest scripts/memory/test_ensemble_search.py -k "not integration" -v

# Teste específico
python -m pytest scripts/memory/test_ensemble_search.py::test_ensemble_search_consolidates_all_sources -v

# Com coverage
python -m pytest scripts/memory/test_ensemble_search.py --cov=scripts.memory.ensemble_search
```

### Cobertura de Testes

- ✅ SearchResult dataclass
- ✅ _search_sqlite (decisions + learnings)
- ✅ _search_faiss
- ✅ _search_neo4j (com fallback)
- ✅ Consolidação e deduplicação
- ✅ Ranking por relevância
- ✅ Cross-encoder reranking (com fallback)
- ✅ ensemble_search() função principal
- ✅ Error handling

---

## Troubleshooting

### Nenhum resultado encontrado

```python
# Verificar cada fonte:

# 1. SQLite vazio?
from scripts.memory import get_decisions, get_all_learnings
decisions = get_decisions(limit=1)
learnings = get_all_learnings(limit=1)

# 2. FAISS não indexado?
from scripts.faiss_rag import get_stats
stats = get_stats()
print(f"FAISS chunks: {stats.get('chunks', 0)}")

# 3. Neo4j offline? (esperado - fallback automático)
```

### Resultados não relevantes

```python
# Aumentar limite para mais contexto:
results = ensemble_search(query, limit=20)

# Especificar projeto:
results = ensemble_search(query, project="specific-project")

# Usar cross-encoder:
results = ensemble_search(query, enable_cross_encoder=True)
```

### Performance lenta

```python
# Desabilitar Neo4j:
results = ensemble_search(query, use_graph=False)

# Desabilitar cross-encoder:
results = ensemble_search(query, enable_cross_encoder=False)

# Limitar resultados:
results = ensemble_search(query, limit=5)
```

---

## Próximos Passos

### V2 Possível

- [ ] Busca com fuzzy matching (antes de pattern matching)
- [ ] Semantic similarity para SQLite (comparar embeddings)
- [ ] Cache distribuído (Redis em vez de in-memory)
- [ ] Query expansion (adicionar sinônimos)
- [ ] Personalized ranking (por usuário/projeto)
