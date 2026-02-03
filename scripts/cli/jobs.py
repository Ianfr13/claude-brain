#!/usr/bin/env python3
"""
Claude Brain - CLI Module: Job Queue

Comandos para gerenciar fila de jobs com TTL.

Comandos implementados:
- brain job create --ttl 60 --data '{"prompt":"..."}'
- brain job get <job_id>
- brain job list [--all]
- brain job cleanup
- brain job delete <job_id>
- brain job stats

Uso interno:
    from scripts.cli.jobs import cmd_job
"""

import json
import sys
from datetime import datetime

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

from .base import Colors, c, print_success, print_error, print_info


def _format_timestamp(ts_str: str) -> str:
    """Formata timestamp ISO para exibicao legivel.

    Args:
        ts_str: Timestamp em formato ISO (YYYY-MM-DDTHH:MM:SS)

    Returns:
        String formatada (DD/MM HH:MM)
    """
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return ts_str


def _format_ttl(seconds: int) -> str:
    """Formata TTL para exibicao legivel.

    Args:
        seconds: TTL em segundos

    Returns:
        String formatada (ex: "1h 30m", "45s")
    """
    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"

    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"

    return f"{hours}h"


def _print_job(job: dict, verbose: bool = False):
    """Imprime um job formatado.

    Args:
        job: Dicionario com job completo
        verbose: Se True, mostra todos os detalhes
    """
    data = job["data"]

    print(c(f"\n[{job['job_id']}]", Colors.BOLD))
    print(c(f"  Criado:  ", Colors.DIM) + _format_timestamp(job["created_at"]))
    print(c(f"  Expira:  ", Colors.DIM) + _format_timestamp(job["expires_at"]) + c(f" (TTL: {_format_ttl(job['ttl'])})", Colors.DIM))
    print(c(f"  Prompt:  ", Colors.DIM) + data["prompt"])

    if verbose:
        if data.get("skills"):
            print(c(f"  Skills:  ", Colors.DIM) + ", ".join(data["skills"]))

        if data.get("brain_queries"):
            print(c(f"  Brain:   ", Colors.DIM))
            for q in data["brain_queries"]:
                proj = f" (-p {q['project']})" if q.get("project") else ""
                print(c(f"    - {q['query']}{proj}", Colors.DIM))

        if data.get("files"):
            print(c(f"  Files:   ", Colors.DIM))
            for f in data["files"]:
                print(c(f"    - {f}", Colors.DIM))

        if data.get("context"):
            print(c(f"  Context: ", Colors.DIM) + json.dumps(data["context"], indent=2))


def cmd_job_create(args):
    """Cria um novo job.

    Uso:
        brain job create --ttl 60 --data '{"prompt":"Implementar X"}'
        brain job create --ttl 3600 --prompt "Implementar X" --skills python-pro-skill
    """
    # Suporta dois modos:
    # 1. --data com JSON completo
    # 2. --prompt + flags individuais (mais conveniente)

    if hasattr(args, 'data') and args.data:
        # Modo 1: JSON completo
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as e:
            print_error(f"JSON invalido em --data: {e}")
            sys.exit(1)
    else:
        # Modo 2: Flags individuais
        if not hasattr(args, 'prompt') or not args.prompt:
            print_error("Obrigatorio: --data ou --prompt")
            sys.exit(1)

        data = {"prompt": " ".join(args.prompt) if isinstance(args.prompt, list) else args.prompt}

        if hasattr(args, 'skills') and args.skills:
            skills = args.skills if isinstance(args.skills, list) else [args.skills]
            data["skills"] = skills

        if hasattr(args, 'brain_query') and args.brain_query:
            queries = []
            for q in (args.brain_query if isinstance(args.brain_query, list) else [args.brain_query]):
                parts = q.split("|")
                query = {"query": parts[0]}
                if len(parts) > 1:
                    query["project"] = parts[1]
                queries.append(query)
            data["brain_queries"] = queries

        if hasattr(args, 'files') and args.files:
            data["files"] = args.files if isinstance(args.files, list) else [args.files]

        if hasattr(args, 'context') and args.context:
            try:
                data["context"] = json.loads(args.context)
            except json.JSONDecodeError:
                print_error("JSON invalido em --context")
                sys.exit(1)

    try:
        job_id = create_job(ttl=args.ttl, data=data)
        print_success(f"Job criado: {job_id}")
        print_info(f"TTL: {_format_ttl(args.ttl)}")
        print_info(f"Expira: {_format_timestamp((datetime.now().timestamp() + args.ttl).__str__())}")
    except Exception as e:
        print_error(f"Erro ao criar job: {e}")
        sys.exit(1)


