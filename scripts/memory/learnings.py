#!/usr/bin/env python3
"""
Claude Brain - Learnings Module

Este modulo gerencia aprendizados de erros (tabela 'learnings').
Learnings sao solucoes para erros que podem ser reutilizadas.

Funcoes principais:
- save_learning: Salva um aprendizado (com fuzzy matching para consolidar)
- find_solution: Busca solucao para um erro
- get_all_learnings: Lista todos os aprendizados

Helper interno:
- _find_similar_learning: Fuzzy matching para evitar duplicatas

Relacionamentos:
- base.py: get_db, _similarity
- maturity.py: funcoes de maturacao
- __init__.py: re-exporta todas as funcoes publicas
"""

from typing import Optional, List, Dict, Any

from .base import get_db, _similarity


def _find_similar_learning(conn, error_type: str, error_message: Optional[str] = None,
                           solution: Optional[str] = None, threshold: float = 0.8) -> Optional[Dict]:
    """
    Busca learning similar usando fuzzy matching.
    Retorna o learning mais similar se acima do threshold.

    Args:
        conn: Conexao SQLite ativa
        error_type: Tipo do erro para filtrar
        error_message: Mensagem para comparar similaridade
        solution: Solucao para comparar similaridade
        threshold: Minimo de similaridade (0.0 a 1.0)

    Returns:
        Dict do learning similar ou None
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

        # Calcula media ponderada
        if scores:
            avg_score = sum(scores) / len(scores)
            if avg_score > best_score:
                best_score = avg_score
                best_match = candidate

    # Retorna apenas se acima do threshold
    if best_match and best_score >= threshold:
        return best_match

    return None


def save_learning(error_type: str, solution: str, error_message: Optional[str] = None,
                  root_cause: Optional[str] = None, prevention: Optional[str] = None, project: Optional[str] = None,
                  context: Optional[str] = None, similarity_threshold: float = 0.8,
                  is_established: bool = False) -> int:
    """
    Salva um aprendizado de erro.
    Usa fuzzy matching para detectar learnings similares e consolidar (aumentar frequencia)
    em vez de duplicar.

    Args:
        error_type: Tipo do erro (ex: "ModuleNotFoundError")
        solution: Solucao aplicada
        error_message: Mensagem de erro completa
        root_cause: Causa raiz identificada
        prevention: Como prevenir no futuro
        project: Projeto onde ocorreu
        context: Contexto do que estava sendo feito quando o erro ocorreu
        similarity_threshold: Threshold para considerar similar (default 0.8)
        is_established: Se True, e solucao conhecida/documentada (comeca confirmed)

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
            # Consolida: atualiza frequencia e melhora solucao se fornecida
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
                  similarity_threshold: float = 0.6, project: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Busca solucao para um erro usando fuzzy matching.

    Args:
        error_type: Tipo do erro (ex: "ModuleNotFoundError")
        error_message: Mensagem de erro para busca por similaridade
        similarity_threshold: Threshold minimo de similaridade (default 0.6 para busca)
        project: Filtrar por projeto (opcional). Se fornecido, prioriza esse projeto.

    Returns:
        Dict com learning encontrado ou None
    """
    with get_db() as conn:
        c = conn.cursor()

        if error_type and error_message:
            # Primeiro tenta match exato por error_type (com prioridade de projeto se fornecido)
            if project:
                c.execute('SELECT * FROM learnings WHERE error_type = ? AND project = ?', (error_type, project))
                candidates = [dict(row) for row in c.fetchall()]

                # Se nao achou no projeto, busca geral
                if not candidates:
                    c.execute('SELECT * FROM learnings WHERE error_type = ?', (error_type,))
                    candidates = [dict(row) for row in c.fetchall()]
            else:
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

            # Se nao achou por tipo, busca por similaridade em todas as mensagens (com projeto como prioridade)
            if project:
                c.execute('SELECT * FROM learnings WHERE project = ?', (project,))
                all_learnings = [dict(row) for row in c.fetchall()]

                # Se ainda nao achou no projeto, busca geral
                if not all_learnings:
                    c.execute('SELECT * FROM learnings')
                    all_learnings = [dict(row) for row in c.fetchall()]
            else:
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
            # Busca por error_type com prioridade de projeto
            if project:
                c.execute('''
                    SELECT * FROM learnings WHERE error_type = ? AND project = ?
                    ORDER BY frequency DESC LIMIT 1
                ''', (error_type, project))
                row = c.fetchone()
                if row:
                    return dict(row)

                # Fallback: busca geral
                c.execute('''
                    SELECT * FROM learnings WHERE error_type = ?
                    ORDER BY frequency DESC LIMIT 1
                ''', (error_type,))
                row = c.fetchone()
                return dict(row) if row else None
            else:
                c.execute('''
                    SELECT * FROM learnings WHERE error_type = ?
                    ORDER BY frequency DESC LIMIT 1
                ''', (error_type,))
                row = c.fetchone()
                return dict(row) if row else None

        return None


def get_all_learnings(limit: int = 20) -> List[Dict[str, Any]]:
    """Lista todos os aprendizados ordenados por frequencia.

    Args:
        limit: Numero maximo de resultados (default: 20)

    Returns:
        Lista de dicts com os campos do learning
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT * FROM learnings
            ORDER BY frequency DESC, last_occurred DESC LIMIT ?
        ''', (limit,))
        return [dict(row) for row in c.fetchall()]
