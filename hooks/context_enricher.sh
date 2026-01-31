#!/bin/bash
# Hook: Context Enricher
# Enriquece o contexto do Claude com memória relevante

# Recebe input do Claude Code via stdin
INPUT=$(cat)

# Extrai a mensagem do usuário (simplificado)
USER_MESSAGE=$(echo "$INPUT" | jq -r '.user_message // empty' 2>/dev/null)

if [ -n "$USER_MESSAGE" ]; then
    # Busca contexto relevante
    CONTEXT=$(python3 /root/claude-brain/scripts/rag_engine.py context "$USER_MESSAGE" 2>/dev/null)

    if [ -n "$CONTEXT" ] && [ "$CONTEXT" != "Nenhum contexto relevante encontrado na memória." ]; then
        # Retorna contexto como system message adicional
        echo "{\"additional_context\": \"$CONTEXT\"}"
    fi
fi

# Retorna vazio se não houver contexto
echo "{}"
