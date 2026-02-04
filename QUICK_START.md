# Claude Brain - Quick Start

**Setup em 5 minutos. Primeiros resultados em 10 minutos.**

## 1. Instalação (2 minutos)

### Opção A: Docker (Recomendado)

```bash
# Clone e entre no diretório
cd /root/claude-brain

# Suba o stack completo (Neo4j, Redis, FastAPI)
docker-compose up -d

# Verifique saúde
curl http://localhost:8765/health

# Veja Neo4j Browser
open http://localhost:7474  # Login: neo4j / sua senha
```

### Opção B: Local (Python)

```bash
# Crie virtual environment
python3 -m venv venv
source venv/bin/activate

# Instale dependências
pip install -r requirements.txt

# Configure API keys
export OPENROUTER_API_KEY="sk_or_..."
export ANTHROPIC_API_KEY="sk_ant_..."

# Rode API
uvicorn api.main:app --host 0.0.0.0 --port 8765

# Rode Neo4j (separado)
docker run -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.15
```

---

## 2. Primeiro Uso (3 minutos)

### Via CLI

```bash
# Setup PATH
export PATH="/root/claude-brain/scripts:$PATH"

# 1. Salvar uma decisão
brain decide "Usar Redis para cache" -p meu-projeto

# 2. Salvar um erro + solução
brain learn "ConnectionError ao conectar Redis" \
  -s "systemctl restart redis-server" \
  -p meu-projeto

# 3. Buscar conhecimento
brain ask "redis cache" -p meu-projeto

# Ver resultados em ~245ms
```

### Via API REST

```bash
# Health check
curl http://localhost:8765/health

# Salvar decisão
curl -X POST http://localhost:8765/decisions \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Use Redis",
    "project": "meu-projeto",
    "confidence": 0.9
  }'

# Busca simples
curl -X POST http://localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query": "redis", "project": "meu-projeto"}'
```

### Via Python

```python
from scripts.memory.ensemble_search import ensemble_search

# Busca em 3 backends em paralelo
results = ensemble_search(
    query="redis cache",
    project="meu-projeto",
    limit=10
)

# Resultados consolidados com ranking
for result in results:
    print(f"[{result['relevance_score']:.2f}] {result['content']}")
```

---

## 3. Exemplos Práticos (5 minutos)

### Exemplo 1: Registrar Conhecimento

```bash
# Decisão estratégica
brain decide "Usar FastAPI em vez de Flask" \
  -p vsl-analysis \
  -r "Suporta async/await, 10x mais rápido" \
  --confidence 0.95

# Learning (erro resolv-ido)
brain learn "ImportError: no module named 'neo4j'" \
  -s "pip install neo4j==5.15.0" \
  -p vsl-analysis

# Memória geral (reutilizável)
brain remember "FastAPI suporta dependency injection"

# Ver stats
brain stats -p vsl-analysis
```

### Exemplo 2: Busca Inteligente

```bash
# Pergunta em linguagem natural
# (Query Decomposer quebra em sub-queries)
brain agentic-ask "Como resolver erro de conexão Redis no vsl-analysis?"

# Retorna:
# Sub-queries identificadas:
#   1. Redis connection troubleshooting
#   2. systemctl redis-server error
#   3. vsl-analysis Redis config
#
# Resultados consolidados de 3 fontes
```

### Exemplo 3: Workflow Longo

```bash
# Iniciar sessão
brain workflow start "Implementar cache Redis" -p meu-projeto

# Durante o trabalho
brain workflow update --todo "Configurar Redis server"
brain workflow update --todo "Criar Redis client"
brain workflow update --insight "Redis precisa de password em produção"
brain workflow update --file "api/cache.py"

# Quando terminar
brain workflow complete --summary "Cache implementado, suporta 50k req/s"

# Próxima sessão: recuperar contexto
brain workflow resume
```

### Exemplo 4: Knowledge Graph

```bash
# Ver conceitos mais importantes
brain graph pagerank --limit 5

# Explorar relações
brain graph traverse "redis"

# Encontrar caminho: erro → solução
brain graph path "ConnectionError" "systemctl restart"

# Sincronizar SQLite → Neo4j
brain graph sync --force
```

---

## 4. Estrutura de Dados

### O que é Salvo Onde

