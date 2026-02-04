# Claude Brain - Arquitetura Completa

> **Knowledge Graph + Agentic RAG System**
> Ultima atualizacao: Fevereiro 2026
> Versao: 1.2.0

## Estatisticas Atuais

| Componente | Quantidade |
|------------|------------|
| Decisoes arquiteturais | 112+ |
| Learnings (erros/solucoes) | 45+ |
| Memorias gerais | 28+ |
| Documentos indexados | 309+ |
| Chunks RAG (FAISS) | 3421+ |
| Entidades no grafo (Neo4j) | 150+ |
| Relacoes no grafo | 280+ |
| Testes | 206+ |
| Cobertura | 48% |

## Visao Geral - 3 Camadas

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USUARIO FINAL                                   │
│  (Claude Code, API REST, CLI Brain)                                          │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
        ▼                                 ▼
    ┌──────────────┐          ┌──────────────────────┐
    │ CLI Brain    │          │  Query Decomposer    │
    │ (python)     │          │  (nvidia/nemotron)   │
    └──────────────┘          └──────────┬───────────┘
        │                                 │
        │                    (decompõe em 3-4 sub-queries)
        │                                 │
        └────────────────┬────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │      ENSEMBLE SEARCH (3 Backends)          │
        ├──────────────┬─────────────┬───────────────┤
        │              │             │               │
        ▼              ▼             ▼               ▼
    ┌────────┐   ┌────────┐   ┌─────────┐   ┌──────────────┐
    │ SQLite │   │ FAISS  │   │ Neo4j   │   │ Redis Cache  │
    │ BrainDB│   │ Vectors│   │ Graph   │   │  (opcional)  │
    │        │   │        │   │ +Rank   │   │ Hit: 60%     │
    │sqlite3 │   │all-    │   │ Cypher  │   │              │
    │        │   │miniLM  │   │ Queries │   │              │
    └────────┘   └────────┘   └─────────┘   └──────────────┘
        │            │            │               │
        └────────────┴────────────┴───────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │    CONSOLIDACAO + RANKING INTELIGENTE      │
        │  (5 fatores de score)                      │
        │  • Especificidade do projeto (0.25)        │
        │  • Recencia (0.20)                         │
        │  • Confianca original (0.25)               │
        │  • Frequencia de uso (0.15)                │
        │  • Status de validacao (0.15)              │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │      TOP 10 RESULTADOS ORDENADOS           │
        │  (com metadata completa e timestamps)      │
        └────────────────────────────────────────────┘
```

## 1. Camada 1: SQLite + DiskCache (Source of Truth)

### Objetivo
Armazenar estruturado: decisions, learnings, memories, workflows com metadados completos.

### Componentes

```
/root/claude-brain/
├── memory/
│   ├── brain.db                # SQLite principal (decisoes, learnings, memorias)
│   └── cache/                  # DiskCache para RAG chunks
├── rag/
│   ├── faiss_index/            # Indice FAISS para busca vetorial
│   │   ├── index.faiss         # Vetores de embeddings (binary)
│   │   └── metadata.json       # Metadados dos chunks
│   ├── index.db                # SQLite com chunks e metadados
│   └── chunks/                 # JSON chunks salvos
├── neo4j_data/                 # Neo4j Community Edition
│   ├── databases/              # Graph database files
│   └── logs/                   # Neo4j logs
├── scripts/memory/
│   ├── base.py                 # Base classes + logging
│   ├── sql_brain.py            # SQLite operations
│   ├── faiss_brain.py          # Vector search (deprecated)
│   ├── neo4j_wrapper.py        # Graph database wrapper
│   ├── ensemble_search.py      # Multi-source search
│   ├── query_decomposer.py     # LLM query decomposition
│   ├── ranking.py              # 5-factor scoring
│   └── jobs.py                 # Job queue system
├── api/                        # FastAPI REST endpoints
├── tests/                      # 206+ testes automatizados
└── docker-compose.yml          # Full stack definition
```

### Schema SQLite

```sql
-- Decisions (estratégicas)
CREATE TABLE decisions (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    project TEXT,
    reasoning TEXT,
    confidence REAL,
    maturity_status TEXT,  -- hypothesis, confirmed, contradicted
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(title, project)
);

-- Learnings (erros/soluções)
CREATE TABLE learnings (
    id INTEGER PRIMARY KEY,
    error_name TEXT NOT NULL,
    solution TEXT NOT NULL,
    project TEXT,
    confidence REAL,
    created_at TIMESTAMP
);

