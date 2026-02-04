# Claude Brain - CLI Completa

**brain - Knowledge Graph + Agentic RAG Command-Line Interface**

Referência completa de todos os comandos da CLI brain.

## Instalação

```bash
# Adicionar ao PATH
export PATH="/root/claude-brain/scripts:$PATH"

# Ou usar diretamente
python /root/claude-brain/scripts/brain_cli.py [comando] [argumentos]
```

## Sumário de Comandos

| Comando | Uso |
|---------|-----|
| [brain ask](#ask) | Busca inteligente com Ensemble Search |
| [brain agentic-ask](#agentic-ask) | Busca com LLM Query Decomposer |
| [brain decide](#decide) | Salvar decisão arquitetural |
| [brain learn](#learn) | Salvar erro + solução |
| [brain remember](#remember) | Salvar memória geral |
| [brain confirm](#confirm) | Confirmar decisão/learning |
| [brain contradict](#contradict) | Marcar como incorreto |
| [brain workflow](#workflow) | Gerenciar sessões longas |
| [brain job](#job) | Sistema de fila de jobs |
| [brain graph](#graph) | Operações Knowledge Graph |
| [brain stats](#stats) | Ver estatísticas |

---

## brain ask

Busca simples com 3 backends (SQLite + FAISS + Neo4j).

### Sintaxe

```bash
brain ask <query> [-p PROJECT] [--limit N] [--no-graph] [--no-cross-encoder]
```

### Exemplos

```bash
# Busca simples
brain ask "redis cache"

# Com projeto
brain ask "como resolver ConnectionError" -p vsl-analysis

# Mais resultados
brain ask "FastAPI" --limit 20

# Sem Neo4j (mais rápido)
brain ask "python async" --no-graph

# Sem reranking (mais rápido)
brain ask "query" --no-cross-encoder
```

### Output

```
BUSCA: redis cache
PROJETO: vsl-analysis
TEMPO: 245ms

[1] ★ 0.92 | SQLite Decision
    Use Redis with TTL 24h for performance
    Projeto: vsl-analysis | Confiança: 90% | Uso: 23x

[2] ★ 0.87 | FAISS Search
    Redis provides 50x throughput improvement
    Semelhança: 0.87 | Timestamp: 2025-11-15

[3] ★ 0.81 | Neo4j Graph
    → Redis ← Performance ← Optimization
    PageRank: 0.78 | Conexões: 15
```

---

## brain agentic-ask

Busca inteligente com LLM Query Decomposer.

### Sintaxe

```bash
brain agentic-ask <query> [-p PROJECT] [--depth N] [--timeout SEC]
```

### Exemplos

```bash
# Pergunta em linguagem natural
brain agentic-ask "Como resolver erro de conexão Redis no vsl-analysis?"

# Com profundidade customizada
brain agentic-ask "Melhor prática para cache" --depth 5

# Com timeout
brain agentic-ask "Query complexa" --timeout 15
```

### Output

```
QUERY DECOMPOSER
Modelo: nvidia/nemotron-nano (OpenRouter)
Confiança: 88%

SUB-QUERIES:
  [1] CONCEPTUAL: Redis connection troubleshooting
      Confiança: 92%
  [2] TECHNICAL: systemctl redis-server error handling
      Confiança: 85%
  [3] PROJECT_SPECIFIC: vsl-analysis Redis configuration
      Confiança: 78%

ENSEMBLE RESULTS:
  [1] ★ 0.95 | ConnectionError: Verify systemctl status redis-server
      Categoria: connectivity | Tipo: troubleshooting
  [2] ★ 0.89 | Redis config: requirepass in /etc/redis/redis.conf
      Categoria: configuration
```

---

## brain decide

Salvar decisão arquitetural.

### Sintaxe

```bash
brain decide <titulo> -p PROJECT [-r REASONING] [--confidence N] [--status STATUS]
```

### Exemplos

```bash
# Decisão simples
brain decide "Usar Redis para cache" -p vsl-analysis

# Com reasoning
brain decide "Use FastAPI instead of Flask" \
  -p vsl-analysis \
  -r "Suporta async/await, better performance"

# Com confiança customizada
brain decide "Migrate to Neo4j" \
  -p claude-brain \
  -r "Graphql queries 10x mais rápidas" \
  --confidence 0.85

# Com status
brain decide "Use Docker for deployment" \
  -p vsl-analysis \
  --status confirmed \
  --confidence 0.95
```

### Output

```
DECISÃO CRIADA
ID: 45
Título: Usar Redis para cache
Projeto: vsl-analysis
Status: hypothesis
Confiança: 90%
Criado: 2026-02-04 10:00:00

Próximas ações:
  → Teste em produção
  → brain confirm decisions 45
```

---

## brain learn

Salvar erro + solução.

### Sintaxe

```bash
brain learn <erro> -s <solucao> [-p PROJECT] [--category CAT]
```

### Exemplos

```bash
# Error + Solution
brain learn "ConnectionError: redis-server not running" \
  -s "systemctl restart redis-server"

# Com projeto
brain learn "ImportError: no module named 'neo4j'" \
  -s "pip install neo4j==5.15.0" \
  -p claude-brain

# Com categoria
brain learn "FAISS index out of sync" \
  -s "python scripts/memory/base.py --rebuild-faiss" \
  -p claude-brain \
  --category infrastructure
```

### Output

```
LEARNING CRIADO
ID: 23
Erro: ConnectionError: redis-server not running
Solução: systemctl restart redis-server
Projeto: vsl-analysis
Categoria: infrastructure
Confiança: 95%
Criado: 2026-02-04 10:00:00
```

---

## brain remember

Salvar memória geral (reutilizável).

### Sintaxe

```bash
brain remember <conteudo> [--category CAT] [--relevance SCORE]
```

### Exemplos

```bash
# Memória simples
brain remember "FastAPI suporta async/await"

# Com categoria
brain remember "Redis precisa de pickle para objetos Python" \
  --category technology

# Com relevância
brain remember "Neo4j Community Edition suporta até 10M nós" \
  --category infrastructure \
  --relevance 0.9
```

### Output

```
MEMÓRIA CRIADA
ID: 128
Conteúdo: FastAPI suporta async/await
Categoria: technology
Relevância: 0.8
Criado: 2026-02-04 10:00:00
```

---

## brain confirm

Confirmar decisão/learning como "confirmed".

### Sintaxe

```bash
brain confirm <tipo> <id> [--reasoning REASON]
```

### Exemplos

```bash
# Confirmar decisão
brain confirm decisions 45

# Confirmar com reasoning
brain confirm decisions 45 \
  --reasoning "Testado em produção com 10k req/s"

# Confirmar learning
brain confirm learnings 23 \
  --reasoning "Solução provou 100% efetiva"
```

### Output

```
CONFIRMADO
Tipo: decisions
ID: 45
Status anterior: hypothesis
Status novo: confirmed
Confiança: 90% → 95%
Timestamp: 2026-02-04 10:00:00
```

---

## brain contradict

Marcar decisão/learning como "contradicted".

### Sintaxe

```bash
brain contradict <tipo> <id> [--reason REASON] [--superseded_by ID]
```

### Exemplos

```bash
# Contraditar decisão
brain contradict decisions 42 \
  --reason "Testes mostraram Flask é melhor para este caso"

# Supersedida por outra
brain contradict decisions 10 \
  --superseded_by 45
```

### Output

```
CONTRADITO
Tipo: decisions
ID: 42
Status novo: contradicted
Razão: Testes mostraram Flask é melhor para este caso
Timestamp: 2026-02-04 10:00:00
```

---

## brain workflow

Gerenciar sessões longas com contexto persistente.

### Sintaxe

```bash
brain workflow <acao> <nome> -p PROJECT [opcoes]
```

### Ações

#### brain workflow start

Iniciar nova sessão.

```bash
brain workflow start "Implementar cache Redis" -p vsl-analysis

# Output:
# Sessão iniciada: workflow_001
# Contexto: context.md, todos.md, insights.md
```

#### brain workflow update

Atualizar durante trabalho.

```bash
# Adicionar TODO
brain workflow update --todo "Implementar Redis client"

# Marcar como done
brain workflow update --done 1

# Adicionar insight
brain workflow update --insight "Redis precisa de password em produção"

# Registrar arquivo modificado
brain workflow update --file "api/cache.py"
```

#### brain workflow complete

Finalizar e salvar no brain.

```bash
brain workflow complete \
  --summary "Cache Redis implementado, suporta 50k req/s"

# Output:
# Workflow concluído
# Insights salvos no brain
# Neo4j sincronizado
```

#### brain workflow resume

Recuperar contexto após memory wipe.

```bash
brain workflow resume

# Output:
# Contexto restaurado: workflow_001
# TODOs pendentes: 3
# Insights: 7
```

---

## brain job

Sistema de fila de jobs para sub-tasks distribuídos.

### Sintaxe

```bash
brain job <acao> [opcoes]
```

### Ações

#### brain job create

Criar novo job.

```bash
# Job simples
brain job create \
  --prompt "Implementar cache Redis" \
  --ttl 43200

# Job com skills
brain job create \
  --prompt "Tarefa..." \
  --skills python-pro-skill \
  --skills devops-engineer-skill

# Job distribuído
brain job create \
  --prompt "Validar 5 endpoints" \
  --distributed \
  --subtask "Testar GET /api/users" \
  --subtask "Testar POST /api/users"

# Output:
# Job criado: 52445047-9d82-45d4-850b-8f76054abb68
# TTL: 12h
```

#### brain job get

Obter status do job.

```bash
brain job get 52445047-9d82-45d4-850b-8f76054abb68

# Output:
# Status: running
# Progress: 67%
# Sub-tasks: 3/5 completed
```

#### brain job list

Listar jobs ativos.

```bash
brain job list

# Output:
# [1] job_52445047 | running | 67% | Expires: 2h
# [2] job_abc12345 | completed | 100% | Expires: 10h
```

#### brain job dispatch

Disparar workers para jobs distribuídos.

```bash
brain job dispatch 52445047-9d82-45d4-850b-8f76054abb68

# Output:
# Dispatch completo
# Workers: 5
# Status: running
```

#### brain job consolidate

Consolidar resultados de job distribuído.

```bash
brain job consolidate 52445047-9d82-45d4-850b-8f76054abb68

# Output:
# Resultados consolidados
# Sub-tasks completados: 5/5
# Resultado final: {...}
```

---

## brain graph

Operações no Knowledge Graph (Neo4j).

### Sintaxe

```bash
brain graph <acao> [opcoes]
```

### Ações

#### brain graph stats

Ver estatísticas do grafo.

```bash
brain graph stats

# Output:
# Nós: 150
# Relações: 280
# Última sincronização: 2h atrás
```

#### brain graph sync

Sincronizar SQLite → Neo4j.

```bash
# Sincronização incremental
brain graph sync

# Forçar full sync
brain graph sync --force

# Output:
# Decisions sincronizadas: 112
# Learnings sincronizadas: 45
# Tempo: 2.3s
```

#### brain graph pagerank

Top conceitos por importância.

```bash
brain graph pagerank --limit 10

# Output:
# [1] Use Redis for caching | Score: 0.85 | Conexões: 23
# [2] Redis | Score: 0.78 | Conexões: 15
# [3] Performance optimization | Score: 0.72 | Conexões: 12
```

#### brain graph traverse

Explorar relações de um conceito.

```bash
brain graph traverse "redis"

# Output:
# redis (Technology)
#   ├─ USED_BY → vsl-analysis (Project)
#   ├─ IMPROVES → performance (Pattern)
#   └─ CONFIGURED_IN → /etc/redis/redis.conf
```

#### brain graph path

Encontrar caminho entre dois conceitos.

```bash
brain graph path "ConnectionError" "systemctl restart"

# Output:
# Caminho (2 hops):
# ConnectionError → (SOLUTION) → Redis restart
#               → (RELATES_TO) → systemctl command
```

---

## brain stats

Estatísticas do sistema.

### Sintaxe

```bash
brain stats [--project PROJECT]
```

### Exemplos

```bash
# Stats gerais
brain stats

# Stats por projeto
brain stats -p vsl-analysis
```

### Output

```
ESTATÍSTICAS CLAUDE BRAIN
═══════════════════════════════════════════

CONHECIMENTO
  Decisões: 112
    └─ Confirmadas: 98 (88%)
    └─ Hypotheses: 12 (11%)
    └─ Contraditas: 2 (2%)

  Learnings: 45
    └─ Erros resolvidos: 45
    └─ Categoria top: infrastructure (18)

  Memórias: 28
    └─ Tech knowledge: 12
    └─ Best practices: 10
    └─ Anti-patterns: 6

ÍNDICES
  FAISS Vectors: 3421
    └─ Dimensões: 384 (all-MiniLM)
    └─ Tamanho: ~45MB

  Neo4j Nodes: 150
    └─ Decision: 112
    └─ Learning: 45
    └─ Technology: 25
    └─ Project: 8

  Neo4j Edges: 280
    └─ RELATES_TO: 145
    └─ VALIDATES: 78
    └─ CONTRADICTS: 12
    └─ USES: 45

PERFORMANCE
  Busca média: 245ms
  Cache hit rate: 62%
  Last sync: 2 hours ago

ARMAZENAMENTO
  SQLite: 1.2MB
  FAISS Index: 45MB
  Neo4j: 156MB
  Total: 202MB
```

---

## Flags Globais

Disponíveis em todos os comandos:

```bash
--debug          # Modo verbose com logs detalhados
--quiet          # Modo silencioso (apenas resultado)
--format json    # Output em JSON (default: text)
--help, -h       # Mostrar ajuda
--version, -v    # Mostrar versão
```

---

## Exemplos End-to-End

### 1. Setup Inicial

```bash
# Salvar decisão
brain decide "Use Redis para cache" -p meu-projeto

# Salvar learning
brain learn "ConnectionError ao conectar" \
  -s "systemctl restart redis-server" \
  -p meu-projeto

# Salvar memória geral
brain remember "FastAPI async é 10x mais rápido"

# Ver stats
brain stats
```

### 2. Busca com Decomposição

```bash
# Pergunta complexa
brain agentic-ask "Como otimizar performance de busca no Neo4j?"

# Retorna sub-queries + results consolidados
```

### 3. Workflow Longo

```bash
# Iniciar
brain workflow start "Feature X" -p projeto

# Durante
brain workflow update --todo "Implementar Y"
brain workflow update --insight "Z descoberto"

# Finalizar
brain workflow complete --summary "Feature pronta"

# Próxima sessão
brain workflow resume
```

### 4. Job Distribuído

```bash
# Criar
brain job create \
  --distributed \
  --prompt "Validar 5 endpoints" \
  --subtask "GET /users" \
  --subtask "POST /users" \
  --subtask "DELETE /users/1"

# Disparar
brain job dispatch <job_id>

# Consolidar
brain job consolidate <job_id>
```

---

## Troubleshooting

### Comando não encontrado

```bash
# Adicionar ao PATH
export PATH="/root/claude-brain/scripts:$PATH"

# Ou usar com python
python /root/claude-brain/scripts/brain_cli.py ask "query"
```

### Erro de conexão Neo4j

```bash
# Verificar se Neo4j está rodando
docker-compose ps

# Reconectar
brain graph sync --force
```

### Timeout em query

```bash
# Usar --no-graph para evitar Neo4j
brain ask "query" --no-graph

# Ou aumentar timeout
brain agentic-ask "query" --timeout 30
```

---

## Best Practices

1. **Use brain ask para buscas rápidas**
   ```bash
   brain ask "query" -p projeto
   ```

2. **Use brain agentic-ask para perguntas complexas**
   ```bash
   brain agentic-ask "Pergunta em linguagem natural?"
   ```

3. **Sempre especificar projeto ao salvar**
   ```bash
   brain decide "..." -p projeto
   ```

4. **Usar workflows para tarefas longas**
   ```bash
   brain workflow start "Feature X" -p projeto
   ```

5. **Confirmar decisões testadas**
   ```bash
   brain confirm decisions 45
   ```

---

**Última atualização**: 2026-02-04
**Versão CLI**: 1.2.0
**Compatibilidade**: Python 3.10+
