#!/usr/bin/env python3
"""
Claude Brain - Job Queue Module

Sistema de fila de jobs com TTL (Time To Live).
Jobs expiram automaticamente apos o TTL configurado.

Jobs contem:
- prompt: Instrucao principal
- skills: Lista de skills a usar
- brain_queries: Consultas ao brain com projeto opcional
- files: Arquivos relevantes
- context: Contexto adicional (dict)

Uso:
    from scripts.memory.jobs import create_job, get_job, list_jobs, cleanup_jobs

    # Criar job
    job_id = create_job(ttl=3600, data={
        "prompt": "Implementar feature X",
        "skills": ["python-pro-skill"],
        "brain_queries": [{"query": "redis", "project": "vsl-analysis"}],
        "files": ["/path/to/file.py"],
        "context": {"priority": "high"}
    })

    # Recuperar job (retorna None se expirado)
    job = get_job(job_id)

    # Listar jobs ativos
    jobs = list_jobs()

    # Limpar expirados (automatico em todos comandos)
    cleanup_jobs()
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from .base import get_db

logger = logging.getLogger(__name__)

# Estados validos do job
JOB_STATES = {
    'pending': 'Aguardando execucao',
    'executing': 'Sendo executado',
    'in_review': 'Aguardando revisao',
    'fixing': 'Em correcao',
    'completed': 'Concluido com sucesso',
    'failed': 'Falhou'
}

# Estados invalidos para iteracao
TERMINAL_STATES = {'completed', 'failed'}


def _init_jobs_table():
    """Cria tabela jobs se nao existir.

    Chamado automaticamente por todas funcoes de job.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ttl INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                data JSON NOT NULL,

                iteration INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                tools_required JSON DEFAULT '[]',
                history JSON DEFAULT '[]'
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_jobs_expires ON jobs(expires_at)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)')

        # Migracao: adiciona colunas em bancos antigos
        try:
            c.execute('ALTER TABLE jobs ADD COLUMN iteration INTEGER DEFAULT 0')
        except Exception:
            pass
        try:
            c.execute('ALTER TABLE jobs ADD COLUMN status TEXT DEFAULT "pending"')
        except Exception:
            pass
        try:
            c.execute('ALTER TABLE jobs ADD COLUMN tools_required JSON DEFAULT "[]"')
        except Exception:
            pass
        try:
            c.execute('ALTER TABLE jobs ADD COLUMN history JSON DEFAULT "[]"')
        except Exception:
            pass


def cleanup_jobs() -> int:
    """Remove jobs expirados do banco.

    Retorna o numero de jobs removidos.
    Chamado automaticamente por todos comandos job.
    """
    _init_jobs_table()

    with get_db() as conn:
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute('DELETE FROM jobs WHERE expires_at < ?', (now,))
        removed = c.rowcount

    if removed > 0:
        logger.info(f"Removidos {removed} job(s) expirado(s)")

    return removed


