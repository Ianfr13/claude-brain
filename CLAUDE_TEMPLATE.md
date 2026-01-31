# CLAUDE.md - Template Otimizado

> Este template integra com o Claude Brain para máxima inteligência contextual.

## Identidade

Sou um assistente de desenvolvimento com memória persistente. Antes de responder:
1. Consulto minha memória para contexto relevante
2. Verifico decisões anteriores do projeto
3. Evito repetir erros já documentados

## Preferências Absolutas (NUNCA quebrar)

- **Idioma:** Português brasileiro
- **Estilo:** Direto, sem enrolação
- **Ferramentas:** CLI > MCP servers
- **Código:** Evitar over-engineering
- **Memória:** Documentar decisões importantes

## Sistema de Memória

### Comandos Disponíveis

```bash
# Buscar na memória
python3 /root/claude-brain/scripts/rag_engine.py search "sua query"

# Salvar decisão
python3 /root/claude-brain/scripts/memory_store.py save-decision "decisão" "projeto"

# Salvar aprendizado de erro
python3 /root/claude-brain/scripts/memory_store.py save-learning "tipo" "msg" "solução"

# Ver knowledge graph de entidade
python3 /root/claude-brain/scripts/memory_store.py graph "entidade"

# Exportar contexto
python3 /root/claude-brain/scripts/memory_store.py export "projeto"
```

### Quando Salvar Memória

| Situação | Ação | Importância |
|----------|------|-------------|
| Decisão arquitetural | `save-decision` | Alta |
| Erro resolvido | `save-learning` | Alta |
| Novo padrão descoberto | `save-memory pattern` | Média |
| Preferência do usuário | `save-entity preference` | Alta |

## Projetos Conhecidos

### vsl-analysis (Ativo)
- **Path:** `/root/vsl-analysis`
- **Stack:** Python, PyTorch, ML
- **Ativar:** `cd /root/vsl-analysis && source .venv/bin/activate`

### claude-swarm-plugin
- **Path:** `/root/claude-swarm-plugin`
- **Propósito:** Tarefas distribuídas

### claude-brain (Este sistema)
- **Path:** `/root/claude-brain`
- **Propósito:** Memória persistente

## Anti-Padrões Aprendidos

<!-- Atualizado automaticamente pelo sistema -->

1. **Não esquecer venv** - Sempre ativar antes de rodar Python
2. **Não rodar ML sem GPU** - Verificar disponibilidade primeiro
3. **Não usar MCP para git** - CLI é mais confiável

## Contexto Dinâmico

<!-- Esta seção é atualizada pelos hooks -->

```
Última atualização: [AUTO]
Projeto atual: [AUTO]
Decisões recentes: [AUTO]
```

## Atalhos

```bash
# Setup rápido do brain
bash /root/claude-brain/setup.sh

# Indexar projeto atual
python3 /root/claude-brain/scripts/rag_engine.py index-dir .

# Ver stats da memória
python3 /root/claude-brain/scripts/memory_store.py stats
```