```
┌─────────────────────────────────────────────────┐
│ SQLite (brain.db) - Source of Truth             │
│  ├── Decisions: 112 registros                   │
│  ├── Learnings: 45 registros                    │
│  ├── Memories: 28 registros                     │
│  └── Workflows: histórico sessões               │
└─────────────────────────────────────────────────┘
                      ↓ sincroniza
┌─────────────────────────────────────────────────┐
│ FAISS Index - Busca Semântica                   │
│  ├── 3421 vetores (384 dimensões)               │
│  └── DiskCache: chunks pré-processados          │
└─────────────────────────────────────────────────┘
                      ↓ sincroniza
┌─────────────────────────────────────────────────┐
│ Neo4j - Knowledge Graph                         │
│  ├── 150 nós (Decision, Learning, etc)          │
│  ├── 280 relações (RELATES_TO, VALIDATES)       │
│  └── PageRank para importância                  │
└─────────────────────────────────────────────────┘
```

---

## 5. Performance

| Operação | Tempo | Fonte |
|----------|-------|-------|
| Busca SQL simples | <10ms | SQLite |
| Busca semântica | <100ms | FAISS |
| Busca grafo | <100ms | Neo4j |
| **Ensemble (3 backends)** | ~245ms | Paralelo |
| Query Decomposer | ~500ms | OpenRouter |
| **Agentic Search completo** | ~1500ms | LLM + Ensemble |
| Cache hit | <1ms | Redis |

---

## 6. Next Steps

### Leitura Recomendada

1. **[docs/CLI.md](docs/CLI.md)** - Todos os comandos detalhados
2. **[docs/API.md](docs/API.md)** - Endpoints REST
3. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Design detalhado (3 camadas)
4. **[CONTRIBUTING.md](CONTRIBUTING.md)** - Como contribuir

### Explorar APIs

```bash
# Swagger UI interativo
open http://localhost:8765/docs

# ReDoc (alternativa)
open http://localhost:8765/redoc

# GraphQL (futuro)
# em desenvolvimento
```

### Integração com Claude

```bash
# Use no seu CLAUDE.md
brain ask "seu-topico" -p seu-projeto

# Exemplo em script
result=$(brain ask "redis cache" -p meu-projeto --format json)
echo $result | jq '.results | .[0]'
```

---

## 7. Troubleshooting

### Erro: "Neo4j connection failed"

```bash
# Verificar se Neo4j está rodando
docker-compose ps

# Reconectar
brain graph sync --force

# Ou rodar Neo4j local
docker run -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.15
```

### Erro: "FAISS index corrupted"

```bash
# Rebuild index
python scripts/memory/base.py --rebuild-faiss
```

### Erro: "Query Decomposer timeout"

```bash
# Aumentar timeout
brain agentic-ask "query" --timeout 30

# Ou usar sem LLM
brain ask "query" --no-graph
```

### Erro: "Rate limit exceeded"

```bash
# Limites padrão: 100 req/60s por endpoint
# Aguarde antes de retry
sleep 60
```

---

## 8. Próximas Ações

### Recomendado

1. ✅ Registrar 5-10 decisões/learnings
2. ✅ Testar busca simples (brain ask)
3. ✅ Testar busca inteligente (brain agentic-ask)
4. ✅ Ver grafo de conhecimento (brain graph)
5. ✅ Ler [docs/CLI.md](docs/CLI.md) para todos comandos

### Integração

- [ ] Integrar com seu projeto
- [ ] Setup hooks do Claude Code
- [ ] Criar CLAUDE.md customizado
- [ ] Contribuir com melhorias

---

## Arquivos Principais

| Arquivo | Descrição |
|---------|-----------|
| [README.md](README.md) | Overview do projeto |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Design detalhado (3 camadas) |
| [docs/CLI.md](docs/CLI.md) | Referência CLI completa |
| [docs/API.md](docs/API.md) | Endpoints REST |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Como contribuir |
| [scripts/memory/](scripts/memory/) | Core implementation |
| [tests/](tests/) | 206+ testes |

---

## Suporte

- 📖 Documentação: [docs/](docs/)
- 🐛 Issues: [GitHub Issues](https://github.com/your-repo/issues)
- 💬 Discussões: [GitHub Discussions](https://github.com/your-repo/discussions)
- 🔧 API Docs: http://localhost:8765/docs

---

**Pronto para usar!** 🚀

Última atualização: 2026-02-04
Versão: 1.2.0
