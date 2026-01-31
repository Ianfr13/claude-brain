#!/usr/bin/env python3
"""
Claude Brain - History Extractor
Extrai conhecimento de conversas anteriores do Claude Code
"""

import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime

from scripts.memory_store import save_decision, save_learning, save_memory

# Patterns compilados para melhor performance (evita recompilar a cada chamada)
DECISION_PATTERNS = [
    re.compile(r"(?:Vou usar|Decidi usar|Vamos usar|Escolhi|Optei por)\s+([^.!\n]{1,200}?)(?:\.|!|\n|$)", re.IGNORECASE),
    re.compile(r"(?:Usando|Implementando com|Criando com)\s+([\w\-]{1,50})\s+(?:para|porque|em vez)", re.IGNORECASE),
    re.compile(r"([\w\-]{1,50})\s+(?:em vez de|instead of|>)\s+([\w\-]{1,50})", re.IGNORECASE),
    re.compile(r"(?:melhor|better)\s+(?:usar|use)\s+([\w\-]{1,50})", re.IGNORECASE),
    re.compile(r"(?:Decisão|Decision|Abordagem|Approach)[:\s]+([^.!\n]{1,200}?)(?:\.|!|\n|$)", re.IGNORECASE),
    re.compile(r"(?:arquitetura|architecture|design)[:\s]+([^.!\n]{1,200}?)(?:\.|!|\n|$)", re.IGNORECASE),
    re.compile(r"(?:stack|tecnologias?|framework)[:\s]+([\w\-\s,+]{1,100}?)(?:\.|!|\n|$)", re.IGNORECASE),
]

LEARNING_PATTERNS = [
    (re.compile(r"([\w\.]+(?:Error|Exception))[:\s]+(.{10,100}?)[\.\\n].*?(?:solução|solution|fix)[:\s]+(.{10,200}?)[\.\\n]", re.IGNORECASE | re.DOTALL),
     lambda m: {"error": m[0], "message": m[1].strip(), "solution": m[2].strip()}),
    (re.compile(r"(?:problema|issue|bug)[:\s]+(.{10,100}?)[\.\\,].*?(?:resolvi|fix|corrigi)[:\s]+(.{10,200}?)[\.\\n]", re.IGNORECASE | re.DOTALL),
     lambda m: {"error": m[0].strip(), "solution": m[1].strip()}),
]

MEMORY_PATTERNS = [
    re.compile(r"(?:Importante|Important|Nota|Note|Lembrar)[:\s]+(.{15,200}?)[\.\\n]", re.IGNORECASE),
    re.compile(r"(?:Descobri|Found|Percebi|Noticed)[:\s]+(.{15,200}?)[\.\\n]", re.IGNORECASE),
    re.compile(r"(?:rate limit|timeout|config|limite)[:\s]+(.{10,150}?)[\.\\n]", re.IGNORECASE),
    re.compile(r"(?:API|endpoint)\s+(?:retorna|returns|precisa|requires)\s+(.{10,150}?)[\.\\n]", re.IGNORECASE),
]


def find_claude_sessions() -> list:
    """Encontra todas as sessões do Claude Code"""
    sessions = []
    claude_dir = Path.home() / ".claude"

    # Procura em projects
    projects_dir = claude_dir / "projects"
    if projects_dir.exists():
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                for session_file in project_dir.glob("*.jsonl"):
                    sessions.append(session_file)

    return sessions


def parse_session(session_file: Path, max_messages: int = 100) -> list:
    """Parse uma sessão JSONL e extrai mensagens.

    Args:
        session_file: Caminho para o arquivo JSONL
        max_messages: Limite de mensagens para evitar memory exhaustion (default: 100)
    """
    messages = []

    try:
        with open(session_file, encoding='utf-8') as f:
            for line in f:
                # Limite de mensagens para evitar memory exhaustion
                if len(messages) >= max_messages:
                    break

                try:
                    data = json.loads(line)

                    # Formato do Claude Code: {"type": "user/assistant", "message": {"role": ..., "content": ...}}
                    if isinstance(data, dict):
                        msg_type = data.get("type", "")
                        msg_data = data.get("message", {})

                        if msg_type not in ("user", "assistant"):
                            continue

                        role = msg_data.get("role", msg_type)
                        content = msg_data.get("content", "")

                        # Content pode ser string ou lista
                        if isinstance(content, list):
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get("type") == "text":
                                        text_parts.append(item.get("text", ""))
                                    # Ignora thinking, tool_use, etc
                                elif isinstance(item, str):
                                    text_parts.append(item)
                            content = "\n".join(text_parts)
                        elif isinstance(content, str):
                            pass  # Já é string
                        else:
                            continue

                        if content and len(content) > 20:
                            messages.append({
                                "role": role,
                                "content": content,
                                "timestamp": data.get("timestamp", "")
                            })

                except json.JSONDecodeError:
                    continue
    except (IOError, OSError) as e:
        print(f"Erro lendo {session_file}: {e}")

    return messages


