#!/bin/bash
# Brain - Alias curto
# Uso: b s "query" = brain search "query"

BRAIN_DIR="/root/claude-brain"

case "$1" in
    s|search)   shift; brain search "$@" ;;
    d|decide)   shift; brain decide "$@" ;;
    l|learn)    shift; brain learn "$@" ;;
    r|recall)   shift; brain recall "$@" ;;
    g|graph)    shift; brain graph "$@" ;;
    i|index)    shift; brain index "$@" ;;
    c|context)  shift; brain context "$@" ;;
    +|useful)   shift; brain useful "$@" ;;
    -|useless)  shift; brain useless "$@" ;;
    ?|solve)    shift; brain solve "$@" ;;
    stats)      brain stats ;;
    dash)       brain dashboard ;;
    prefs)      brain prefs ;;
    # Session shortcuts
    ss)         shift; python3 "$BRAIN_DIR/scripts/session_manager.py" start "$@" ;;
    se)         shift; python3 "$BRAIN_DIR/scripts/session_manager.py" end "$@" ;;
    sn)         shift; python3 "$BRAIN_DIR/scripts/session_manager.py" note "$@" ;;
    sd)         shift; python3 "$BRAIN_DIR/scripts/session_manager.py" decision "$@" ;;
    sh)         python3 "$BRAIN_DIR/scripts/session_manager.py" history ;;
    session)    python3 "$BRAIN_DIR/scripts/session_manager.py" show ;;
    # Server
    server)
        case "$2" in
            start)  source "$BRAIN_DIR/.venv/bin/activate" && python3 "$BRAIN_DIR/scripts/embedding_server.py" start ;;
            status) python3 "$BRAIN_DIR/scripts/embedding_server.py" status ;;
            *)      echo "Uso: b server [start|status]" ;;
        esac
        ;;
    # Auto indexer
    watch)      source "$BRAIN_DIR/.venv/bin/activate" && python3 "$BRAIN_DIR/scripts/auto_indexer.py" daemon ;;
    reindex)    source "$BRAIN_DIR/.venv/bin/activate" && python3 "$BRAIN_DIR/scripts/auto_indexer.py" ;;
    # Help
    *)
        echo "🧠 Brain - Atalhos rápidos"
        echo ""
        echo "  b s <query>     Busca semântica"
        echo "  b d <decisão>   Salvar decisão"
        echo "  b l <erro>      Salvar aprendizado"
        echo "  b ? <erro>      Buscar solução"
        echo "  b g <entidade>  Ver grafo"
        echo "  b c <query>     Contexto formatado"
        echo "  b + [feedback]  Marcar útil"
        echo "  b - [feedback]  Marcar inútil"
        echo ""
        echo "  b ss [projeto]  Iniciar sessão"
        echo "  b se [resumo]   Encerrar sessão"
        echo "  b sn <nota>     Adicionar nota"
        echo "  b session       Ver sessão atual"
        echo "  b sh            Histórico de sessões"
        echo ""
        echo "  b stats         Estatísticas"
        echo "  b dash          Dashboard eficácia"
        echo "  b prefs         Preferências"
        echo ""
        echo "  b server start  Iniciar servidor (embeddings rápidos)"
        echo "  b watch         Auto-indexar novos arquivos"
        echo "  b reindex       Indexar agora"
        ;;
esac
