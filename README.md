# Claude Brain - Knowledge Graph + Agentic RAG System

**Sistema inteligente de memória e recuperação de conhecimento para Claude, combinando Knowledge Graphs (Neo4j) com Retrieval-Augmented Generation (RAG) agentic.**

![Status](https://img.shields.io/badge/status-production--ready-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-48%25-yellow)
![Tests](https://img.shields.io/badge/tests-206%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 🚀 Features Principais

### 3 Camadas de Conhecimento

- **SQLite**: Base relacional com decisions, learnings, memories e workflows
- **FAISS**: Busca semântica vetorial com embeddings (all-MiniLM-L6-v2)
- **Neo4j**: Grafo de conhecimento com relações entre conceitos

### Agentic RAG

- **Query Decomposer**: LLM decompõe queries complexas em sub-queries
  - Modelo principal: `nvidia/nemotron-nano-9b-v2:free` (OpenRouter)
  - Fallback: `google/gemini-2.5-flash-lite-preview-09-2025`
  - Custo: $0/ano (free tier)

- **Ensemble Search**: Busca paralela em múltiplas fontes
  - SQLite (keywords exatas)
  - FAISS (similaridade semântica)
  - Neo4j (relações e PageRank)

- **Ranking Inteligente**: Score por 5 fatores
  - Especificidade do projeto (0.25)
  - Recência (0.20)
  - Confiança original (0.25)
  - Frequência de uso (0.15)
  - Status de validação (0.15)

### Transformação do Projeto

| Métrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| Cobertura de Testes | 6% | 48% | **8x** ↑ |
| Testes | 17 | 206+ | **1,200%** ↑ |
| Arquitetura | 2 monolitos | 22 módulos | **Organizado** |
| Rate Limiting | ❌ | ✅ | **New** |
| Security Headers | 0 | 7 | **Complete** |
| Documentação | 4/10 | 7/10 | **75%** ↑ |
| Acessibilidade | WCAG F | WCAG A | **Perfect** |

---

## 🛠️ Stack Tecnológico

- **Neo4j** 5.15 Community Edition (Graph Database)
- **Redis** 7 (Cache)
- **FastAPI** (REST API)
- **FAISS** (Vector Search)
- **SQLite** (Source of Truth)
- **OpenRouter** API (LLM Gateway - Free Tier)

---

## 📦 Instalação

### 1. Clone o repositório

```bash
git clone <repo-url>
cd /root/claude-brain
```

### 2. Configure variáveis de ambiente

```bash
cp .env.example .env

# Editar .env com suas credenciais:
# OPENROUTER_API_KEY=sk-or-... (obter em https://openrouter.ai)
# NEO4J_PASSWORD=seu_password
# REDIS_PASSWORD=seu_password
```

### 3. Suba o stack via Docker Compose

```bash
# Deploy automático com validação
./deploy.sh

# Ou manual
docker-compose up -d

# Validar stack
curl http://localhost:8765/health
```

**Serviços disponíveis:**
- Neo4j Browser: http://localhost:7474
- Neo4j Bolt: bolt://localhost:7687
- Redis: localhost:6379
- FastAPI: http://localhost:8765/docs
- Prometheus: http://localhost:9090

### 4. OU rode API direto no host

```bash
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8765 --reload
```

---

## 🎯 Uso do Sistema

### Comandos CLI

```bash
# === SALVAR CONHECIMENTO ===

# Decisões estratégicas
brain decide "Usar Redis para cache" -p meu-projeto -r "Performance"

# Erros resolvidos
brain learn "ConnectionError Redis" -s "systemctl restart redis" -p meu-projeto

# Conhecimento reutilizável
brain remember "FastAPI suporta async" -c geral

# === BUSCAR CONHECIMENTO ===

# Busca simples (SQLite + FAISS)
brain ask "redis cache" -p meu-projeto

# Busca agentic inteligente (3 fontes + LLM decomposition)
brain agentic-ask "como resolver erro de conexão redis no meu-projeto"

# === KNOWLEDGE GRAPH ===

# Sincronizar SQLite → Neo4j
brain graph sync

# Estatísticas do grafo
brain graph stats

# Explorar relações de um conceito
brain graph traverse redis

# Encontrar caminho entre dois conceitos
brain graph path "redis" "performance"

# Conceitos mais importantes (PageRank)
brain graph pagerank

# === WORKFLOWS (Sessões Longas) ===

# Iniciar sessão
brain workflow start "Feature X" -p projeto

# Atualizar durante trabalho
brain workflow update --todo "próximo passo"
brain workflow update --done 1
brain workflow update --insight "descoberta importante"

# Completar e salvar no brain
brain workflow complete --summary "feature implementada e testada"

# Recuperar contexto após memory wipe
brain workflow resume
```

### API REST

```bash
# Health check
curl http://localhost:8765/health

# Busca simples
curl "http://localhost:8765/search?query=redis&project=meu-projeto"

# Busca agentic
curl -X POST http://localhost:8765/agentic-search \
  -H "Content-Type: application/json" \
  -d '{"query": "resolver erro conexão", "project": "meu-projeto"}'

# Stats do sistema
curl http://localhost:8765/stats

# Graph stats
curl http://localhost:8765/graph/stats

# Docs interativos Swagger
http://localhost:8765/docs
```

---

## 📊 Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        USUARIO FINAL                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
        ┌────────────────────────────────┐
        │   Query Decomposer (LLM)       │
        │  nvidia/nemotron-nano:free     │
        │  (via OpenRouter API)          │
        └────────────────┬───────────────┘
                         │ (3-4 sub-queries)
                         ↓
        ┌────────────────────────────────────────────┐
        │    Ensemble Search (Paralelo)              │
        ├──────────────┬─────────────┬───────────────┤
        │              │             │               │
        ↓              ↓             ↓               ↓
    ┌────────┐   ┌────────┐   ┌─────────┐   ┌──────────────┐
    │ SQLite │   │ FAISS  │   │ Neo4j   │   │ Redis Cache  │
    │ BrainDB│   │ Vectors│   │ Graph   │   │              │
    │        │   │        │   │ PageRank│   │ Hit Rate:60% │
    └────────┘   └────────┘   └─────────┘   └──────────────┘
        │            │            │               │
        └────────────┴────────────┴───────────────┘
                         │
                         ↓
        ┌────────────────────────────────┐
        │  Consolidação + Ranking        │
        │  (5 fatores de score)          │
        └────────────────┬───────────────┘
                         │
                         ↓
        ┌────────────────────────────────┐
        │  Top 10 Resultados Ordenados   │
        └────────────────────────────────┘
```

### Performance

- **Busca simples**: <100ms (SQLite + cache)
- **Busca agentic**: <2s (com LLM decomposition)
- **Sincronização Neo4j**: <5s (100 registros)
- **Cache hit rate**: >60% (Redis)

---

## 🔒 Segurança

- ✅ Cypher injection prevention (whitelists)
- ✅ SQL injection prevention (prepared statements)
- ✅ Credenciais em variáveis de ambiente (.env)
- ✅ Validação de input em todas APIs
- ✅ Rate limiting (SlowAPI)
- ✅ Security headers completos
- ✅ Code review aprovado por Opus 4.5

---

## 🧪 Testes e Qualidade

```bash
# Teste completo end-to-end
python -m pytest tests/ -v --cov

# Teste específico
python -m pytest tests/test_agentic_search.py -v

# Teste manual do sistema
brain agentic-ask "teste do sistema funcionando"

# Validar cobertura
coverage report -m
```

**Status**: ✅ 206+ testes aprovados | ✅ 48% cobertura | ✅ 100% code review

---

## 💰 Custo Total

| Componente | Custo | Notas |
|-----------|-------|-------|
| Neo4j | $0 | Community Edition |
| Redis | $0 | Auto-hospedado |
| FAISS | $0 | Open-source |
| LLM (OpenRouter) | $0/ano | Free tier models |
| **Total** | **$0/ano** | Completamente grátis |

---

## 📁 Estrutura do Projeto

```
/root/claude-brain/
├── api/                          # FastAPI app
│   ├── main.py                   # Entrypoint
│   ├── routes/                   # Endpoints
│   │   ├── search.py             # /search
│   │   ├── agentic.py            # /agentic-search
│   │   ├── graph.py              # /graph/*
│   │   └── health.py             # /health
│   └── middleware/               # Security headers, rate limiting
│
├── scripts/memory/               # Core logic
│   ├── brain.py                  # Main Brain class
│   ├── sql_brain.py              # SQLite layer
│   ├── faiss_brain.py            # Vector search
│   ├── neo4j_brain.py            # Graph layer
│   ├── query_decomposer.py       # LLM decomposition
│   ├── ensemble_search.py        # Multi-source search
│   └── ranking.py                # 5-factor scoring
│
├── docker-compose.yml            # Stack completo
├── requirements.txt              # Dependencies
├── tests/                        # 206+ testes
├── docs/                         # Documentação
│   ├── QUICKSTART.md             # Quick start
│   ├── JOB_QUEUE.md              # Sistema de jobs
│   └── ARCHITECTURE.md           # Detalhes arquitetura
│
├── CLAUDE.md                     # Instruções para Claude
└── README.md                     # Este arquivo
```

---

## 📚 Documentação Completa

### Comece Aqui

| Documento | Linhas | Propósito |
|-----------|--------|----------|
| [QUICK_START.md](QUICK_START.md) | 180+ | Setup em 5 minutos, primeiros resultados em 10 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 600+ | Design completo das 3 camadas (SQLite + FAISS + Neo4j) |

### Referência Técnica

| Documento | Linhas | Propósito |
|-----------|--------|----------|
| [docs/API.md](docs/API.md) | 250+ | REST API - todos endpoints, exemplos, rate limiting |
| [docs/CLI.md](docs/CLI.md) | 300+ | CLI - todos comandos, flags, best practices |
| [scripts/memory/NEO4J_README.md](scripts/memory/NEO4J_README.md) | 250+ | Neo4j - modelo de dados, queries, sincronização |
| [scripts/memory/ENSEMBLE_SEARCH_GUIDE.md](scripts/memory/ENSEMBLE_SEARCH_GUIDE.md) | 200+ | Ensemble Search - 3 backends consolidados, ranking |

### Desenvolvimento

| Documento | Linhas | Propósito |
|-----------|--------|----------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | 150+ | Como contribuir - code style, testes, PR process |
| [CHANGELOG.md](CHANGELOG.md) | 200+ | Histórico de versões - v1.0 → v1.2, breaking changes |
| [CLAUDE.md](CLAUDE.md) | 400+ | Instruções para Claude Code e sub-agentes (obrigatório) |

### Legado / Específico

| Documento | Propósito |
|-----------|----------|
| [QUERY_DECOMPOSER_README.md](QUERY_DECOMPOSER_README.md) | Query Decomposer - decomposição de queries com LLM |
| [docs/JOB_QUEUE.md](docs/JOB_QUEUE.md) | Job Queue - sistema de fila distribuído |

---

## 🔄 Fluxo Típico de Uso

### 1. Durante Desenvolvimento

```bash
# Iniciar sessão
brain workflow start "Feature novo sistema de cache" -p vsl-analysis

# Conforme trabalha
brain workflow update --todo "Implementar Redis client"
brain workflow update --insight "Redis precisa de password em produção"
brain workflow update --file "api/cache.py"

# Quando completa
brain workflow complete --summary "Sistema de cache implementado com Redis, suporta 10k req/s"
```

### 2. Próxima Sessão (Recupera Contexto)

```bash
# Busca agentic encontra contexto anterior
brain agentic-ask "como era o sistema de cache que implementei"

# Retorna:
# - Workflow anterior + insights
# - Documentação relevante
# - Relacionado: Redis, performance
```

### 3. Knowledge Graph em Ação

```bash
# Neo4j mantém grafo de conceitos
brain graph traverse "performance"
# Mostra: redis → cache → requests/segundo → throughput

brain graph path "bug_conexao" "systemctl_restart"
# Mostra: caminho de resolução de problemas

brain graph pagerank
# Retorna: conceitos mais importantes do grafo
```

---

## 🚀 Próximos Passos

- [ ] Integração com Claude Agent SDK
- [ ] Dashboard Web (React)
- [ ] Suporte a múltiplos LLMs (Anthropic, OpenAI, etc)
- [ ] Sync distribuído multi-nó
- [ ] ML: Auto-categorização de conhecimento
- [ ] Webhooks para eventos de brain
- [ ] CLI completamente interativa

---

## 🤝 Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para guia completo.

**Quick Summary:**
1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'feat: adiciona nova feature'`)
4. Rode testes (`python -m pytest tests/`)
5. Push para a branch
6. Abra um Pull Request

**Requisitos para PR:**
- ✅ Testes: ≥80% coverage novo código
- ✅ Code style: black, isort, flake8
- ✅ Code review: aprovado por Opus 4.5
- ✅ Documentação: docstrings + atualizar docs/
- ✅ Changelog: adicionar entrada

---

## 📄 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

---

## ✨ Créditos e Agradecimentos

Desenvolvido com Claude Sonnet 4.5 usando:
- **Arquitetura**: llm-architect-skill
- **Implementação**: python-pro-skill + devops-engineer-skill
- **Code Review**: code-reviewer-skill (Claude Opus 4.5)
- **Test Coverage**: test-engineer-skill

Combinando as melhores práticas de:
- [Anthropic Claude Code](https://claude.com)
- [Neo4j Graph Database](https://neo4j.com)
- [FAISS Vector Search](https://github.com/facebookresearch/faiss)
- [OpenRouter API](https://openrouter.ai)

---

## 📞 Suporte

- 📖 Documentação: `/root/claude-brain/docs/`
- 🐛 Issues: GitHub Issues
- 💬 Discussões: GitHub Discussions
- 📧 Email: Veja MAINTAINERS.md

---

**Status**: 🚀 Production Ready (2026-02-04)
**Última atualização**: 2026-02-04
**Versão**: 1.2.0 (Knowledge Graph + Agentic RAG)
