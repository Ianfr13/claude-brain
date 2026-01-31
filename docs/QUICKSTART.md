# Claude Brain - Quickstart (5 minutos)

Guia rapido para comecar a usar o Claude Brain como sistema de memoria.

## 1. Instalacao (2 min)

```bash
# Clone o repositorio
git clone https://github.com/seu-usuario/claude-brain.git
cd claude-brain

# Crie e ative o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Instale as dependencias
pip install -r requirements.txt

# Execute o setup
./setup.sh
```

**Verificar instalacao:**
```bash
$ brain stats

Estatisticas do Claude Brain
──────────────────────────────────────────────────

Memoria:
  memories: 0
  decisions: 0
  learnings: 0
  ...
```

## 2. Primeiros Comandos (3 min)

### Salvar uma Memoria

```bash
$ brain remember "Usuario prefere respostas em portugues"

✓ Memoria salva (ID: 1)
```

### Salvar uma Decisao Arquitetural

```bash
$ brain decide "Usar FastAPI para a API REST" -p meu-projeto --reason "Suporte async nativo"

✓ Decisao salva (ID: 1) ○ como hipotese
```

**Flags uteis:**
- `-p, --project` - Nome do projeto
- `-r, --reason` - Motivo da decisao
- `--fact` - Marcar como fato (ja confirmado)

### Salvar um Aprendizado (Erro/Solucao)

```bash
$ brain learn "ModuleNotFoundError: torch" \
    --solution "pip install torch" \
    --context "Treinando modelo de ML" \
    --cause "Dependencia nao instalada"

✓ Aprendizado salvo (ID: 1) ○ como hipotese
```

**Flags uteis:**
- `-s, --solution` - Solucao do erro (obrigatorio)
- `-c, --context` - O que estava fazendo
- `--cause` - Causa raiz
- `--prevention` - Como evitar no futuro

### Consultar o Brain

```bash
$ brain ask "como resolver ModuleNotFoundError"

SOLUCAO CONHECIDA: ✓ 85%
   Erro: ModuleNotFoundError: torch
   Solucao: pip install torch
   Contexto: Treinando modelo de ML

DECISOES RELACIONADAS:
   ○ 50% [meu-projeto] Usar FastAPI para a API REST
```

## 3. Fluxo de Trabalho Recomendado

```
1. Ao iniciar tarefa:
   $ brain ask "como fazer X"

2. Ao tomar decisao importante:
   $ brain decide "descricao" -p projeto --reason "motivo"

3. Ao resolver um erro:
   $ brain learn "erro" -s "solucao" -c "contexto"

4. Ao confirmar que algo funciona:
   $ brain confirm decisions 1
```

## 4. Comandos Essenciais

| Comando | Descricao |
|---------|-----------|
| `brain ask <query>` | Consulta inteligente (combina tudo) |
| `brain remember <texto>` | Salva memoria geral |
| `brain decide <texto>` | Salva decisao arquitetural |
| `brain learn <erro> -s <solucao>` | Salva erro/solucao |
| `brain solve <erro>` | Busca solucao para erro |
| `brain search <query>` | Busca semantica nos docs |
| `brain stats` | Mostra estatisticas |
| `brain decisions` | Lista decisoes |
| `brain learnings` | Lista aprendizados |

## 5. Atalhos (opcional)

O script `b` fornece atalhos rapidos:

```bash
$ b s "query"     # = brain search
$ b d "decisao"   # = brain decide
$ b l "erro"      # = brain learn
$ b ? "erro"      # = brain solve
```

## 6. Integracao com Claude Code

Adicione ao seu `~/.claude/CLAUDE.md`:

```markdown
## Brain - Consultar antes de agir

brain ask "sua duvida"      # Consulta inteligente
brain solve "erro"          # Busca solucao
brain decide "X" -p projeto # Salva decisao
brain learn "erro" -s "sol" # Salva aprendizado
```

## Proximos Passos

- Leia `ARCHITECTURE.md` para entender a arquitetura
- Execute `brain --help` para ver todos os comandos
- Configure hooks em `.claude/hooks/` para automacao
- Use `brain index /path` para indexar documentos

## Troubleshooting

**Erro: "command not found: brain"**
```bash
# Adicione ao PATH
echo 'export PATH="$PATH:/root/claude-brain"' >> ~/.bashrc
source ~/.bashrc
```

**Erro: "No module named X"**
```bash
# Ative o venv
source /root/claude-brain/.venv/bin/activate
```

**Busca lenta**
```bash
# Inicie o servidor de embeddings
b server start
```
