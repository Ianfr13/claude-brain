#!/usr/bin/env python3
"""
Claude Brain - Workflows Module

Sistema de contexto em 3 niveis para sessoes longas:
- Curto prazo: arquivos .md temporarios
- Medio prazo: tabela workflows no SQLite
- Longo prazo: insights salvos no brain

Fluxo:
1. brain workflow start → cria .md + entrada no DB
2. brain workflow update → salva em .md e SQLite
3. brain workflow resume → le .md apos memory wipe
4. brain workflow complete → extrai insights pro brain
"""

import json
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

from .base import get_db, DB_PATH

WORKFLOWS_DIR = DB_PATH.parent / "workflows"
WORKFLOWS_DIR.mkdir(exist_ok=True)


def _generate_workflow_id() -> str:
    """Gera ID unico de 8 caracteres para workflow"""
    return str(uuid.uuid4())[:8].lower()


def save_workflow(
    name: str,
    goal: str,
    project: Optional[str] = None,
    context: Optional[str] = None
) -> str:
    """Inicia novo workflow

    Retorna: workflow_id
    """
    workflow_id = _generate_workflow_id()

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            '''INSERT INTO workflows
               (workflow_id, name, project, goal, status, todos, insights, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''',
            (workflow_id, name, project, goal, "active", json.dumps([]), json.dumps([]))
        )

    # Cria diretorio de arquivos .md
    wf_dir = WORKFLOWS_DIR / workflow_id
    wf_dir.mkdir(exist_ok=True)

    # Gera arquivos iniciais
    _generate_markdown_files(workflow_id)

    return workflow_id


def get_workflow(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Recupera workflow do banco"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM workflows WHERE workflow_id = ?",
            (workflow_id,)
        )
        row = c.fetchone()
        if not row:
            return None

        # Converte Row para dict
        return dict(row)


def get_active_workflow() -> Optional[Dict[str, Any]]:
    """Retorna ultimo workflow ativo"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM workflows WHERE status = 'active' ORDER BY updated_at DESC LIMIT 1"
        )
        row = c.fetchone()
        if not row:
            return None
        return dict(row)


def list_workflows(status: Optional[str] = None, project: Optional[str] = None) -> List[Dict]:
    """Lista workflows com filtros opcionais"""
    with get_db() as conn:
        c = conn.cursor()

        query = "SELECT * FROM workflows WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if project:
            query += " AND project = ?"
            params.append(project)

        query += " ORDER BY updated_at DESC"

        c.execute(query, params)
        return [dict(row) for row in c.fetchall()]


def add_todo(workflow_id: str, item: str, priority: int = 2) -> int:
    """Adiciona TODO ao workflow

    Retorna: indice do TODO (para --done usar depois)
    """
    wf = get_workflow(workflow_id)
    if not wf:
        raise ValueError(f"Workflow {workflow_id} nao encontrado")

    todos = json.loads(wf["todos"] or "[]")
    todo_id = len(todos)

    todos.append({
        "id": todo_id,
        "item": item,
        "priority": priority,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    })

    _update_workflow_field(workflow_id, "todos", json.dumps(todos))
    _update_markdown_files(workflow_id)

    return todo_id


def complete_todo(workflow_id: str, todo_id: int) -> bool:
    """Marca TODO como concluido"""
    wf = get_workflow(workflow_id)
    if not wf:
        return False

    todos = json.loads(wf["todos"] or "[]")

    for todo in todos:
        if todo["id"] == todo_id:
            todo["status"] = "done"
            todo["completed_at"] = datetime.now().isoformat()
            break

    _update_workflow_field(workflow_id, "todos", json.dumps(todos))
    _update_markdown_files(workflow_id)
    return True


def add_insight(workflow_id: str, text: str) -> bool:
    """Adiciona insight ao workflow"""
    wf = get_workflow(workflow_id)
    if not wf:
        return False

    insights = json.loads(wf["insights"] or "[]")

    insights.append({
        "text": text,
        "created_at": datetime.now().isoformat()
    })

    _update_workflow_field(workflow_id, "insights", json.dumps(insights))
    _update_markdown_files(workflow_id)
    return True


def add_file(workflow_id: str, filepath: str) -> bool:
    """Registra arquivo modificado"""
    wf = get_workflow(workflow_id)
    if not wf:
        return False

    files = json.loads(wf["files_modified"] or "[]")

    if filepath not in files:
        files.append(filepath)

    _update_workflow_field(workflow_id, "files_modified", json.dumps(files))
    _update_markdown_files(workflow_id)
    return True


def complete_workflow(workflow_id: str, summary: Optional[str] = None) -> bool:
    """Finaliza workflow

    - Marca como completed
    - Extrai insights pro brain (futuro)
    - Arquiva .md
    """
    wf = get_workflow(workflow_id)
    if not wf:
        return False

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            '''UPDATE workflows
               SET status = ?, summary = ?, completed_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE workflow_id = ?
            ''',
            ("completed", summary or "", workflow_id)
        )

    # TODO: Extrai insights -> save_memory()
    # TODO: Arquiva arquivos .md

    return True


def _update_workflow_field(workflow_id: str, field: str, value: str) -> None:
    """Atualiza campo especifico do workflow"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            f"UPDATE workflows SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE workflow_id = ?",
            (value, workflow_id)
        )


