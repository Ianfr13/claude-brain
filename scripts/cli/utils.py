#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo Utils

Comandos utilitarios:
- cmd_delete: Deleta registro especifico
- cmd_forget: Busca e deleta registros
- cmd_export: Exporta contexto
- cmd_stats: Estatisticas do brain
- cmd_help: Mostra ajuda
- cmd_useful/cmd_useless: Feedback de utilidade
- cmd_dashboard: Dashboard de metricas
- cmd_extract: Extrai conhecimento do historico
"""

import sys

from .base import Colors, c, print_header, print_success, print_error, print_info
from scripts.memory_store import (
    export_context, get_stats as memory_stats, delete_record
)
from scripts.rag_engine import get_stats as rag_stats
from scripts.metrics import log_action, mark_useful, get_effectiveness, print_dashboard

# Importa busca do rag.py (para cmd_forget)
try:
    from scripts.faiss_rag import semantic_search
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    from scripts.rag_engine import search as simple_search


def search(query, doc_type=None, limit=5):
    """Busca hibrida para cmd_forget"""
    if HAS_FAISS:
        return semantic_search(query, doc_type, limit)
    return simple_search(query, doc_type, limit)


def cmd_delete(args):
    """Deleta um registro especifico do banco.

    Remove permanentemente uma memoria, decisao ou learning.
    Pede confirmacao a menos que --force seja usado.

    Args:
        args: Namespace do argparse contendo:
            - table (str): Tabela (memories|decisions|learnings)
            - id (int): ID do registro
            - force (bool): Pular confirmacao

    Returns:
        None. Imprime confirmacao ou erro.

    Examples:
        $ brain delete decisions 15
        Deletar decisions #15? [s/N] s
        * Deletado decisions #15

        $ brain delete learnings 3 -f
        * Deletado learnings #3
    """
    if not args.table or args.id is None:
        print_error("Uso: brain delete <memories|decisions|learnings> <id> [-f]")
        sys.exit(1)

    if not args.force:
        # Robustez: Verificar se stdin e terminal antes de pedir input
        if not sys.stdin.isatty():
            print_error("Use -f/--force em modo nao-interativo (pipe/script)")
            sys.exit(1)
        confirm = input(f"Deletar {args.table} #{args.id}? [s/N] ")
        if confirm.lower() != 's':
            print_info("Cancelado.")
            return

    if delete_record(args.table, args.id):
        print_success(f"Deletado {args.table} #{args.id}")
    else:
        print_error(f"Registro nao encontrado")
        sys.exit(1)


def cmd_forget(args):
    """Busca e deleta registros por busca semantica.

    Encontra registros similares a query e permite deletar
    em lote. Por padrao roda em dry-run.

    Args:
        args: Namespace do argparse contendo:
            - query (list[str]): Texto para buscar
            - table (str, optional): Filtrar por tabela
            - threshold (float): Score minimo (default: 0.8)
            - execute (bool): Executar delecao (default: dry-run)

    Returns:
        None. Imprime resultados e deleta se --execute.

    Examples:
        $ brain forget "redis config"
        [DRY-RUN] Resultados para 'redis config':
          [85%] decisions:15
               Usar Redis para cache...

        $ brain forget "redis" --execute
        [100%] decisions:15
               -> Deletado!
    """
    if not args.query:
        print_error("Uso: brain forget <query> [-t table] [--threshold 0.8] [--execute]")
        return

    query = " ".join(args.query)

    # Busca semantica
    results = search(query, doc_type=args.table, limit=10)

    if not results:
        print_info("Nenhum resultado encontrado.")
        return

    print(f"\n{'[DRY-RUN] ' if not args.execute else ''}Resultados para '{query}':\n")

    to_delete = []
    for r in results:
        score = r.get('score', 0)
        if score >= args.threshold:
            source = r.get('source', 'unknown')
            text = r.get('text', '')[:100]

            # Tenta extrair table e id do source (formato: "table:id" ou similar)
            table_id = None
            if ':' in source:
                parts = source.split(':')
                if len(parts) >= 2 and parts[0] in ['memories', 'decisions', 'learnings']:
                    try:
                        table_id = (parts[0], int(parts[1]))
                    except ValueError:
                        pass

            score_color = Colors.GREEN if score > 0.8 else Colors.YELLOW
            print(f"  {c(f'[{score:.0%}]', score_color)} {c(source, Colors.CYAN)}")
            print(f"       {text}...")

            if table_id:
                to_delete.append(table_id)

            if args.execute and table_id:
                if delete_record(table_id[0], table_id[1]):
                    print(c(f"       -> Deletado!", Colors.RED))

    if not args.execute:
        print(f"\n{c('Use --execute para deletar os registros acima.', Colors.DIM)}")
        if to_delete:
            print(c(f"Encontrados {len(to_delete)} registros deletaveis.", Colors.DIM))


def cmd_export(args):
    """Exporta todo o contexto do brain em formato texto.

    Gera um dump completo de decisoes, learnings e memorias
    para backup ou injecao em sessao do Claude.

    Args:
        args: Namespace do argparse contendo:
            - project (str, optional): Filtrar por projeto

    Returns:
        None. Imprime contexto completo formatado.

    Examples:
        $ brain export
        # Contexto do Claude Brain
        ## Decisoes
        ...

        $ brain export -p vsl-analysis > contexto.md
        # Salva em arquivo
    """
    context = export_context(project=args.project, include_learnings=True)
    print(context)


def cmd_stats(args):
    """Mostra estatisticas completas do brain.

    Exibe contagem de memorias, decisoes, learnings, documentos
    indexados, e metricas de eficacia.

    Args:
        args: Namespace do argparse (sem argumentos especificos)

    Returns:
        None. Imprime estatisticas formatadas.

    Examples:
        $ brain stats
        Estatisticas do Claude Brain
        Memoria:
          memories: 28
          decisions: 112
          learnings: 12
        RAG:
          Documentos: 309
          Chunks: 3421
        Eficacia:
          Taxa: 95% util
    """
    m_stats = memory_stats()
    r_stats = rag_stats()

    print_header("Estatisticas do Claude Brain")

    print(f"\n{c('Memoria:', Colors.CYAN)}")
    for k, v in m_stats.items():
        if not k.startswith('top_'):
            print(f"  {k}: {v}")

    if m_stats.get('top_preferences'):
        print(f"\n  {c('Top preferencias:', Colors.DIM)}")
        for p in m_stats['top_preferences']:
            print(f"    {p['key']}: {p['times_observed']}x")

    if m_stats.get('top_errors'):
        print(f"\n  {c('Erros frequentes:', Colors.DIM)}")
        for e in m_stats['top_errors']:
            print(f"    {e['error_type']}: {e['frequency']}x")

    print(f"\n{c('RAG:', Colors.CYAN)}")
    print(f"  Documentos: {r_stats['documents']}")
    print(f"  Chunks: {r_stats['chunks']}")
    if r_stats.get('doc_types'):
        print(f"  Tipos: {', '.join(r_stats['doc_types'])}")
    elif r_stats.get('sources'):
        print(f"  Fontes: {len(r_stats['sources'])}")

    # Eficacia
    eff = get_effectiveness()
    if eff['total_actions'] > 0:
        print(f"\n{c('Eficacia:', Colors.CYAN)}")
        print(f"  Acoes: {eff['total_actions']}")
        if eff['rated_actions'] > 0:
            print(f"  Taxa: {eff['effectiveness_pct']}% util")


def cmd_useful(args):
    """Marca a ultima acao do brain como util.

    Registra feedback positivo para melhorar as metricas
    de eficacia e ajudar a priorizar resultados.

    Args:
        args: Namespace do argparse contendo:
            - feedback (list[str], optional): Comentario adicional

    Returns:
        None. Imprime confirmacao.

    Examples:
        $ brain useful
        * Marcado como util

        $ brain useful "solucao funcionou perfeitamente"
        * Marcado como util
    """
    feedback = " ".join(args.feedback) if args.feedback else None
    mark_useful(useful=True, feedback=feedback)
    log_action("feedback", category="useful")
    print_success("Marcado como util")


def cmd_useless(args):
    """Marca a ultima acao do brain como nao util.

    Registra feedback negativo para ajustar metricas
    e identificar areas de melhoria.

    Args:
        args: Namespace do argparse contendo:
            - feedback (list[str], optional): Motivo da insatisfacao

    Returns:
        None. Imprime confirmacao.

    Examples:
        $ brain useless
        x Marcado como nao util

        $ brain useless "solucao desatualizada"
        x Marcado como nao util
    """
    feedback = " ".join(args.feedback) if args.feedback else None
    mark_useful(useful=False, feedback=feedback)
    log_action("feedback", category="useless")
    print_error("Marcado como nao util")


def cmd_extract(args):
    """Extrai conhecimento do historico de sessoes do Claude Code.

    Analisa conversas anteriores e extrai automaticamente
    decisoes, learnings e memorias relevantes.

    Args:
        args: Namespace do argparse contendo:
            - limit (int): Numero de sessoes a processar (default: 10)
            - dry_run (bool): Se True, nao salva nada

    Returns:
        None. Imprime progresso e totais extraidos.

    Examples:
        $ brain extract --limit 50
        Extrator de Historico
        i Encontradas 50 sessoes
        * session_abc123: {'decisions': 2, 'learnings': 1}
        Total: 15 decisoes, 8 learnings, 3 memorias

        $ brain extract --dry-run
        ...modo dry-run - nada foi salvo
    """
    from scripts.extract_history import find_claude_sessions, process_session

    print_header("Extrator de Historico")

    sessions = find_claude_sessions()
    sessions.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    sessions = sessions[:args.limit]

    print_info(f"Encontradas {len(sessions)} sessoes")

    total = {"decisions": 0, "learnings": 0, "memories": 0}

    for session in sessions:
        stats = process_session(session, dry_run=args.dry_run)
        for key in total:
            total[key] += stats[key]
        if any(stats.values()):
            print(f"  {c('*', Colors.GREEN)} {session.name[:30]}: {stats}")

    print(f"\n{c('Total:', Colors.CYAN)} {total['decisions']} decisoes, {total['learnings']} learnings, {total['memories']} memorias")

    if args.dry_run:
        print_info("Modo dry-run - nada foi salvo")


def cmd_dashboard(args):
    """Mostra dashboard de eficacia do brain.

    Exibe metricas de uso, taxa de utilidade, e historico
    de acoes para avaliar o valor do sistema.

    Args:
        args: Namespace do argparse (sem argumentos especificos)

    Returns:
        None. Imprime dashboard formatado.

    Examples:
        $ brain dashboard
        Dashboard de Eficacia
        Acoes totais: 150
        Acoes avaliadas: 45
        Taxa de utilidade: 93%
        ...
    """
    print_dashboard()


def cmd_help(args):
    """Mostra tela de ajuda com todos os comandos.

    Exibe lista completa de comandos disponiveis com
    descricao e exemplos de uso.

    Args:
        args: Namespace do argparse (sem argumentos especificos)

    Returns:
        None. Imprime ajuda formatada.

    Examples:
        $ brain help
        Claude Brain - Sistema de Memoria Inteligente
        ...lista de comandos...

        $ brain --help
        ...mesmo resultado...
    """
    print("""
