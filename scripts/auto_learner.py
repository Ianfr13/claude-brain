#!/usr/bin/env python3
"""
Claude Brain - Auto Learner
Sistema de aprendizado automático que observa padrões e extrai conhecimento
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from scripts.memory_store import (
    save_memory, save_decision, save_learning, save_preference,
    save_entity, save_relation, find_solution
)


class AutoLearner:
    """
    Observa interações e aprende automaticamente:
    - Detecta preferências implícitas
    - Extrai decisões de código
    - Aprende com erros
    - Identifica padrões de uso
    """

    # Patterns para detectar erros
    ERROR_PATTERNS = [
        (r"(ModuleNotFoundError|ImportError):\s*(.+)", "import_error"),
        (r"(FileNotFoundError):\s*(.+)", "file_error"),
        (r"(PermissionError):\s*(.+)", "permission_error"),
        (r"(SyntaxError):\s*(.+)", "syntax_error"),
        (r"(TypeError|ValueError):\s*(.+)", "type_error"),
        (r"(KeyError):\s*(.+)", "key_error"),
        (r"(ConnectionError|TimeoutError):\s*(.+)", "connection_error"),
        (r"command not found:\s*(\w+)", "command_not_found"),
        (r"No such file or directory:\s*(.+)", "file_not_found"),
    ]

    # Patterns para detectar preferências
    PREFERENCE_PATTERNS = [
        (r"(sempre|nunca|prefiro|gosto de|não gosto de)\s+(.+)", 0.7),
        (r"(use|usar|utilize)\s+(\w+)\s+(em vez de|instead of)\s+(\w+)", 0.8),
        (r"(responda?|escreva?|faça?)\s+(em|no)\s+(português|inglês|english)", 0.9),
    ]

    # Patterns para detectar decisões em código
    DECISION_PATTERNS = [
        r"# DECISION:\s*(.+)",
        r"# TODO:\s*(.+)",
        r"# FIXME:\s*(.+)",
        r"// DECISION:\s*(.+)",
        r"<!-- DECISION:\s*(.+)\s*-->",
    ]

    # Tecnologias conhecidas
    KNOWN_TECHNOLOGIES = {
        "python", "javascript", "typescript", "rust", "go", "java", "ruby",
        "react", "vue", "angular", "svelte", "nextjs", "django", "flask", "fastapi",
        "pytorch", "tensorflow", "sklearn", "pandas", "numpy",
        "docker", "kubernetes", "terraform", "aws", "gcp", "azure",
        "postgres", "mysql", "mongodb", "redis", "sqlite", "chromadb",
        "git", "github", "gitlab", "npm", "pip", "cargo"
    }

    def __init__(self):
        self.session_errors = []
        self.session_decisions = []

    def analyze_error(self, text: str) -> Optional[Dict]:
        """Analisa texto para detectar erros"""
        for pattern, error_type in self.ERROR_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return {
                    "error_type": error_type,
                    "error_message": match.group(0),
                    "details": match.groups()
                }
        return None

    def analyze_text_for_preferences(self, text: str) -> List[Dict]:
        """Analisa texto para detectar preferências implícitas"""
        preferences = []

        for pattern, confidence in self.PREFERENCE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                preferences.append({
                    "pattern": pattern,
                    "match": match.group(0),
                    "groups": match.groups(),
                    "confidence": confidence
                })

        return preferences

    def extract_technologies(self, text: str) -> List[str]:
        """Extrai tecnologias mencionadas no texto"""
        words = set(re.findall(r'\b\w+\b', text.lower()))
        return list(words & self.KNOWN_TECHNOLOGIES)

    def analyze_code_for_decisions(self, code: str) -> List[str]:
        """Extrai decisões de comentários no código"""
        decisions = []

        for pattern in self.DECISION_PATTERNS:
            matches = re.finditer(pattern, code)
            for match in matches:
                decisions.append(match.group(1).strip())

        return decisions

    def learn_from_error(self, error_text: str, solution_text: str = None,
                         project: str = None) -> Optional[int]:
        """Aprende com um erro e sua solução"""
        error_info = self.analyze_error(error_text)
        if not error_info:
            return None

        # Verifica se já conhecemos solução
        existing = find_solution(
            error_type=error_info["error_type"],
            error_message=error_info["error_message"]
        )

        if existing and not solution_text:
            # Já temos solução, retorna ela
            return existing["id"]

        # Salva novo aprendizado
        if solution_text:
            return save_learning(
                error_type=error_info["error_type"],
                error_message=error_info["error_message"],
                solution=solution_text,
                project=project
            )

        return None

    def learn_from_conversation(self, user_message: str, assistant_response: str,
                                 project: str = None):
        """Aprende com uma troca de mensagens"""
        # Detecta preferências
        for text in [user_message, assistant_response]:
            prefs = self.analyze_text_for_preferences(text)
            for p in prefs:
                if p["confidence"] >= 0.7:
                    key = p["groups"][0] if len(p["groups"]) > 0 else "general"
                    value = p["match"]
                    save_preference(key, value, confidence=p["confidence"], source="conversation")

        # Detecta tecnologias mencionadas
        techs = self.extract_technologies(user_message + " " + assistant_response)
        for tech in techs:
            save_entity(tech, "technology")
            if project:
                save_relation(project, tech, "mentions")

        # Detecta erros no response
        error_info = self.analyze_error(assistant_response)
        if error_info:
            self.session_errors.append(error_info)
            save_memory("error", error_info["error_message"], category=error_info["error_type"])

    def learn_from_file_change(self, file_path: str, content: str, project: str = None):
        """Aprende com mudanças em arquivos"""
        # Detecta decisões em comentários
        decisions = self.analyze_code_for_decisions(content)
        for d in decisions:
            save_decision(d, project=project, context=f"Arquivo: {file_path}")

        # Detecta tecnologias usadas
        techs = self.extract_technologies(content)
        for tech in techs:
            save_entity(tech, "technology")
            if project:
                save_relation(project, tech, "uses")

        # Detecta padrões de import
        imports = self.extract_imports(content, file_path)
        for imp in imports:
            save_entity(imp, "dependency")
            if project:
                save_relation(project, imp, "depends_on")

    def extract_imports(self, content: str, file_path: str) -> List[str]:
        """Extrai imports/dependências do código"""
        imports = []
        ext = Path(file_path).suffix.lower()

        if ext == ".py":
            # Python imports
            patterns = [
                r"^import (\w+)",
                r"^from (\w+)",
            ]
            for p in patterns:
                imports.extend(re.findall(p, content, re.MULTILINE))

        elif ext in [".js", ".ts", ".tsx", ".jsx"]:
            # JS/TS imports
            patterns = [
                r"import .+ from ['\"](@?\w+)",
                r"require\(['\"](\w+)",
            ]
            for p in patterns:
                imports.extend(re.findall(p, content))

        return list(set(imports))

    def suggest_solution(self, error_text: str) -> Optional[str]:
        """Sugere solução baseada em aprendizados anteriores"""
        error_info = self.analyze_error(error_text)
        if not error_info:
            return None

        solution = find_solution(
            error_type=error_info["error_type"],
            error_message=error_info["error_message"]
        )

        if solution:
            return solution["solution"]

        # Soluções genéricas baseadas no tipo de erro
        generic_solutions = {
            "import_error": "Verifique se o módulo está instalado: pip install <modulo>",
            "file_error": "Verifique se o arquivo existe e o caminho está correto",
            "permission_error": "Verifique as permissões do arquivo/diretório",
            "connection_error": "Verifique a conexão de rede e se o serviço está rodando",
            "command_not_found": "Instale o comando ou verifique o PATH",
        }

        return generic_solutions.get(error_info["error_type"])

    def get_session_summary(self) -> Dict:
        """Retorna resumo da sessão atual"""
        return {
            "errors_detected": len(self.session_errors),
            "decisions_made": len(self.session_decisions),
            "errors": self.session_errors[-5:],  # Últimos 5
            "decisions": self.session_decisions[-5:]
        }


# Singleton
_learner = None

def get_learner() -> AutoLearner:
    global _learner
    if _learner is None:
        _learner = AutoLearner()
    return _learner


# Funções de conveniência
def learn_error(error_text: str, solution: str = None, project: str = None):
    """Aprende com um erro"""
    return get_learner().learn_from_error(error_text, solution, project)


def learn_conversation(user_msg: str, assistant_msg: str, project: str = None):
    """Aprende com uma conversa"""
    return get_learner().learn_from_conversation(user_msg, assistant_msg, project)


def learn_file(file_path: str, content: str, project: str = None):
    """Aprende com mudança de arquivo"""
    return get_learner().learn_from_file_change(file_path, content, project)


def suggest_fix(error_text: str) -> Optional[str]:
    """Sugere fix para um erro"""
    return get_learner().suggest_solution(error_text)


if __name__ == "__main__":
    # Testes
    learner = AutoLearner()

    # Teste de detecção de erro
    error = "ModuleNotFoundError: No module named 'pandas'"
    result = learner.analyze_error(error)
    print(f"Erro detectado: {result}")

    # Teste de preferências
    text = "Sempre use português nas respostas"
    prefs = learner.analyze_text_for_preferences(text)
    print(f"Preferências: {prefs}")

    # Teste de tecnologias
    text = "Vamos usar pytorch com fastapi e redis"
    techs = learner.extract_technologies(text)
    print(f"Tecnologias: {techs}")

    # Teste de solução
    solution = learner.suggest_solution(error)
    print(f"Solução sugerida: {solution}")
