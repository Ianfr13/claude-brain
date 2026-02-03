# Query Decomposer - Documentação Técnica

## Visão Geral

O **Query Decomposer** é um sistema de decomposição semântica de queries que quebra queries complexas em sub-queries otimizadas para busca RAG (Retrieval-Augmented Generation).

```
Query Complexa
     ↓
    [Decomposer]
     ↓
Sub-queries Otimizadas
```

## Arquitetura

### Componentes Principais

```
QueryDecomposer (Orquestrador)
├── OpenRouterDecomposer (Preferred)
│   └── OpenRouter API (Llama 3.1, auto-routing)
│
└── AnthropicDecomposer (Fallback)
    └── Claude Haiku 3.5 (200k context)
```

### Fluxo de Execução

```
1. decompose_query(query)
   ↓
2. QueryDecomposer.decompose()
   ├─→ Tentativa 1: OpenRouter
   │   ├─ Se sucesso → Retorna resultado com provider="openrouter"
   │   └─ Se falha → Pula para tentativa 2
   │
   ├─→ Tentativa 2: Anthropic (Fallback)
   │   ├─ Se sucesso → Retorna resultado com provider="anthropic"
   │   └─ Se falha → Retorna erro
   │
   └─→ DecompositionResult estruturado
```

## Instalação & Setup

### Dependências

Todas as dependências já estão no `requirements.txt`:

```bash
pip install -r requirements.txt
```

Pacotes necessários:
- `requests>=2.31.0` (OpenRouter API)
- `anthropic>=0.28.0` (Claude via Anthropic)

### Configuração de API Keys

```bash
# OpenRouter (preferido)
export OPENROUTER_API_KEY="sk_or_..."

# Anthropic (fallback)
export ANTHROPIC_API_KEY="sk_ant_..."
```

## Uso Básico

### 1. Função de Conveniência

```python
from scripts.memory import decompose_query

result = decompose_query("Como implementar cache Redis com TTL?")

print(f"Provider: {result.provider}")
print(f"Confiança: {result.decomposition_confidence:.0%}")

for sq in result.sub_queries:
    print(f"  • [{sq.type}] {sq.query} (conf: {sq.confidence:.0%})")
```

**Output:**
```
Provider: anthropic
Confiança: 87%
  • [semantic] Como implementar cache? (conf: 95%)
  • [entity] Redis Python client (conf: 88%)
  • [temporal] TTL 24 horas (conf: 99%)
```

### 2. Controle Direto

```python
from scripts.memory import QueryDecomposer

decomposer = QueryDecomposer()

# Check disponibilidade
print(f"OpenRouter: {decomposer.openrouter.available}")
print(f"Anthropic: {decomposer.anthropic.available}")

# Decomposição
result = decomposer.decompose("sua query")
```

### 3. Integração com RAG

```python
from scripts.memory import decompose_query

# Expandir busca
result = decompose_query("query complexa")

# Usar sub-queries para busca paralela
for sq in result.sub_queries:
    if sq.confidence > 0.7:  # Filtrar por confiança
        rag_results = rag.search(sq.query, weight=sq.weight)
        consolidate_results(rag_results)
```

## Data Structures

### DecompositionResult

```python
@dataclass
class DecompositionResult:
    original_query: str           # Query original
    sub_queries: List[SubQuery]   # Sub-queries geradas
    decomposition_confidence: float  # Confiança geral (0.0-1.0)
    provider: str                 # "openrouter" ou "anthropic"
    model_used: str               # Nome do modelo
    timestamp: str                # ISO 8601
    processing_time_ms: float     # Tempo de processamento
    error: Optional[str]          # Erro se houver
```

### SubQuery

```python
@dataclass
class SubQuery:
    query: str                    # Sub-query text
    type: str                     # "semantic" | "entity" | "temporal" | "relational"
    confidence: float             # Confiança (0.0-1.0)
    weight: float                 # Importância relativa
    tags: List[str]               # Categorização
```

## Tipos de Sub-queries

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| **semantic** | Conceitos e semântica | "Como implementar cache" |
| **entity** | Entidades nomeadas | "Redis", "FastAPI", "Python" |
| **temporal** | Informações de tempo | "24 horas", "TTL", "segundo" |
| **relational** | Relações entre conceitos | "cache para", "usado com" |

