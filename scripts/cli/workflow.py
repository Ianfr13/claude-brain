#!/usr/bin/env python3
"""
Claude Brain CLI - Workflow Commands

Comandos:
- brain workflow start "nome" -p projeto
- brain workflow update --todo/--done/--insight/--file
- brain workflow resume
- brain workflow complete
- brain workflow status
- brain workflow list
- brain workflow show <id>
"""

from .base import Colors, c, print_header, print_success, print_error, print_info
from scripts.memory import (
    save_workflow, get_workflow, get_active_workflow, list_workflows,
    add_todo, complete_todo, add_insight, add_file, complete_workflow,
    read_workflow_context
)


def cmd_workflow(args):
    """Dispatcher de comandos workflow"""
    action = args.action

    if action == "start":
        cmd_workflow_start(args)
    elif action == "update":
        cmd_workflow_update(args)
    elif action == "resume":
        cmd_workflow_resume(args)
    elif action == "complete":
        cmd_workflow_complete(args)
    elif action == "status":
        cmd_workflow_status(args)
    elif action == "list":
        cmd_workflow_list(args)
    elif action == "show":
        cmd_workflow_show(args)
    else:
        print_error(f"Acao desconhecida: {action}")


def cmd_workflow_start(args):
    """Inicia novo workflow"""
    name = " ".join(args.name) if args.name else None
    if not name:
        print_error("Uso: brain workflow start <nome> [-p projeto] [-g goal]")
        return

    project = args.project
    goal = args.goal or name

    wf_id = save_workflow(name, goal, project)

    print_success(f"Workflow iniciado: {c(wf_id, Colors.YELLOW)}")
    print_info(f"Arquivos em: memory/workflows/{wf_id}/")


def cmd_workflow_update(args):
    """Atualiza workflow ativo"""
    wf = get_active_workflow()
    if not wf:
        print_error("Nenhum workflow ativo. Use: brain workflow start")
        return

    wf_id = wf["workflow_id"]
    updated = False

    if args.todo:
        todo_item = args.todo
        idx = add_todo(wf_id, todo_item)
        print_success(f"TODO adicionado: #{idx} {todo_item}")
        updated = True

    if args.done:
        todo_id = int(args.done)
        if complete_todo(wf_id, todo_id):
            print_success(f"TODO #{todo_id} marcado como concluido")
            updated = True
        else:
            print_error(f"TODO #{todo_id} nao encontrado")

    if args.insight:
        add_insight(wf_id, args.insight)
        print_success(f"Insight adicionado: {args.insight}")
        updated = True

    if args.file:
        add_file(wf_id, args.file)
        print_success(f"Arquivo registrado: {args.file}")
        updated = True

    if not updated:
        # Se nenhuma acao, mostra status
        cmd_workflow_status(args)


def cmd_workflow_resume(args):
    """Resumir workflow apos memory wipe"""
    wf_id = args.id if hasattr(args, 'id') and args.id else None

    if not wf_id:
        wf = get_active_workflow()
        if wf:
            wf_id = wf["workflow_id"]

    if not wf_id:
        print_error("Nenhum workflow ativo. Use: brain workflow start")
        return

    context = read_workflow_context(wf_id)
    print(context)


def cmd_workflow_complete(args):
    """Finaliza workflow"""
    wf = get_active_workflow()
    if not wf:
        print_error("Nenhum workflow ativo")
        return

    wf_id = wf["workflow_id"]
    summary = args.summary or ""

    if complete_workflow(wf_id, summary):
        print_success(f"Workflow concluido: {wf['name']}")
        if summary:
            print_info(f"Resumo: {summary}")
    else:
        print_error("Erro ao completar workflow")


def cmd_workflow_status(args):
    """Mostra status do workflow ativo"""
    wf = get_active_workflow()
    if not wf:
        print_info("Nenhum workflow ativo")
        return

    import json
    todos = json.loads(wf["todos"] or "[]")
    insights = json.loads(wf["insights"] or "[]")
    files = json.loads(wf["files_modified"] or "[]")

    done_count = len([t for t in todos if t["status"] == "done"])

    print_header(f"Workflow: {wf['name']}")
    print(f"ID: {c(wf['workflow_id'], Colors.YELLOW)}")
    if wf["project"]:
        print(f"Projeto: {wf['project']}")

    print(f"\n{c('Objetivo:', Colors.CYAN)} {wf['goal']}")
    print(f"\n{c('Progresso:', Colors.CYAN)}")
    print(f"  TODOs: {done_count}/{len(todos)} concluidos")
    print(f"  Insights: {len(insights)}")
    print(f"  Arquivos: {len(files)}")

    if todos:
        print(f"\n{c('Proximos TODOs:', Colors.CYAN)}")
        for todo in todos[:3]:
            check = "x" if todo["status"] == "done" else " "
            print(f"  [{check}] #{todo['id']} {todo['item']}")

    if insights:
        print(f"\n{c('Ultimos Insights:', Colors.CYAN)}")
        for insight in insights[-2:]:
            print(f"  - {insight['text']}")


def cmd_workflow_list(args):
    """Lista workflows"""
    status = args.status if hasattr(args, 'status') else None
    project = args.project if hasattr(args, 'project') else None

    workflows = list_workflows(status=status, project=project)

    if not workflows:
        print_info("Nenhum workflow encontrado")
        return

    print_header("Workflows")
    for wf in workflows:
        status_color = Colors.GREEN if wf["status"] == "completed" else Colors.YELLOW
        print(
            f"{c(wf['workflow_id'], Colors.CYAN)} - "
            f"{wf['name']} "
            f"[{c(wf['status'], status_color)}]"
        )
        if wf["project"]:
            print(f"  Projeto: {wf['project']}")


def cmd_workflow_show(args):
    """Mostra detalhes de um workflow anterior"""
    if not args.name:
        print_error("Uso: brain workflow show <workflow_id>")
        return

    wf_id = " ".join(args.name)
    wf = get_workflow(wf_id)

    if not wf:
        print_error(f"Workflow {wf_id} nao encontrado")
        return

    import json
    todos = json.loads(wf["todos"] or "[]")
    insights = json.loads(wf["insights"] or "[]")

    print_header(wf["name"])
    print(f"ID: {wf['workflow_id']}")
    if wf["project"]:
        print(f"Projeto: {wf['project']}")

    print(f"\nStatus: {wf['status']}")
    print(f"Criado: {wf['created_at']}")
    if wf["completed_at"]:
        print(f"Concluido: {wf['completed_at']}")

    if wf["summary"]:
        print(f"\nResumo: {wf['summary']}")

    print(f"\nTODOs: {len([t for t in todos if t['status'] == 'done'])}/{len(todos)}")
    print(f"Insights: {len(insights)}")
