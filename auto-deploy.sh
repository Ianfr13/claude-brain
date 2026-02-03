#!/bin/bash

# Claude Brain - Auto Deploy Script
# Configura deploy automático com auto-recovery em 3 camadas

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║      CLAUDE BRAIN - Auto Deploy & Recovery Setup         ║"
echo "╚════════════════════════════════════════════════════════════╝"

PROJECT_DIR="/root/claude-brain"
SYSTEMD_SERVICE="/etc/systemd/system/claude-brain.service"
WATCHDOG_SCRIPT="/usr/local/bin/claude-brain-watchdog"
WATCHDOG_TIMER="/etc/systemd/system/claude-brain-watchdog.timer"
WATCHDOG_SERVICE="/etc/systemd/system/claude-brain-watchdog.service"

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}✅${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠️${NC} $1"; }
log_error() { echo -e "${RED}❌${NC} $1"; }

# Verificar root
if [ "$EUID" -ne 0 ]; then
    log_error "Execute como root: sudo $0"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "CAMADA 1: Docker Restart Policy"
echo "═══════════════════════════════════════════════════════════"

# Atualizar docker-compose.yml com restart always
cd "$PROJECT_DIR"

if ! grep -q "restart: always" docker-compose.yml; then
    log_warn "Atualizando docker-compose.yml com restart: always"
    sed -i 's/restart: unless-stopped/restart: always/g' docker-compose.yml
fi

log_info "Docker configurado para restart automático"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "CAMADA 2: Systemd Service (Inicia com o Sistema)"
echo "═══════════════════════════════════════════════════════════"

# Criar systemd service
cat > "$SYSTEMD_SERVICE" << 'EOF'
[Unit]
Description=Claude Brain API & Dashboard
Documentation=https://github.com/Ianfr13/claude-brain
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/root/claude-brain
User=root

# Start: Build e up com compose
ExecStart=/usr/bin/docker-compose up -d --build

# Stop: Down com compose
ExecStop=/usr/bin/docker-compose down

# Restart: Recreate containers
ExecReload=/usr/bin/docker-compose restart

# Auto-restart on failure
Restart=on-failure
RestartSec=10s

# Timeout
TimeoutStartSec=300
TimeoutStopSec=30

# Logs
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-brain

[Install]
WantedBy=multi-user.target
EOF

log_info "Systemd service criado: $SYSTEMD_SERVICE"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "CAMADA 3: Watchdog Health Checker (Monitora a cada 2min)"
echo "═══════════════════════════════════════════════════════════"

# Criar watchdog script
cat > "$WATCHDOG_SCRIPT" << 'WATCHDOG'
#!/bin/bash

# Claude Brain Watchdog - Health Check & Auto-Recovery
# Verifica saúde da API e reinicia se necessário

API_URL="http://localhost:8765/"
HEALTH_ENDPOINT="http://localhost:8765/v1/stats"
MAX_FAILURES=3
FAILURE_COUNT_FILE="/tmp/claude-brain-failures"
LOG_FILE="/var/log/claude-brain-watchdog.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Inicializar contador
if [ ! -f "$FAILURE_COUNT_FILE" ]; then
    echo "0" > "$FAILURE_COUNT_FILE"
fi

FAILURES=$(cat "$FAILURE_COUNT_FILE")

# Health check
if curl -sf "$API_URL" > /dev/null 2>&1; then
    # API respondendo - resetar contador
    if [ "$FAILURES" -gt 0 ]; then
        log "✅ API recovered after $FAILURES failures"
        echo "0" > "$FAILURE_COUNT_FILE"
    fi
    exit 0
fi

# API não respondendo - incrementar falhas
FAILURES=$((FAILURES + 1))
echo "$FAILURES" > "$FAILURE_COUNT_FILE"

log "⚠️  Health check failed ($FAILURES/$MAX_FAILURES)"

# Se atingiu limite, tentar recovery
if [ "$FAILURES" -ge "$MAX_FAILURES" ]; then
    log "🚨 Max failures reached. Initiating auto-recovery..."

    # Tentar restart via systemd
    systemctl restart claude-brain

    # Aguardar 30s para inicialização
    sleep 30

    # Verificar se recuperou
    if curl -sf "$API_URL" > /dev/null 2>&1; then
        log "✅ Auto-recovery successful via systemd restart"
        echo "0" > "$FAILURE_COUNT_FILE"
    else
        # Se systemd falhou, tentar docker-compose direto
        log "⚠️  Systemd restart failed. Trying docker-compose..."
        cd /root/claude-brain
        docker-compose down
        docker-compose up -d --build

        sleep 30

        if curl -sf "$API_URL" > /dev/null 2>&1; then
            log "✅ Auto-recovery successful via docker-compose"
            echo "0" > "$FAILURE_COUNT_FILE"
        else
            log "❌ Auto-recovery failed. Manual intervention required."
            # Enviar notificação (implementar webhook/email se necessário)
        fi
    fi
fi
WATCHDOG

chmod +x "$WATCHDOG_SCRIPT"
log_info "Watchdog script criado: $WATCHDOG_SCRIPT"

# Criar systemd timer para watchdog (executa a cada 2 minutos)
cat > "$WATCHDOG_TIMER" << 'EOF'
[Unit]
Description=Claude Brain Watchdog Timer
Documentation=https://github.com/Ianfr13/claude-brain

[Timer]
# Executar a cada 2 minutos
OnBootSec=2min
OnUnitActiveSec=2min

# Randomize delay (evita spike de CPU)
RandomizedDelaySec=10s

# Persistir timer mesmo se sistema desligar
Persistent=true

[Install]
WantedBy=timers.target
EOF

log_info "Watchdog timer criado: $WATCHDOG_TIMER"

# Criar systemd service para watchdog
cat > "$WATCHDOG_SERVICE" << 'EOF'
[Unit]
Description=Claude Brain Watchdog Service
Documentation=https://github.com/Ianfr13/claude-brain

[Service]
Type=oneshot
ExecStart=/usr/local/bin/claude-brain-watchdog

# Logs
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-brain-watchdog
EOF

log_info "Watchdog service criado: $WATCHDOG_SERVICE"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "ATIVANDO SERVIÇOS"
echo "═══════════════════════════════════════════════════════════"

# Reload systemd
systemctl daemon-reload
log_info "Systemd daemon reloaded"

# Ativar e iniciar claude-brain service
systemctl enable claude-brain
systemctl start claude-brain
log_info "Claude Brain service habilitado e iniciado"

# Ativar e iniciar watchdog timer
systemctl enable claude-brain-watchdog.timer
systemctl start claude-brain-watchdog.timer
log_info "Watchdog timer habilitado e iniciado"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "AGUARDANDO INICIALIZAÇÃO (30 segundos)"
echo "═══════════════════════════════════════════════════════════"

sleep 30

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "VALIDANDO DEPLOY"
echo "═══════════════════════════════════════════════════════════"

# Verificar container
if docker ps | grep -q claude-brain-api; then
    log_info "Container claude-brain-api está rodando"
else
    log_error "Container não está rodando"
    echo "Verifique com: docker-compose logs"
fi

# Verificar API
if curl -sf http://localhost:8765/ > /dev/null 2>&1; then
    log_info "API está respondendo em http://localhost:8765"
else
    log_warn "API não está respondendo ainda (pode levar mais tempo)"
fi

# Status dos serviços
echo ""
echo "Status dos serviços:"
systemctl status claude-brain --no-pager || true
echo ""
systemctl status claude-brain-watchdog.timer --no-pager || true

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          🎉 AUTO-DEPLOY CONFIGURADO COM SUCESSO! 🎉       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "🛡️  CAMADAS DE PROTEÇÃO ATIVAS:"
echo ""
echo "   1️⃣  Docker Restart Policy"
echo "       • Container reinicia automaticamente se crashar"
echo "       • Policy: restart=always"
echo ""
echo "   2️⃣  Systemd Service"
echo "       • Serviço inicia com o sistema operacional"
echo "       • Reinicia automaticamente em caso de falha"
echo "       • Comando: systemctl [start|stop|restart|status] claude-brain"
echo ""
echo "   3️⃣  Watchdog Health Checker"
echo "       • Verifica saúde da API a cada 2 minutos"
echo "       • Auto-recovery após 3 falhas consecutivas"
echo "       • Logs em: /var/log/claude-brain-watchdog.log"
echo ""
echo "📍 ACESSO:"
echo "   • API: http://localhost:8765"
echo "   • Dashboard: http://localhost:8765/dashboard"
echo "   • Stats: http://localhost:8765/v1/stats"
echo ""
echo "📋 COMANDOS ÚTEIS:"
echo "   # Gerenciar serviço"
echo "   sudo systemctl status claude-brain"
echo "   sudo systemctl restart claude-brain"
echo "   sudo systemctl stop claude-brain"
echo ""
echo "   # Ver logs"
echo "   docker-compose logs -f                    # Logs do container"
echo "   journalctl -u claude-brain -f             # Logs do systemd"
echo "   tail -f /var/log/claude-brain-watchdog.log # Logs do watchdog"
echo ""
echo "   # Status do watchdog"
echo "   systemctl status claude-brain-watchdog.timer"
echo "   systemctl list-timers | grep claude-brain"
echo ""
echo "   # Forçar health check manual"
echo "   sudo /usr/local/bin/claude-brain-watchdog"
echo ""
echo "🧪 TESTE DE AUTO-RECOVERY:"
echo "   # Simular crash"
echo "   docker stop claude-brain-api"
echo "   # Aguardar ~2-6 minutos e verificar auto-recovery"
echo "   docker ps | grep claude-brain"
echo ""
echo "✅ Próximos passos:"
echo "   1. Testar API: curl http://localhost:8765/v1/stats"
echo "   2. Testar auto-recovery: docker stop claude-brain-api && sleep 5m && docker ps"
echo "   3. Reiniciar servidor: sudo reboot (serviço volta automaticamente)"
echo ""