def create_job(ttl: int, data: Dict[str, Any]) -> str:
    """Cria um novo job na fila.

    Args:
        ttl: Time to live em segundos
        data: Dicionario com:
            - prompt (str): Instrucao principal
            - skills (list): Lista de skills a usar (opcional)
            - brain_queries (list): Lista de dicts com query e project (opcional)
            - files (list): Lista de paths (opcional)
            - context (dict): Contexto adicional (opcional)

    Returns:
        job_id gerado (UUID)

    Raises:
        ValueError: Se data nao conter 'prompt' ou TTL for invalido
    """
    _init_jobs_table()
    cleanup_jobs()

    # Validacao
    if not isinstance(data, dict):
        raise ValueError("data deve ser um dicionario")

    if "prompt" not in data:
        raise ValueError("data deve conter 'prompt'")

    if not isinstance(ttl, int) or ttl <= 0:
        raise ValueError("ttl deve ser um inteiro positivo")

    # Normaliza campos opcionais
    job_data = {
        "prompt": data["prompt"],
        "skills": data.get("skills", []),
        "brain_queries": data.get("brain_queries", []),
        "files": data.get("files", []),
        "context": data.get("context", {})
    }

    # Gera job_id e calcula expiracao
    job_id = str(uuid.uuid4())
    created_at = datetime.now()
    expires_at = created_at + timedelta(seconds=ttl)

    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO jobs (job_id, created_at, ttl, expires_at, data)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            job_id,
            created_at.isoformat(),
            ttl,
            expires_at.isoformat(),
            json.dumps(job_data)
        ))

    logger.info(f"Job criado: {job_id} (TTL: {ttl}s, expira: {expires_at})")
    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Recupera um job pelo ID.

    Args:
        job_id: ID do job

    Returns:
        Dicionario com job completo ou None se nao existir/expirado

        Estrutura do retorno:
        {
            "job_id": "uuid",
            "created_at": "2025-01-01T10:00:00",
            "ttl": 3600,
            "expires_at": "2025-01-01T11:00:00",
            "iteration": 0,
            "status": "pending",
            "tools_required": [],
            "history": [],
            "data": {
                "prompt": "...",
                "skills": [...],
                "brain_queries": [...],
                "files": [...],
                "context": {...}
            }
        }
    """
    _init_jobs_table()
    cleanup_jobs()

    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT job_id, created_at, ttl, expires_at, iteration, status, tools_required, history, data
            FROM jobs
            WHERE job_id = ?
        ''', (job_id,))

        row = c.fetchone()

    if not row:
        return None

    return {
        "job_id": row[0],
        "created_at": row[1],
        "ttl": row[2],
        "expires_at": row[3],
        "iteration": row[4],
        "status": row[5],
        "tools_required": json.loads(row[6]) if row[6] else [],
        "history": json.loads(row[7]) if row[7] else [],
        "data": json.loads(row[8])
    }


def list_jobs(include_expired: bool = False, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista todos os jobs na fila.

    Args:
        include_expired: Se True, inclui jobs expirados (default: False)
        status_filter: Filtrar por status especifico (ex: 'pending', 'in_review')

    Returns:
        Lista de jobs (mesmo formato de get_job)
        Ordenados por expires_at (mais recentes primeiro)
    """
    _init_jobs_table()

    if not include_expired:
        cleanup_jobs()

    with get_db() as conn:
        c = conn.cursor()

        if include_expired:
            if status_filter:
                c.execute('''
                    SELECT job_id, created_at, ttl, expires_at, iteration, status, tools_required, history, data
                    FROM jobs
                    WHERE status = ?
                    ORDER BY expires_at DESC
                ''', (status_filter,))
            else:
                c.execute('''
                    SELECT job_id, created_at, ttl, expires_at, iteration, status, tools_required, history, data
                    FROM jobs
                    ORDER BY expires_at DESC
                ''')
        else:
            now = datetime.now().isoformat()
            if status_filter:
                c.execute('''
                    SELECT job_id, created_at, ttl, expires_at, iteration, status, tools_required, history, data
                    FROM jobs
                    WHERE expires_at >= ? AND status = ?
                    ORDER BY expires_at DESC
                ''', (now, status_filter))
            else:
                c.execute('''
                    SELECT job_id, created_at, ttl, expires_at, iteration, status, tools_required, history, data
                    FROM jobs
                    WHERE expires_at >= ?
                    ORDER BY expires_at DESC
                ''', (now,))

        rows = c.fetchall()

    return [
        {
            "job_id": row[0],
            "created_at": row[1],
            "ttl": row[2],
            "expires_at": row[3],
            "iteration": row[4],
            "status": row[5],
            "tools_required": json.loads(row[6]) if row[6] else [],
            "history": json.loads(row[7]) if row[7] else [],
            "data": json.loads(row[8])
        }
        for row in rows
    ]


def delete_job(job_id: str) -> bool:
    """Deleta um job manualmente.

    Args:
        job_id: ID do job

    Returns:
        True se job foi deletado, False se nao existia
    """
    _init_jobs_table()

    with get_db() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
        deleted = c.rowcount > 0

    if deleted:
        logger.info(f"Job deletado: {job_id}")

    return deleted


def get_job_count(active_only: bool = True) -> Dict[str, int]:
    """Retorna estatisticas de jobs.

    Args:
        active_only: Se False, conta todos (incluindo expirados)

    Returns:
        {
            "total": int,
            "active": int (se active_only=False),
            "expired": int (se active_only=False)
        }
    """
    _init_jobs_table()

    with get_db() as conn:
        c = conn.cursor()

        if active_only:
            cleanup_jobs()
            c.execute('SELECT COUNT(*) FROM jobs')
            total = c.fetchone()[0]
            return {"total": total}
        else:
            now = datetime.now().isoformat()
            c.execute('SELECT COUNT(*) FROM jobs WHERE expires_at >= ?', (now,))
            active = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM jobs WHERE expires_at < ?', (now,))
            expired = c.fetchone()[0]
            return {
                "total": active + expired,
                "active": active,
                "expired": expired
            }


