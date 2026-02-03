# 🚀 Claude Brain - Guia de Deploy com Auto-Recovery

## Visão Geral

Sistema de deploy automático com **3 camadas de proteção** contra falhas:

1. **Docker Restart Policy** - Container reinicia se crashar
2. **Systemd Service** - Inicia com o sistema operacional
3. **Watchdog Health Checker** - Monitora e recupera falhas a cada 2 minutos

---

## Deploy Rápido

```bash
cd /root/claude-brain
sudo ./auto-deploy.sh
```

**O script faz automaticamente:**
- ✅ Configura Docker com restart=always
- ✅ Cria systemd service para iniciar com o sistema
- ✅ Configura watchdog para monitoramento contínuo
- ✅ Habilita e inicia todos os serviços
- ✅ Valida o deploy

---

## Arquitetura de Auto-Recovery

### Fluxo de Recuperação

```
Container crash
    ↓
Docker tenta restart (política: always)
    ↓
Se falhar → Systemd detecta e reinicia
    ↓
Se falhar → Watchdog detecta após 3x (6 min)
    ↓
Watchdog força docker-compose down/up
    ↓
Se falhar → Alerta manual necessário
```

### Tempos de Recuperação

| Cenário | Tempo de Recovery | Método |
|---------|-------------------|--------|
| Container crash | ~5-10 segundos | Docker restart policy |
| Service crash | ~20-30 segundos | Systemd restart |
| API não responde | ~6-8 minutos | Watchdog (3 checks × 2min) |
| Reboot servidor | ~1-2 minutos | Systemd auto-start |

---

## Componentes

### 1. Docker Restart Policy

**Arquivo:** `docker-compose.yml`

```yaml
services:
  brain-api:
    restart: always  # Sempre reinicia, mesmo após reboot
```

**Comportamento:**
- Container para → Docker reinicia automaticamente
- Sistema reinicia → Docker inicia container após boot
- Delay: ~5-10 segundos

### 2. Systemd Service

**Arquivo:** `/etc/systemd/system/claude-brain.service`

**Comandos:**
```bash
# Status
sudo systemctl status claude-brain

# Iniciar
sudo systemctl start claude-brain

# Parar
sudo systemctl stop claude-brain

# Reiniciar
sudo systemctl restart claude-brain

# Ver logs
journalctl -u claude-brain -f
```

**Comportamento:**
- Sistema inicia → Serviço inicia automaticamente
- Serviço falha → Systemd reinicia após 10s
- Gerenciamento centralizado

### 3. Watchdog Health Checker

**Arquivos:**
- Script: `/usr/local/bin/claude-brain-watchdog`
- Timer: `/etc/systemd/system/claude-brain-watchdog.timer`
- Service: `/etc/systemd/system/claude-brain-watchdog.service`

**Comandos:**
```bash
# Status do timer
systemctl status claude-brain-watchdog.timer

# Ver próxima execução
systemctl list-timers | grep claude-brain

# Executar manualmente
sudo /usr/local/bin/claude-brain-watchdog

# Ver logs
tail -f /var/log/claude-brain-watchdog.log
```

**Comportamento:**
- Executa a cada 2 minutos
- Faz health check em http://localhost:8765/
- Conta 3 falhas consecutivas antes de agir
- Recovery em 2 etapas:
  1. Tenta `systemctl restart claude-brain`
  2. Se falhar, força `docker-compose down && up`

**Logs:**
```
[2026-02-02 23:30:00] ✅ API recovered after 2 failures
[2026-02-02 23:32:00] ⚠️  Health check failed (1/3)
[2026-02-02 23:34:00] ⚠️  Health check failed (2/3)
[2026-02-02 23:36:00] ⚠️  Health check failed (3/3)
[2026-02-02 23:36:05] 🚨 Max failures reached. Initiating auto-recovery...
[2026-02-02 23:36:35] ✅ Auto-recovery successful via systemd restart
```

---

## Testes de Auto-Recovery

### Teste 1: Container Crash
```bash
# Simular crash
docker stop claude-brain-api

# Verificar recovery (~10 segundos)
sleep 15
docker ps | grep claude-brain

# Resultado esperado: Container rodando novamente
```

