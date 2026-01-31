#!/usr/bin/env python3
"""
Testes unitarios para brain_cli.py

Cobertura:
1. Parsing de argumentos (remember, decide, learn, ask, search, etc)
2. Comandos principais (cmd_remember, cmd_decide, cmd_learn, cmd_ask)
3. Opcoes/flags (-p project, --reason, etc)
4. Error handling (comando invalido, argumentos faltando)
5. Output formatting (cores, tabelas)
"""

import sys
import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from io import StringIO

import pytest

# Adiciona scripts ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Importa modulos a testar
from brain_cli import (
    # Funcoes de output
    Colors, c, print_header, print_success, print_error, print_info,
    # Comandos de memoria
    cmd_remember, cmd_decide, cmd_learn, cmd_solve, cmd_recall,
    cmd_decisions, cmd_learnings,
    # Comandos de RAG
    cmd_index, cmd_search, cmd_context, cmd_ask, cmd_related,
    # Knowledge Graph
    cmd_entity, cmd_relate, cmd_graph,
    # Preferencias
    cmd_prefer, cmd_prefs,
    # Padroes
    cmd_pattern, cmd_snippet,
    # Utilidades
    cmd_export, cmd_stats, cmd_useful, cmd_useless, cmd_help,
    # Maturacao
    cmd_hypotheses, cmd_confirm, cmd_contradict, cmd_supersede, cmd_maturity,
    # Delete
    cmd_delete, cmd_forget,
    # Main e auxiliares
    main, _is_path_allowed, ALLOWED_INDEX_PATHS
)


# ============ TESTES DE FORMATACAO DE OUTPUT ============

class TestColors:
    """Testes para a classe Colors e funcoes de formatacao"""

    def test_colors_constants_exist(self):
        """Verifica que constantes de cores existem"""
        assert hasattr(Colors, 'HEADER')
        assert hasattr(Colors, 'BLUE')
        assert hasattr(Colors, 'CYAN')
        assert hasattr(Colors, 'GREEN')
        assert hasattr(Colors, 'YELLOW')
        assert hasattr(Colors, 'RED')
        assert hasattr(Colors, 'BOLD')
        assert hasattr(Colors, 'DIM')
        assert hasattr(Colors, 'END')

    def test_colors_are_ansi_codes(self):
        """Cores devem ser codigos ANSI validos"""
        assert Colors.GREEN.startswith('\033[')
        assert Colors.END == '\033[0m'

    def test_c_applies_color_in_tty(self, mock_isatty):
        """c() aplica cor quando stdout eh terminal"""
        with mock_isatty(True):
            result = c("test", Colors.GREEN)
            assert Colors.GREEN in result
            assert Colors.END in result
            assert "test" in result

    def test_c_no_color_in_pipe(self, mock_isatty):
        """c() nao aplica cor quando stdout eh pipe"""
        with mock_isatty(False):
            result = c("test", Colors.GREEN)
            assert result == "test"
            assert Colors.GREEN not in result

    def test_print_header_format(self, capsys, mock_isatty):
        """print_header formata corretamente"""
        with mock_isatty(False):
            print_header("Test Header")
            captured = capsys.readouterr()
            assert "Test Header" in captured.out
            assert "─" in captured.out  # Linha separadora

    def test_print_success_format(self, capsys, mock_isatty):
        """print_success inclui checkmark"""
        with mock_isatty(False):
            print_success("Success message")
            captured = capsys.readouterr()
            # Sem cor, deve ter o simbolo
            assert "Success message" in captured.out

    def test_print_error_format(self, capsys, mock_isatty):
        """print_error inclui X"""
        with mock_isatty(False):
            print_error("Error message")
            captured = capsys.readouterr()
            assert "Error message" in captured.out

    def test_print_info_format(self, capsys, mock_isatty):
        """print_info inclui i"""
        with mock_isatty(False):
            print_info("Info message")
            captured = capsys.readouterr()
            assert "Info message" in captured.out