def iterate_job(job_id: str, iteration_type: str, agent: str, result: str) -> bool:
    """Itera um job - adiciona entrada no histórico e atualiza status.

    Args:
        job_id: ID do job
        iteration_type: Tipo de iteracao ('execution' ou 'review')
        agent: Agente que realizou iteracao ('haiku' ou 'opus')
        result: Resultado/output da iteracao

    Returns:
        True se iteracao foi bem-sucedida, False se job nao existir/estiver em estado terminal

    Raises:
        ValueError: Se iteration_type ou agent for invalido
    """
    _init_jobs_table()

    if iteration_type not in ('execution', 'review'):
        raise ValueError(f"iteration_type deve ser 'execution' ou 'review', recebido: {iteration_type}")

    if agent not in ('haiku', 'opus'):
        raise ValueError(f"agent deve ser 'haiku' ou 'opus', recebido: {agent}")

    job = get_job(job_id)
    if not job:
        return False

    # Verifica se job esta em estado terminal
    if job['status'] in TERMINAL_STATES:
        logger.warning(f"Nao pode iterar job em estado terminal: {job['status']}")
        return False

    # Cria entrada do histórico
    history_entry = {
        'timestamp': datetime.now().isoformat(),
        'iteration': job['iteration'] + 1,
        'type': iteration_type,
        'agent': agent,
        'result': result[:500],  # Limita resultado a 500 chars no histórico
    }

    # Determina novo status
    new_status = 'executing' if iteration_type == 'execution' else 'in_review'

    with get_db() as conn:
        c = conn.cursor()

        # Carrega histórico atual
        c.execute('SELECT history FROM jobs WHERE job_id = ?', (job_id,))
        row = c.fetchone()
        if row:
            current_history = json.loads(row[0]) if row[0] else []
        else:
            return False

        # Adiciona nova entrada
        current_history.append(history_entry)

        # Atualiza job
        c.execute('''
            UPDATE jobs
            SET iteration = iteration + 1,
                status = ?,
                history = ?
            WHERE job_id = ?
        ''', (new_status, json.dumps(current_history), job_id))

    logger.info(f"Job iterado: {job_id} (iteracao {job['iteration'] + 1}, {iteration_type} por {agent})")
    return True