### Teste 2: Reboot do Sistema
```bash
# Reiniciar servidor
sudo reboot

# Após boot, verificar (~1-2 minutos)
docker ps | grep claude-brain
curl http://localhost:8765/v1/stats

# Resultado esperado: Serviço rodando automaticamente
```

### Teste 3: Watchdog Recovery
```bash
# Parar container e desabilitar restart temporariamente
docker update --restart=no claude-brain-api
docker stop claude-brain-api

# Aguardar watchdog (6-8 minutos)
tail -f /var/log/claude-brain-watchdog.log

# Resultado esperado: Watchdog detecta e reinicia
```

---

## Monitoramento

### Health Check Manual
```bash
# Verificar API
curl http://localhost:8765/

# Verificar stats
curl http://localhost:8765/v1/stats

# Verificar container
docker ps | grep claude-brain

# Verificar logs em tempo real
docker-compose logs -f
```

### Dashboard de Monitoramento
```bash
# Acessar dashboard web
open http://localhost:8765/dashboard

# Métricas disponíveis:
# - Total de memórias
# - Total de decisões
# - Total de aprendizados
# - Total de entidades no grafo
# - Status da API
```

### Logs Centralizados
```bash
# Container logs
docker-compose logs -f

# Systemd logs
journalctl -u claude-brain -f

# Watchdog logs
tail -f /var/log/claude-brain-watchdog.log

# Todos os logs juntos
tail -f /var/log/claude-brain-watchdog.log & \
journalctl -u claude-brain -f & \
docker-compose logs -f
```

---

## Troubleshooting

### Container não inicia

**Sintomas:**
```bash
$ docker ps | grep claude-brain
# (vazio)
```

**Diagnóstico:**
```bash
# Ver logs do container
docker-compose logs brain-api

# Ver logs do systemd
journalctl -u claude-brain -xe

# Verificar se porta está em uso
sudo lsof -i :8765
```

**Soluções:**
```bash
# 1. Rebuild completo
cd /root/claude-brain
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 2. Verificar dependências
docker-compose config

# 3. Verificar recursos do sistema
free -h
df -h
```

### API não responde

**Sintomas:**
```bash
$ curl http://localhost:8765/
curl: (7) Failed to connect to localhost port 8765
```

**Diagnóstico:**
```bash
# Container está rodando?
docker ps | grep claude-brain

# Porta está aberta?
netstat -tulpn | grep 8765

# Ver logs da aplicação
docker-compose logs --tail=50 brain-api
```

**Soluções:**
```bash
# 1. Reiniciar serviço
sudo systemctl restart claude-brain

# 2. Verificar health do container
docker inspect claude-brain-api | grep Health -A 10

# 3. Entrar no container para debug
docker exec -it claude-brain-api bash
curl http://localhost:8765/
```

### Watchdog não está monitorando

**Sintomas:**
```bash
$ systemctl status claude-brain-watchdog.timer
# Inactive (dead)
```

**Diagnóstico:**
```bash
# Timer está habilitado?
systemctl is-enabled claude-brain-watchdog.timer

# Ver próxima execução
systemctl list-timers --all | grep claude-brain

# Executar manualmente
sudo /usr/local/bin/claude-brain-watchdog
```

**Soluções:**
```bash
# 1. Habilitar timer
sudo systemctl enable claude-brain-watchdog.timer
sudo systemctl start claude-brain-watchdog.timer

# 2. Recarregar systemd
sudo systemctl daemon-reload

# 3. Verificar script do watchdog
ls -la /usr/local/bin/claude-brain-watchdog
cat /usr/local/bin/claude-brain-watchdog
```

### Performance Issues

**Sintomas:**
- API lenta para responder
- Alto uso de CPU/memória

**Diagnóstico:**
```bash
# Recursos do container
docker stats claude-brain-api

# Processos no container
docker top claude-brain-api

# Logs de erros
docker-compose logs brain-api | grep -i error
```

**Soluções:**
```bash
# 1. Aumentar recursos no docker-compose.yml
vim /root/claude-brain/docker-compose.yml
# Alterar: memory: 4G → 8G

# 2. Rebuild e restart
docker-compose down
docker-compose up -d --build

# 3. Habilitar Redis cache (reduz carga)
# Descomentar seção redis no docker-compose.yml
```

