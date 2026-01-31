#!/usr/bin/env python3
"""
Claude Brain - Auto-save Hook v2
Detecta e salva automaticamente decisões, erros e aprendizados
com contexto completo para uso futuro
"""

import sys
import re
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from memory_store import save_decision, save_learning, save_memory


def detect_decision(text: str) -> list:
    """Detecta decisões no texto - padrões expandidos"""
    patterns = [
        # Decisões explícitas
        r"(?:decidi|decidimos|vou usar|vamos usar|escolhi|optei por|a decisão é)\s+(.+?)(?:\.|!|\n|$)",
        r"(?:decision|approach|strategy):\s*(.+?)(?:\.|!|\n|$)",

        # Escolhas de tecnologia
        r"(?:usar(?:ei|emos)?|implementar com|migrar para|adotar)\s+([\w\-]+(?:\s+[\w\-]+)?)\s+(?:para|porque|por ser|em vez)",

        # Arquitetura
        r"(?:arquitetura|architecture|design):\s*(.+?)(?:\.|!|\n|$)",
        r"(?:padrão|pattern):\s*([\w\-\s]+)(?:\.|!|\n|$)",

        # Escolhas comparativas
        r"([\w\-]+)\s+(?:em vez de|instead of|over|>)\s+([\w\-]+)",
    ]
    decisions = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            if isinstance(m, tuple):
                decisions.append(" vs ".join(m) if len(m) > 1 else m[0])
            else:
                decisions.append(m)
    return decisions


def detect_error_solution(text: str) -> list:
    """Detecta erros e soluções com contexto"""
    results = []

    # Padrões de erro com solução
    patterns = [
        # Erro -> Solução explícita
        (r"((?:Error|Exception|Erro|Falha|Failed)[\w\s:]+?)(?:resolvido|fixed|solved|solução|solution)[:\s]+(.+?)(?:\.|!|\n|$)",
         lambda m: {"error": m[0].strip(), "solution": m[1].strip()}),

        # O problema era X, solução foi Y
        (r"(?:o problema era|the issue was|problema:|issue:)\s*(.+?)[,\-\.]+\s*(?:solução|solution|fix|corrigido|fixed)[:\s]+(.+?)(?:\.|!|\n|$)",
         lambda m: {"error": m[0].strip(), "solution": m[1].strip()}),

        # Traceback / Stack trace seguido de fix
        (r"([\w\.]+Error|[\w\.]+Exception)[:\s]+(.+?)(?:\n.*?)*?(?:fix|solução|solved|resolvido)[:\s]+(.+?)(?:\.|!|\n|$)",
         lambda m: {"error": f"{m[0]}: {m[1][:100]}", "solution": m[2].strip()}),

        # Bug fix
        (r"(?:bug fix|correção|fixed)[:\s]+(.+?)(?:porque|due to|caused by)[:\s]+(.+?)(?:\.|!|\n|$)",
         lambda m: {"error": m[1].strip(), "solution": m[0].strip()}),
    ]

    for pattern, extractor in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        for m in matches:
            try:
                result = extractor(m)
                if result and len(result.get("solution", "")) > 10:
                    results.append(result)
            except (IndexError, KeyError):
                continue

    return results


def detect_important_memory(text: str) -> list:
    """Detecta informações importantes para memorizar"""
    patterns = [
        # Notas explícitas
        r"(?:importante|important|lembrar|remember|nota|note)[:\s]+(.+?)(?:\.|!|\n|$)",

        # Descobertas
        r"(?:descobri|found out|aprendi|learned|percebi|realized)[:\s]+(.+?)(?:\.|!|\n|$)",

        # Tips e dicas
        r"(?:dica|tip|trick|macete)[:\s]+(.+?)(?:\.|!|\n|$)",

        # Rate limits, configs, etc
        r"(?:rate limit|timeout|config|setting)[:\s]+(.+?)(?:\.|!|\n|$)",

        # API behaviors
        r"(?:API|endpoint|service)\s+(?:retorna|returns|requires|precisa)\s+(.+?)(?:\.|!|\n|$)",
    ]
    memories = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        memories.extend(matches)
    return memories


def extract_context(text: str, max_len: int = 200) -> str:
    """Extrai contexto do que estava acontecendo"""
    # Tenta pegar a primeira frase ou linha relevante
    lines = text.strip().split('\n')

    # Procura por indicadores de contexto
    context_patterns = [
        r"(?:trabalhando em|working on|fazendo|doing|tentando|trying)\s+(.+?)(?:\.|!|\n|$)",
        r"(?:implementando|implementing|criando|creating|configurando|setting up)\s+(.+?)(?:\.|!|\n|$)",
    ]

    for pattern in context_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)[:max_len]

    # Fallback: primeira linha não vazia
    for line in lines[:5]:
        line = line.strip()
        if len(line) > 20 and not line.startswith('#'):
            return line[:max_len]

    return ""


def process_text(text: str, project: str = None) -> dict:
    """Processa texto e salva automaticamente no brain"""
    saved = {"decisions": 0, "learnings": 0, "memories": 0}

    context = extract_context(text)

    # Detecta e salva decisões
    decisions = detect_decision(text)
    for d in decisions[:3]:  # Máximo 3 por vez
        d = d.strip()
        if len(d) > 15 and len(d) < 500:  # Tamanho razoável
            save_decision(d, project=project, context=context[:200] if context else None)
            saved["decisions"] += 1

    # Detecta e salva soluções de erros com contexto
    solutions = detect_error_solution(text)
    for s in solutions[:2]:
        if isinstance(s, dict):
            save_learning(
                error_type=s.get("error", "Erro detectado")[:200],
                solution=s.get("solution", "")[:500],
                context=context[:300] if context else None,
                project=project
            )
            saved["learnings"] += 1

    # Detecta memórias importantes
    memories = detect_important_memory(text)
    for m in memories[:2]:
        m = m.strip()
        if len(m) > 15 and len(m) < 500:
            save_memory("auto_detected", m, importance=6, metadata={"context": context} if context else None)
            saved["memories"] += 1

    return saved


def main():
    """Entry point para hook do Claude Code"""
    # Lê input do stdin
    if not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        text = " ".join(sys.argv[1:])

    if not text or len(text) < 30:
        return

    # Detecta projeto do diretório atual
    cwd = os.getcwd()
    project = Path(cwd).name if cwd != "/" else None

    result = process_text(text, project)

    total = sum(result.values())
    if total > 0:
        # Log silencioso para não poluir output
        log_file = Path("/root/claude-brain/logs/auto_save.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"{datetime.now().isoformat()} | {project} | {result}\n")


if __name__ == "__main__":
    main()
