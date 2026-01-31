#!/usr/bin/env python3
"""
Claude Brain - Memory Store (Enhanced)
Sistema de memória persistente com auto-learning
"""

import sqlite3
import json
import os
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

DB_PATH = Path("/root/claude-brain/memory/brain.db")

# Tabelas permitidas para queries dinâmicas (proteção contra SQL Injection)
ALLOWED_TABLES = {'memories', 'decisions', 'learnings'}

# Todas as tabelas do sistema (para stats e outras operações internas)
ALL_TABLES = {'memories', 'decisions', 'learnings', 'entities', 'relations', 'preferences', 'patterns', 'sessions'}


def _escape_like(query: str) -> str:
    """Escapa caracteres especiais do LIKE para evitar injection.

    % e _ são wildcards em SQLite LIKE, precisam ser escapados se forem literais.
    """
    return query.replace('%', r'\%').replace('_', r'\_')


@contextmanager
def get_db():
    """Context manager para conexão com banco"""
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


def migrate_db():
    """Adiciona colunas novas em bancos antigos"""
    with get_db() as conn:
        c = conn.cursor()
        # Tenta adicionar cada coluna, ignora se já existir
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
                    pass  # Coluna já existe


def init_db():
    """Inicializa o banco de dados completo"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_db() as conn:
        c = conn.cursor()

        # Memórias gerais com embeddings
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

        # Decisões arquiteturais
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

        # Aprendizados de erros (para não repetir)
        c.execute('''
            CREATE TABLE IF NOT EXISTS learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                error_pattern TEXT,
                error_message TEXT,
                root_cause TEXT,
                solution TEXT NOT NULL,
                prevention TEXT,
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

        # Relações (edges do graph)
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

        # Sessões e contexto
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

        # Preferências do usuário (auto-detectadas)
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

        # Padrões de código (snippets frequentes)
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

        # Índices
        c.execute('CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(content_hash)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_learnings_error ON learnings(error_type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_entity)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_preferences_key ON preferences(key)')

    # Migra bancos antigos para adicionar colunas novas
    migrate_db()


def _hash(text: str) -> str:
    """Gera hash único do conteúdo (128 bits para evitar colisões)"""
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _similarity(a: str, b: str) -> float:
    """Calcula similaridade entre duas strings usando SequenceMatcher"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _find_similar_learning(conn, error_type: str, error_message: Optional[str] = None,
                           solution: Optional[str] = None, threshold: float = 0.8) -> Optional[Dict]:
    """
    Busca learning similar usando fuzzy matching.
    Retorna o learning mais similar se acima do threshold.
    """
    c = conn.cursor()

    # Busca todos os learnings do mesmo error_type
    c.execute('SELECT * FROM learnings WHERE error_type = ?', (error_type,))
    candidates = [dict(row) for row in c.fetchall()]

    if not candidates:
        return None

    best_match = None
    best_score = 0.0

    for candidate in candidates:
        # Calcula similaridade combinada
        scores = []

        # Similaridade do error_message (peso maior)
        if error_message and candidate.get('error_message'):
            msg_sim = _similarity(error_message, candidate['error_message'])
            scores.append(msg_sim * 2)  # Peso 2x

        # Similaridade da solution
        if solution and candidate.get('solution'):
            sol_sim = _similarity(solution, candidate['solution'])
            scores.append(sol_sim)

        # Calcula média ponderada
        if scores:
            avg_score = sum(scores) / len(scores)
            if avg_score > best_score:
                best_score = avg_score
                best_match = candidate

    # Retorna apenas se acima do threshold
    if best_match and best_score >= threshold:
        return best_match

    return None


# ============ MEMÓRIAS ============

