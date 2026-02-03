# Brain CLI - Job Queue com TTL

Sistema de fila de jobs com Time To Live (TTL) para o Brain CLI.

## Visao Geral

O Job Queue permite criar, gerenciar e recuperar jobs que expiram automaticamente apos um tempo configurado. Ideal para:

- Sessoes de trabalho longas que precisam de contexto persistente
- Tarefas agendadas para execucao posterior
- Distribuicao de trabalho entre sessoes/agentes
- Recovery apos memory wipes ou reinicializacoes

## Arquitetura

### Tabela SQLite

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,           -- UUID gerado automaticamente
    created_at TIMESTAMP,              -- Data/hora de criacao
    ttl INTEGER NOT NULL,              -- Time to live em segundos
    expires_at TIMESTAMP NOT NULL,     -- Data/hora de expiracao (calculado)
    data JSON NOT NULL                 -- Dados do job (prompt, skills, etc)
);
```

### Estrutura do JSON data

```json
{
  "prompt": "Instrucao principal do job",
  "skills": ["skill1", "skill2"],
  "brain_queries": [
    {"query": "texto da query", "project": "nome-projeto"},
    {"query": "query sem projeto"}
  ],
  "files": ["/path/to/file1.py", "/path/to/file2.py"],
  "context": {
    "priority": "high",
    "deadline": "2026-02-05",
    "custom_field": "valor"
  }
}
```

### Auto-cleanup

Todos os comandos job executam cleanup automatico ao iniciar, removendo jobs expirados. Nao precisa chamar `brain job cleanup` manualmente (mas pode se quiser).

## Comandos CLI

### 1. Create - Criar Job

Cria um novo job com TTL configurado.

**Sintaxe:**

```bash
# Modo 1: JSON completo
brain job create --ttl SECONDS --data 'JSON'

# Modo 2: Flags individuais (mais conveniente)
brain job create --ttl SECONDS \
  --prompt "texto" \
  [--skills SKILL] \           # pode repetir
  [--brain-query "query|project"] \  # pode repetir
  [--files PATH] \             # pode repetir
  [--context 'JSON']
```

**Exemplos:**

```bash
# Simples
brain job create --ttl 60 --prompt "Analisar logs de erro"

# Com skills
brain job create --ttl 3600 \
  --prompt "Implementar cache Redis" \
  --skills python-pro-skill \
  --skills sql-pro-skill

# Completo
brain job create --ttl 7200 \
  --prompt "Otimizar queries do banco" \
  --skills sql-pro-skill \
  --brain-query "performance|vsl-analysis" \
  --brain-query "database optimization" \
  --files /root/vsl-analysis/db.py \
  --files /root/vsl-analysis/queries.py \
  --context '{"priority":"high","deadline":"2026-02-05"}'

# JSON completo
brain job create --ttl 1800 --data '{
  "prompt": "Revisar codigo de seguranca",
  "skills": ["python-pro-skill"],
  "brain_queries": [
    {"query": "security", "project": "vsl-analysis"}
  ],
  "files": ["/root/vsl-analysis/auth.py"],
  "context": {"priority": "critical"}
}'
```

**Retorno:**

```
* Job criado: cd98bf39-9fc6-48f2-b2a2-58e5e66948d8
i TTL: 1m
i Expira: 03/02 16:29
```

### 2. Get - Recuperar Job

Recupera um job pelo ID. Retorna erro se job nao existe ou esta expirado.

**Sintaxe:**

```bash
brain job get JOB_ID [--json]
```

**Exemplos:**

```bash
# Formato legivel
brain job get cd98bf39-9fc6-48f2-b2a2-58e5e66948d8

