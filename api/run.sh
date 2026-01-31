#!/bin/bash
# Inicia a API do Claude Brain na porta 8765

cd /root/claude-brain
source .venv/bin/activate

echo "Iniciando Claude Brain API em http://0.0.0.0:8765"
echo "Docs: http://localhost:8765/docs"
echo ""

uvicorn api.main:app --host 0.0.0.0 --port 8765 --reload