def save_memory(memory_type: str, content: str, category: Optional[str] = None,
                metadata: Optional[Dict[str, Any]] = None, importance: int = 5) -> int:
    """Salva uma memória no banco, evitando duplicatas.

    Se o conteúdo já existir, incrementa o contador de acesso e retorna o ID existente.

    Args:
        memory_type: Tipo da memória (general, session, extracted, etc)
        content: Conteúdo textual da memória
        category: Categoria opcional para agrupamento
        metadata: Dicionário com metadados extras (será serializado como JSON)
        importance: Nível de importância de 1-10 (default: 5)

    Returns:
        ID da memória (nova ou existente se duplicata)
    """
    content_hash = _hash(content)

    with get_db() as conn:
        c = conn.cursor()

        # Verifica se já existe
        c.execute('SELECT id, access_count FROM memories WHERE content_hash = ?', (content_hash,))
        existing = c.fetchone()

        if existing:
            # Incrementa acesso
            c.execute('''
                UPDATE memories
                SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (existing['id'],))
            return existing['id']

        # Insere nova
        c.execute('''
            INSERT INTO memories (type, category, content, content_hash, metadata, importance)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (memory_type, category, content, content_hash,
              json.dumps(metadata) if metadata else None, importance))

        return c.lastrowid


def search_memories(query: Optional[str] = None, type: Optional[str] = None, category: Optional[str] = None,
                    min_importance: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    """Busca memórias por critérios combinados.

    Args:
        query: Texto para busca LIKE no conteúdo (opcional)
        type: Filtrar por tipo de memória (opcional)
        category: Filtrar por categoria (opcional)
        min_importance: Importância mínima (0-10, default: 0)
        limit: Número máximo de resultados (default: 10)

    Returns:
        Lista de dicts com os campos da memória, ordenados por importância/acesso/data
    """
    with get_db() as conn:
        c = conn.cursor()

        sql = "SELECT * FROM memories WHERE importance >= ?"
        params: List[Any] = [min_importance]

        if type:
            sql += " AND type = ?"
            params.append(type)
        if category:
            sql += " AND category = ?"
            params.append(category)
        if query:
            sql += " AND content LIKE ? ESCAPE '\\'"
            params.append(f"%{_escape_like(query)}%")

        sql += " ORDER BY importance DESC, access_count DESC, created_at DESC LIMIT ?"
        params.append(limit)

        c.execute(sql, params)
        return [dict(row) for row in c.fetchall()]


# ============ DECISÕES ============

def save_decision(decision: str, reasoning: Optional[str] = None, project: Optional[str] = None,
                  context: Optional[str] = None, alternatives: Optional[str] = None,
                  is_established: bool = False) -> int:
    """Salva uma decisão arquitetural no banco.

    Args:
        decision: Texto descrevendo a decisão tomada
        reasoning: Justificativa/motivo da decisão (opcional)
        project: Nome do projeto relacionado (opcional)
        context: Contexto em que a decisão foi tomada (opcional)
        alternatives: Alternativas consideradas (opcional)
        is_established: Se True, é conhecimento estabelecido (best practice)
                       e começa como 'confirmed' com confiança 0.85.
                       Se False (padrão), começa como 'hypothesis' com confiança 0.5.

    Returns:
        ID da decisão criada
    """
    status = "confirmed" if is_established else "hypothesis"
    confidence = 0.85 if is_established else 0.5

    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO decisions (project, context, decision, reasoning, alternatives,
                                   maturity_status, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (project, context, decision, reasoning, alternatives, status, confidence))
        return c.lastrowid


def update_decision_outcome(decision_id: int, outcome: str, status: Optional[str] = None) -> None:
    """Atualiza resultado de uma decisão"""
    with get_db() as conn:
        c = conn.cursor()
        if status:
            c.execute('''
                UPDATE decisions SET outcome = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (outcome, status, decision_id))
        else:
            c.execute('''
                UPDATE decisions SET outcome = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (outcome, decision_id))


def get_decisions(project: Optional[str] = None, status: str = 'active', limit: int = 10) -> List[Dict[str, Any]]:
    """Busca decisões"""
    with get_db() as conn:
        c = conn.cursor()

        if project:
            c.execute('''
                SELECT * FROM decisions WHERE project = ? AND status = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (project, status, limit))
        else:
            c.execute('''
                SELECT * FROM decisions WHERE status = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (status, limit))

        return [dict(row) for row in c.fetchall()]


# ============ APRENDIZADOS ============

def save_learning(error_type: str, solution: str, error_message: Optional[str] = None,
                  root_cause: Optional[str] = None, prevention: Optional[str] = None, project: Optional[str] = None,
                  context: Optional[str] = None, similarity_threshold: float = 0.8,
                  is_established: bool = False) -> int:
    """
    Salva um aprendizado de erro.
    Usa fuzzy matching para detectar learnings similares e consolidar (aumentar frequência)
    em vez de duplicar.

    Args:
        error_type: Tipo do erro (ex: "ModuleNotFoundError")
        solution: Solução aplicada
        error_message: Mensagem de erro completa
        root_cause: Causa raiz identificada
        prevention: Como prevenir no futuro
        project: Projeto onde ocorreu
        context: Contexto do que estava sendo feito quando o erro ocorreu
        similarity_threshold: Threshold para considerar similar (default 0.8)
        is_established: Se True, é solução conhecida/documentada (começa confirmed)

    Returns:
        ID do learning (existente ou novo)
    """
    status = "confirmed" if is_established else "hypothesis"
    confidence = 0.85 if is_established else 0.5

    with get_db() as conn:
        c = conn.cursor()

        # Busca learning similar usando fuzzy matching
        existing = _find_similar_learning(
            conn, error_type, error_message, solution, threshold=similarity_threshold
        )

        if existing:
            # Consolida: atualiza frequência e melhora solução se fornecida
            c.execute('''
                UPDATE learnings SET frequency = frequency + 1,
                last_occurred = CURRENT_TIMESTAMP,
                solution = COALESCE(?, solution),
                root_cause = COALESCE(?, root_cause),
                prevention = COALESCE(?, prevention),
                context = COALESCE(?, context)
                WHERE id = ?
            ''', (solution, root_cause, prevention, context, existing['id']))
            return existing['id']

        # Novo learning
        c.execute('''
            INSERT INTO learnings (error_type, error_message, root_cause, solution, prevention, project, context,
                                   maturity_status, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (error_type, error_message, root_cause, solution, prevention, project, context, status, confidence))
        return c.lastrowid


def find_solution(error_type: Optional[str] = None, error_message: Optional[str] = None,
                  similarity_threshold: float = 0.6) -> Optional[Dict[str, Any]]:
    """
    Busca solução para um erro usando fuzzy matching.

    Args:
        error_type: Tipo do erro (ex: "ModuleNotFoundError")
        error_message: Mensagem de erro para busca por similaridade
        similarity_threshold: Threshold minimo de similaridade (default 0.6 para busca)

    Returns:
        Dict com learning encontrado ou None
    """
    with get_db() as conn:
        c = conn.cursor()

        if error_type and error_message:
            # Primeiro tenta match exato por error_type
            c.execute('SELECT * FROM learnings WHERE error_type = ?', (error_type,))
            candidates = [dict(row) for row in c.fetchall()]

            if candidates:
                # Usa fuzzy matching para encontrar o melhor match
                best_match = None
                best_score = 0.0

                for candidate in candidates:
                    if candidate.get('error_message'):
                        score = _similarity(error_message, candidate['error_message'])
                        if score > best_score:
                            best_score = score
                            best_match = candidate

                # Retorna se acima do threshold ou o mais frequente
                if best_match and best_score >= similarity_threshold:
                    return best_match

                # Fallback: retorna o mais frequente do mesmo tipo
                return max(candidates, key=lambda x: (x.get('frequency', 0), x.get('last_occurred', '')))

            # Se nao achou por tipo, busca por similaridade em todas as mensagens
            c.execute('SELECT * FROM learnings')
            all_learnings = [dict(row) for row in c.fetchall()]

            best_match = None
            best_score = 0.0

            for learning in all_learnings:
                if learning.get('error_message'):
                    score = _similarity(error_message, learning['error_message'])
                    if score > best_score:
                        best_score = score
                        best_match = learning

            if best_match and best_score >= similarity_threshold:
                return best_match

        elif error_type:
            c.execute('''
                SELECT * FROM learnings WHERE error_type = ?
                ORDER BY frequency DESC LIMIT 1
            ''', (error_type,))
            row = c.fetchone()
            return dict(row) if row else None

        return None


def get_all_learnings(limit: int = 20) -> List[Dict[str, Any]]:
    """Lista todos os aprendizados"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT * FROM learnings
            ORDER BY frequency DESC, last_occurred DESC LIMIT ?
        ''', (limit,))
        return [dict(row) for row in c.fetchall()]


# ============ KNOWLEDGE GRAPH ============

def save_entity(name: str, type: str, description: Optional[str] = None,
                properties: Optional[Dict[str, Any]] = None) -> int:
    """Salva ou atualiza uma entidade"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO entities (name, type, description, properties, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(name) DO UPDATE SET
                type = excluded.type,
                description = COALESCE(excluded.description, entities.description),
                properties = COALESCE(excluded.properties, entities.properties),
                updated_at = CURRENT_TIMESTAMP
        ''', (name, type, description, json.dumps(properties) if properties else None))
        return c.lastrowid


def save_relation(from_entity: str, to_entity: str, relation_type: str,
                  weight: float = 1.0, properties: Optional[Dict[str, Any]] = None) -> None:
    """Salva uma relação entre entidades"""
    # Garante que entidades existem
    with get_db() as conn:
        c = conn.cursor()

        c.execute('SELECT 1 FROM entities WHERE name = ?', (from_entity,))
        if not c.fetchone():
            save_entity(from_entity, "unknown")

        c.execute('SELECT 1 FROM entities WHERE name = ?', (to_entity,))
        if not c.fetchone():
            save_entity(to_entity, "unknown")

        c.execute('''
            INSERT INTO relations (from_entity, to_entity, relation_type, weight, properties)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(from_entity, to_entity, relation_type) DO UPDATE SET
                weight = excluded.weight,
                properties = excluded.properties
        ''', (from_entity, to_entity, relation_type, weight,
              json.dumps(properties) if properties else None))


def get_entity(name: str) -> Optional[Dict[str, Any]]:
    """Busca uma entidade"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM entities WHERE name = ?', (name,))
        row = c.fetchone()
        return dict(row) if row else None


def get_entity_graph(name: str) -> Optional[Dict[str, Any]]:
    """Retorna grafo completo de uma entidade"""
    entity = get_entity(name)
    if not entity:
        return None

    with get_db() as conn:
        c = conn.cursor()

        # Relações de saída
        c.execute('''
            SELECT r.*, e.type as to_type, e.description as to_desc
            FROM relations r
            LEFT JOIN entities e ON r.to_entity = e.name
            WHERE r.from_entity = ?
        ''', (name,))
        outgoing = [dict(row) for row in c.fetchall()]

        # Relações de entrada
        c.execute('''
            SELECT r.*, e.type as from_type, e.description as from_desc
            FROM relations r
            LEFT JOIN entities e ON r.from_entity = e.name
            WHERE r.to_entity = ?
        ''', (name,))
        incoming = [dict(row) for row in c.fetchall()]

    return {
        "entity": entity,
        "outgoing": outgoing,
        "incoming": incoming
    }


def get_related_entities(name: str, relation_type: Optional[str] = None, depth: int = 1) -> List[Dict[str, Any]]:
    """Busca entidades relacionadas (com profundidade)

    Refatorado: Usa conexão única para evitar N+1 queries
    """
    # Limitar profundidade máxima para evitar stack overflow
    MAX_DEPTH = 10
    depth = min(depth, MAX_DEPTH)

    visited = set()
    results = []

    # Refactoring: Conexão única para toda a travessia (evita N+1)
    with get_db() as conn:
        c = conn.cursor()

        def _traverse(entity_name: str, current_depth: int):
            if current_depth > depth or entity_name in visited:
                return
            visited.add(entity_name)

            sql = 'SELECT to_entity, relation_type FROM relations WHERE from_entity = ?'
            params = [entity_name]

            if relation_type:
                sql += ' AND relation_type = ?'
                params.append(relation_type)

            c.execute(sql, params)

            for row in c.fetchall():
                results.append({
                    "entity": row['to_entity'],
                    "relation": row['relation_type'],
                    "depth": current_depth
                })
                _traverse(row['to_entity'], current_depth + 1)

        _traverse(name, 1)

    return results


# ============ PREFERÊNCIAS ============

def save_preference(key: str, value: str, confidence: float = 0.5, source: Optional[str] = None) -> None:
    """Salva ou atualiza uma preferência"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO preferences (key, value, confidence, source, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                confidence = MAX(preferences.confidence, excluded.confidence),
                times_observed = preferences.times_observed + 1,
                updated_at = CURRENT_TIMESTAMP
        ''', (key, value, confidence, source))


def get_preference(key: str) -> Optional[str]:
    """Busca uma preferência"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT value FROM preferences WHERE key = ?', (key,))
        row = c.fetchone()
        return row['value'] if row else None


def get_all_preferences(min_confidence: float = 0.3) -> Dict[str, str]:
    """Retorna todas as preferências"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT key, value FROM preferences
            WHERE confidence >= ?
            ORDER BY times_observed DESC
        ''', (min_confidence,))
        return {row['key']: row['value'] for row in c.fetchall()}


# ============ PADRÕES DE CÓDIGO ============

def save_pattern(name: str, code: str, pattern_type: Optional[str] = None, language: Optional[str] = None) -> None:
    """Salva um padrão de código"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO patterns (name, pattern_type, code, language)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                code = excluded.code,
                pattern_type = excluded.pattern_type,
                usage_count = patterns.usage_count + 1,
                last_used = CURRENT_TIMESTAMP
        ''', (name, pattern_type, code, language))


def get_pattern(name: str) -> Optional[str]:
    """Busca um padrão de código (sem side-effects)"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT code FROM patterns WHERE name = ?', (name,))
        row = c.fetchone()
        return row['code'] if row else None


def increment_pattern_usage(name: str) -> bool:
    """Incrementa contador de uso de um pattern (usar separadamente de get_pattern)"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            UPDATE patterns SET usage_count = usage_count + 1, last_used = CURRENT_TIMESTAMP
            WHERE name = ?
        ''', (name,))
        return c.rowcount > 0


