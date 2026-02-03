# ✅ Claude Brain - Deploy Completo

## 🎉 STATUS: FUNCIONANDO!

A API Claude Brain está rodando em **http://localhost:8765**

---

## 🚀 Uso Rápido

### Iniciar o serviço
```bash
cd /root/claude-brain
./START.sh
```

### Parar o serviço
```bash
./STOP.sh
```

### Ver logs em tempo real
```bash
tail -f /tmp/claude-brain.log
```

### Testar API
```bash
curl http://localhost:8765/v1/stats | python3 -m json.tool
```

### Testar CLI
```bash
brain ask "como funciona redis?"
brain decisions
brain learnings
```

---

## 🛡️ Auto-Recovery Configurado

### Watchdog Ativo
- **Monitoramento**: A cada 2 minutos via cron
- **Threshold**: 3 falhas consecutivas
- **Ação**: Restart automático (STOP.sh + START.sh)
- **Logs**: `/var/log/claude-brain-watch.log`

### Verificar watchdog
```bash
# Ver cron job
sudo crontab -l | grep claude-brain

# Ver logs do watchdog
tail -f /var/log/claude-brain-watch.log

# Executar manualmente
sudo /usr/local/bin/claude-brain-watch
```

### Testar auto-recovery
```bash
# Simular crash
./STOP.sh

# Aguardar 6 minutos (3 checks × 2 min)
# Watchdog vai detectar e reiniciar automaticamente

# Verificar recovery
tail -f /var/log/claude-brain-watch.log
curl http://localhost:8765/
```

---

## 📦 Arquivos Criados

| Arquivo | Descrição |
|---------|-----------|
| `/root/claude-brain/START.sh` | Inicia a API em background |
| `/root/claude-brain/STOP.sh` | Para todos os processos |
| `/usr/local/bin/claude-brain-watch` | Watchdog de monitoramento |
| `/tmp/claude-brain.pid` | PID do processo principal |
| `/tmp/claude-brain.log` | Logs da aplicação |
| `/var/log/claude-brain-watch.log` | Logs do watchdog |
| `/tmp/claude-brain-failures` | Contador de falhas |

---

## 🔄 Iniciar Automaticamente com o Sistema

### Opção 1: Adicionar ao /etc/rc.local
```bash
echo "/root/claude-brain/START.sh" | sudo tee -a /etc/rc.local
sudo chmod +x /etc/rc.local
```

### Opção 2: Adicionar ao crontab
```bash
sudo crontab -e
# Adicionar linha:
@reboot sleep 30 && /root/claude-brain/START.sh
```

### Opção 3: Usar systemd (se preferir)
O systemd service já foi criado em `/etc/systemd/system/claude-brain-api.service`, mas tinha conflitos com processos existentes.

Se quiser usá-lo, primeiro execute:
```bash
./STOP.sh
sudo systemctl enable claude-brain-api
sudo systemctl start claude-brain-api
```

---

## 📊 Endpoints da API

| Endpoint | Descrição |
|----------|-----------|
| `GET /` | Status da API |
| `GET /v1/stats` | Estatísticas completas |
| `GET /v1/decisions` | Listar decisões |
| `GET /v1/learnings` | Listar aprendizados |
| `GET /v1/memories` | Buscar memórias |
| `GET /v1/search?q=query` | Busca semântica (FAISS) |
| `GET /v1/graph/{entity}` | Knowledge graph |
| `GET /dashboard` | Dashboard web |

---

## 🧪 Testes

### Teste 1: API está respondendo
```bash
curl http://localhost:8765/ && echo "✅ OK"
```

### Teste 2: Stats completos
```bash
curl -s http://localhost:8765/v1/stats | python3 -m json.tool | head -20
```

### Teste 3: CLI funcionando
```bash
brain ask "teste" 2>&1 | head -10
```

### Teste 4: Watchdog está ativo
```bash
sudo crontab -l | grep claude-brain-watch && echo "✅ Watchdog ativo"
```