def extract_decisions(text: str) -> list:
    """Extrai decisões de um texto

    Performance: Usa DECISION_PATTERNS pré-compilados para evitar recompilação
    e patterns otimizados para evitar ReDoS (backtracking catastrófico)
    """
    decisions = []
    for pattern in DECISION_PATTERNS:
        matches = pattern.findall(text)
        for m in matches:
            if isinstance(m, tuple):
                m = " vs ".join([x.strip() for x in m if x.strip()])
            m = m.strip()
            if 10 < len(m) < 200 and not m.startswith("http"):
                decisions.append(m)

    return decisions[:5]  # Limita a 5


def extract_learnings(text: str) -> list:
    """Extrai aprendizados de erro (usa LEARNING_PATTERNS pré-compilados)"""
    learnings = []

    # Padrões simples e eficientes
    error_keywords = ["Error", "Exception", "erro", "falha", "failed", "problema"]
    solution_keywords = ["solução", "solution", "fix", "resolvido", "resolved", "corrigido"]

    # Verifica se tem erro E solução no texto
    has_error = any(kw.lower() in text.lower() for kw in error_keywords)
    has_solution = any(kw.lower() in text.lower() for kw in solution_keywords)

    if not (has_error and has_solution):
        return []

    for pattern, extractor in LEARNING_PATTERNS:
        matches = pattern.findall(text)
        for m in matches[:2]:  # Limita
            try:
                learning = extractor(m)
                if learning and len(learning.get("solution", "")) > 10:
                    learnings.append(learning)
            except (IndexError, KeyError):
                continue

    return learnings[:3]  # Limita a 3


def extract_memories(text: str) -> list:
    """Extrai memórias importantes (usa MEMORY_PATTERNS pré-compilados)"""
    memories = []
    for pattern in MEMORY_PATTERNS:
        matches = pattern.findall(text)
        for m in matches[:2]:  # Limita por padrão
            m = m.strip()
            if 15 < len(m) < 250 and not m.startswith("http"):
                memories.append(m)

    return memories[:3]  # Limita total


def extract_project_from_path(session_file: Path) -> str:
    """Extrai nome do projeto do path da sessão"""
    # Path típico: ~/.claude/projects/-root-project-name/xxx.jsonl
    parts = session_file.parts
    for i, part in enumerate(parts):
        if part == "projects" and i + 1 < len(parts):
            project_name = parts[i + 1]
            # Remove prefixo -root- comum
            project_name = re.sub(r"^-root-?", "", project_name)
            return project_name or "unknown"
    return "unknown"


def process_session(session_file: Path, dry_run: bool = False, max_messages: int = 100) -> dict:
    """Processa uma sessão e extrai conhecimento"""
    stats = {"decisions": 0, "learnings": 0, "memories": 0}

    # Pula arquivos muito grandes (> 5MB)
    if session_file.stat().st_size > 5 * 1024 * 1024:
        return stats

    messages = parse_session(session_file, max_messages=max_messages)
    project = extract_project_from_path(session_file)

    # Processa apenas mensagens do assistant (contêm as decisões e soluções)
    for msg in messages:
        if msg["role"] != "assistant":
            continue

        text = msg["content"]

        # Extrai decisões
        for decision in extract_decisions(text)[:5]:
            if not dry_run:
                save_decision(decision, project=project)
            stats["decisions"] += 1

        # Extrai learnings
        for learning in extract_learnings(text)[:3]:
            if not dry_run:
                save_learning(
                    error_type=learning.get("error", "Erro")[:150],
                    solution=learning.get("solution", "")[:400],
                    error_message=learning.get("message"),
                    project=project
                )
            stats["learnings"] += 1

        # Extrai memórias
        for memory in extract_memories(text)[:3]:
            if not dry_run:
                save_memory("extracted", memory, importance=5)
            stats["memories"] += 1

    return stats


def main():
    """Entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Extrai conhecimento do histórico do Claude Code")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra o que seria extraído")
    parser.add_argument("--session", help="Processa apenas uma sessão específica")
    parser.add_argument("--limit", type=int, default=10, help="Limite de sessões a processar")
    args = parser.parse_args()

    print("🧠 Claude Brain - History Extractor")
    print("=" * 50)

    if args.session:
        sessions = [Path(args.session)]
    else:
        sessions = find_claude_sessions()
        # Ordena por data de modificação (mais recentes primeiro)
        sessions.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        sessions = sessions[:args.limit]

    print(f"📁 Encontradas {len(sessions)} sessões")

    total_stats = {"decisions": 0, "learnings": 0, "memories": 0}

    for session in sessions:
        print(f"\n📄 Processando: {session.name[:40]}...")
        stats = process_session(session, dry_run=args.dry_run)

        for key in total_stats:
            total_stats[key] += stats[key]

        if any(stats.values()):
            print(f"   ✓ Extraído: {stats}")

    print("\n" + "=" * 50)
    print(f"📊 Total extraído:")
    print(f"   Decisões: {total_stats['decisions']}")
    print(f"   Learnings: {total_stats['learnings']}")
    print(f"   Memórias: {total_stats['memories']}")

    if args.dry_run:
        print("\n⚠️  Modo dry-run - nada foi salvo")


if __name__ == "__main__":
    main()