def cmd_job_get(args):
    """Recupera um job pelo ID.

    Uso:
        brain job get <job_id>
        brain job get <job_id> --json
    """
    if not args.job_id:
        print_error("Obrigatorio: job_id")
        sys.exit(1)

    job = get_job(args.job_id)

    if not job:
        print_error(f"Job nao encontrado ou expirado: {args.job_id}")
        sys.exit(1)

    if hasattr(args, 'json') and args.json:
        # Modo JSON (para parsing automatico)
        print(json.dumps(job, indent=2))
    else:
        # Modo legivel
        _print_job(job, verbose=True)


def cmd_job_list(args):
    """Lista jobs ativos (ou todos).

    Uso:
        brain job list
        brain job list --all
        brain job list --json
    """
    include_expired = hasattr(args, 'all') and args.all
    jobs = list_jobs(include_expired=include_expired)

    if not jobs:
        print_info("Nenhum job na fila")
        return

    if hasattr(args, 'json') and args.json:
        # Modo JSON
        print(json.dumps(jobs, indent=2))
    else:
        # Modo legivel
        print(c(f"\n{len(jobs)} job(s) na fila:\n", Colors.BOLD))
        for job in jobs:
            _print_job(job, verbose=False)
        print()


def cmd_job_cleanup(args):
    """Remove jobs expirados.

    Uso:
        brain job cleanup
    """
    removed = cleanup_jobs()

    if removed > 0:
        print_success(f"{removed} job(s) expirado(s) removido(s)")
    else:
        print_info("Nenhum job expirado")


def cmd_job_delete(args):
    """Deleta um job manualmente.

    Uso:
        brain job delete <job_id>
    """
    if not args.job_id:
        print_error("Obrigatorio: job_id")
        sys.exit(1)

    deleted = delete_job(args.job_id)

    if deleted:
        print_success(f"Job deletado: {args.job_id}")
    else:
        print_error(f"Job nao encontrado: {args.job_id}")
        sys.exit(1)


def cmd_job_stats(args):
    """Mostra estatisticas de jobs.

    Uso:
        brain job stats
        brain job stats --all
    """
    active_only = not (hasattr(args, 'all') and args.all)
    stats = get_job_count(active_only=active_only)

    print(c("\nEstatisticas de Jobs:", Colors.BOLD))

    if active_only:
        print(c(f"  Jobs ativos: ", Colors.DIM) + str(stats["total"]))
    else:
        print(c(f"  Jobs ativos: ", Colors.DIM) + str(stats["active"]))
        print(c(f"  Jobs expirados: ", Colors.DIM) + str(stats["expired"]))
        print(c(f"  Total: ", Colors.DIM) + str(stats["total"]))

    print()


def cmd_job_iterate(args):
    """Itera um job - adiciona ao histórico e muda status.

    Uso:
        brain job iterate <job_id> --type execution --agent haiku --result "Resultado..."
        brain job iterate <job_id> --type review --agent opus --result "Review..."
    """
    if not args.job_id:
        print_error("Obrigatorio: job_id")
        sys.exit(1)

    if not (hasattr(args, 'type') and args.type):
        print_error("Obrigatorio: --type (execution ou review)")
        sys.exit(1)

    if not (hasattr(args, 'agent') and args.agent):
        print_error("Obrigatorio: --agent (haiku ou opus)")
        sys.exit(1)

    if not (hasattr(args, 'result') and args.result):
        print_error("Obrigatorio: --result")
        sys.exit(1)

    try:
        success = iterate_job(
            job_id=args.job_id,
            iteration_type=args.type,
            agent=args.agent,
            result=args.result
        )

        if success:
            job = get_job(args.job_id)
            print_success(f"Job iterado: {args.job_id}")
            print_info(f"Iteracao: {job['iteration']}")
            print_info(f"Status: {job['status']}")
        else:
            print_error(f"Job nao encontrado ou em estado terminal: {args.job_id}")
            sys.exit(1)

    except ValueError as e:
        print_error(str(e))
        sys.exit(1)