# Formato JSON (para parsing automatico)
brain job get cd98bf39-9fc6-48f2-b2a2-58e5e66948d8 --json
```

**Retorno (legivel):**

```
[cd98bf39-9fc6-48f2-b2a2-58e5e66948d8]
  Criado:  03/02 16:28
  Expira:  03/02 17:28 (TTL: 1h)
  Prompt:  Implementar cache Redis
  Skills:  python-pro-skill, sql-pro-skill
  Brain:
    - performance (-p vsl-analysis)
    - database optimization
  Files:
    - /root/vsl-analysis/db.py
    - /root/vsl-analysis/queries.py
  Context: {
  "priority": "high",
  "deadline": "2026-02-05"
}
```

**Retorno (JSON):**

```json
{
  "job_id": "cd98bf39-9fc6-48f2-b2a2-58e5e66948d8",
  "created_at": "2026-02-03T16:28:54.964423",
  "ttl": 3600,
  "expires_at": "2026-02-03T17:28:54.964423",
  "data": {
    "prompt": "Implementar cache Redis",
    "skills": ["python-pro-skill", "sql-pro-skill"],
    "brain_queries": [
      {"query": "performance", "project": "vsl-analysis"},
      {"query": "database optimization"}
    ],
    "files": [
      "/root/vsl-analysis/db.py",
      "/root/vsl-analysis/queries.py"
    ],
    "context": {
      "priority": "high",
      "deadline": "2026-02-05"
    }
  }
}
```

### 3. List - Listar Jobs

Lista todos os jobs ativos (ou todos, incluindo expirados).

**Sintaxe:**

```bash
brain job list [--all] [--json]
```

**Exemplos:**

```bash
# Jobs ativos
brain job list

# Todos (incluindo expirados)
brain job list --all

# JSON
brain job list --json
```

**Retorno:**

```
3 job(s) na fila:

[cd98bf39-9fc6-48f2-b2a2-58e5e66948d8]
  Criado:  03/02 16:28
  Expira:  03/02 17:28 (TTL: 1h)
  Prompt:  Implementar cache Redis

[880af292-1321-41c9-b4db-1cd95d6501db]
  Criado:  03/02 16:31
  Expira:  03/02 18:31 (TTL: 2h)
  Prompt:  Otimizar queries do banco
```

### 4. Cleanup - Remover Expirados

Remove manualmente todos os jobs expirados.

**Sintaxe:**

```bash
brain job cleanup
```

**Retorno:**

```
* 3 job(s) expirado(s) removido(s)
```

ou

```
i Nenhum job expirado
```

### 5. Delete - Deletar Job

Deleta um job manualmente (mesmo se nao expirado).

**Sintaxe:**

```bash
brain job delete JOB_ID
```

**Exemplo:**

```bash
brain job delete cd98bf39-9fc6-48f2-b2a2-58e5e66948d8
```

**Retorno:**

```
* Job deletado: cd98bf39-9fc6-48f2-b2a2-58e5e66948d8
```

### 6. Stats - Estatisticas

Mostra estatisticas de jobs (ativos/expirados).

**Sintaxe:**

```bash
brain job stats [--all]
```

**Exemplos:**

```bash
# Apenas ativos
brain job stats

# Com expirados
brain job stats --all
```

**Retorno:**

```
Estatisticas de Jobs:
  Jobs ativos: 3
  Jobs expirados: 2
  Total: 5
```

## Job Iterativo (NEW)

Jobs agora suportam iteracoes - tracking de execucoes, revisoes e mudancas de status.

### 7. Iterate - Iterar um Job

Adiciona entrada no historico e atualiza status/iteracao.

**Sintaxe:**

```bash
brain job iterate JOB_ID --type execution|review --agent haiku|opus --result 'resultado'
```

**Exemplos:**

```bash
# Haiku executando tarefa
brain job iterate abc123... --type execution --agent haiku --result "Funcoes implementadas"

# Opus revisando
brain job iterate abc123... --type review --agent opus --result "LGTM, pronto para deploy"
```

**Retorno:**

```
2026-02-03 17:27:47 - INFO - Job iterado: abc123... (iteracao 2, execution por haiku)
* Job iterado: abc123...
i Iteracao: 2
i Status: executing
```

### 8. History - Ver Historico

Exibe todas as iteracoes do job em ordem reversa.

**Sintaxe:**

```bash
brain job history JOB_ID [--json]
```

**Exemplos:**

```bash
# Legivel
brain job history abc123...

# JSON
brain job history abc123... --json
```

**Retorno (legivel):**

```
Historico do job abc123...:
(ultimas iteracoes primeiro)

  [2] execution @ 03/02 17:27:41
      Agente: haiku
      Resultado: Funcoes backend implementadas...

  [1] review @ 03/02 17:20:15
      Agente: opus
      Resultado: Revisar implementation de check_cli_tools...