### Teste 5: Auto-restart
```bash
# Matar processo
./STOP.sh

# Aguardar 6 minutos
sleep 360

# Verificar se voltou
curl http://localhost:8765/ && echo "✅ Auto-recovery OK"
```

---

## 🐛 Troubleshooting

### API não responde
```bash
# Ver logs
cat /tmp/claude-brain.log

# Reiniciar
./STOP.sh && ./START.sh

# Verificar porta
netstat -tulpn | grep 8765 || ss -tulpn | grep 8765
```

### Watchdog não está funcionando
```bash
# Verificar cron
sudo crontab -l | grep claude-brain

# Adicionar manualmente
sudo crontab -e
# Adicionar: */2 * * * * /usr/local/bin/claude-brain-watch

# Testar manualmente
sudo /usr/local/bin/claude-brain-watch
cat /var/log/claude-brain-watch.log
```

### Processo travado
```bash
# Forçar kill de tudo
sudo pkill -9 -f uvicorn
sudo pkill -9 -f "brain.*api"

# Limpar PIDs
rm -f /tmp/claude-brain.pid

# Reiniciar limpo
./START.sh
```

### Porta 8765 ocupada
```bash
# Ver quem está usando
sudo lsof -i :8765 || sudo ss -tulpn | grep 8765

# Matar processo
sudo fuser -k 8765/tcp

# Reiniciar
./START.sh
```

---

## 📈 Monitoramento

### Dashboard web
```bash
# Abrir no navegador
open http://localhost:8765/dashboard

# Ou via curl
curl -s http://localhost:8765/v1/stats | python3 -m json.tool
```

### Logs em tempo real
```bash
# Logs da aplicação
tail -f /tmp/claude-brain.log

# Logs do watchdog
tail -f /var/log/claude-brain-watch.log

# Ambos juntos
tail -f /tmp/claude-brain.log /var/log/claude-brain-watch.log
```

### Performance
```bash
# Ver uso de CPU/memória
ps aux | grep uvicorn

# Uso de disco
du -sh /root/claude-brain/memory
du -sh /root/claude-brain/rag

# Tamanho do banco
ls -lh /root/claude-brain/memory/brain.db
```

---

## 🔐 Segurança

✅ **API escuta apenas em 127.0.0.1** (localhost)
✅ **Não exposto externamente** por padrão
✅ **Rate limiting** configurado na API
✅ **Security headers** ativos

### Para expor externamente (usar com cuidado)
```bash
# Editar START.sh e mudar:
# --host 127.0.0.1  →  --host 0.0.0.0

# Recomendado: usar nginx como reverse proxy com HTTPS
```

---

## 📝 Próximos Passos

1. **Configurar backup automático**
```bash
# Adicionar ao cron
0 2 * * * tar -czf /root/backup/brain-$(date +\%Y\%m\%d).tar.gz /root/claude-brain/memory /root/claude-brain/rag
```

2. **Configurar alertas** (opcional)
- Integrar webhook no watchdog para Slack/Discord
- Configurar email alerts

3. **Otimizar performance** (se necessário)
- Habilitar Redis cache (descomentar no docker-compose.yml)
- Aumentar workers no uvicorn

4. **Salvar configuração no brain**
```bash
brain decide "Deploy via START.sh script" -p claude-brain \
  --reason "Simples, funciona, auto-recovery via cron"

brain learn "Deploy problema" \
  -s "Usar START.sh em vez de systemd" \
  -c "systemd tinha conflitos com processos existentes" \
  -p claude-brain
```

---

## ✅ Resumo

**O que foi configurado:**
- ✅ API rodando em http://localhost:8765
- ✅ Scripts START.sh / STOP.sh para gerenciamento
- ✅ Watchdog com auto-recovery a cada 2 minutos
- ✅ Logs em /tmp/claude-brain.log
- ✅ CLI `brain` funcionando
- ✅ Dashboard acessível

**Comandos principais:**
```bash
./START.sh          # Iniciar
./STOP.sh           # Parar
tail -f /tmp/claude-brain.log  # Ver logs
brain ask "query"   # Usar CLI
```

**Sucesso! 🎉**