def cmd_job_history(args):
    """Exibe histórico de iteracoes de um job.

    Uso:
        brain job history <job_id>
        brain job history <job_id> --json
    """
    if not args.job_id:
        print_error("Obrigatorio: job_id")
        sys.exit(1)

    history = get_job_history(args.job_id, formatted=not (hasattr(args, 'json') and args.json))

    if history is None:
        print_error(f"Job nao encontrado: {args.job_id}")
        sys.exit(1)

    if not history:
        print_info("Nenhuma iteracao neste job ainda")
        return

    if hasattr(args, 'json') and args.json:
        # Modo JSON
        print(json.dumps(history, indent=2))
    else:
        # Modo legivel
        print(c(f"\nHistorico do job {args.job_id}:", Colors.BOLD))
        print(c("(ultimas iteracoes primeiro)\n", Colors.DIM))

        for entry in reversed(history):
            iteration_num = entry.get('iteration', '?')
            entry_type = entry.get('type', 'unknown')
            agent = entry.get('agent', 'unknown')
            timestamp = entry.get('timestamp', '?')

            print(c(f"  [{iteration_num}] ", Colors.BOLD) + c(f"{entry_type}", Colors.CYAN) + c(f" @ {timestamp}", Colors.DIM))
            print(c(f"      Agente: ", Colors.DIM) + agent)
            print(c(f"      Resultado: ", Colors.DIM) + entry.get('result', '(vazio)')[:100] + "...")
            print()


def cmd_job_status(args):
    """Exibe ou atualiza status de um job.

    Uso:
        brain job status <job_id>
        brain job status <job_id> --set completed
        brain job status <job_id> --set in_review
    """
    if not args.job_id:
        print_error("Obrigatorio: job_id")
        sys.exit(1)

    job = get_job(args.job_id)
    if not job:
        print_error(f"Job nao encontrado: {args.job_id}")
        sys.exit(1)

    # Modo leitura
    if not (hasattr(args, 'set') and args.set):
        print(c(f"\nJob: {args.job_id}", Colors.BOLD))
        print(c(f"  Status: ", Colors.DIM) + job['status'])
        print(c(f"  Iteracoes: ", Colors.DIM) + str(job['iteration']))
        print(c(f"  Criado: ", Colors.DIM) + _format_timestamp(job['created_at']))
        print(c(f"  Expira: ", Colors.DIM) + _format_timestamp(job['expires_at']))
        if job['tools_required']:
            print(c(f"  Tools: ", Colors.DIM) + ", ".join(job['tools_required']))
        print()
        return

    # Modo escrita - atualizar status
    try:
        success = update_job_status(args.job_id, args.set)
        if success:
            print_success(f"Status atualizado: {job['status']} -> {args.set}")
        else:
            print_error(f"Transicao invalida: {job['status']} -> {args.set}")
            sys.exit(1)
    except ValueError as e:
        print_error(str(e))
        sys.exit(1)


def cmd_cli_list(args):
    """Lista CLIs disponibles em .claude/cli/.

    Uso:
        brain cli list
        brain cli list --json
    """
    from pathlib import Path

    cli_dir = Path.home() / '.claude' / 'cli'

    if not cli_dir.exists():
        print_info(f"Diretorio nao existe: {cli_dir}")
        return

    # Escaneia diretorio
    cli_tools = []
    for item in sorted(cli_dir.iterdir()):
        if item.is_dir():
            # Verifica se tem setup.py, package.json, etc
            has_setup = (item / 'setup.py').exists()
            has_package = (item / 'package.json').exists()
            has_main = any((item / name).exists() for name in ['main.py', 'index.js', '__main__.py'])

            tool_info = {
                'name': item.name,
                'path': str(item),
                'has_setup': has_setup,
                'has_package': has_package,
                'has_main': has_main,
            }
            cli_tools.append(tool_info)

    if not cli_tools:
        print_info("Nenhum CLI encontrado em .claude/cli/")
        return

    if hasattr(args, 'json') and args.json:
        # Modo JSON
        print(json.dumps(cli_tools, indent=2))
    else:
        # Modo legivel
        print(c(f"\n{len(cli_tools)} CLI(s) disponivel(is):\n", Colors.BOLD))
        for tool in cli_tools:
            status = ""
            if tool['has_setup']:
                status += " [Python]"
            if tool['has_package']:
                status += " [Node.js]"
            print(c(f"  {tool['name']}", Colors.CYAN) + c(status, Colors.DIM))
        print()