## Integração Avançada

### Search Expansion

```python
from scripts.memory.query_decomposer_integration import expand_search

queries = expand_search(
    "Como usar Redis?",
    min_confidence=0.7,
    max_sub_queries=5
)
# ['Como usar Redis?', 'Redis cache', 'Python Redis client', ...]
```

### Batch Processing

```python
from scripts.memory.query_decomposer_integration import batch_decompose

queries = ["Query 1", "Query 2", "Query 3"]
results = batch_decompose(queries, save_to_db=True)
```

### Ranking de Sub-queries

```python
from scripts.memory.query_decomposer_integration import rank_sub_queries

result = decompose_query("query")
ranked = rank_sub_queries(result)

for sq in ranked:
    print(f"{sq.query} (score: {sq.weight})")
```

### Caching

```python
from scripts.memory.query_decomposer_integration import DecompositionCache

cache = DecompositionCache(max_size=100)

# Com cache automático
result = cache.decompose_cached("Query 1")

# Segunda call reutiliza cache
result = cache.decompose_cached("Query 1")

print(cache.stats())
# {'hits': 1, 'misses': 1, 'hit_rate': '50.0%'}
```

### Analytics

```python
from scripts.memory.query_decomposer_integration import analyze_decompositions

results = [result1, result2, result3, ...]
analytics = analyze_decompositions(results)

print(analytics)
# {
#   'total_queries': 3,
#   'avg_sub_queries_per_query': 3.2,
#   'providers': {'anthropic': 2, 'openrouter': 1},
#   'success_rate': '100%',
#   ...
# }
```

## Logging

### Níveis de Log

```
DEBUG   - Conteúdo bruto de respostas, parsing JSON
INFO    - Decomposição iniciada, sucesso, provider usado
WARNING - Provider indisponível, fallback ativado
ERROR   - Falha em ambos providers, JSON inválido
```

### Capturar Logs

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('scripts.memory.query_decomposer')

# Agora todos os logs do decomposer aparecem
```

### Exemplo de Output

```
2026-02-03 20:59:48 [scripts.memory.query_decomposer] INFO: OpenRouter disponível: True
2026-02-03 20:59:48 [scripts.memory.query_decomposer] INFO: Iniciando decomposição: 'Como implementar cache com TTL?'
2026-02-03 20:59:48 [scripts.memory.query_decomposer] INFO: Tentativa 1: OpenRouter
2026-02-03 20:59:48 [scripts.memory.query_decomposer] INFO: Enviando para OpenRouter: modelo=meta-llama/llama-3.1-8b-instruct
2026-02-03 20:59:49 [scripts.memory.query_decomposer] INFO: OpenRouter respondeu com status 200
2026-02-03 20:59:49 [scripts.memory.query_decomposer] INFO: Decomposição bem-sucedida: 3 sub-queries
2026-02-03 20:59:49 [scripts.memory.query_decomposer] INFO: Sucesso com OpenRouter
```

## Tratamento de Erros

### Cenários Tratados

1. **API Keys não configuradas**
   - Provider marcado como indisponível
   - Fallback automático

2. **Timeout de API**
   - Log de warning
   - Tenta próximo provider

3. **JSON inválido**
   - Tenta extrair JSON de markdown
   - Se falhar, pula provider

4. **Ambos providers falharem**
   - Retorna `DecompositionResult` com `error` preenchido
   - `decomposition_confidence` = 0.0

### Exemplo

```python
result = decompose_query("query")

if result.error:
    print(f"Decomposição falhou: {result.error}")
    # Fallback: usar query original
    queries = [result.original_query]
else:
    queries = [sq.query for sq in result.sub_queries]