-- Memories (conhecimento geral)
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    category TEXT,
    relevance_score REAL,
    created_at TIMESTAMP
);

-- Workflows (sessões longas)
CREATE TABLE workflows (
    id INTEGER PRIMARY KEY,
    name TEXT,
    project TEXT,
    todos TEXT,  -- JSON array
    insights TEXT,  -- JSON array
    files TEXT,  -- JSON array
    status TEXT,  -- active, completed, archived
    created_at TIMESTAMP
);
```

### Performance (Camada 1)

| Operação | Tempo | Notes |
|----------|-------|-------|
| Busca exata (SQL WHERE) | <10ms | Indexed columns |
| Busca FTS (full-text) | <50ms | SQLite built-in |
| Listar 100 registros | <20ms | Com LIMIT |
| Insert/Update | <5ms | Commit imediato |

---

## 2. Camada 2: FAISS (Busca Semântica)

### Objetivo
Busca por similaridade vetorial usando embeddings (all-MiniLM-L6-v2, 384 dims).

### Stack

| Componente | Detalhe | Notas |
|------------|---------|-------|
| Embeddings | all-MiniLM-L6-v2 | 384 dimensões, open-source |
| Index Type | **IVF-PQ** | Inverse Index + Product Quantization |
| Vector DB | **FAISS** | Meta AI, estável em Docker |
| Metadata | SQLite index.db | Links FAISS ↔ SQLite |
| Cache | DiskCache | Chunks pré-processados |

### Uso (ensemble_search.py)

```python
from scripts.memory.ensemble_search import ensemble_search

# Busca paralela: SQLite + FAISS + Neo4j
results = ensemble_search(
    "Como resolver erro de conexão Redis",
    project="vsl-analysis",
    limit=10
)

# Cada resultado tem:
# - id: unique identifier
# - content: texto principal
# - source: 'sqlite_decision' | 'sqlite_learning' | 'faiss' | 'neo4j'
# - relevance_score: 0.0-1.0 (score final consolidado)
# - metadata: dados específicos da fonte
# - timestamp: ISO format
```

### Performance (Camada 2)

| Operação | Tempo | Notes |
|----------|-------|-------|
| Busca semântica (FAISS) | <100ms | Sobre 3400 chunks |
| Embedding novo texto | <50ms | all-MiniLM on CPU |
| Reindex completo | <5s | 100 registros |

---

## 3. Camada 3: Neo4j (Knowledge Graph)

### Objetivo
Modelar relacionamentos conceituais: Project → Technology → Pattern → Solution.

### Modelo de Dados

```cypher
-- Nós (Labels)
(Decision {title, confidence, project})
(Learning {error, solution, category})
(Memory {content, category})
(Project {name, status})
(Technology {name, version})
(Pattern {name, type})

-- Relações (tipos)
RELATES_TO     -- Conexão genérica entre conceitos
VALIDATES      -- Learning confirma Decision
CONTRADICTS    -- Learning contradiz Decision
USES           -- Project usa Technology
SOLVED_BY      -- Pattern é resolvido por Learning
DEPENDS_ON     -- Dependência entre conceitos
HAS_INSIGHT    -- Knowledge tem insight específico
```

### Queries Úteis

```cypher
-- PageRank: conceitos mais importantes
CALL algo.pageRank.stream("Decision|Learning", "RELATES_TO")
YIELD nodeId, score
RETURN algo.getNodeById(nodeId) AS node, score
ORDER BY score DESC LIMIT 10;

-- Caminhos (2-3 hops): de erro para solução
MATCH path = shortestPath(
    (error:Learning) -[*..3]-> (solution:Learning)
)
WHERE error.error CONTAINS "ConnectionError"
RETURN path;

-- Conceitos relacionados (grafo local)
MATCH (decision:Decision)-[r]-(related)
WHERE decision.project = "vsl-analysis"
RETURN decision, r, related;

