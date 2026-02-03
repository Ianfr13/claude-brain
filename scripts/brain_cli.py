#!/usr/bin/env python3
"""
Claude Brain - CLI Unificado (Refatorado)

Interface completa para memoria, RAG e knowledge graph.

Este arquivo agora importa os comandos dos submodulos em scripts/cli/:
- cli/base.py: Classes e funcoes base (Colors, print_*, etc)
- cli/memory.py: remember, recall
- cli/decisions.py: decide, decisions, confirm, contradict
- cli/learnings.py: learn, learnings, solve
- cli/graph.py: entity, relate, graph
- cli/rag.py: index, search, context, ask, related
- cli/preferences.py: prefer, prefs, pattern, snippet
- cli/maturity.py: hypotheses, supersede, maturity
- cli/utils.py: delete, forget, export, stats, help, etc
"""

import sys
import argparse

# Imports dos submodulos CLI
from scripts.cli import (
    # Base
    Colors, c,
    # Memory
    cmd_remember, cmd_recall,
    # Decisions
    cmd_decide, cmd_decisions, cmd_confirm, cmd_contradict,
    # Learnings
    cmd_learn, cmd_learnings, cmd_solve,
    # Graph
    cmd_entity, cmd_relate, cmd_graph,
    # Agentic
    cmd_agentic_ask,
    # RAG
    cmd_index, cmd_search, cmd_context, cmd_ask, cmd_related,
    # Preferences
    cmd_prefer, cmd_prefs, cmd_pattern, cmd_snippet,
    # Maturity
    cmd_hypotheses, cmd_supersede, cmd_maturity,
    # Utils
    cmd_delete, cmd_forget, cmd_export, cmd_stats, cmd_help,
    cmd_useful, cmd_useless, cmd_dashboard, cmd_extract,
    # Workflow
    cmd_workflow,
    # Jobs
    cmd_job, cmd_cli,
)