```

## Performance

### Benchmarks

| Cenário | Tempo | Provider |
|---------|-------|----------|
| Query simples | ~500ms | OpenRouter |
| Query complexa | ~1200ms | OpenRouter |
| Fallback (Anthropic) | ~800ms | Anthropic |
| Cache hit | ~1ms | Memory |

### Otimizações

1. **Caching de decomposições**
   ```python
   cache = DecompositionCache(max_size=100)
   result = cache.decompose_cached("Query frequente")
   ```

2. **Batch processing**
   ```python
   results = batch_decompose(queries)  # Mais eficiente
   ```

3. **Confidence filtering**
   ```python
   filtered = [sq for sq in result.sub_queries if sq.confidence > 0.8]
   ```

## Testes

### Rodar Test Suite

```bash
python test_query_decomposer.py
```

**Output esperado:**
```
QUERY DECOMPOSER - TEST SUITE
======================================================================
TEST 1: SubQuery Structure
✓ SubQuery tests passed
TEST 2: DecompositionResult Structure
✓ DecompositionResult tests passed
...
======================================================================
TEST SUMMARY
Passed: 7/7
Failed: 0/7
```

### Rodar Demo

```bash
python demo_query_decomposer.py
```

## API Keys Recomendadas

### OpenRouter (Preferido)

```
Vantagens:
✓ Múltiplos modelos (Llama, Claude, Mistral, etc)
✓ Auto-routing inteligente
✓ Mais rápido para queries simples
✓ Suporte a fallback automático

URL: https://openrouter.io
Documentação: https://openrouter.io/docs/api/keys
```

### Anthropic (Fallback)

```
Vantagens:
✓ Claude Haiku (rápido e barato)
✓ 200k context window
✓ Excelente qualidade de decomposição
✓ Mais confiável

URL: https://console.anthropic.com
Documentação: https://docs.anthropic.com
```

## Exemplos Práticos

### 1. Integração com RAG

```python
from scripts.memory import decompose_query

def search_with_decomposition(query: str, rag_engine):
    # Decomposição
    result = decompose_query(query)

    if result.error:
        # Fallback
        return rag_engine.search(query)

    # Busca paralela
    all_results = []
    for sq in result.sub_queries:
        if sq.confidence > 0.7:
            results = rag_engine.search(sq.query, weight=sq.weight)
            all_results.extend(results)

    return consolidate_results(all_results)
```

### 2. Análise de Padrões

```python
from scripts.memory.query_decomposer_integration import batch_decompose, analyze_decompositions

# Processar muitas queries
queries = load_user_queries()
results = batch_decompose(queries)

# Análise
analytics = analyze_decompositions(results)

print(f"Tipos de sub-queries mais comuns:")
for type_name, count in analytics['sub_query_types'].items():
    print(f"  {type_name}: {count}")
```

### 3. Quality Assurance

```python
from scripts.memory import decompose_query

def validate_decomposition(query: str) -> bool:
    result = decompose_query(query)

    # Validações
    if result.error:
        return False

    if result.decomposition_confidence < 0.7:
        return False

    if len(result.sub_queries) == 0:
        return False

    # Confiança mínima por sub-query
    min_confidence = all(sq.confidence > 0.5 for sq in result.sub_queries)

    return min_confidence
```

## Troubleshooting

### Problema: "OPENROUTER_API_KEY não configurada"

**Solução:**
```bash
export OPENROUTER_API_KEY="sk_or_your_key_here"
python -c "from scripts.memory import decompose_query; print(decompose_query('test'))"
```

### Problema: "JSON inválido de OpenRouter"

**Causa:** Modelo retornando JSON com markdown

**Solução:**
- Sistema tenta automaticamente extrair JSON
- Se ainda falhar, usa fallback Anthropic
- Check logs com `level=DEBUG`

### Problema: Timeout em queries longas

**Solução:**
```python
# Aumentar timeout
result = openrouter.decompose(query, timeout=60)
```

### Problema: Sub-queries com baixa confiança

**Solução:**
```python
# Filtrar por confiança
high_confidence = [
    sq for sq in result.sub_queries
    if sq.confidence > 0.85
]
```

## Roadmap

- [x] OpenRouter integration
- [x] Anthropic fallback
- [x] JSON serialization
- [x] Logging completo
- [x] Caching
- [x] Batch processing
- [ ] Database persistence
- [ ] Metrics/observability
- [ ] GraphQL API
- [ ] Distributed decomposition

## Contribuindo

Para adicionar suporte a novo provider:

1. Criar classe `XxxDecomposer` com método `decompose()`
2. Adicionar ao `QueryDecomposer.__init__()`
3. Testar com `test_query_decomposer.py`

## Licença

Claude Brain - MIT License

## Contato & Suporte

- Issues: GitHub Issues
- Docs: QUERY_DECOMPOSER_README.md
- Logs: Verificar output de logging