```

### 9. Status - Ver/Atualizar Status

Exibe status atual ou atualiza para novo estado.

**Sintaxe:**

```bash
brain job status JOB_ID [--set novo_status]
```

**Estados Validos:**

- `pending`: Aguardando execucao (inicial)
- `executing`: Sendo executado
- `in_review`: Aguardando revisao
- `fixing`: Em correcao
- `completed`: Concluido (terminal)
- `failed`: Falhou (terminal)

**Transicoes Validas:**

```
pending    -> executing, in_review, failed
executing  -> in_review, failed
in_review  -> fixing, completed, failed
fixing     -> executing, failed
completed  -> [terminal]
failed     -> [terminal]
```

**Exemplos:**

```bash
# Ver status
brain job status abc123...

# Mudar para in_review
brain job status abc123... --set in_review

# Marcar como completo
brain job status abc123... --set completed
```

**Retorno (legivel):**

```
Job: abc123...
  Status: executing
  Iteracoes: 2
  Criado: 03/02 17:25
  Expira: 03/02 19:25
  Tools: gdrive, missing-tool-123
```

## CLI Management (NEW)

Sistema de deteccao e criacao automatica de ferramentas CLI.

### 10. CLI List - Listar CLIs Disponiveis

Escaneia /root/.claude/cli/ e lista ferramentas disponiveis.

**Sintaxe:**

```bash
brain cli list [--json]
```

**Exemplos:**

```bash
# Legivel
brain cli list

# JSON
brain cli list --json
```

**Retorno:**

```
8 CLI(s) disponivel(is):

  bin
  elevenlabs-cli [Node.js]
  gdrive [Python]
  pexels-cli [Node.js]
  sync-cli [Node.js]
  uazapi
  vsl-producer [Node.js]
```

### 11. Job Tools - Verificar Ferramentas de um Job

Verifica status das ferramentas requeridas por um job.

**Sintaxe:**

```bash
brain job tools JOB_ID [--json] [--build-missing]
```

**Exemplos:**

```bash
# Ver status das ferramentas
brain job tools abc123...

# Criar job builder para ferramentas faltando
brain job tools abc123... --build-missing

# JSON
brain job tools abc123... --json
```

**Retorno (com ferramentas faltando):**

```
Ferramentas requeridas por abc123...:

  ✓ gdrive: disponivel
  ✗ missing-tool-123: nao encontrada

x Faltam 1 ferramentas: missing-tool-123
i Use --build-missing para criar job builder automatico
```

**Retorno (com --build-missing):**

```
* Job builder criado para construir 1 CLI(s)
i Child job: 7025a423-90b3-4642-aefb-74b99c93d4dd
i Monitorar com: brain job status 7025a423-90b3-4642-aefb-74b99c93d4dd
```

## Protocolo Orquestrador (NEW)

Fluxo completo para executar um job com iteracoes, deteccao de tools e review automatico.

### Fluxo Basico: Create -> Check -> Build -> Execute -> Review -> Iterate

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CREATE JOB                                               │
│    brain job create --ttl 3600 --prompt "Tarefa" ...       │
│    └─> job_id = abc123...                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 2. CHECK TOOLS                                              │
│    brain job tools abc123...                               │
│    └─> Status de ferramentas requeridas                    │
│        ├─ Se todas disponivel → 3. EXECUTE                 │
│        └─ Se faltando → 2b. BUILD                          │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────────┐
        │                             │
   ┌────▼──────┐             ┌────────▼────────┐
   │ Todas OK  │             │ FALTANDO TOOLS  │
   └────┬──────┘             └────────┬────────┘
        │                             │
        │                   ┌─────────▼──────────────────┐
        │                   │ 2b. BUILD MISSING TOOLS    │
        │                   │ brain job tools abc123...  │
        │                   │        --build-missing     │
        │                   │ └─> child_job_id = xyz789  │
        │                   │ └─> Aguarda child.status   │
        │                   │     == 'completed'         │
        │                   └─────────┬──────────────────┘
        │                             │
        │                   ┌─────────▼──────────────────┐
        │                   │ Child: Build CLIs          │
        │                   │ [haiku] create → test      │
        │                   │ [opus] review → approve    │
        │                   │ iterate until approved     │
        │                   └─────────┬──────────────────┘
        │                             │
        └─────────────────────┬───────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│ 3. EXECUTE                                                │
│    brain job iterate abc123... --type execution \        │
│            --agent haiku --result "Resultado..."         │
│    └─> iteration++, status = 'executing'                 │
└─────────────────────┬─────────────────────────────────────┘
                      │
┌─────────────────────▼─────────────────────────────────────┐
│ 4. REVIEW                                                 │
│    brain job iterate abc123... --type review \           │
│            --agent opus --result "Analise..."            │
│    └─> iteration++, status = 'in_review'                 │
│    └─> Resultado pode indicar:                           │
│        ├─ LGTM → 5a. COMPLETE                            │
│        └─ Issues → 4b. FIX                               │
└─────────────┬──────────────────────────┬──────────────────┘
              │                          │
         ┌────▼────┐           ┌────────▼──────────┐
         │ LGTM    │           │ ISSUES FOUND      │
         └────┬────┘           └────────┬──────────┘
              │                         │
         ┌────▼────┐          ┌────────▼──────────────┐
         │ 5a.     │          │ 4b. FIX              │
         │ COMPLETE│          │ brain job status     │
         │ brain   │          │   abc123... --set    │
         │ job     │          │   fixing             │
         │ status  │          │ [Corrigir codigo]    │
         │ abc123..│          │ → volta a 3. EXECUTE │
         │ --set   │          └──────────────────────┘
         │ complete│
         └────┬────┘
              │
         ┌────▼────────────────────────┐
         │ Job concluido!              │
         │ brain job get abc123...     │
         │ status = 'completed'        │
         │ iterations = N              │
         └─────────────────────────────┘
```