def main():
    """Funcao principal do CLI - configura argparse e despacha comandos."""
    parser = argparse.ArgumentParser(description="Claude Brain CLI", add_help=False)
    subparsers = parser.add_subparsers(dest="command")

    # ============ MEMORIA ============

    p = subparsers.add_parser("remember")
    p.add_argument("text", nargs="*")
    p.add_argument("-c", "--category")
    p.add_argument("-i", "--importance", type=int)
    p.add_argument("-p", "--project", help="Projeto associado (se omitido, e conhecimento geral)")

    p = subparsers.add_parser("decide")
    p.add_argument("decision", nargs="*")
    p.add_argument("-p", "--project")
    p.add_argument("-r", "--reason")
    p.add_argument("-a", "--alternatives")
    p.add_argument("--fact", action="store_true", help="Marcar como fato estabelecido (ja confirmado)")

    p = subparsers.add_parser("learn")
    p.add_argument("error", nargs="*")
    p.add_argument("-s", "--solution", required=True)
    p.add_argument("--prevention")
    p.add_argument("-p", "--project")
    p.add_argument("-c", "--context", help="O que estava fazendo quando o erro ocorreu")
    p.add_argument("--cause", help="Causa raiz do erro")
    p.add_argument("-m", "--message", help="Mensagem de erro completa")
    p.add_argument("--fact", action="store_true", help="Marcar como solucao conhecida/documentada (ja confirmada)")

    p = subparsers.add_parser("solve")
    p.add_argument("error", nargs="*")

    p = subparsers.add_parser("ask", help="Consulta inteligente (semantica + decisoes + learnings)")
    p.add_argument("query", nargs="*")
    p.add_argument("-p", "--project", help="Prioriza contexto do projeto especificado")

    p = subparsers.add_parser("recall")
    p.add_argument("query", nargs="*")
    p.add_argument("-t", "--type")
    p.add_argument("-l", "--limit", type=int)

    p = subparsers.add_parser("decisions")
    p.add_argument("-p", "--project")
    p.add_argument("-l", "--limit", type=int)

    p = subparsers.add_parser("learnings")
    p.add_argument("-l", "--limit", type=int)

    # ============ RAG ============

    p = subparsers.add_parser("index")
    p.add_argument("path", nargs="*")
    p.add_argument("--no-recursive", action="store_true")

    p = subparsers.add_parser("search")
    p.add_argument("query", nargs="*")
    p.add_argument("-t", "--type")
    p.add_argument("-l", "--limit", type=int)

    p = subparsers.add_parser("context")
    p.add_argument("query", nargs="*")
    p.add_argument("--tokens", type=int)

    p = subparsers.add_parser("related")
    p.add_argument("source", nargs="*")
    p.add_argument("-l", "--limit", type=int)

    # ============ KNOWLEDGE GRAPH ============

    p = subparsers.add_parser("entity")
    p.add_argument("name", nargs="*")

    p = subparsers.add_parser("relate")
    p.add_argument("relation", nargs="*")

    p = subparsers.add_parser("graph", help="Comandos avançados do knowledge graph")
    p.add_argument("entity", nargs="*", help="[subcomando] ou [entidade]")
    p.add_argument("--depth", type=int, default=2, help="Profundidade da traversal (default: 2)")
    p.add_argument("--relation", help="Filtro de tipo de relacao (ex: uses, maintains)")
    p.add_argument("--top", type=int, default=10, help="Quantidade de top nós para pagerank (default: 10)")

    # Agentic Ask - Busca inteligente com ensemble
    p = subparsers.add_parser("agentic-ask", help="Busca inteligente com decomposicao de query e ensemble")
    p.add_argument("query", nargs="*", help="Query para buscar (pode usar AND/OR)")
    p.add_argument("-p", "--project", help="Projeto especifico para priorizar")
    p.add_argument("--explain", action="store_true", help="Mostra explicacao detalhada do processo")

    # ============ PREFERENCIAS ============

    p = subparsers.add_parser("prefer")
    p.add_argument("pref", nargs="*")

    subparsers.add_parser("prefs")

    # ============ PADROES ============

    p = subparsers.add_parser("pattern")
    p.add_argument("pattern", nargs="*")
    p.add_argument("--language", "-L")

    p = subparsers.add_parser("snippet")
    p.add_argument("name", nargs="*")

    # ============ UTILIDADES ============

    p = subparsers.add_parser("export")
    p.add_argument("-p", "--project")

    subparsers.add_parser("stats")
    subparsers.add_parser("help")

    # Extrator de historico
    p = subparsers.add_parser("extract")
    p.add_argument("--dry-run", action="store_true", help="Mostra o que seria extraido sem salvar")
    p.add_argument("-l", "--limit", type=int, default=10, help="Limite de sessoes")

    # Metricas
    p = subparsers.add_parser("useful")
    p.add_argument("feedback", nargs="*")

    p = subparsers.add_parser("useless")
    p.add_argument("feedback", nargs="*")

    subparsers.add_parser("dashboard")

    # ============ SISTEMA DE MATURACAO ============

    p = subparsers.add_parser("hypotheses", help="Lista conhecimentos nao confirmados")
    p.add_argument("-l", "--limit", type=int, default=15)

    p = subparsers.add_parser("confirm", help="Confirma que conhecimento esta correto")
    p.add_argument("table", nargs="?", choices=["decisions", "learnings", "memories"])
    p.add_argument("id", nargs="?", type=int)

    p = subparsers.add_parser("contradict", help="Marca conhecimento como incorreto")
    p.add_argument("table", nargs="?", choices=["decisions", "learnings", "memories"])
    p.add_argument("id", nargs="?", type=int)
    p.add_argument("-r", "--reason", help="Motivo da contradicao")

    p = subparsers.add_parser("supersede", help="Substitui conhecimento antigo por novo")
    p.add_argument("table", nargs="?", choices=["decisions", "learnings", "memories"])
    p.add_argument("id", nargs="?", type=int)
    p.add_argument("-n", "--new", required=True, help="Novo conhecimento")
    p.add_argument("-r", "--reason", help="Motivo da substituicao")

    p = subparsers.add_parser("maturity", help="Estatisticas de maturidade")

    # ============ DELETE ============

    p = subparsers.add_parser("delete", help="Deleta registro especifico")
    p.add_argument("table", nargs="?", choices=["memories", "decisions", "learnings"])
    p.add_argument("id", nargs="?", type=int, help="ID do registro")
    p.add_argument("-f", "--force", action="store_true", help="Nao pedir confirmacao")

    # Forget (busca e deleta)
    p = subparsers.add_parser("forget", help="Busca e deleta registros")
    p.add_argument("query", nargs="*", help="Query de busca")
    p.add_argument("-t", "--table", choices=["memories", "decisions", "learnings"])
    p.add_argument("--threshold", type=float, default=0.8, help="Score minimo para deletar")
    p.add_argument("--execute", action="store_true", help="Executar delecao (padrao e dry-run)")

    # ============ WORKFLOWS ============

    p = subparsers.add_parser("workflow", help="Sessoes de trabalho com contexto")
    p.add_argument("action", choices=["start", "update", "resume", "complete", "status", "list", "show"])
    p.add_argument("name", nargs="*", help="Nome da tarefa (para start/show)")
    p.add_argument("-p", "--project", help="Projeto associado")
    p.add_argument("-g", "--goal", help="Goal detalhado da sessao")
    p.add_argument("--todo", help="Adicionar TODO")
    p.add_argument("--done", help="Marcar TODO como concluido (numero)")
    p.add_argument("--insight", help="Adicionar insight")
    p.add_argument("--file", help="Registrar arquivo modificado")
    p.add_argument("--summary", help="Resumo ao completar")
    p.add_argument("--id", help="ID do workflow (para resume)")
    p.add_argument("--status", choices=["active", "completed"], help="Filtrar por status (list)")

    # ============ JOB QUEUE ============

    p = subparsers.add_parser("job", help="Fila de jobs com TTL")
    p.add_argument("action", choices=["create", "get", "list", "cleanup", "delete", "stats", "iterate", "history", "status", "tools"])
    p.add_argument("job_id", nargs="?", help="ID do job (para get/delete/iterate/history/status/tools)")
    p.add_argument("--ttl", type=int, default=43200, help="Time to live em segundos (para create, default: 12h)")
    p.add_argument("--data", help="JSON completo do job (para create)")
    p.add_argument("--prompt", nargs="*", help="Prompt do job (para create)")
    p.add_argument("--skills", action="append", help="Skills a usar (para create, pode repetir)")
    p.add_argument("--brain-query", action="append", help="Brain queries no formato 'query|project' (para create, pode repetir)")
    p.add_argument("--files", action="append", help="Arquivos relevantes (para create, pode repetir)")
    p.add_argument("--context", help="Contexto JSON adicional (para create)")
    p.add_argument("--json", action="store_true", help="Saida em JSON (para get/list/history/tools)")
    p.add_argument("--all", action="store_true", help="Incluir expirados (para list/stats)")
    p.add_argument("--type", help="Tipo de iteracao: execution ou review (para iterate)")
    p.add_argument("--agent", help="Agente que executa: haiku ou opus (para iterate)")
    p.add_argument("--result", help="Resultado da iteracao (para iterate)")
    p.add_argument("--set", help="Novo status para o job (para status)")
    p.add_argument("--build-missing", action="store_true", help="Criar job builder para ferramentas faltando (para tools)")

    p = subparsers.add_parser("cli", help="Gerenciamento de ferramentas CLI em .claude/cli/")
    p.add_argument("action", choices=["list"])
    p.add_argument("--json", action="store_true", help="Saida em JSON")

    args = parser.parse_args()

    # Mapeamento de comandos para funcoes
    commands = {
        # Memoria
        "remember": cmd_remember,
        "recall": cmd_recall,
        # Decisoes
        "decide": cmd_decide,
        "decisions": cmd_decisions,
        "confirm": cmd_confirm,
        "contradict": cmd_contradict,
        # Learnings
        "learn": cmd_learn,
        "learnings": cmd_learnings,
        "solve": cmd_solve,
        # RAG
        "index": cmd_index,
        "search": cmd_search,
        "context": cmd_context,
        "ask": cmd_ask,
        "related": cmd_related,
        # Graph
        "entity": cmd_entity,
        "relate": cmd_relate,
        "graph": cmd_graph,
        # Agentic
        "agentic-ask": cmd_agentic_ask,
        # Preferences
        "prefer": cmd_prefer,
        "prefs": cmd_prefs,
        "pattern": cmd_pattern,
        "snippet": cmd_snippet,
        # Utils
        "export": cmd_export,
        "stats": cmd_stats,
        "help": cmd_help,
        "useful": cmd_useful,
        "useless": cmd_useless,
        "dashboard": cmd_dashboard,
        "extract": cmd_extract,
        # Maturity
        "hypotheses": cmd_hypotheses,
        "supersede": cmd_supersede,
        "maturity": cmd_maturity,
        # Delete
        "delete": cmd_delete,
        "forget": cmd_forget,
        # Workflow
        "workflow": cmd_workflow,
        # Jobs
        "job": cmd_job,
        # CLI
        "cli": cmd_cli,
    }

    # Robustez: Try/except global com exit codes apropriados
    try:
        if args.command in commands:
            commands[args.command](args)
        else:
            cmd_help(args)
    except KeyboardInterrupt:
        print("\n" + c("Interrompido pelo usuario.", Colors.DIM))
        sys.exit(130)
    except Exception as e:
        from scripts.cli.base import print_error
        print_error(f"Erro inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