---

## Manutenção

### Backup

```bash
# Backup do banco de dados
cp /root/claude-brain/memory/brain.db /root/backup/brain.db.$(date +%Y%m%d)

# Backup do índice FAISS
tar -czf /root/backup/rag-$(date +%Y%m%d).tar.gz /root/claude-brain/rag/

# Backup completo
tar -czf /root/backup/claude-brain-$(date +%Y%m%d).tar.gz \
  /root/claude-brain/memory \
  /root/claude-brain/rag \
  /root/claude-brain/logs
```

### Update

```bash
cd /root/claude-brain

# Pull latest changes
git pull origin main

# Rebuild e restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Verificar
curl http://localhost:8765/v1/stats
```

### Logs Rotation

**Configurado automaticamente:**
- Docker: `max-size: 10m`, `max-file: 3`
- Watchdog: gerenciado por logrotate

**Manual (se necessário):**
```bash
# Limpar logs antigos do Docker
docker-compose down
docker system prune -f
docker-compose up -d

# Truncar log do watchdog
sudo truncate -s 0 /var/log/claude-brain-watchdog.log
```

---

## Desinstalar

```bash
# Parar serviços
sudo systemctl stop claude-brain
sudo systemctl stop claude-brain-watchdog.timer

# Desabilitar
sudo systemctl disable claude-brain
sudo systemctl disable claude-brain-watchdog.timer

# Remover arquivos systemd
sudo rm /etc/systemd/system/claude-brain.service
sudo rm /etc/systemd/system/claude-brain-watchdog.timer
sudo rm /etc/systemd/system/claude-brain-watchdog.service
sudo rm /usr/local/bin/claude-brain-watchdog

# Recarregar systemd
sudo systemctl daemon-reload

# Parar containers
cd /root/claude-brain
docker-compose down

# Remover volumes (CUIDADO: apaga dados)
docker-compose down -v

# Remover imagens
docker rmi $(docker images | grep claude-brain | awk '{print $3}')
```

---

## Configuração Avançada

### Alterar Intervalo do Watchdog

**Arquivo:** `/etc/systemd/system/claude-brain-watchdog.timer`

```ini
# Padrão: 2 minutos
OnUnitActiveSec=2min

# Alterar para 1 minuto (mais agressivo)
OnUnitActiveSec=1min

# Alterar para 5 minutos (menos agressivo)
OnUnitActiveSec=5min
```

**Aplicar mudança:**
```bash
sudo systemctl daemon-reload
sudo systemctl restart claude-brain-watchdog.timer
```

### Alterar Threshold de Falhas

**Arquivo:** `/usr/local/bin/claude-brain-watchdog`

```bash
# Padrão: 3 falhas
MAX_FAILURES=3

# Mais tolerante: 5 falhas
MAX_FAILURES=5

# Menos tolerante: 2 falhas
MAX_FAILURES=2
```

**Aplicar mudança:**
```bash
# Apenas editar o arquivo, não precisa restart
sudo vim /usr/local/bin/claude-brain-watchdog
```

### Notificações (Webhook/Email)

**Adicionar ao watchdog script:**

```bash
# No final da função de recovery, adicionar:
send_notification() {
    # Webhook (Slack, Discord, etc)
    curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
      -H 'Content-Type: application/json' \
      -d "{\"text\":\"🚨 Claude Brain auto-recovery: $1\"}"

    # Ou email
    echo "$1" | mail -s "Claude Brain Alert" admin@example.com
}

# Chamar quando recovery falhar
if ! curl -sf "$API_URL" > /dev/null 2>&1; then
    log "❌ Auto-recovery failed. Manual intervention required."
    send_notification "Auto-recovery failed - manual check needed"
fi
```

---

## Recursos Adicionais

- **README.md** - Documentação principal do projeto
- **ARCHITECTURE.md** - Arquitetura e design system
- **docs/QUICKSTART.md** - Tutorial rápido de 5 minutos

---

## Suporte

- **GitHub Issues**: https://github.com/Ianfr13/claude-brain/issues
- **Logs**: `/var/log/claude-brain-watchdog.log`
- **Systemd**: `journalctl -u claude-brain -f`
