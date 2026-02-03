# Job Queue - Sistema de Sub-Tasks Distribuído

## Visão Geral

Sistema de fila de jobs com suporte para execução distribuída de sub-tasks. Permite buscar/validar múltiplos endpoints ou arquivos em paralelo, consolidando resultados.

### Tipos de Jobs

1. **normal** - Job simples, execução linear
2. **distributed_search** - Job com múltiplas sub-tasks paralelas

## Schema Database

```sql
-- Tabela jobs estendida
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    ttl INTEGER,
    expires_at TIMESTAMP,
    data JSON,

    iteration INTEGER,
    status TEXT,
    tools_required JSON,
    history JSON,

    -- NOVO: Sub-tasks distribuído
    type TEXT DEFAULT 'normal',
    sub_tasks JSON DEFAULT '[]',
    consolidated_result JSON DEFAULT 'null'
)
```

### Campos Novos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `type` | TEXT | 'normal' ou 'distributed_search' |
| `sub_tasks` | JSON | Array de sub-tasks |
| `consolidated_result` | JSON | Resultado final consolidado |

## Sub-Task Structure

```json
{
  "sub_task_id": "sub_1",
  "query": "Buscar endpoints",
  "agent_id": null,
  "status": "pending",
  "result": null
}
```

### Campos Sub-Task

| Campo | Tipo | Valores | Descrição |
|-------|------|--------|-----------|
| `sub_task_id` | string | "sub_N" | ID único da sub-task |
| `query` | string | texto | Descrição/query da busca |
| `agent_id` | string | null | ID do agente executando |
| `status` | enum | pending, running, completed, failed | Estado atual |
| `result` | string | null | Resultado (max 200 chars) |

## Comandos CLI

### 1. Criar Job Distribuído

```bash
brain job create --distributed --ttl 60 \
  --prompt "Busca paralela" \
  --subtask 'GET /api/users' \
  --subtask 'GET /api/posts' \
  --subtask 'GET /api/comments'
```

**Retorna:** `job_id`

### 2. Listar Sub-Tasks

```bash
brain job subtasks <job_id>
brain job subtasks <job_id> --json
```

**Output:**
```
Sub-tasks do job abc123:

  ○ sub_1: GET /api/users
  ◉ sub_2: GET /api/posts
      Agent: agent_haiku
  ✓ sub_3: GET /api/comments
      Resultado: [200 OK] 5 items
```

### 3. Disparar Workers

```bash
brain job dispatch <job_id>
brain job dispatch <job_id> --model haiku
```

**Comportamento:**
- Cria Task com `run_in_background=True` para cada sub-task
- Atualiza status para "running"
- Prompt: "Busque {query} em {file}. Retorne APENAS resultado (max 200 chars)"
- Retorna ao usuário imediatamente (background)

### 4. Consolidar Resultados

```bash
brain job consolidate <job_id>
brain job consolidate <job_id> --json
```

**Retorna:**
```json
{
  "job_id": "abc123",
  "total_tasks": 3,
  "completed": 2,
  "failed": 1,
  "results": [
    {
      "sub_task_id": "sub_1",
      "query": "GET /api/users",
      "status": "completed",
      "result": "[200 OK] 5 users"
    },
    ...
  ],
  "consolidated_at": "2025-02-03T10:30:45"
}
```

## Fluxo Completo

### 1. Criar Job com Sub-Tasks

```bash
job_id=$(brain job create --distributed --ttl 300 \
  --prompt "Validar endpoints" \
  --subtask "GET /health" \
  --subtask "POST /auth" \
  --subtask "GET /users" | grep -oP "job_\K\w+")
```

### 2. Disparar Execução

```bash
brain job dispatch $job_id
```

Worker inicia em background para cada sub-task.

### 3. Monitorar Progresso

```bash
brain job subtasks $job_id
```

Output mostra status em tempo real:
- `○` = pending
- `◉` = running
- `✓` = completed
- `✗` = failed

### 4. Consolidar

```bash
result=$(brain job consolidate $job_id --json)
echo $result | jq '.results | map(select(.status == "completed")) | length'
```

## Implementação em Python

### Criar Job Distribuído

```python
from scripts.memory.jobs import create_job_with_subtasks

job_id = create_job_with_subtasks(
    ttl=3600,
    data={
        "prompt": "Busca paralela",
        "skills": ["python-pro-skill"]
    },
    subtasks=[
        "Buscar users no BD",
        "Buscar posts no BD",
        "Buscar comments no BD"
    ]
)
```

### Atualizar Sub-Task

```python
from scripts.memory.jobs import update_subtask_status

update_subtask_status(
    job_id="abc123",
    sub_task_id="sub_1",
    status="completed",
    result="Encontrados 42 users",
    agent_id="agent_haiku_001"
)
```

### Consolidar Resultados

```python
from scripts.memory.jobs import consolidate_subtask_results

result = consolidate_subtask_results(job_id="abc123")
# result é um dict com todos os resultados consolidados
```

## Performance

### Vantagens

- ✅ Execução paralela (todos sub-tasks ao mesmo tempo)
- ✅ Isolamento (falha em um não afeta outros)
- ✅ Background (chat não fica bloqueado)
- ✅ Monitorável (status em tempo real)
- ✅ Consolidável (resultado único final)

### TTLs Recomendados

- **Busca rápida**: 60s
- **Validação**: 300s (5min)
- **Agregação**: 600s (10min)
- **Processamento pesado**: 1800s (30min)

## Segurança

- ✅ Path traversal prevention (sub_task_id validado)
- ✅ Query size limit (max 500 chars)
- ✅ Result truncation (max 200 chars)
- ✅ Atomic updates (sem race conditions)
- ✅ TTL expiration (auto-cleanup)

---

**Última atualização:** 03/02/2025
**Status:** ✅ Production Ready
