#!/bin/bash
# Hook: Project Detector
# Detecta o projeto atual e carrega contexto específico

CWD=$(pwd)

# Detecta projeto baseado no diretório
case "$CWD" in
    /root/vsl-analysis*)
        PROJECT="vsl-analysis"
        ;;
    /root/claude-swarm-plugin*)
        PROJECT="claude-swarm"
        ;;
    /root/slack-claude-bot*)
        PROJECT="slack-bot"
        ;;
    *)
        PROJECT=""
        ;;
esac

if [ -n "$PROJECT" ]; then
    # Exporta contexto do projeto
    CONTEXT=$(python3 /root/claude-brain/scripts/memory_store.py export "$PROJECT" 2>/dev/null)
    if [ -n "$CONTEXT" ]; then
        echo "{\"project\": \"$PROJECT\", \"context\": \"$CONTEXT\"}"
        exit 0
    fi
fi

echo "{}"