### Exemplo Completo: Implementar Funcao Redis

```bash
# 1. Criar job
JOB_ID=$(brain job create --ttl 7200 \
  --prompt "Implementar cache Redis com TTL configuravel" \
  --skills python-pro-skill \
  --brain-query "redis|vsl-analysis" \
  --files /root/vsl-analysis/cache.py \
  --context '{"priority":"high"}' | grep -oP 'Job criado: \K[^ ]+')

echo "Job criado: $JOB_ID"

# 2. Verificar ferramentas requeridas
brain job tools "$JOB_ID"

# Se ferramentas faltando, criar job builder automaticamente
# brain job tools $JOB_ID --build-missing

# 3. [HAIKU] Implementar cache
brain job iterate "$JOB_ID" --type execution --agent haiku \
  --result "Implementada classe RedisCache com suporte a TTL, retry, e circuit breaker"

# Ver progresso
brain job status "$JOB_ID"
brain job history "$JOB_ID"

# 4. [OPUS] Revisar implementacao
brain job iterate "$JOB_ID" --type review --agent opus \
  --result "Implementacao solida. Verificar:
- Circuit breaker timeout precisa tunagem
- Logs poderiam ser mais detalhados
- Considerar metricas de hit rate

Status: APPROVED com melhorias opcio­nais"

# 5. Marcar como completo ou retornar para fix
# Se LGTM:
brain job status "$JOB_ID" --set completed

# Se precisa melhorias:
brain job status "$JOB_ID" --set fixing
# [Aplicar mudancas]
# Volta a step 3

# Ver resultado final
brain job get "$JOB_ID"
brain job history "$JOB_ID" --json
```

### Exemplo: Job com Ferramentas Faltando

```bash
# Criar job que requer ferramentas customizadas
JOB_ID=$(brain job create --ttl 3600 \
  --prompt "Criar pipeline de ML com ferramentas customizadas" \
  --context '{"tools_required":["ml-validator-cli","data-processor-cli"]}' \
  | grep -oP 'Job criado: \K[^ ]+')

# Verificar ferramentas
brain job tools "$JOB_ID"
# Saida: ✗ ml-validator-cli, ✗ data-processor-cli

# Criar job builder para construir CLIs
BUILDER_ID=$(brain job tools "$JOB_ID" --build-missing | \
  grep -oP 'Child job: \K[^ ]+')

echo "Builder job: $BUILDER_ID"

# [HAIKU] Constroi ferramentas
brain job iterate "$BUILDER_ID" --type execution --agent haiku \
  --result "Criadas CLIs em /root/.claude/cli/ml-validator-cli e /root/.claude/cli/data-processor-cli"

# [OPUS] Revisa CLIs
brain job iterate "$BUILDER_ID" --type review --agent opus \
  --result "APPROVED - CLIs prontas para producao"

# Marcar builder como completo
brain job status "$BUILDER_ID" --set completed

# Agora ferramentas estao disponiveis no job original
brain job tools "$JOB_ID"
# ✓ ml-validator-cli, ✓ data-processor-cli

# Continuar com job original
brain job iterate "$JOB_ID" --type execution --agent haiku \
  --result "Pipeline implementado usando CLIs recentemente construidas"
```

