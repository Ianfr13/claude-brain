#!/bin/bash

# Claude Brain Deploy Script
# Configura e inicia o serviço localmente com Docker

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         CLAUDE BRAIN - Deploy Script (Local)              ║"
echo "╚════════════════════════════════════════════════════════════╝"

PROJECT_DIR="/root/claude-brain"
VENV_DIR="$PROJECT_DIR/.venv"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}✅${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

log_error() {
    echo -e "${RED}❌${NC} $1"
}

# 1. Verificar Docker
echo ""
echo "1️⃣  Verificando Docker..."
if ! command -v docker &> /dev/null; then
    log_error "Docker não está instalado"
    echo "Instale com: sudo apt-get install docker.io docker-compose"
    exit 1
fi
log_info "Docker versão: $(docker --version)"

# 2. Preparar ambiente
echo ""
echo "2️⃣  Preparando ambiente..."
cd "$PROJECT_DIR"

# Ativar venv
if [ ! -d "$VENV_DIR" ]; then
    log_warn "Virtual env não existe, criando..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
log_info "Virtual env ativado"

# 3. Instalar dependências
echo ""
echo "3️⃣  Instalando dependências..."
pip install -q -r requirements.txt
log_info "Dependências instaladas"

# 4. Inicializar banco de dados
echo ""
echo "4️⃣  Inicializando banco de dados..."
python3 -c "
from scripts.memory.base import init_db
init_db()
print('✅ Banco inicializado')
" || log_warn "Banco pode já estar inicializado"

# 5. Build Docker image
echo ""
echo "5️⃣  Building Docker image..."
docker-compose build --no-cache

# 6. Iniciar serviço
echo ""
echo "6️⃣  Iniciando serviço com docker-compose..."
docker-compose up -d
log_info "Serviço iniciado"

# 7. Aguardar inicialização
echo ""
echo "7️⃣  Aguardando inicialização (10 segundos)..."
sleep 10

# 8. Validar saúde
echo ""
echo "8️⃣  Validando saúde da API..."
for i in {1..5}; do
    if curl -s http://localhost:8765/ | grep -q "online"; then
        log_info "API está respondendo corretamente ✓"
        break
    fi
    if [ $i -lt 5 ]; then
        log_warn "Tentativa $i/5... aguardando..."
        sleep 2
    else
        log_error "API não respondeu após 10 segundos"
        echo "Verifique com: docker-compose logs"
        exit 1
    fi
done

# 9. Mostrar status
echo ""
echo "9️⃣  Status final:"
docker-compose ps

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║           🎉 DEPLOY CONCLUÍDO COM SUCESSO! 🎉             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📍 Serviço rodando em: http://localhost:8765"
echo "📍 API REST em: http://localhost:8765/v1/"
echo "📍 Dashboard em: http://localhost:8765/dashboard"
echo ""
echo "📋 Comandos úteis:"
echo "   docker-compose logs -f              # Ver logs em tempo real"
echo "   docker-compose down                 # Parar serviço"
echo "   docker-compose restart              # Reiniciar"
echo ""
echo "✅ Próximos passos:"
echo "   1. Testar API: curl http://localhost:8765/v1/stats"
echo "   2. Testar CLI: brain --help"
echo "   3. Acessar dashboard: http://localhost:8765/dashboard"
echo ""