def get_job_history(job_id: str, formatted: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Retorna histórico formatado de um job.

    Args:
        job_id: ID do job
        formatted: Se True, formata timestamps para legibilidade

    Returns:
        Lista de dicts com histórico ou None se job nao existir
    """
    _init_jobs_table()

    job = get_job(job_id)
    if not job:
        return None

    history = job.get('history', [])

    if not formatted:
        return history

    # Formata timestamps
    formatted_history = []
    for entry in history:
        formatted_entry = entry.copy()
        try:
            ts = datetime.fromisoformat(entry['timestamp'])
            formatted_entry['timestamp'] = ts.strftime("%d/%m %H:%M:%S")
        except Exception:
            pass
        formatted_history.append(formatted_entry)

    return formatted_history


def update_job_status(job_id: str, new_status: str) -> bool:
    """Atualiza status de um job com transicoes validas.

    Transicoes validas:
    - pending -> executing, in_review
    - executing -> in_review, failed
    - in_review -> fixing, completed, failed
    - fixing -> executing, failed
    - completed -> [terminal]
    - failed -> [terminal]

    Args:
        job_id: ID do job
        new_status: Novo status

    Returns:
        True se transicao foi sucesso, False caso contrario

    Raises:
        ValueError: Se new_status for invalido
    """
    _init_jobs_table()

    if new_status not in JOB_STATES:
        raise ValueError(f"Status invalido: {new_status}. Opcoes: {', '.join(JOB_STATES.keys())}")

    job = get_job(job_id)
    if not job:
        return False

    current_status = job['status']

    # Define transicoes validas
    valid_transitions = {
        'pending': {'executing', 'in_review', 'failed'},
        'executing': {'in_review', 'failed'},
        'in_review': {'fixing', 'completed', 'failed'},
        'fixing': {'executing', 'failed'},
        'completed': set(),  # Terminal - sem transicoes
        'failed': set(),  # Terminal - sem transicoes
    }

    # Verifica se transicao e valida
    if current_status not in valid_transitions:
        logger.error(f"Status atual desconhecido: {current_status}")
        return False

    if new_status not in valid_transitions[current_status] and new_status != current_status:
        logger.warning(f"Transicao invalida: {current_status} -> {new_status}")
        return False

    with get_db() as conn:
        c = conn.cursor()
        c.execute('UPDATE jobs SET status = ? WHERE job_id = ?', (new_status, job_id))

    logger.info(f"Job status atualizado: {job_id} ({current_status} -> {new_status})")
    return True


def check_cli_tools(tools_required: List[str]) -> Dict[str, bool]:
    """Verifica existencia de ferramentas CLI em .claude/cli/.

    Args:
        tools_required: Lista de nomes de ferramentas (ex: ['gdrive', 'elevenlabs-cli'])

    Returns:
        Dict com disponibilidade de cada ferramenta
        {
            "gdrive": True,
            "missing-tool": False,
        }
    """
    from pathlib import Path

    cli_dir = Path.home() / '.claude' / 'cli'

    result = {}
    for tool_name in tools_required:
        # Verifica se existe diretorio ou arquivo com o nome da ferramenta
        tool_path = cli_dir / tool_name
        result[tool_name] = tool_path.exists()

        if not result[tool_name]:
            logger.debug(f"Ferramenta nao encontrada: {tool_name} (esperado em {tool_path})")

    return result


def create_cli_builder_job(parent_job_id: str, missing_tools: List[str], ttl: int = 3600) -> str:
    """Cria um job filho para construir CLIs faltantes.

    Este job e criado automaticamente quando um job pai detecta que ferramentas
    CLI estao faltando. O job filho segue este fluxo:
    - Haiku cria CLI inicial
    - Opus revisa CLI
    - Itera ate aprovacao
    - Parent aguarda conclusao

    Args:
        parent_job_id: ID do job pai
        missing_tools: Lista de ferramentas faltando
        ttl: TTL do job em segundos (default: 1h)

    Returns:
        job_id do novo job filho

    Raises:
        ValueError: Se parent_job_id nao existir ou if missing_tools vazio
    """
    # Valida parent
    parent = get_job(parent_job_id)
    if not parent:
        raise ValueError(f"Parent job nao encontrado: {parent_job_id}")

    if not missing_tools:
        raise ValueError("missing_tools nao pode ser vazio")

    # Cria prompt para o job filho
    tools_list = ", ".join(missing_tools)
    child_prompt = f"""Construir e revisar ferramentas CLI faltantes para job pai {parent_job_id[:8]}...

Ferramentas faltando: {tools_list}

FLUXO:
1. [HAIKU] Criar CLI em /root/.claude/cli/<tool_name>/
   - main.py ou __main__.py (Python)
   - package.json + index.js (Node.js)
   - Incluir argumentos, --help, tratamento de erro

2. [OPUS] Revisar e aprovar CLI
   - Validar estrutura
   - Testar em terminal se possivel
   - Marcar como approved

3. [HAIKU] Iterar se revisao indicar problemas

Apos completo:
- Atualizar parent job com tools_required
- Registrar no brain qualquer decisao de design
"""

    child_data = {
        "prompt": child_prompt,
        "skills": ["cli-developer-skill"],
        "context": {
            "parent_job_id": parent_job_id,
            "tools_to_build": missing_tools,
            "parent_prompt": parent["data"]["prompt"][:200],  # Resumo do pai
        }
    }

    child_job_id = create_job(ttl=ttl, data=child_data)
    logger.info(f"Job filho criado para construir CLIs: {child_job_id}")
    logger.info(f"  Parent: {parent_job_id}")
    logger.info(f"  Tools: {', '.join(missing_tools)}")

    return child_job_id


def get_missing_cli_tools(job_id: str) -> List[str]:
    """Retorna lista de ferramentas CLI faltando para um job.

    Args:
        job_id: ID do job

    Returns:
        Lista de nomes de ferramentas faltando ou lista vazia se todas existem
    """
    job = get_job(job_id)
    if not job:
        return []

    tools_required = job.get('tools_required', [])
    if not tools_required:
        return []

    availability = check_cli_tools(tools_required)
    missing = [tool for tool, available in availability.items() if not available]

    return missing


__all__ = [
    'create_job',
    'get_job',
    'list_jobs',
    'delete_job',
    'cleanup_jobs',
    'get_job_count',
    'iterate_job',
    'get_job_history',
    'update_job_status',
    'check_cli_tools',
    'create_cli_builder_job',
    'get_missing_cli_tools',
]