-- Sincronização automática
MATCH (d:Decision)
WHERE NOT EXISTS(d.synced_to_sqlite)
AND d.confidence > 0.8
RETURN d;  -- Voltar para SQLite
```

### Sincronização SQLite → Neo4j

**Automática via scripts/memory/base.py:**

```python
class Neo4jSync:
    def sync_decisions(self):
        """Sincroniza decisions de SQLite para Neo4j"""
        # 1. Buscar de SQLite
        decisions = self.db.query("SELECT * FROM decisions")

        # 2. Criar nós em Neo4j
        for d in decisions:
            self.graph.add_node(
                "Decision",
                node_id=d["id"],
                properties={
                    "title": d["title"],
                    "project": d["project"],
                    "confidence": d["confidence"]
                }
            )

        # 3. Criar relações baseado em tipo
        # Se a decision valida/contradiz learnings:
        self.graph.add_relation(decision_id, learning_id, "VALIDATES")
```

### Performance (Camada 3)

| Operação | Tempo | Notes |
|----------|-------|-------|
| Criar nó | <5ms | One Cypher statement |
| Busca PageRank | <100ms | Sobre 150 nós |
| Shortest path | <50ms | Até 3 hops |
| Sync 100 records | <2s | Batch operations |

---

## 4. Query Decomposer - LLM Intelligence

### Objetivo
Quebrar queries complexas em 3-4 sub-queries otimizadas.

### Fluxo

```
Usuario: "Como resolver erro de conexão Redis no vsl-analysis"
          ↓
Query Decomposer (OpenRouter API)
   • Provider: nvidia/nemotron-nano-9b:free
   • Fallback: google/gemini-2.5-flash
   • Confidence: 85-95%
          ↓
Sub-queries geradas:
  1. [CONCEPTUAL] "Redis connection troubleshooting"
  2. [TECHNICAL] "systemctl redis-server error handling"
  3. [PROJECT_SPECIFIC] "vsl-analysis Redis configuration"
          ↓
Cada sub-query → Ensemble Search paralelo
          ↓
Consolidação de resultados com cross-encoder reranking
```

### Implementação

```python
from scripts.memory.query_decomposer import decompose_query

result = decompose_query(
    "Como resolver erro de conexão Redis no vsl-analysis"
)

print(f"Provider: {result.provider}")
print(f"Confiança: {result.decomposition_confidence:.0%}")

for sq in result.sub_queries:
    print(f"  [{sq.type}] {sq.query}")
    print(f"    Confiança: {sq.confidence:.0%}")
```

### Performance (Query Decomposer)

| Operação | Tempo | Notes |
|----------|-------|-------|
| Decomposição OpenRouter | ~500ms | Free tier API |
| Decomposição Anthropic | ~800ms | Fallback, 200k context |
| Processamento 3 sub-queries | ~1.5s | Paralelo ensemble |
| Cache hit | <1ms | Lru_cache 100 |

---

## 5. Ensemble Search - Consolidação

### Algoritmo

```
1. PARALELO: executar 3 buscas
   ├─ SQLite (FTS + WHERE)
   ├─ FAISS (embedding similarity)
   └─ Neo4j (Cypher + PageRank)

2. DEDUPLICACAO: remover duplicatas (id)

3. RANKING por 5 fatores:
   score = (
       especificidade_projeto * 0.25 +
       recencia * 0.20 +
       confianca_original * 0.25 +
       frequencia_uso * 0.15 +
       status_validacao * 0.15
   )

4. TOP 10: retornar top N resultados ordenados

5. (OPCIONAL) Cross-encoder reranking:
   - Usar sentence-transformers cross-encoder
   - Re-order top 10 por relevancia final
```

### Resultado Consolidado

```json
{
  "query": "redis cache",
  "project": "vsl-analysis",
  "timestamp": "2026-02-04T10:00:00Z",
  "execution_time_ms": 1234,
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
        "usage_count": 23
      },
      "timestamp": "2025-11-15T09:30:00Z"
    },
    ...10 results
  ]
}
```

## 2. Sistema de Hooks Inteligentes

### Hooks Disponíveis no Claude Code

```
~/.claude/hooks/
├── pre-tool-use/          # Antes de executar ferramenta
├── post-tool-use/         # Depois de executar ferramenta
├── pre-message/           # Antes de responder
├── post-message/          # Depois de responder
├── on-error/              # Quando ocorre erro
└── on-session-start/      # Início de sessão
```

### Hooks Recomendados

1. **context-loader** - Carrega contexto relevante automaticamente
2. **memory-saver** - Salva decisões importantes
3. **project-detector** - Detecta projeto e carrega CLAUDE.md específico
4. **error-learner** - Aprende com erros para não repetir

## 3. Knowledge Graph

### Estrutura

```json
{
  "nodes": [
    {"id": "vsl-analysis", "type": "project", "props": {"status": "active"}},
    {"id": "pytorch", "type": "technology", "props": {"version": "2.x"}},
    {"id": "user-preference-gpu", "type": "preference", "props": {"value": "sempre usar GPU"}}
  ],
  "edges": [
    {"from": "vsl-analysis", "to": "pytorch", "relation": "uses"},
    {"from": "vsl-analysis", "to": "user-preference-gpu", "relation": "applies"}
  ]
}
```

### Queries Úteis

- "Quais tecnologias o projeto X usa?"
- "Quais preferências se aplicam a projetos Python?"
- "Qual foi a última decisão sobre deploy?"

## 4. CLAUDE.md Otimizado

### Estrutura Hierárquica

```
~/.claude/CLAUDE.md           # Global (todas as sessões)
~/projeto/CLAUDE.md           # Projeto específico
~/projeto/feature/CLAUDE.md   # Feature específica (se necessário)
```

### Template Otimizado

```markdown
# CLAUDE.md

