#!/bin/bash
# Demonstracao do sistema de Job Queue do Brain CLI
#
# Este script demonstra todos os comandos do job queue:
# - create: Criar jobs com diferentes configuracoes
# - get: Recuperar jobs especificos
# - list: Listar jobs ativos
# - cleanup: Remover jobs expirados
# - delete: Deletar jobs manualmente
# - stats: Ver estatisticas

set -e

echo "========================================="
echo "  Brain CLI - Job Queue Demonstration"
echo "========================================="
echo

# Limpa jobs anteriores
echo "1. Limpando jobs anteriores..."
brain job cleanup
echo

# Cria job simples
echo "2. Criando job simples (TTL: 60s)..."
JOB1=$(brain job create --ttl 60 \
  --prompt "Analisar logs de erro" \
  | grep "Job criado:" | awk '{print $4}')
echo "   Job ID: $JOB1"
echo

# Cria job com skills
echo "3. Criando job com skills (TTL: 2h)..."
JOB2=$(brain job create --ttl 7200 \
  --prompt "Implementar cache Redis" \
  --skills python-pro-skill \
  --skills sql-pro-skill \
  | grep "Job criado:" | awk '{print $4}')
echo "   Job ID: $JOB2"
echo

# Cria job completo
echo "4. Criando job completo com brain queries e files (TTL: 1h)..."
JOB3=$(brain job create --ttl 3600 \
  --prompt "Otimizar queries do banco de dados" \
  --skills sql-pro-skill \
  --brain-query "performance|vsl-analysis" \
  --brain-query "database optimization" \
  --files /root/vsl-analysis/db.py \
  --files /root/vsl-analysis/queries.py \
  --context '{"priority":"high","deadline":"2026-02-05"}' \
  | grep "Job criado:" | awk '{print $4}')
echo "   Job ID: $JOB3"
echo

# Cria job usando JSON completo
echo "5. Criando job com JSON completo (TTL: 30m)..."
JOB4=$(brain job create --ttl 1800 \
  --data '{
    "prompt": "Revisar codigo de seguranca",
    "skills": ["python-pro-skill"],
    "brain_queries": [
      {"query": "security", "project": "vsl-analysis"}
    ],
    "files": ["/root/vsl-analysis/auth.py"],
    "context": {"priority": "critical"}
  }' \
  | grep "Job criado:" | awk '{print $4}')
echo "   Job ID: $JOB4"
echo

# Lista todos os jobs
echo "6. Listando jobs ativos..."
brain job list
echo

# Mostra detalhes de um job especifico
echo "7. Detalhes do job completo:"
brain job get $JOB3
echo

# Mostra job em JSON
echo "8. Job em formato JSON (para parsing automatico):"
brain job get $JOB3 --json
echo

# Mostra estatisticas
echo "9. Estatisticas de jobs:"
brain job stats
echo

# Deleta um job manualmente
echo "10. Deletando job $JOB1 manualmente..."
brain job delete $JOB1
echo

# Lista novamente
echo "11. Jobs apos delecao:"
brain job list
echo

# Stats atualizadas
echo "12. Estatisticas atualizadas:"
brain job stats
echo

echo "========================================="
echo "  Demonstracao de TTL e Auto-cleanup"
echo "========================================="
echo

# Cria job com TTL curto para demonstrar expiracao
echo "13. Criando job com TTL de 5 segundos..."
JOB_SHORT=$(brain job create --ttl 5 \
  --prompt "Job que expira rapidamente" \
  | grep "Job criado:" | awk '{print $4}')
echo "   Job ID: $JOB_SHORT"
echo

echo "14. Verificando que job existe..."
brain job get $JOB_SHORT > /dev/null && echo "   OK: Job encontrado"
echo

echo "15. Aguardando 6 segundos para job expirar..."
sleep 6
echo

echo "16. Tentando recuperar job expirado..."
if brain job get $JOB_SHORT 2>&1 | grep -q "expirado"; then
  echo "   OK: Job foi automaticamente removido apos expiracao"
fi
echo

# Lista final
echo "17. Jobs ativos finais:"
brain job list
echo

# Cleanup manual
echo "18. Executando cleanup manual (remove jobs expirados)..."
brain job cleanup
echo

# Stats finais
echo "19. Estatisticas finais:"
brain job stats
echo

echo "========================================="
echo "  Casos de Uso Praticos"
echo "========================================="
echo

echo "CASO 1: Job para sessao de trabalho longa"
echo "-------------------------------------------"
echo "brain job create --ttl 14400 \\"
echo "  --prompt 'Implementar sistema de notificacoes' \\"
echo "  --skills python-pro-skill \\"
echo "  --brain-query 'websockets|vsl-analysis' \\"
echo "  --brain-query 'real-time notifications' \\"
echo "  --files /root/vsl-analysis/notifications.py \\"
echo "  --context '{\"session\":\"afternoon\",\"priority\":\"high\"}'"
echo

echo "CASO 2: Job rapido para debug"
echo "-------------------------------------------"
echo "brain job create --ttl 300 \\"
echo "  --prompt 'Investigar erro de conexao Redis' \\"
echo "  --skills python-pro-skill \\"
echo "  --brain-query 'redis errors|vsl-analysis' \\"
echo "  --files /root/vsl-analysis/cache.py"
echo

echo "CASO 3: Job de refatoracao"
echo "-------------------------------------------"
echo "brain job create --ttl 7200 \\"
echo "  --prompt 'Refatorar modulo de autenticacao' \\"
echo "  --skills python-pro-skill \\"
echo "  --brain-query 'auth patterns' \\"
echo "  --brain-query 'security best practices' \\"
echo "  --files /root/vsl-analysis/auth.py \\"
echo "  --files /root/vsl-analysis/middleware.py \\"
echo "  --context '{\"type\":\"refactor\",\"tests_required\":true}'"
echo

echo "========================================="
echo "  Limpeza Final"
echo "========================================="
echo

echo "Removendo todos os jobs de demonstracao..."
brain job delete $JOB2 2>/dev/null || true
brain job delete $JOB3 2>/dev/null || true
brain job delete $JOB4 2>/dev/null || true
brain job cleanup
echo

echo "Jobs restantes:"
brain job list
echo

echo "========================================="
echo "  Demonstracao Concluida!"
echo "========================================="
echo
echo "Para mais informacoes:"
echo "  brain job --help"
echo