## Casos de Uso

### 1. Sessao de Trabalho Longa

Criar job para uma tarefa que vai durar varias horas:

```bash
brain job create --ttl 14400 \
  --prompt "Implementar sistema de notificacoes" \
  --skills python-pro-skill \
  --brain-query "websockets|vsl-analysis" \
  --brain-query "real-time notifications" \
  --files /root/vsl-analysis/notifications.py \
  --context '{"session":"afternoon","priority":"high"}'
```

### 2. Debug Rapido

Job de curta duracao para investigar um problema:

```bash
brain job create --ttl 300 \
  --prompt "Investigar erro de conexao Redis" \
  --skills python-pro-skill \
  --brain-query "redis errors|vsl-analysis" \
  --files /root/vsl-analysis/cache.py
```

### 3. Refatoracao

Job para refatoracao de codigo com multiplos arquivos:

```bash
brain job create --ttl 7200 \
  --prompt "Refatorar modulo de autenticacao" \
  --skills python-pro-skill \
  --brain-query "auth patterns" \
  --brain-query "security best practices" \
  --files /root/vsl-analysis/auth.py \
  --files /root/vsl-analysis/middleware.py \
  --context '{"type":"refactor","tests_required":true}'
```

### 4. Recovery Apos Memory Wipe

Se Claude perde memoria, pode recuperar o job:

```bash
# Listar jobs ativos
brain job list

# Recuperar job especifico
brain job get <job_id>

# Continuar trabalho com contexto do job
```

### 5. Distribuicao de Trabalho

Criar jobs para distribuir trabalho entre multiplas sessoes:

```bash
# Criar varios jobs
for task in task1 task2 task3; do
  brain job create --ttl 3600 \
    --prompt "Processar $task" \
    --context "{\"task\":\"$task\"}"
done

# Outra sessao pode pegar jobs da fila
brain job list --json | jq -r '.[0].job_id'
```

## TTL Recomendados

| Duracao | TTL (segundos) | Uso |
|---------|---------------|-----|
| 5 min   | 300           | Debug rapido, testes |
| 30 min  | 1800          | Tarefa curta |
| 1 hora  | 3600          | Tarefa media |
| 2 horas | 7200          | Sessao de trabalho |
| 4 horas | 14400         | Sessao longa |
| 1 dia   | 86400         | Job agendado |

## Integracao com Brain Workflow

Jobs podem ser usados junto com workflows:

```bash
# Iniciar workflow
brain workflow start "Implementar feature X" -p projeto

# Criar job para persistir contexto
brain job create --ttl 14400 \
  --prompt "$(brain workflow status | grep Goal | cut -d: -f2-)" \
  --brain-query "feature-x|projeto" \
  --context '{"workflow_id":"current"}'

# Apos memory wipe, recuperar de job
brain job list
brain job get <job_id>

# Continuar workflow
brain workflow resume
```

## API Python

Para uso em scripts:

```python
from scripts.memory.jobs import (
    create_job,
    get_job,
    list_jobs,
    delete_job,
    cleanup_jobs,
    get_job_count,
    iterate_job,
    get_job_history,
    update_job_status,
    check_cli_tools,
    create_cli_builder_job,
    get_missing_cli_tools,
)

# Criar job
job_id = create_job(
    ttl=3600,
    data={
        "prompt": "Implementar feature X",
        "skills": ["python-pro-skill"],
        "brain_queries": [
            {"query": "redis", "project": "vsl-analysis"}
        ],
        "files": ["/root/test.py"],
        "context": {"priority": "high", "tools_required": ["gdrive"]}
    }
)

# Recuperar job
job = get_job(job_id)
if job:
    print(f"Prompt: {job['data']['prompt']}")
    print(f"Status: {job['status']}")
    print(f"Iteracao: {job['iteration']}")
    print(f"Expira: {job['expires_at']}")

# Iterar job (adicionar execucao/revisao)
success = iterate_job(
    job_id=job_id,
    iteration_type='execution',  # ou 'review'
    agent='haiku',               # ou 'opus'
    result='Funcao implementada com sucesso'
)

# Ver historico
history = get_job_history(job_id, formatted=True)
for entry in history:
    print(f"[{entry['iteration']}] {entry['type']} by {entry['agent']}")
    print(f"  Result: {entry['result']}")

# Atualizar status
update_job_status(job_id, 'in_review')

# Verificar ferramentas
availability = check_cli_tools(['gdrive', 'missing-tool'])
for tool, available in availability.items():
    print(f"{tool}: {'OK' if available else 'MISSING'}")

# Obter ferramentas faltando
missing = get_missing_cli_tools(job_id)
if missing:
    # Criar job builder para construir CLIs
    builder_id = create_cli_builder_job(job_id, missing)
    print(f"Builder job criado: {builder_id}")

# Listar jobs
jobs = list_jobs()
for job in jobs:
    print(f"{job['job_id']}: {job['data']['prompt']} (status={job['status']})")

# Cleanup
removed = cleanup_jobs()
print(f"Removidos {removed} jobs expirados")

# Stats
stats = get_job_count(active_only=False)
print(f"Ativos: {stats['active']}, Expirados: {stats['expired']}")
```

