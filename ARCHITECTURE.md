# Claude Brain - Arquitetura Completa de Otimizacao

> **Sistema de memoria persistente para Claude Code**
> Ultima atualizacao: Janeiro 2026

## Estatisticas Atuais

| Componente | Quantidade |
|------------|------------|
| Decisoes arquiteturais | 112 |
| Learnings (erros/solucoes) | 12 |
| Memorias gerais | 28 |
| Documentos indexados | 309 |
| Chunks RAG | 3421 |
| Entidades no grafo | 12 |
| Relacoes | 9 |

## Visao Geral

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              CLAUDE CODE                                    │
│                         (Opus 4.5 / Haiku)                                 │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Hooks     │  │   Skills    │  │    MCP      │  │   Agentes   │       │
│  │ (triggers)  │  │ (expertise) │  │  (tools)    │  │ (subagents) │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │                │               │
│         └────────────────┴────────────────┴────────────────┘               │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    CONTEXT ORCHESTRATOR                              │  │
│  │  • Decide o que carregar                                            │  │
│  │  • Prioriza por relevancia                                          │  │
│  │  • Comprime contexto antigo                                         │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
│         ┌──────────────────────────┼──────────────────────────┐           │
│         ▼                          ▼                          ▼           │
│  ┌─────────────┐           ┌─────────────┐           ┌─────────────┐      │
│  │  CLAUDE.md  │           │  RAG Local  │           │  Knowledge  │      │
│  │  (regras)   │           │ (FAISS)     │           │   Graph     │      │
│  └─────────────┘           └─────────────┘           └─────────────┘      │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                         STORAGE LAYER                                │  │
│  │  SQLite │ FAISS Index │ JSON Files │ Git History                    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## 1. Camada de Memória Persistente (RAG Local)

### Objetivo
Permitir que o Claude "lembre" de conversas, decisões e aprendizados anteriores.

### Componentes

```
/root/claude-brain/
├── memory/
│   └── brain.db           # SQLite principal (decisoes, learnings, memorias)
├── rag/
│   ├── faiss_index/       # Indice FAISS para busca vetorial
│   │   ├── index.faiss    # Vetores de embeddings
│   │   └── metadata.json  # Metadados dos chunks
│   ├── index.db           # SQLite com chunks e metadados
│   └── embeddings/        # Cache de embeddings (opcional)
├── knowledge-graph/
│   ├── nodes.json         # Entidades do grafo
│   └── edges.json         # Relacoes entre entidades
├── scripts/
│   ├── brain_cli.py       # CLI principal (38KB)
│   ├── memory_store.py    # Camada de persistencia
│   ├── faiss_rag.py       # Motor de busca semantica FAISS
│   ├── rag_engine.py      # RAG alternativo (SQLite FTS)
│   └── metrics.py         # Sistema de metricas
├── api/                   # API REST (FastAPI)
├── hooks/                 # Hooks para Claude Code
└── tests/                 # Testes automatizados
```

### Stack Atual

| Componente | Implementacao | Notas |
|------------|---------------|-------|
| Embeddings | all-MiniLM-L6-v2 | Modelo local, 384 dimensoes |
| Vector DB | **FAISS** | Meta AI, busca vetorial rapida |
| Metadata | SQLite | brain.db + index.db |
| CLI | Python + argparse | brain_cli.py |
| API | FastAPI | Opcional, para integracao |

> **Nota**: FAISS foi escolhido em vez de ChromaDB por estabilidade
> em containers Docker e menor uso de memoria.

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
