# ✅ Claude Brain - Problema Resolvido

## 🚨 Problema Identificado

**Data:** 2026-02-02
**Sintoma:** Servidor caindo constantemente
**Causa Raiz:** PM2 brain-api com `--workers 2` causando loop infinito de crashes

## 🔍 Diagnóstico

### Evidências:
- **PM2 Status:** brain-api com 1,365 restarts
- **Erro:** `ERROR: [Errno 98] Address already in use`
- **Loop:** Crash → PM2 restart → Crash → repeat

### Causa Técnica:
```
PM2 config: --workers 2
↓
Uvicorn cria 2 processos workers
↓
Worker 1 pega porta 8765 ✅
Worker 2 tenta porta 8765 ❌ (já em uso)
↓
Processo crash
↓
PM2 autorestart=true → reinicia
↓
LOOP INFINITO 🔄
```

## ✅ Solução Aplicada

### 1. Parou processo problemático
```bash
pm2 stop brain-api
pm2 delete brain-api
pm2 save
```

### 2. Iniciou com script correto
```bash
./START.sh
```

### 3. Atualizou ecosystem.config.cjs
- Comentou config do brain-api
- Adicionou documentação do problema
- Se reativado, removeu `--workers 2`

### 4. Watchdog já estava ativo
```bash
*/2 * * * * /usr/local/bin/claude-brain-watch
```

## 📊 Status Final

```
✅ API rodando: http://localhost:8765
✅ PID: 110231
✅ Método: START.sh (script simples)
✅ Auto-recovery: watchdog via cron
✅ Memórias: 99
✅ Decisões: 71
```

## 🛡️ Prevenção

### Arquivos modificados:
1. **ecosystem.config.cjs** - brain-api comentado
2. **PM2 state** - brain-api removido permanentemente
3. **Cron watchdog** - monitora a cada 2 minutos

### Se PM2 voltar a iniciar:
```bash
# Verificar
pm2 list | grep brain

# Remover se necessário
pm2 delete brain-api
pm2 save
```

### Gerenciamento correto:
```bash
# Iniciar
/root/claude-brain/START.sh

# Parar
/root/claude-brain/STOP.sh

# Status
ps aux | grep uvicorn | grep -v grep
curl http://localhost:8765/v1/stats
```

## 📝 Lições Aprendidas

1. **Múltiplos workers** em uvicorn precisam usar socket compartilhado ou portas diferentes
2. **PM2 com autorestart** pode causar loops infinitos se não configurado corretamente
3. **Scripts simples** são mais confiáveis que gerenciadores complexos para apps pequenos
4. **Watchdog via cron** é suficiente para auto-recovery

## 🔗 Referências

- **Documentação:** DEPLOY_COMPLETO.md
- **Scripts:** START.sh, STOP.sh
- **Watchdog:** /usr/local/bin/claude-brain-watch
- **Logs:** /tmp/claude-brain.log, /var/log/claude-brain-watch.log

## ⚠️ Notas Importantes

- **Não use** `pm2 start ecosystem.config.cjs` - brain-api está desabilitado
- **Use** `START.sh` para iniciar manualmente
- **Watchdog** cuida do auto-recovery
- **PM2** gerencia outros apps (slack-bot, webui) - deixe-os como estão

---

**Problema resolvido em:** 2026-02-02 23:33 UTC
**Downtime total:** ~10 minutos
**Status:** FUNCIONANDO ✅
