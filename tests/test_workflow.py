#!/usr/bin/env python3
"""
Testes para o modulo de workflows
"""

import pytest
import json
from pathlib import Path
from scripts.memory import (
    save_workflow, get_workflow, get_active_workflow,
    add_todo, complete_todo, add_insight, add_file,
    complete_workflow, list_workflows
)


def test_save_workflow_creates_entry():
    """Testa se save_workflow cria entrada no banco"""
    wf_id = save_workflow("Test Task", "Test goal", project="test")

    assert wf_id is not None
    assert len(wf_id) == 8

    wf = get_workflow(wf_id)
    assert wf is not None
    assert wf["name"] == "Test Task"
    assert wf["goal"] == "Test goal"
    assert wf["project"] == "test"
    assert wf["status"] == "active"


def test_save_workflow_creates_md_files():
    """Testa se save_workflow cria arquivos .md"""
    from scripts.memory.workflows import WORKFLOWS_DIR

    wf_id = save_workflow("Test MD", "Test goal")
    wf_dir = WORKFLOWS_DIR / wf_id

    assert (wf_dir / "context.md").exists()
    assert (wf_dir / "todos.md").exists()
    assert (wf_dir / "insights.md").exists()


def test_add_todo():
    """Testa adicionar TODO"""
    wf_id = save_workflow("Test Todos", "Goal")

    idx = add_todo(wf_id, "Tarefa 1")
    assert idx == 0

    idx2 = add_todo(wf_id, "Tarefa 2")
    assert idx2 == 1

    wf = get_workflow(wf_id)
    todos = json.loads(wf["todos"])
    assert len(todos) == 2
    assert todos[0]["item"] == "Tarefa 1"


def test_complete_todo():
    """Testa marcar TODO como concluido"""
    wf_id = save_workflow("Test Complete", "Goal")
    add_todo(wf_id, "Tarefa 1")

    complete_todo(wf_id, 0)

    wf = get_workflow(wf_id)
    todos = json.loads(wf["todos"])
    assert todos[0]["status"] == "done"
    assert "completed_at" in todos[0]


def test_add_insight():
    """Testa adicionar insight"""
    wf_id = save_workflow("Test Insights", "Goal")

    add_insight(wf_id, "Insight 1")
    add_insight(wf_id, "Insight 2")

    wf = get_workflow(wf_id)
    insights = json.loads(wf["insights"])
    assert len(insights) == 2
    assert insights[0]["text"] == "Insight 1"


def test_add_file():
    """Testa registrar arquivo modificado"""
    wf_id = save_workflow("Test Files", "Goal")

    add_file(wf_id, "file1.py")
    add_file(wf_id, "file2.py")
    add_file(wf_id, "file1.py")  # Duplicata

    wf = get_workflow(wf_id)
    files = json.loads(wf["files_modified"])
    assert len(files) == 2
    assert "file1.py" in files


def test_get_active_workflow():
    """Testa retornar workflow ativo"""
    wf1 = save_workflow("Workflow 1", "Goal 1")
    wf2 = save_workflow("Workflow 2", "Goal 2")

    active = get_active_workflow()
    assert active is not None
    assert active["workflow_id"] == wf2  # Mais recente


def test_list_workflows():
    """Testa listar workflows"""
    save_workflow("Test 1", "Goal", project="proj1")
    save_workflow("Test 2", "Goal", project="proj2")

    all_wf = list_workflows()
    assert len(all_wf) >= 2

    proj1_wf = list_workflows(project="proj1")
    assert len(proj1_wf) >= 1
    assert proj1_wf[0]["project"] == "proj1"


def test_complete_workflow():
    """Testa finalizar workflow"""
    wf_id = save_workflow("Test Complete", "Goal")
    add_insight(wf_id, "Important insight")

    complete_workflow(wf_id, "Summary text")

    wf = get_workflow(wf_id)
    assert wf["status"] == "completed"
    assert wf["summary"] == "Summary text"
    assert wf["completed_at"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