def get_all_entities(type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Lista todas as entidades"""
    with get_db() as conn:
        c = conn.cursor()
        if type:
            c.execute('''
                SELECT * FROM entities
                WHERE type = ?
                ORDER BY updated_at DESC LIMIT ?
            ''', (type, limit))
        else:
            c.execute('''
                SELECT * FROM entities
                ORDER BY updated_at DESC LIMIT ?
            ''', (limit,))

        entities = []
        for row in c.fetchall():
            entity = dict(row)
            if entity.get('properties'):
                try:
                    entity['properties'] = json.loads(entity['properties'])
                except (json.JSONDecodeError, TypeError):
                    pass
            entities.append(entity)
        return entities


def get_all_patterns(pattern_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Lista todos os padrões"""
    with get_db() as conn:
        c = conn.cursor()
        if pattern_type:
            c.execute('''
                SELECT * FROM patterns
                WHERE pattern_type = ?
                ORDER BY usage_count DESC, last_used DESC LIMIT ?
            ''', (pattern_type, limit))
        else:
            c.execute('''
                SELECT * FROM patterns
                ORDER BY usage_count DESC, last_used DESC LIMIT ?
            ''', (limit,))

        return [dict(row) for row in c.fetchall()]


# ============ SESSÕES ============

def save_session(session_id: str, project: Optional[str] = None, summary: Optional[str] = None,
                 key_decisions: Optional[List[Dict[str, Any]]] = None, files_modified: Optional[List[str]] = None,
                 duration_minutes: Optional[int] = None) -> None:
    """Salva resumo de uma sessão"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO sessions (session_id, project, summary, key_decisions, files_modified, duration_minutes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                summary = excluded.summary,
                key_decisions = excluded.key_decisions,
                files_modified = excluded.files_modified,
                duration_minutes = excluded.duration_minutes
        ''', (session_id, project, summary,
              json.dumps(key_decisions) if key_decisions else None,
              json.dumps(files_modified) if files_modified else None,
              duration_minutes))


def get_recent_sessions(project: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca sessões recentes"""
    with get_db() as conn:
        c = conn.cursor()

        if project:
            c.execute('''
                SELECT * FROM sessions WHERE project = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (project, limit))
        else:
            c.execute('''
                SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?
            ''', (limit,))

        return [dict(row) for row in c.fetchall()]


# ============ EXPORT ============

def export_context(project: Optional[str] = None, include_learnings: bool = True) -> str:
    """Exporta contexto formatado para Claude"""
    output = ["# Contexto da Memória\n"]

    # Preferências
    prefs = get_all_preferences()
    if prefs:
        output.append("## Preferências Conhecidas")
        for k, v in list(prefs.items())[:10]:
            output.append(f"- **{k}**: {v}")
        output.append("")

    # Decisões recentes
    decisions = get_decisions(project, limit=5)
    if decisions:
        output.append("## Decisões Recentes")
        for d in decisions:
            proj = f"[{d['project']}] " if d['project'] else ""
            output.append(f"- {proj}{d['decision']}")
            if d['reasoning']:
                output.append(f"  - Razão: {d['reasoning']}")
        output.append("")

    # Aprendizados (erros a evitar)
    if include_learnings:
        learnings = get_all_learnings(limit=5)
        if learnings:
            output.append("## Erros a Evitar")
            for l in learnings:
                output.append(f"- **{l['error_type']}**: {l['prevention'] or l['solution']}")
            output.append("")

    # Entidades do projeto
    if project:
        graph = get_entity_graph(project)
        if graph:
            output.append(f"## Contexto: {project}")
            if graph['entity'].get('description'):
                output.append(f"{graph['entity']['description']}\n")
            if graph['outgoing']:
                output.append("Tecnologias/Dependências:")
                for r in graph['outgoing']:
                    output.append(f"- [{r['relation_type']}] {r['to_entity']}")
            output.append("")

    return "\n".join(output)


def get_stats() -> Dict[str, Any]:
    """Retorna estatísticas do banco"""
    with get_db() as conn:
        c = conn.cursor()

        stats = {}

        for table in ALL_TABLES:
            c.execute(f'SELECT COUNT(*) FROM {table}')
            stats[table] = c.fetchone()[0]

        # Preferências mais observadas
        c.execute('SELECT key, times_observed FROM preferences ORDER BY times_observed DESC LIMIT 3')
        stats['top_preferences'] = [dict(row) for row in c.fetchall()]

        # Erros mais frequentes
        c.execute('SELECT error_type, frequency FROM learnings ORDER BY frequency DESC LIMIT 3')
        stats['top_errors'] = [dict(row) for row in c.fetchall()]

    return stats


# ============ SISTEMA DE MATURAÇÃO ============

# Estados de maturidade
MATURITY_STATES = {
    "hypothesis": 0.3,    # Ideia inicial, não testada
    "testing": 0.5,       # Sendo usada/validada
    "confirmed": 0.8,     # Validada como correta
    "deprecated": 0.1,    # Substituída ou incorreta
    "contradicted": 0.0,  # Contradita por evidência
}


def record_usage(table: str, record_id: int, was_useful: bool = True) -> float:
    """
    Registra uso de um conhecimento e atualiza confiança.
    Retorna novo score de confiança.
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela inválida: {table}")

    with get_db() as conn:
        c = conn.cursor()

        # Incrementa uso
        c.execute(f'''
            UPDATE {table} SET
                times_used = times_used + 1,
                times_confirmed = times_confirmed + ?
            WHERE id = ?
        ''', (1 if was_useful else 0, record_id))

        # Recalcula confiança
        c.execute(f'''
            SELECT times_used, times_confirmed, times_contradicted, maturity_status
            FROM {table} WHERE id = ?
        ''', (record_id,))
        row = c.fetchone()

        if not row:
            return 0.5

        used = row['times_used'] or 1
        confirmed = row['times_confirmed'] or 0
        contradicted = row['times_contradicted'] or 0
        status = row['maturity_status'] or 'hypothesis'

        # Calcula score baseado em confirmações vs contradições
        if used > 0:
            confirm_rate = confirmed / used
            contradict_rate = contradicted / used if used > 0 else 0
            new_score = min(0.95, max(0.05, 0.5 + (confirm_rate * 0.4) - (contradict_rate * 0.5)))
        else:
            new_score = MATURITY_STATES.get(status, 0.5)

        # Atualiza status baseado no score e uso
        new_status = status
        if used >= 3:  # Precisa de pelo menos 3 usos para mudar status
            if new_score >= 0.7:
                new_status = "confirmed"
            elif new_score <= 0.2:
                new_status = "deprecated"
            elif status == "hypothesis":
                new_status = "testing"

        c.execute(f'''
            UPDATE {table} SET confidence_score = ?, maturity_status = ?
            WHERE id = ?
        ''', (new_score, new_status, record_id))

        return new_score


def contradict_knowledge(table: str, record_id: int, reason: Optional[str] = None,
                         replacement_id: Optional[int] = None) -> None:
    """
    Marca um conhecimento como contradito/incorreto.
    Opcionalmente aponta para o conhecimento que o substitui.
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela inválida: {table}")

    with get_db() as conn:
        c = conn.cursor()

        c.execute(f'''
            UPDATE {table} SET
                times_contradicted = times_contradicted + 1,
                maturity_status = CASE
                    WHEN times_contradicted >= 2 THEN 'contradicted'
                    ELSE 'deprecated'
                END,
                confidence_score = CASE
                    WHEN times_contradicted >= 2 THEN 0.0
                    ELSE confidence_score * 0.5
                END,
                superseded_by = COALESCE(?, superseded_by)
            WHERE id = ?
        ''', (replacement_id, record_id))


def confirm_knowledge(table: str, record_id: int) -> float:
    """
    Confirma explicitamente que um conhecimento está correto.
    Retorna novo score de confiança.
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela inválida: {table}")

    return record_usage(table, record_id, was_useful=True)


def get_knowledge_by_maturity(table: str, status: Optional[str] = None,
                               min_confidence: float = 0.0,
                               limit: int = 20) -> List[Dict[str, Any]]:
    """
    Busca conhecimentos por status de maturidade.
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela inválida: {table}")

    with get_db() as conn:
        c = conn.cursor()

        sql = f'''
            SELECT *,
                CASE maturity_status
                    WHEN 'confirmed' THEN '✓'
                    WHEN 'testing' THEN '?'
                    WHEN 'hypothesis' THEN '○'
                    WHEN 'deprecated' THEN '✗'
                    WHEN 'contradicted' THEN '⊗'
                    ELSE '?'
                END as status_icon
            FROM {table}
            WHERE confidence_score >= ?
        '''
        params: List[Any] = [min_confidence]

        if status:
            sql += ' AND maturity_status = ?'
            params.append(status)

        sql += ' ORDER BY confidence_score DESC, times_used DESC LIMIT ?'
        params.append(limit)

        c.execute(sql, params)
        return [dict(row) for row in c.fetchall()]


def get_hypotheses(table: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retorna conhecimentos que ainda são hipóteses (não confirmados).
    Útil para revisão periódica.
    """
    if table is not None and table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela inválida: {table}")

    results = []

    # Queries específicas para cada tabela
    queries = {
        'decisions': '''
            SELECT 'decisions' as source_table, id, decision as summary,
                confidence_score, maturity_status, times_used, created_at
            FROM decisions
            WHERE maturity_status IN ('hypothesis', 'testing')
        ''',
        'learnings': '''
            SELECT 'learnings' as source_table, id, error_type || ': ' || solution as summary,
                confidence_score, maturity_status, times_used, created_at
            FROM learnings
            WHERE maturity_status IN ('hypothesis', 'testing')
        ''',
        # NOTA: memories não tem colunas de maturidade, removido do query
    }

    # Database optimization: memories não tem colunas de maturidade
    tables_to_query = [table] if table else ['decisions', 'learnings']

    with get_db() as conn:
        c = conn.cursor()

        for t in tables_to_query:
            if t in queries:
                try:
                    c.execute(queries[t] + ' ORDER BY created_at DESC LIMIT ?', (limit,))
                    results.extend([dict(row) for row in c.fetchall()])
                except Exception as e:
                    logger.warning(f"Erro ao buscar hipoteses em {t}: {e}")
                    continue

    return sorted(results, key=lambda x: x.get('confidence_score', 0))[:limit]


def get_contradicted(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retorna conhecimentos que foram contraditos.
    Útil para auditoria e limpeza.
    """
    results = []

    with get_db() as conn:
        c = conn.cursor()

        # Query específica para cada tabela
        queries = {
            'decisions': '''
                SELECT 'decisions' as source_table, id, decision as summary,
                    confidence_score, times_contradicted, superseded_by
                FROM decisions
                WHERE maturity_status IN ('deprecated', 'contradicted')
            ''',
            'learnings': '''
                SELECT 'learnings' as source_table, id, error_type || ': ' || solution as summary,
                    confidence_score, times_contradicted, superseded_by
                FROM learnings
                WHERE maturity_status IN ('deprecated', 'contradicted')
            ''',
            # NOTA: memories não tem colunas de maturidade, removido
        }

        for t, query in queries.items():
            try:
                c.execute(query + ' ORDER BY times_contradicted DESC LIMIT ?', (limit,))
                results.extend([dict(row) for row in c.fetchall()])
            except Exception as e:
                logger.warning(f"Erro ao buscar contradicted em {t}: {e}")
                continue

    return results[:limit]


def supersede_knowledge(table: str, old_id: int, new_content: str,
                        reason: Optional[str] = None, **kwargs: Any) -> int:
    """
    Substitui um conhecimento antigo por um novo.
    Marca o antigo como deprecated e cria o novo.
    Retorna o ID do novo conhecimento.
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela inválida: {table}")

    # Cria o novo conhecimento
    if table == 'decisions':
        new_id = save_decision(new_content, reasoning=reason, **kwargs)
    elif table == 'learnings':
        new_id = save_learning(new_content, **kwargs)
    elif table == 'memories':
        new_id = save_memory('updated', new_content, **kwargs)
    else:
        raise ValueError(f"Tabela desconhecida: {table}")

    # Marca o antigo como superseded
    contradict_knowledge(table, old_id, reason=reason, replacement_id=new_id)

    return new_id


# ============ FUNÇÕES DE DELETE ============

def delete_record(table: str, record_id: int) -> bool:
    """Deleta um registro específico"""
    if table not in ALLOWED_TABLES:
        logger.warning(f"Tentativa de delete em tabela não permitida: {table}")
        raise ValueError(f"Tabela inválida: {table}")

    with get_db() as conn:
        c = conn.cursor()
        c.execute(f'DELETE FROM {table} WHERE id = ?', (record_id,))
        deleted = c.rowcount > 0
        if deleted:
            logger.info(f"Deletado registro {table}#{record_id}")
        return deleted


def delete_by_search(query: str, table: Optional[str] = None, dry_run: bool = True) -> List[Dict[str, Any]]:
    """
    Encontra registros por busca LIKE e opcionalmente deleta.
    dry_run=True apenas retorna o que seria deletado.

    Args:
        query: Texto para buscar
        table: Tabela específica ('memories', 'decisions', 'learnings') ou None para todas
        dry_run: Se True, apenas mostra o que seria deletado

    Returns:
        Lista de registros encontrados/deletados
    """
    if table and table not in ALLOWED_TABLES:
        raise ValueError(f"Tabela inválida: {table}")

    tables_to_search = [table] if table else list(ALLOWED_TABLES)
    results = []
    escaped_query = _escape_like(query)

    with get_db() as conn:
        c = conn.cursor()

        for tbl in tables_to_search:
            # Campo de conteúdo varia por tabela
            content_field = 'content' if tbl == 'memories' else 'decision' if tbl == 'decisions' else 'solution'

            c.execute(f'''
                SELECT id, {content_field} as content FROM {tbl}
                WHERE {content_field} LIKE ? ESCAPE '\\'
            ''', (f'%{escaped_query}%',))

            for row in c.fetchall():
                results.append({
                    'id': row['id'],
                    'table': tbl,
                    'content': row['content'][:100] + '...' if len(row['content']) > 100 else row['content']
                })

        if not dry_run:
            for r in results:
                c.execute(f"DELETE FROM {r['table']} WHERE id = ?", (r['id'],))
            if results:
                logger.info(f"delete_by_search deletou {len(results)} registros para query '{query}'")

    return results


# Inicializa ao importar
init_db()