def _generate_markdown_files(workflow_id: str) -> None:
    """Gera arquivos .md iniciais"""
    wf = get_workflow(workflow_id)
    if not wf:
        return

    wf_dir = WORKFLOWS_DIR / workflow_id

    # context.md
    context_md = f"""# Tarefa: {wf['name']}
Workflow ID: {wf['workflow_id']}
Projeto: {wf['project'] or 'N/A'}
Iniciado: {wf['created_at']}

## Objetivo
{wf['goal']}

## Arquivos Modificados
(nenhum ainda)
"""

    (wf_dir / "context.md").write_text(context_md)

    # todos.md
    todos_md = "# TODOs\n"
    (wf_dir / "todos.md").write_text(todos_md)

    # insights.md
    insights_md = "# Insights\n(nenhum ainda)\n"
    (wf_dir / "insights.md").write_text(insights_md)


def _update_markdown_files(workflow_id: str) -> None:
    """Atualiza arquivos .md com dados atuais"""
    wf = get_workflow(workflow_id)
    if not wf:
        return

    wf_dir = WORKFLOWS_DIR / workflow_id

    # Atualiza todos.md
    todos = json.loads(wf["todos"] or "[]")
    todos_md = "# TODOs\n\n"

    for todo in todos:
        check = "x" if todo["status"] == "done" else " "
        todos_md += f"- [{check}] #{todo['id']} ({todo['priority']}) {todo['item']}\n"

    (wf_dir / "todos.md").write_text(todos_md)

    # Atualiza insights.md
    insights = json.loads(wf["insights"] or "[]")
    insights_md = "# Insights\n\n"

    for insight in insights:
        insights_md += f"- {insight['text']}\n"

    (wf_dir / "insights.md").write_text(insights_md)

    # Atualiza context.md com arquivos
    files = json.loads(wf["files_modified"] or "[]")
    files_section = "\n".join(f"- {f}" for f in files) if files else "(nenhum)"

    context_md = f"""# Tarefa: {wf['name']}
Workflow ID: {wf['workflow_id']}
Projeto: {wf['project'] or 'N/A'}
Iniciado: {wf['created_at']}

## Objetivo
{wf['goal']}

## Arquivos Modificados
{files_section}

## Progresso
TODOs: {len([t for t in todos if t['status'] == 'done'])}/{len(todos)} concluidos
Insights: {len(insights)}
"""

    (wf_dir / "context.md").write_text(context_md)


def read_workflow_context(workflow_id: str) -> str:
    """Retorna contexto formatado para Claude ler apos resume"""
    wf = get_workflow(workflow_id)
    if not wf:
        return ""

    wf_dir = WORKFLOWS_DIR / workflow_id

    # Le os 3 arquivos
    context_md = (wf_dir / "context.md").read_text() if (wf_dir / "context.md").exists() else ""
    todos_md = (wf_dir / "todos.md").read_text() if (wf_dir / "todos.md").exists() else ""
    insights_md = (wf_dir / "insights.md").read_text() if (wf_dir / "insights.md").exists() else ""

    return f"""
=== WORKFLOW RESUMIDO ===

{context_md}

{todos_md}

{insights_md}
"""