## Testes

Executar suite de testes:

```bash
cd /root/claude-brain
python3 tests/test_jobs.py
```

Demonstracao interativa:

```bash
cd /root/claude-brain
./examples/job_queue_demo.sh
```

## Limitacoes

1. **TTL Minimo:** 1 segundo (recomendado: >= 60s)
2. **Nao ha fila de prioridade:** Jobs sao retornados por ordem de expiracao
3. **Sem locking:** Sistema nao previne multiplos agentes pegando o mesmo job
4. **Cleanup manual:** Se nunca chamar comandos job, expirados acumulam no banco

## Melhorias Futuras

- [x] Job Iterativo (tracking de execucoes, revisoes, status)
- [x] CLI Management (deteccao e builder de ferramentas)
- [x] Protocolo orquestrador completo (create → execute → review → iterate)
- [ ] Sistema de locks para prevenir duplicacao
- [ ] Fila de prioridade baseada em context.priority
- [ ] Job hooks (callbacks ao expirar/completar)
- [ ] Renovacao de TTL (extend job lifetime)
- [ ] Job templates para tipos comuns
- [ ] Integracao direta com brain workflow
- [ ] Job chaining (dependencies entre jobs)
- [ ] Webhook callbacks ao mudar status

## Troubleshooting

### Job nao aparece na lista

- Verifique se TTL nao expirou: `brain job get <job_id>`
- Use `--all` para ver expirados: `brain job list --all`

### Job expirou antes do esperado

- Verifique TTL configurado no get
- Cleanup automatico remove jobs ao listar

### Banco corrompido

```bash
# Recriar tabela jobs
python3 -c "
from scripts.memory.jobs import _init_jobs_table
_init_jobs_table()
print('Tabela recriada')
"
```

## Referencias

- **Backend:** `/root/claude-brain/scripts/memory/jobs.py`
  - Funcoes: create_job, get_job, list_jobs, iterate_job, get_job_history, update_job_status, check_cli_tools, create_cli_builder_job, get_missing_cli_tools
- **CLI:** `/root/claude-brain/scripts/cli/jobs.py`
  - Comandos: cmd_job, cmd_cli
- **Main CLI:** `/root/claude-brain/scripts/brain_cli.py`
  - Parser: brain job, brain cli
- **Testes:** `/root/claude-brain/tests/test_jobs.py`
- **Demo:** `/root/claude-brain/examples/job_queue_demo.sh`

## Status da Implementacao

### Completado (Sprint Atual)
- [x] Backend: iterate_job(), get_job_history(), update_job_status(), check_cli_tools()
- [x] CLI: brain job iterate, brain job history, brain job status
- [x] CLI: brain job tools, brain cli list
- [x] Integration: create_cli_builder_job(), get_missing_cli_tools()
- [x] Documentacao: Protocolo orquestrador completo

### Estrutura de Dados

```sql
-- Colunas adicionadas na tabela jobs
ALTER TABLE jobs ADD COLUMN iteration INTEGER DEFAULT 0;
ALTER TABLE jobs ADD COLUMN status TEXT DEFAULT 'pending';
ALTER TABLE jobs ADD COLUMN tools_required JSON DEFAULT '[]';
ALTER TABLE jobs ADD COLUMN history JSON DEFAULT '[]';
```

### Estados do Job

```
pending → executing → in_review → fixing → completed
         ↓                    ↓           ↓
         failed ←────────────┴───────────┘

Terminal states: completed, failed
```
