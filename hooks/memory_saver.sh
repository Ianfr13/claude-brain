#!/bin/bash
# Hook: Memory Saver
# Salva decisões e aprendizados automaticamente

INPUT=$(cat)

# Detecta padrões de decisão
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
TOOL_OUTPUT=$(echo "$INPUT" | jq -r '.tool_output // empty' 2>/dev/null)

# Se foi um comando que modificou algo, pode ser uma decisão
if [ "$TOOL_NAME" = "Write" ] || [ "$TOOL_NAME" = "Edit" ]; then
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
    if [ -n "$FILE_PATH" ]; then
        # Salva como decisão
        python3 /root/claude-brain/scripts/memory_store.py save-memory \
            "file_change" \
            "Modificado: $FILE_PATH" 2>/dev/null
    fi
fi

# Se houve erro, salva para aprendizado
if echo "$TOOL_OUTPUT" | grep -qi "error\|failed\|exception"; then
    ERROR_PREVIEW=$(echo "$TOOL_OUTPUT" | head -c 200)
    python3 /root/claude-brain/scripts/memory_store.py save-memory \
        "error" \
        "$ERROR_PREVIEW" 2>/dev/null
fi

echo "{}"
