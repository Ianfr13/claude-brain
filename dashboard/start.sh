#!/bin/bash
# Claude Brain Dashboard - Start Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRAIN_DIR="$(dirname "$SCRIPT_DIR")"

# Ativa venv
source "$BRAIN_DIR/.venv/bin/activate"

# Inicia servidor
echo "Iniciando Claude Brain Dashboard..."
echo "Dashboard: http://localhost:${1:-8765}/"
echo ""

cd "$SCRIPT_DIR"
python api.py --port ${1:-8765}
