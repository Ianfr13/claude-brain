#!/bin/bash
# Claude Brain - Start Script Simples

cd /root/claude-brain

# Matar processos antigos
pkill -9 -f uvicorn 2>/dev/null

# Ativar venv e iniciar
source .venv/bin/activate
nohup uvicorn api.main:app --host 127.0.0.1 --port 8765 > /tmp/claude-brain.log 2>&1 &

echo $! > /tmp/claude-brain.pid
echo "✅ Claude Brain iniciado (PID: $(cat /tmp/claude-brain.pid))"
echo "📍 API: http://localhost:8765"
echo "📊 Stats: http://localhost:8765/v1/stats"
echo "📋 Logs: tail -f /tmp/claude-brain.log"
echo "🛑 Parar: kill \$(cat /tmp/claude-brain.pid)"

sleep 3
if curl -sf http://localhost:8765/ > /dev/null; then
    echo "✅ API está respondendo!"
else
    echo "❌ API não está respondendo. Ver logs: cat /tmp/claude-brain.log"
fi