Claude Brain - Sistema de Memoria Inteligente

+-------------------------------------------------------------+
| MEMORIA                                                     |
+-------------------------------------------------------------+
| brain remember <texto>           Salva memoria geral        |
| brain decide <decisao>           Salva decisao arquitetural |
| brain learn <erro> --solution X  Salva aprendizado de erro  |
| brain solve <erro>               Busca solucao para erro    |
| brain recall [query]             Busca na memoria           |
| brain decisions                  Lista decisoes             |
| brain learnings                  Lista aprendizados         |
+-------------------------------------------------------------+
| RAG (Busca Semantica)                                       |
+-------------------------------------------------------------+
| brain index <path>               Indexa arquivo/diretorio   |
| brain search <query>             Busca semantica            |
| brain context <query>            Contexto para Claude       |
| brain related <arquivo>          Documentos relacionados    |
+-------------------------------------------------------------+
| KNOWLEDGE GRAPH & AGENTIC                                   |
+-------------------------------------------------------------+
| brain entity <nome> <tipo>       Cria/atualiza entidade     |
| brain relate <de> <para> <rel>   Cria relacao               |
| brain graph <entidade>           Mostra grafo               |
| brain graph sync                 Sincroniza com Neo4j       |
| brain graph traverse <no> [--depth 2] [--relation uses]     |
| brain graph path <source> <target>  Caminho mais curto      |
| brain graph pagerank [--top 10]  Calcula PageRank dos nos   |
| brain graph stats                Estatisticas do grafo      |
| brain agentic-ask '<query>'      Busca inteligente ensemble |
+-------------------------------------------------------------+
| PREFERENCIAS & PADROES                                      |
+-------------------------------------------------------------+
| brain prefer <chave> <valor>     Salva preferencia          |
| brain prefs                      Lista preferencias         |
| brain pattern <nome> <codigo>    Salva snippet              |
| brain snippet <nome>             Busca snippet              |
+-------------------------------------------------------------+
| DELETE                                                      |
+-------------------------------------------------------------+
| brain delete <table> <id> [-f]   Deleta registro especifico |
| brain forget <query> [--execute] Busca e deleta registros   |
+-------------------------------------------------------------+
| UTILIDADES                                                  |
+-------------------------------------------------------------+
| brain export [--project X]       Exporta contexto           |
| brain stats                      Estatisticas               |
+-------------------------------------------------------------+

Opcoes comuns:
  --project, -p    Filtrar por projeto
  --limit, -l      Limitar resultados
  --type, -t       Filtrar por tipo

Exemplos:
  brain remember "Usuario prefere codigo conciso"
  brain decide "Usar FastAPI" -p meu-projeto --reason "Melhor performance"
  brain learn "ImportError" --solution "pip install X" --prevention "Verificar deps"
  brain index /root/meu-projeto
  brain search "como configurar auth"
  brain entity "redis" "technology" "Cache layer"
  brain relate "meu-projeto" "redis" "uses"
  brain graph stats                        # Mostra estatísticas do grafo
  brain graph traverse redis --depth 2     # Traversa desde redis
  brain graph path redis fastapi           # Caminho mais curto
  brain graph pagerank --top 5             # Top 5 nós por importância
  brain agentic-ask "redis cache ttl"      # Busca inteligente com ensemble
  brain agentic-ask "api design" --explain # Com explicação do processo
  brain delete decisions 15 -f
  brain forget "redis config" --execute
""")