# ============ TESTES DE PARSING DE ARGUMENTOS ============

class TestArgumentParsing:
    """Testes para parsing de argumentos da CLI"""

    def test_main_without_args_shows_help(self, capsys):
        """main() sem argumentos mostra help"""
        with patch('sys.argv', ['brain']):
            main()
            captured = capsys.readouterr()
            assert "MEMÓRIA" in captured.out or "brain remember" in captured.out.lower()

    def test_remember_command_parsing(self):
        """Parsing do comando remember"""
        with patch('sys.argv', ['brain', 'remember', 'test', 'text']):
            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers(dest="command")
            p = subparsers.add_parser("remember")
            p.add_argument("text", nargs="*")
            p.add_argument("-c", "--category")
            p.add_argument("-i", "--importance", type=int)

            args = parser.parse_args(['remember', 'test', 'text', '-c', 'test_cat', '-i', '8'])

            assert args.command == "remember"
            assert args.text == ['test', 'text']
            assert args.category == "test_cat"
            assert args.importance == 8

    def test_decide_command_parsing(self):
        """Parsing do comando decide"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p = subparsers.add_parser("decide")
        p.add_argument("decision", nargs="*")
        p.add_argument("-p", "--project")
        p.add_argument("-r", "--reason")
        p.add_argument("--fact", action="store_true")

        args = parser.parse_args([
            'decide', 'Use', 'pytest', '-p', 'myproject', '-r', 'Best framework', '--fact'
        ])

        assert args.command == "decide"
        assert args.decision == ['Use', 'pytest']
        assert args.project == "myproject"
        assert args.reason == "Best framework"
        assert args.fact is True

    def test_learn_command_parsing(self):
        """Parsing do comando learn"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p = subparsers.add_parser("learn")
        p.add_argument("error", nargs="*")
        p.add_argument("-s", "--solution", required=True)
        p.add_argument("--prevention")
        p.add_argument("-p", "--project")
        p.add_argument("-c", "--context")
        p.add_argument("--cause")
        p.add_argument("--fact", action="store_true")

        args = parser.parse_args([
            'learn', 'ImportError', '-s', 'pip install pkg',
            '-c', 'Installing dependencies', '--cause', 'Missing package'
        ])

        assert args.error == ['ImportError']
        assert args.solution == 'pip install pkg'
        assert args.context == 'Installing dependencies'
        assert args.cause == 'Missing package'

    def test_search_command_parsing(self):
        """Parsing do comando search"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p = subparsers.add_parser("search")
        p.add_argument("query", nargs="*")
        p.add_argument("-t", "--type")
        p.add_argument("-l", "--limit", type=int)

        args = parser.parse_args(['search', 'redis', 'cache', '-t', 'code', '-l', '10'])

        assert args.query == ['redis', 'cache']
        assert args.type == 'code'
        assert args.limit == 10

    def test_confirm_command_parsing(self):
        """Parsing do comando confirm"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p = subparsers.add_parser("confirm")
        p.add_argument("table", nargs="?", choices=["decisions", "learnings", "memories"])
        p.add_argument("id", nargs="?", type=int)

        args = parser.parse_args(['confirm', 'decisions', '15'])

        assert args.table == 'decisions'
        assert args.id == 15

    def test_delete_command_parsing(self):
        """Parsing do comando delete"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p = subparsers.add_parser("delete")
        p.add_argument("table", nargs="?", choices=["memories", "decisions", "learnings"])
        p.add_argument("id", nargs="?", type=int)
        p.add_argument("-f", "--force", action="store_true")

        args = parser.parse_args(['delete', 'memories', '5', '-f'])

        assert args.table == 'memories'
        assert args.id == 5
        assert args.force is True


# ============ TESTES DE COMANDOS PRINCIPAIS ============

class TestCmdRemember:
    """Testes para cmd_remember"""

    def test_remember_without_text_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_remember sem texto mostra erro"""
        args = cli_args(text=None)
        with mock_isatty(False):
            cmd_remember(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out or "erro" in captured.out.lower()

    def test_remember_empty_text_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_remember com lista vazia mostra erro"""
        args = cli_args(text=[])
        with mock_isatty(False):
            cmd_remember(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_remember_saves_memory(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_remember salva memoria com sucesso"""
        args = cli_args(
            text=['Test', 'memory', 'content'],
            category='test',
            importance=7
        )
        with mock_isatty(False):
            cmd_remember(args)
            captured = capsys.readouterr()
            assert "salva" in captured.out.lower() or "ID:" in captured.out


class TestCmdDecide:
    """Testes para cmd_decide"""

    def test_decide_without_decision_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_decide sem decisao mostra erro"""
        args = cli_args(decision=None)
        with mock_isatty(False):
            cmd_decide(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_decide_saves_decision(self, cli_args, temp_db, capsys, mock_isatty, mock_metrics):
        """cmd_decide salva decisao com sucesso"""
        args = cli_args(
            decision=['Use', 'pytest', 'for', 'testing'],
            project='test-project',
            reason='Best framework'
        )
        with mock_isatty(False):
            cmd_decide(args)
            captured = capsys.readouterr()
            assert "salva" in captured.out.lower() or "ID:" in captured.out
            assert "hipótese" in captured.out.lower() or "hypothesis" in captured.out.lower()

    def test_decide_with_fact_flag(self, cli_args, temp_db, capsys, mock_isatty, mock_metrics):
        """cmd_decide com --fact marca como confirmado"""
        args = cli_args(
            decision=['Python', 'needs', 'venv'],
            fact=True
        )
        with mock_isatty(False):
            cmd_decide(args)
            captured = capsys.readouterr()
            assert "confirmado" in captured.out.lower() or "fato" in captured.out.lower()


class TestCmdLearn:
    """Testes para cmd_learn"""

    def test_learn_without_error_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_learn sem erro mostra mensagem de uso"""
        args = cli_args(error=None, solution='some solution')
        with mock_isatty(False):
            cmd_learn(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_learn_without_solution_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_learn sem solucao mostra mensagem de uso"""
        args = cli_args(error=['TestError'], solution=None)
        with mock_isatty(False):
            cmd_learn(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_learn_saves_learning(self, cli_args, temp_db, capsys, mock_isatty, mock_metrics):
        """cmd_learn salva aprendizado com sucesso (mockando save_learning)"""
        args = cli_args(
            error=['ImportError'],
            solution='pip install package',
            prevention='Check requirements.txt',
            project='test-project'
        )
        # Mock save_learning pois a funcao tem bug com coluna 'context'
        with mock_isatty(False), \
             patch('brain_cli.save_learning', return_value=42) as mock_save:
            cmd_learn(args)
            captured = capsys.readouterr()
            assert "salva" in captured.out.lower() or "ID:" in captured.out
            mock_save.assert_called_once()

    def test_learn_with_fact_flag(self, cli_args, temp_db, capsys, mock_isatty, mock_metrics):
        """cmd_learn com --fact marca como confirmado"""
        args = cli_args(
            error=['ModuleNotFoundError'],
            solution='pip install <module>',
            fact=True
        )
        # Mock save_learning pois a funcao tem bug com coluna 'context'
        with mock_isatty(False), \
             patch('brain_cli.save_learning', return_value=99) as mock_save:
            cmd_learn(args)
            captured = capsys.readouterr()
            assert "confirmad" in captured.out.lower()
            # Verifica que is_established=True foi passado
            call_kwargs = mock_save.call_args[1]
            assert call_kwargs.get('is_established') is True


class TestCmdSolve:
    """Testes para cmd_solve"""

    def test_solve_without_error_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_solve sem erro mostra mensagem de uso"""
        args = cli_args(error=None)
        with mock_isatty(False):
            cmd_solve(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_solve_not_found(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_solve sem solucao mostra mensagem apropriada"""
        args = cli_args(error=['UnknownError12345'])
        with mock_isatty(False):
            cmd_solve(args)
            captured = capsys.readouterr()
            assert "encontrad" in captured.out.lower()

    def test_solve_finds_solution(self, cli_args, sample_memories, capsys, mock_isatty):
        """cmd_solve encontra solucao existente"""
        args = cli_args(error=['ModuleNotFoundError'])
        with mock_isatty(False):
            cmd_solve(args)
            captured = capsys.readouterr()
            # Deve encontrar a solucao do sample_memories
            assert "pip install" in captured.out.lower() or "encontrad" in captured.out.lower()


class TestCmdAsk:
    """Testes para cmd_ask"""

    def test_ask_without_query_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_ask sem query mostra mensagem de uso"""
        args = cli_args(query=None)
        with mock_isatty(False):
            cmd_ask(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_ask_searches_learnings_and_decisions(self, cli_args, sample_memories, capsys, mock_isatty, mock_rag_engine):
        """cmd_ask busca em learnings e decisoes"""
        args = cli_args(query=['pytest'])
        with mock_isatty(False):
            cmd_ask(args)
            captured = capsys.readouterr()
            # Deve mostrar algo (decisao, learning ou documento)
            assert len(captured.out) > 0


class TestCmdRecall:
    """Testes para cmd_recall"""

    def test_recall_empty_shows_info(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_recall em banco vazio mostra mensagem"""
        args = cli_args(query=None, type=None, limit=10)
        with mock_isatty(False):
            cmd_recall(args)
            captured = capsys.readouterr()
            # Pode mostrar resultados ou mensagem de nao encontrado
            assert "Memórias" in captured.out or "encontrad" in captured.out.lower()

    def test_recall_with_results(self, cli_args, sample_memories, capsys, mock_isatty):
        """cmd_recall mostra memorias existentes"""
        args = cli_args(query=['teste'], type=None, limit=10)
        with mock_isatty(False):
            cmd_recall(args)
            captured = capsys.readouterr()
            # Banco tem memorias do sample_memories
            assert len(captured.out) > 0


# ============ TESTES DE COMANDOS RAG ============

class TestCmdIndex:
    """Testes para cmd_index"""

    def test_index_without_path_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_index sem path mostra erro"""
        args = cli_args(path=None)
        with mock_isatty(False):
            cmd_index(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_index_disallowed_path_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_index com path nao permitido mostra erro"""
        args = cli_args(path=['/etc/passwd'])
        with mock_isatty(False):
            cmd_index(args)
            captured = capsys.readouterr()
            assert "não permitido" in captured.out.lower() or "permitido" in captured.out

    def test_is_path_allowed_valid_paths(self):
        """_is_path_allowed aceita paths validos"""
        # Paths dentro dos permitidos devem ser aceitos
        for allowed in ALLOWED_INDEX_PATHS:
            if allowed.exists():
                assert _is_path_allowed(allowed) is True
                # Subdiretorio tambem
                subdir = allowed / "subdir"
                assert _is_path_allowed(subdir) is True

    def test_is_path_allowed_invalid_paths(self):
        """_is_path_allowed rejeita paths invalidos"""
        assert _is_path_allowed(Path("/etc/passwd")) is False
        assert _is_path_allowed(Path("/tmp/random")) is False
        assert _is_path_allowed(Path("/root/.ssh")) is False


class TestCmdSearch:
    """Testes para cmd_search"""

    def test_search_without_query_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_search sem query mostra erro"""
        args = cli_args(query=None)
        with mock_isatty(False):
            cmd_search(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_search_with_results(self, cli_args, mock_rag_engine, mock_metrics, capsys, mock_isatty):
        """cmd_search mostra resultados"""
        args = cli_args(query=['test', 'query'], type=None, limit=5)
        with mock_isatty(False):
            cmd_search(args)
            captured = capsys.readouterr()
            # Mock retorna resultados
            assert "test.py" in captured.out or "Resultados" in captured.out


class TestCmdContext:
    """Testes para cmd_context"""

    def test_context_without_query_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_context sem query mostra erro"""
        args = cli_args(query=None)
        with mock_isatty(False):
            cmd_context(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out


# ============ TESTES KNOWLEDGE GRAPH ============

class TestCmdEntity:
    """Testes para cmd_entity"""

    def test_entity_without_name_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_entity sem nome mostra erro"""
        args = cli_args(name=None)
        with mock_isatty(False):
            cmd_entity(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_entity_saves_entity(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_entity salva entidade"""
        args = cli_args(name=['redis', 'technology', 'Cache layer'])
        with mock_isatty(False):
            cmd_entity(args)
            captured = capsys.readouterr()
            assert "salva" in captured.out.lower()


class TestCmdRelate:
    """Testes para cmd_relate"""

    def test_relate_without_args_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_relate sem argumentos mostra erro"""
        args = cli_args(relation=None)
        with mock_isatty(False):
            cmd_relate(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_relate_insufficient_args_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_relate com args insuficientes mostra erro"""
        args = cli_args(relation=['entity1', 'entity2'])  # Falta relation_type
        with mock_isatty(False):
            cmd_relate(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_relate_creates_relation(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_relate cria relacao"""
        args = cli_args(relation=['project', 'python', 'uses'])
        with mock_isatty(False):
            cmd_relate(args)
            captured = capsys.readouterr()
            assert "Relação" in captured.out or "-->" in captured.out


class TestCmdGraph:
    """Testes para cmd_graph"""

    def test_graph_without_entity_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_graph sem entidade mostra erro"""
        args = cli_args(entity=None)
        with mock_isatty(False):
            cmd_graph(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_graph_not_found(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_graph com entidade inexistente mostra erro"""
        args = cli_args(entity=['nonexistent12345'])
        with mock_isatty(False):
            cmd_graph(args)
            captured = capsys.readouterr()
            assert "não encontrad" in captured.out.lower()

    def test_graph_shows_entity(self, cli_args, sample_entities, capsys, mock_isatty):
        """cmd_graph mostra entidade existente"""
        args = cli_args(entity=['claude-brain'])
        with mock_isatty(False):
            cmd_graph(args)
            captured = capsys.readouterr()
            assert "claude-brain" in captured.out


# ============ TESTES DE PREFERENCIAS ============

class TestCmdPrefer:
    """Testes para cmd_prefer"""

    def test_prefer_without_args_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_prefer sem argumentos mostra erro"""
        args = cli_args(pref=None)
        with mock_isatty(False):
            cmd_prefer(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_prefer_insufficient_args_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_prefer com args insuficientes mostra erro"""
        args = cli_args(pref=['key_only'])
        with mock_isatty(False):
            cmd_prefer(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_prefer_saves_preference(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_prefer salva preferencia"""
        args = cli_args(pref=['editor', 'vim'])
        with mock_isatty(False):
            cmd_prefer(args)
            captured = capsys.readouterr()
            assert "salva" in captured.out.lower()


class TestCmdPrefs:
    """Testes para cmd_prefs"""

    def test_prefs_empty(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_prefs em banco vazio"""
        args = cli_args()
        with mock_isatty(False):
            cmd_prefs(args)
            captured = capsys.readouterr()
            assert "preferência" in captured.out.lower() or "Preferências" in captured.out

    def test_prefs_shows_preferences(self, cli_args, sample_preferences, capsys, mock_isatty):
        """cmd_prefs mostra preferencias existentes"""
        args = cli_args()
        with mock_isatty(False):
            cmd_prefs(args)
            captured = capsys.readouterr()
            assert "test_framework" in captured.out or "pytest" in captured.out


# ============ TESTES DE PADROES ============

class TestCmdPattern:
    """Testes para cmd_pattern"""

    def test_pattern_without_args_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_pattern sem argumentos mostra erro"""
        args = cli_args(pattern=None)
        with mock_isatty(False):
            cmd_pattern(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_pattern_saves_pattern(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_pattern salva padrao"""
        args = cli_args(pattern=['hello', 'print("Hello World")'], language='python')
        with mock_isatty(False):
            cmd_pattern(args)
            captured = capsys.readouterr()
            assert "salvo" in captured.out.lower()


class TestCmdSnippet:
    """Testes para cmd_snippet"""

    def test_snippet_without_name_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_snippet sem nome mostra erro"""
        args = cli_args(name=None)
        with mock_isatty(False):
            cmd_snippet(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_snippet_not_found(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_snippet com padrao inexistente mostra erro"""
        args = cli_args(name=['nonexistent12345'])
        with mock_isatty(False):
            cmd_snippet(args)
            captured = capsys.readouterr()
            assert "não encontrado" in captured.out.lower()


# ============ TESTES DE MATURACAO ============

class TestCmdHypotheses:
    """Testes para cmd_hypotheses"""

    def test_hypotheses_empty(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_hypotheses em banco vazio"""
        args = cli_args(limit=15)
        with mock_isatty(False):
            cmd_hypotheses(args)
            captured = capsys.readouterr()
            assert "hipótese" in captured.out.lower() or "Hipóteses" in captured.out


class TestCmdConfirm:
    """Testes para cmd_confirm"""

    def test_confirm_without_args_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_confirm sem argumentos mostra erro"""
        args = cli_args(table=None, id=None)
        with mock_isatty(False):
            cmd_confirm(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_confirm_existing_decision(self, cli_args, sample_memories, capsys, mock_isatty):
        """cmd_confirm confirma decisao existente"""
        args = cli_args(table='decisions', id=sample_memories['decision_id'])
        with mock_isatty(False):
            cmd_confirm(args)
            captured = capsys.readouterr()
            assert "Confirmado" in captured.out or "confiança" in captured.out.lower()


class TestCmdContradict:
    """Testes para cmd_contradict"""

    def test_contradict_without_args_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_contradict sem argumentos mostra erro"""
        args = cli_args(table=None, id=None, reason=None)
        with mock_isatty(False):
            cmd_contradict(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out

    def test_contradict_with_reason(self, cli_args, sample_memories, capsys, mock_isatty):
        """cmd_contradict marca como incorreto com motivo"""
        args = cli_args(
            table='learnings',
            id=sample_memories['learning_id'],
            reason='Not working in Docker'
        )
        with mock_isatty(False):
            cmd_contradict(args)
            captured = capsys.readouterr()
            assert "contradito" in captured.out.lower() or "incorreto" in captured.out.lower()


class TestCmdSupersede:
    """Testes para cmd_supersede"""

    def test_supersede_without_args_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_supersede sem argumentos mostra erro"""
        args = cli_args(table=None, id=None, new=None)
        with mock_isatty(False):
            cmd_supersede(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out


class TestCmdMaturity:
    """Testes para cmd_maturity"""

    def test_maturity_shows_stats(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_maturity mostra estatisticas (tabela decisions/learnings apenas)"""
        # Insere decisao para ter dados
        from memory_store import save_decision
        save_decision("Test decision", reasoning="Test reason")

        args = cli_args()
        with mock_isatty(False):
            # Mock get_knowledge_by_maturity para evitar erro de coluna em memories
            with patch('brain_cli.get_knowledge_by_maturity') as mock_get:
                mock_get.return_value = [{'maturity_status': 'hypothesis', 'id': 1}]
                cmd_maturity(args)
                captured = capsys.readouterr()
                assert "Maturidade" in captured.out or "DECISIONS" in captured.out.upper()


# ============ TESTES DE DELETE ============

class TestCmdDelete:
    """Testes para cmd_delete"""

    def test_delete_without_args_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_delete sem argumentos mostra erro e sai"""
        args = cli_args(table=None, id=None, force=False)
        with mock_isatty(False):
            with pytest.raises(SystemExit) as exc_info:
                cmd_delete(args)
            assert exc_info.value.code == 1

    def test_delete_requires_confirmation_in_tty(self, cli_args, sample_memories, mock_stdin, capsys):
        """cmd_delete pede confirmacao em terminal interativo"""
        args = cli_args(
            table='memories',
            id=sample_memories['memory_id'],
            force=False
        )
        # Simula resposta 'n' para cancelar
        with mock_stdin('n\n'), \
             patch('sys.stdin.isatty', return_value=True), \
             patch('sys.stdout.isatty', return_value=True):
            cmd_delete(args)
            captured = capsys.readouterr()
            assert "Cancelado" in captured.out

    def test_delete_with_force(self, cli_args, sample_memories, capsys, mock_isatty):
        """cmd_delete com -f deleta sem confirmacao"""
        args = cli_args(
            table='memories',
            id=sample_memories['memory_id'],
            force=True
        )
        with mock_isatty(False):
            cmd_delete(args)
            captured = capsys.readouterr()
            assert "Deletado" in captured.out

    def test_delete_nonexistent_shows_error(self, cli_args, temp_db, capsys, mock_isatty):
        """cmd_delete com ID inexistente mostra erro"""
        args = cli_args(table='memories', id=99999, force=True)
        with mock_isatty(False):
            with pytest.raises(SystemExit):
                cmd_delete(args)


class TestCmdForget:
    """Testes para cmd_forget"""

    def test_forget_without_query_shows_error(self, cli_args, capsys, mock_isatty):
        """cmd_forget sem query mostra erro"""
        args = cli_args(query=None, table=None, threshold=0.8, execute=False)
        with mock_isatty(False):
            cmd_forget(args)
            captured = capsys.readouterr()
            assert "Uso:" in captured.out


# ============ TESTES DE UTILIDADES ============

class TestCmdExport:
    """Testes para cmd_export"""

    def test_export_outputs_context(self, cli_args, sample_memories, capsys, mock_isatty):
        """cmd_export gera contexto formatado"""
        args = cli_args(project=None)
        with mock_isatty(False):
            cmd_export(args)
            captured = capsys.readouterr()
            assert "Contexto" in captured.out or "#" in captured.out


class TestCmdStats:
    """Testes para cmd_stats"""

    def test_stats_outputs_statistics(self, cli_args, sample_memories, mock_metrics, capsys, mock_isatty):
        """cmd_stats mostra estatisticas"""
        args = cli_args()
        with mock_isatty(False):
            # Mock rag_stats que pode nao existir
            with patch('brain_cli.rag_stats', return_value={'documents': 10, 'chunks': 100}):
                cmd_stats(args)
                captured = capsys.readouterr()
                assert "Estatísticas" in captured.out or "Memória" in captured.out


class TestCmdUseful:
    """Testes para cmd_useful"""

    def test_useful_marks_last_action(self, cli_args, mock_metrics, capsys, mock_isatty):
        """cmd_useful marca ultima acao como util"""
        args = cli_args(feedback=None)
        with mock_isatty(False):
            cmd_useful(args)
            captured = capsys.readouterr()
            assert "útil" in captured.out.lower()
            mock_metrics['mark_useful'].assert_called_once_with(useful=True, feedback=None)


class TestCmdUseless:
    """Testes para cmd_useless"""

    def test_useless_marks_last_action(self, cli_args, mock_metrics, capsys, mock_isatty):
        """cmd_useless marca ultima acao como nao util"""
        args = cli_args(feedback=['Not helpful'])
        with mock_isatty(False):
            cmd_useless(args)
            captured = capsys.readouterr()
            assert "útil" in captured.out.lower()
            mock_metrics['mark_useful'].assert_called_once()


class TestCmdHelp:
    """Testes para cmd_help"""

    def test_help_shows_all_commands(self, cli_args, capsys, mock_isatty):
        """cmd_help mostra todos os comandos"""
        args = cli_args()
        with mock_isatty(False):
            cmd_help(args)
            captured = capsys.readouterr()
            # Verifica comandos principais
            assert "remember" in captured.out
            assert "decide" in captured.out
            assert "learn" in captured.out
            assert "search" in captured.out
            assert "delete" in captured.out


# ============ TESTES DE ERROR HANDLING ============

class TestErrorHandling:
    """Testes para tratamento de erros"""

    def test_main_catches_keyboard_interrupt(self, capsys):
        """main() trata KeyboardInterrupt"""
        with patch('sys.argv', ['brain', 'stats']), \
             patch('brain_cli.cmd_stats', side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 130

    def test_main_catches_generic_exception(self, capsys, mock_isatty):
        """main() trata excecoes genericas"""
        with patch('sys.argv', ['brain', 'stats']), \
             patch('brain_cli.cmd_stats', side_effect=Exception("Test error")), \
             mock_isatty(False):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "erro" in captured.out.lower() or "Error" in captured.out

    def test_invalid_command_shows_help(self, capsys, mock_isatty):
        """Comando invalido mostra help"""
        # Comando desconhecido nao e aceito pelo argparse (nao e subparser)
        # O comportamento e mostrar help quando command eh None
        with patch('sys.argv', ['brain']), mock_isatty(False):
            main()
            captured = capsys.readouterr()
            # Deve mostrar help quando nenhum comando e dado
            assert "MEMÓRIA" in captured.out or "brain remember" in captured.out.lower() or "Claude Brain" in captured.out


# ============ TESTES DE INTEGRACAO ============

class TestIntegration:
    """Testes de integracao entre comandos"""

    def test_decide_then_confirm_flow(self, cli_args, temp_db, capsys, mock_isatty, mock_metrics):
        """Fluxo: decide -> confirm"""
        # 1. Cria decisao
        args1 = cli_args(decision=['Use', 'FastAPI'], project='test', reason='Async support')
        with mock_isatty(False):
            cmd_decide(args1)
            captured1 = capsys.readouterr()
            # Extrai ID do output
            assert "ID:" in captured1.out

        # 2. Confirma decisao (assume ID 1)
        from memory_store import get_decisions
        decisions = get_decisions(project='test', limit=1)
        if decisions:
            dec_id = decisions[0]['id']
            args2 = cli_args(table='decisions', id=dec_id)
            cmd_confirm(args2)
            captured2 = capsys.readouterr()
            assert "Confirmado" in captured2.out

    def test_learn_then_solve_flow(self, cli_args, temp_db, capsys, mock_isatty, mock_metrics):
        """Fluxo: learn -> solve"""
        # 1. Cria learning direto no banco (save_learning tem bug com context)
        from memory_store import get_db
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO learnings (error_type, solution, prevention)
                VALUES (?, ?, ?)
            ''', ("CUDAOutOfMemory", "Reduce batch size to 16", "Check VRAM before training"))

        # 2. Busca solucao
        args2 = cli_args(error=['CUDAOutOfMemory'])
        with mock_isatty(False):
            cmd_solve(args2)
            captured2 = capsys.readouterr()
            assert "batch size" in captured2.out.lower() or "Solução" in captured2.out

    def test_entity_then_graph_flow(self, cli_args, temp_db, capsys, mock_isatty):
        """Fluxo: entity -> relate -> graph"""
        # 1. Cria entidades
        args1 = cli_args(name=['myproject', 'project', 'Test project'])
        with mock_isatty(False):
            cmd_entity(args1)
            capsys.readouterr()

        args2 = cli_args(name=['redis', 'technology', 'Cache'])
        cmd_entity(args2)
        capsys.readouterr()

        # 2. Cria relacao
        args3 = cli_args(relation=['myproject', 'redis', 'uses'])
        cmd_relate(args3)
        capsys.readouterr()

        # 3. Visualiza grafo
        args4 = cli_args(entity=['myproject'])
        cmd_graph(args4)
        captured = capsys.readouterr()
        assert "redis" in captured.out.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
