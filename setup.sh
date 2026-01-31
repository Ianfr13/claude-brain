#!/bin/bash
# Claude Brain - Setup Script
# Instala e configura o sistema de memória inteligente

set -e

BRAIN_DIR="/root/claude-brain"
CLAUDE_DIR="$HOME/.claude"

echo "🧠 Claude Brain - Setup"
echo "========================"

# 1. Cria estrutura de diretórios
echo -e "\n📁 Criando estrutura de diretórios..."
mkdir -p "$BRAIN_DIR"/{memory,rag/chunks,hooks,knowledge-graph,scripts,logs}
mkdir -p "$CLAUDE_DIR/hooks"

# 2. Torna scripts executáveis
echo "🔧 Configurando permissões..."
chmod +x "$BRAIN_DIR"/scripts/*.py
chmod +x "$BRAIN_DIR"/hooks/*.sh

# 3. Inicializa banco de dados
echo "💾 Inicializando banco de dados de memória..."
python3 "$BRAIN_DIR/scripts/memory_store.py" init

# 4. Instala dependências opcionais
echo -e "\n📦 Verificando dependências..."
if python3 -c "import chromadb" 2>/dev/null; then
    echo "  ✓ ChromaDB instalado"
else
    echo "  ⚠ ChromaDB não instalado (busca semântica desabilitada)"
    echo "  Para instalar: pip install chromadb sentence-transformers"
fi

# 5. Indexa documentos importantes
echo -e "\n📚 Indexando documentos..."

# Indexa CLAUDE.md global
if [ -f "$HOME/CLAUDE.md" ]; then
    python3 "$BRAIN_DIR/scripts/rag_engine.py" index-file "$HOME/CLAUDE.md"
fi

# Indexa docs do vsl-analysis
if [ -d "/root/vsl-analysis/docs" ]; then
    python3 "$BRAIN_DIR/scripts/rag_engine.py" index-dir "/root/vsl-analysis/docs"
fi

# 6. Popula entidades iniciais
echo -e "\n🔗 Criando knowledge graph inicial..."
python3 << 'EOF'
import sys
sys.path.insert(0, '/root/claude-brain/scripts')
from memory_store import init_db, save_entity, save_relation

init_db()

# Projetos
save_entity("vsl-analysis", "project", "Sistema de ML para gerar VSLs", {"status": "active", "path": "/root/vsl-analysis"})
save_entity("claude-swarm-plugin", "project", "Sistema de swarm distribuído", {"status": "active"})
save_entity("slack-claude-bot", "project", "Bot Slack com Claude", {"status": "active"})
save_entity("claude-brain", "project", "Sistema de memória do Claude", {"status": "active"})

# Tecnologias
save_entity("pytorch", "technology", "Framework ML", {"version": "2.x"})
save_entity("chromadb", "technology", "Vector database", {})
save_entity("sqlite", "technology", "Database local", {})
save_entity("python", "technology", "Linguagem principal", {"version": "3.11+"})

# Preferências
save_entity("pref-gpu", "preference", "Sempre usar GPU quando disponível", {})
save_entity("pref-cli", "preference", "Preferir CLI a MCP servers", {})
save_entity("pref-portugues", "preference", "Responder em português", {})

# Relações
save_relation("vsl-analysis", "pytorch", "uses")
save_relation("vsl-analysis", "pref-gpu", "applies")
save_relation("claude-brain", "chromadb", "uses")
save_relation("claude-brain", "sqlite", "uses")

print("  ✓ Knowledge graph inicializado")
EOF

# 7. Mostra estatísticas
echo -e "\n📊 Estatísticas finais:"
python3 "$BRAIN_DIR/scripts/memory_store.py" stats
python3 "$BRAIN_DIR/scripts/rag_engine.py" stats

echo -e "\n✅ Setup completo!"
echo ""
echo "Próximos passos:"
echo "  1. Indexar mais documentos:"
echo "     python3 $BRAIN_DIR/scripts/rag_engine.py index-dir /seu/projeto"
echo ""
echo "  2. Para busca semântica (opcional):"
echo "     pip install chromadb sentence-transformers"
echo "     python3 $BRAIN_DIR/scripts/rag_engine.py build-embeddings"
echo ""
echo "  3. Salvar decisões importantes:"
echo "     python3 $BRAIN_DIR/scripts/memory_store.py save-decision 'sua decisão' projeto"
echo ""
echo "  4. Configurar hooks no Claude Code (manual):"
echo "     Edite ~/.claude/settings.json"
