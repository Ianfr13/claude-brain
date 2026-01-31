#!/usr/bin/env python3
"""
Claude Brain CLI - Modulo Preferences

Comandos de preferencias e padroes de codigo:
- cmd_prefer: Salva preferencia
- cmd_prefs: Lista preferencias
- cmd_pattern: Salva snippet de codigo
- cmd_snippet: Recupera snippet
"""

from .base import Colors, c, print_header, print_success, print_error, print_info
from scripts.memory_store import (
    save_preference, get_all_preferences,
    save_pattern, get_pattern
)


def cmd_prefer(args):
    """Salva uma preferencia do usuario.

    Preferencias sao configuracoes de comportamento como
    idioma, framework preferido, estilo de codigo, etc.

    Args:
        args: Namespace do argparse contendo:
            - pref (list[str]): [chave, valor]

    Returns:
        None. Imprime confirmacao de salvamento.

    Examples:
        $ brain prefer idioma portugues
        * Preferencia salva: idioma = portugues

        $ brain prefer test_framework pytest
        * Preferencia salva: test_framework = pytest
    """
    if not args.pref or len(args.pref) < 2:
        print_error("Uso: brain prefer <chave> <valor>")
        return

    key = args.pref[0]
    value = " ".join(args.pref[1:])
    save_preference(key, value, confidence=0.9, source="manual")
    print_success(f"Preferencia salva: {key} = {value}")


def cmd_prefs(args):
    """Lista todas as preferencias conhecidas.

    Exibe as preferencias do usuario salvas no banco,
    filtradas por nivel minimo de confianca.

    Args:
        args: Namespace do argparse (sem argumentos especificos)

    Returns:
        None. Imprime lista de preferencias chave=valor.

    Examples:
        $ brain prefs
        Preferencias Conhecidas
          idioma: portugues
          test_framework: pytest
          editor: vscode
    """
    prefs = get_all_preferences(min_confidence=0.3)

    if not prefs:
        print_info("Nenhuma preferencia registrada.")
        return

    print_header("Preferencias Conhecidas")
    for k, v in prefs.items():
        print(f"  {c(k, Colors.CYAN)}: {v}")


def cmd_pattern(args):
    """Salva um padrao/snippet de codigo reutilizavel.

    Patterns sao trechos de codigo que podem ser
    recuperados rapidamente via brain snippet.

    Args:
        args: Namespace do argparse contendo:
            - pattern (list[str]): [nome, codigo]
            - language (str, optional): Linguagem do codigo

    Returns:
        None. Imprime confirmacao de salvamento.

    Examples:
        $ brain pattern fastapi-route "@app.get('/') def root(): return {}"
        * Padrao 'fastapi-route' salvo

        $ brain pattern pytest-fixture "..." --language python
        * Padrao 'pytest-fixture' salvo
    """
    if not args.pattern or len(args.pattern) < 2:
        print_error("Uso: brain pattern <nome> <codigo>")
        return

    name = args.pattern[0]
    code = " ".join(args.pattern[1:])
    save_pattern(name, code, language=args.language)
    print_success(f"Padrao '{name}' salvo")


def cmd_snippet(args):
    """Recupera um padrao/snippet de codigo salvo.

    Busca e imprime o codigo de um pattern salvo
    anteriormente via brain pattern.

    Args:
        args: Namespace do argparse contendo:
            - name (list[str]): Nome do pattern

    Returns:
        None. Imprime codigo do pattern ou erro.

    Examples:
        $ brain snippet fastapi-route
        @app.get('/')
        def root():
            return {}

        $ brain snippet inexistente
        x Padrao nao encontrado: inexistente
    """
    if not args.name:
        print_error("Uso: brain snippet <nome>")
        return

    code = get_pattern(args.name[0])
    if code:
        print(code)
    else:
        print_error(f"Padrao nao encontrado: {args.name[0]}")
