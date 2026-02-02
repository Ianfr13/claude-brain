#!/usr/bin/env python3
"""
Claude Brain - Memory Base Module

Este modulo contem:
- Conexao com banco de dados (get_db)
- Constantes globais (DB_PATH, ALLOWED_TABLES, ALL_TABLES)
- Funcoes utilitarias (_hash, _escape_like, _similarity)
- Inicializacao e migracao do banco (init_db, migrate_db)

Todos os outros modulos de memory/ importam get_db daqui.

Relacionamentos:
- decisions.py, learnings.py, memories.py, etc -> importam get_db
- __init__.py -> re-exporta init_db para inicializacao externa
"""

import sqlite3
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import contextmanager
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# ============ CONSTANTES ============

DB_PATH = Path("/root/claude-brain/memory/brain.db")

# Tabelas permitidas para queries dinamicas (protecao contra SQL Injection)
ALLOWED_TABLES = {'memories', 'decisions', 'learnings'}

# Todas as tabelas do sistema (para stats e outras operacoes internas)
ALL_TABLES = {'memories', 'decisions', 'learnings', 'entities', 'relations', 'preferences', 'patterns', 'sessions', 'workflows'}

# Estados de maturidade (usado por decisions.py e learnings.py)
MATURITY_STATES = {
    "hypothesis": 0.3,    # Ideia inicial, nao testada
    "testing": 0.5,       # Sendo usada/validada
    "confirmed": 0.8,     # Validada como correta
    "deprecated": 0.1,    # Substituida ou incorreta
    "contradicted": 0.0,  # Contradita por evidencia
}


# ============ CONEXAO COM BANCO ============

@contextmanager
def get_db():
    """Context manager para conexao com banco.

    Uso:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM memories')

    Features:
    - Auto-commit em caso de sucesso
    - Auto-rollback em caso de erro
    - Conexao fechada automaticamente
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        logger.error(f"Erro no banco, fazendo rollback: {type(e).__name__}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


# ============ FUNCOES UTILITARIAS ============

def _escape_like(query: str) -> str:
    """Escapa caracteres especiais do LIKE para evitar injection.

    % e _ sao wildcards em SQLite LIKE, precisam ser escapados se forem literais.
    """
    return query.replace('%', r'\%').replace('_', r'\_')


def _hash(text: str) -> str:
    """Gera hash unico do conteudo (128 bits para evitar colisoes)"""
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _similarity(a: str, b: str) -> float:
    """Calcula similaridade entre duas strings usando SequenceMatcher"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# ============ MIGRACAO E INICIALIZACAO ============

def migrate_db():
    """Adiciona colunas novas em bancos antigos.

    Chamado automaticamente por init_db() para garantir
    que bancos existentes tenham as colunas de maturidade.
    """
    with get_db() as conn:
        c = conn.cursor()
        # Tenta adicionar cada coluna, ignora se ja existir
        for table in ['decisions', 'learnings']:
            for col, default in [
                ('maturity_status', "'hypothesis'"),
                ('confidence_score', '0.5'),
                ('times_used', '0'),
                ('times_confirmed', '0'),
                ('times_contradicted', '0'),
                ('superseded_by', 'NULL')
            ]:
                try:
                    c.execute(f'ALTER TABLE {table} ADD COLUMN {col} DEFAULT {default}')
                except Exception:
                    pass  # Coluna ja existe

        # Coluna context para learnings (adicionada posteriormente)
        try:
            c.execute("ALTER TABLE learnings ADD COLUMN context TEXT")
        except Exception:
            pass  # Coluna ja existe


def init_db():
    """Inicializa o banco de dados completo.

    Cria todas as tabelas e indices necessarios.
    Seguro para chamar multiplas vezes (usa IF NOT EXISTS).
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_db() as conn:
        c = conn.cursor()

        # Memorias gerais com embeddings
        c.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                category TEXT,
                content TEXT NOT NULL,
                content_hash TEXT UNIQUE,
                metadata JSON,
                importance INTEGER DEFAULT 5,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                decay_rate FLOAT DEFAULT 0.1
            )
        ''')

        # Decisoes arquiteturais
        c.execute('''
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT,
                context TEXT,
                decision TEXT NOT NULL,
                reasoning TEXT,
                alternatives TEXT,
                outcome TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                maturity_status TEXT DEFAULT 'hypothesis',
                confidence_score REAL DEFAULT 0.5,
                times_used INTEGER DEFAULT 0,
                times_confirmed INTEGER DEFAULT 0,
                times_contradicted INTEGER DEFAULT 0,
                superseded_by INTEGER
            )
        ''')

        # Aprendizados de erros (para nao repetir)
        c.execute('''
            CREATE TABLE IF NOT EXISTS learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                error_pattern TEXT,
                error_message TEXT,
                root_cause TEXT,
                solution TEXT NOT NULL,
                prevention TEXT,
                context TEXT,
                project TEXT,
                frequency INTEGER DEFAULT 1,
                last_occurred TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                maturity_status TEXT DEFAULT 'hypothesis',
                confidence_score REAL DEFAULT 0.5,
                times_used INTEGER DEFAULT 0,
                times_confirmed INTEGER DEFAULT 0,
                times_contradicted INTEGER DEFAULT 0,
                superseded_by INTEGER
            )
        ''')

        # Entidades do knowledge graph
        c.execute('''
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                properties JSON,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')

        # Relacoes (edges do graph)
        c.execute('''
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_entity TEXT NOT NULL,
                to_entity TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight FLOAT DEFAULT 1.0,
                properties JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(from_entity, to_entity, relation_type)
            )
        ''')

        # Sessoes e contexto
        c.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                project TEXT,
                summary TEXT,
                key_decisions JSON,
                files_modified JSON,
                duration_minutes INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Preferencias do usuario (auto-detectadas)
        c.execute('''
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                confidence FLOAT DEFAULT 0.5,
                source TEXT,
                times_observed INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')

        # Padroes de codigo (snippets frequentes)
        c.execute('''
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                pattern_type TEXT,
                code TEXT NOT NULL,
                language TEXT,
                usage_count INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Workflows (sessoes de trabalho com contexto em 3 niveis)
        c.execute('''
            CREATE TABLE IF NOT EXISTS workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                project TEXT,
                status TEXT DEFAULT 'active',

                goal TEXT NOT NULL,
                todos JSON,
                insights JSON,
                files_modified JSON,

                summary TEXT,
                decisions_created JSON,
                learnings_created JSON,
                memories_created JSON,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

        # Indices
        c.execute('CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(content_hash)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_learnings_error ON learnings(error_type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_entity)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_preferences_key ON preferences(key)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_workflows_project ON workflows(project)')

    # Migra bancos antigos para adicionar colunas novas
    migrate_db()
