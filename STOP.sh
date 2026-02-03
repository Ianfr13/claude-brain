#!/bin/bash
# Claude Brain - Stop Script

if [ -f /tmp/claude-brain.pid ]; then
    PID=$(cat /tmp/claude-brain.pid)
    kill $PID 2>/dev/null && echo "✅ Processo $PID encerrado"
    rm /tmp/claude-brain.pid
fi

pkill -9 -f "uvicorn api.main" 2>/dev/null
echo "✅ Todos os processos uvicorn encerrados"