def cmd_job_tools(args):
    """Verifica status das ferramentas CLI requeridas por um job.

    Uso:
        brain job tools <job_id>
        brain job tools <job_id> --json
        brain job tools <job_id> --build-missing
    """
    if not args.job_id:
        print_error("Obrigatorio: job_id")
        sys.exit(1)

    job = get_job(args.job_id)
    if not job:
        print_error(f"Job nao encontrado: {args.job_id}")
        sys.exit(1)

    tools_required = job.get('tools_required', [])

    if not tools_required:
        print_info(f"Job {args.job_id} nao requer ferramentas")
        return

    # Verifica disponibilidade
    availability = check_cli_tools(tools_required)
    missing = [tool for tool, available in availability.items() if not available]

    if hasattr(args, 'json') and args.json:
        # Modo JSON
        print(json.dumps(availability, indent=2))
    else:
        # Modo legivel
        all_available = all(availability.values())

        print(c(f"\nFerramentas requeridas por {args.job_id}:\n", Colors.BOLD))
        for tool_name, available in availability.items():
            status_icon = c("✓", Colors.GREEN) if available else c("✗", Colors.RED)
            status_text = c("disponivel", Colors.GREEN) if available else c("nao encontrada", Colors.RED)
            print(f"  {status_icon} {tool_name}: {status_text}")

        print()

        if not all_available:
            if hasattr(args, 'build_missing') and args.build_missing:
                # Criar job filho para construir CLIs
                try:
                    child_job_id = create_cli_builder_job(args.job_id, missing)
                    print_success(f"Job builder criado para construir {len(missing)} CLI(s)")
                    print_info(f"Child job: {child_job_id}")
                    print_info(f"Monitorar com: brain job status {child_job_id}")
                except Exception as e:
                    print_error(f"Erro ao criar job builder: {e}")
                    sys.exit(1)
            else:
                print_error(f"Faltam {len(missing)} ferramentas: {', '.join(missing)}")
                print_info("Use --build-missing para criar job builder automatico")
        else:
            print_success("Todas ferramentas sao disponibles")


def cmd_job(args):
    """Dispatcher para subcomandos de job.

    Comandos:
    - create: Cria job
    - get: Recupera job
    - list: Lista jobs
    - cleanup: Remove expirados
    - delete: Deleta job
    - stats: Estatisticas
    - iterate: Itera job (adiciona ao historico)
    - history: Exibe historico de iteracoes
    - status: Exibe/atualiza status
    - tools: Verifica ferramentas requeridas
    """
    subcommands = {
        "create": cmd_job_create,
        "get": cmd_job_get,
        "list": cmd_job_list,
        "cleanup": cmd_job_cleanup,
        "delete": cmd_job_delete,
        "stats": cmd_job_stats,
        "iterate": cmd_job_iterate,
        "history": cmd_job_history,
        "status": cmd_job_status,
        "tools": cmd_job_tools,
    }

    if not hasattr(args, 'action') or not args.action:
        print_error("Subcomando obrigatorio: create|get|list|cleanup|delete|stats|iterate|history|status|tools")
        sys.exit(1)

    if args.action not in subcommands:
        print_error(f"Subcomando invalido: {args.action}")
        print_info("Opcoes: " + "|".join(subcommands.keys()))
        sys.exit(1)

    subcommands[args.action](args)


def cmd_cli(args):
    """Dispatcher para subcomandos de cli management.

    Comandos:
    - list: Lista CLIs disponibles em .claude/cli/
    """
    subcommands = {
        "list": cmd_cli_list,
    }

    if not hasattr(args, 'action') or not args.action:
        print_error("Subcomando obrigatorio: list")
        sys.exit(1)

    if args.action not in subcommands:
        print_error(f"Subcomando invalido: {args.action}")
        print_info("Opcoes: " + "|".join(subcommands.keys()))
        sys.exit(1)

    subcommands[args.action](args)


__all__ = ['cmd_job', 'cmd_cli']
