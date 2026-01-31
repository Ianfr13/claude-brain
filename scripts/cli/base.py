#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo Base

Contem:
- Classe Colors para output colorido
- Funcoes de print formatado (print_header, print_success, etc)
- Funcao c() para aplicar cores
- Constantes compartilhadas (ALLOWED_INDEX_PATHS)

Todos os outros modulos de cli/ importam deste modulo.
"""

import sys
from pathlib import Path

# Diretorios permitidos para indexacao (protecao contra path traversal)
ALLOWED_INDEX_PATHS = [
    Path("/root/claude-brain"),
    Path("/root/vsl-analysis"),
    Path("/root/vsl-tools"),
    Path("/root/slack-claude-bot"),
    Path("/root/claude-swarm-plugin"),
    Path.home() / "projects",  # ~/projects
]


class Colors:
    """ANSI colors para output bonito"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def c(text: str, color: str) -> str:
    """Aplica cor ao texto (desativa cores em pipes/redirecionamentos)"""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{Colors.END}"


def print_header(text: str):
    """Imprime cabecalho formatado com linha separadora"""
    print(f"\n{c(text, Colors.BOLD + Colors.CYAN)}")
    print("-" * 50)


def print_success(text: str):
    """Imprime mensagem de sucesso em verde"""
    print(c(f"* {text}", Colors.GREEN))


def print_error(text: str):
    """Imprime mensagem de erro em vermelho"""
    print(c(f"x {text}", Colors.RED))


def print_info(text: str):
    """Imprime informacao em azul"""
    print(c(f"i {text}", Colors.BLUE))


def is_path_allowed(path: Path) -> bool:
    """Verifica se o path esta dentro de diretorios permitidos."""
    resolved = path.resolve()
    return any(
        resolved == allowed or allowed in resolved.parents
        for allowed in ALLOWED_INDEX_PATHS
    )