## Identidade
[Quem sou eu neste contexto]

## Preferências Absolutas
[Regras que NUNCA devem ser quebradas]

## Contexto Atual
[O que está acontecendo agora - atualizado por hooks]

## Memória de Curto Prazo
[Últimas decisões/ações - rotacionado automaticamente]

## Atalhos
[Comandos frequentes, snippets]

## Anti-Padrões
[O que NÃO fazer - aprendido de erros]
```

## 5. Sistema de Compressão de Contexto

### Estratégias

1. **Summarização Progressiva**
   - Mensagens > 10 turnos: resumir em 1 parágrafo
   - Mensagens > 50 turnos: manter apenas decisões-chave

2. **Retrieval Seletivo**
   - Buscar apenas contexto relevante para a tarefa atual
   - Usar embeddings para similaridade semântica

3. **Caching Inteligente**
   - Cache de arquivos frequentemente lidos
   - Cache de resultados de comandos estáveis

## 6. Implementacao - Status Atual

### Fase 1: Memoria Basica - CONCLUIDO
- [x] SQLite para memoria (brain.db)
- [x] CLI unificado (brain_cli.py)
- [x] CLAUDE.md integrado

### Fase 2: RAG Local - CONCLUIDO
- [x] FAISS para busca vetorial
- [x] Pipeline de indexacao (index_file, index_directory)
- [x] Busca semantica (semantic_search)

### Fase 3: Knowledge Graph - CONCLUIDO
- [x] Schema de entidades (nodes.json)
- [x] Relacoes (edges.json)
- [x] Queries via CLI (brain graph, brain entity)

### Fase 4: Automacao - EM PROGRESSO
- [x] Auto-indexer (auto_indexer.py)
- [ ] Limpeza de memoria antiga
- [ ] Backup automatico

### Fase 5: Maturacao - CONCLUIDO
- [x] Sistema de confianca (hypothesis -> confirmed)
- [x] Contradicao e supersede
- [x] Metricas de uso

## 7. Metricas de Sucesso

| Metrica | Antes | Objetivo | Atual |
|---------|-------|----------|-------|
| Contexto perdido entre sessoes | 100% | < 10% | ~5% |
| Repeticao de perguntas | Frequente | Raro | Raro |
| Erros repetidos | Comum | Aprendido | 12 learnings |
| Tempo para entender projeto | Alto | Baixo | Imediato |

## 8. Comandos Principais

```bash
# Memoria
brain remember "texto"              # Salva memoria geral
brain decide "decisao" -p projeto   # Salva decisao arquitetural
brain learn "erro" -s "solucao"     # Salva aprendizado

# Busca
brain ask "duvida"                  # Consulta inteligente
brain search "query"                # Busca semantica
brain solve "erro"                  # Busca solucao

# Maturacao
brain hypotheses                    # Lista hipoteses
brain confirm decisions 15          # Confirma decisao
brain contradict learnings 3        # Marca como incorreto
```

## 9. Arquivos Principais

| Arquivo | Tamanho | Descricao |
|---------|---------|-----------|
| scripts/brain_cli.py | 38KB | CLI principal com 30+ comandos |
| scripts/memory_store.py | 44KB | Camada de persistencia SQLite |
| scripts/faiss_rag.py | 22KB | Motor de busca FAISS |
| memory/brain.db | ~1MB | Banco de dados principal |
| rag/faiss_index/ | ~10MB | Indice vetorial |
