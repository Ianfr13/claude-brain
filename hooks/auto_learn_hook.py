#!/usr/bin/env python3
"""
Claude Code Hook - Auto Learn
Aprende automaticamente com cada interação
"""

import sys
import json
import os
from pathlib import Path

# Adiciona path do brain
sys.path.insert(0, "/root/claude-brain/scripts")

from auto_learner import learn_error, learn_conversation, learn_file, suggest_fix
from memory_store import save_memory


def process_hook(hook_data: dict):
    """Processa dados do hook e aprende"""

    hook_type = hook_data.get("hook_type", "")
    project = hook_data.get("cwd", "").split("/")[-1] if hook_data.get("cwd") else None

    # Hook de mensagem
    if hook_type == "post_message":
        user_msg = hook_data.get("user_message", "")
        assistant_msg = hook_data.get("assistant_message", "")

        if user_msg and assistant_msg:
            learn_conversation(user_msg, assistant_msg, project)

    # Hook de ferramenta
    elif hook_type == "post_tool":
        tool_name = hook_data.get("tool_name", "")
        tool_output = hook_data.get("tool_output", "")

        # Detecta erros no output
        if tool_output:
            error_keywords = ["error", "failed", "exception", "traceback", "not found"]
            if any(kw in tool_output.lower() for kw in error_keywords):
                learn_error(tool_output, project=project)

                # Tenta sugerir solução
                suggestion = suggest_fix(tool_output)
                if suggestion:
                    return {"suggestion": suggestion}

        # Aprende com mudanças de arquivo
        if tool_name in ["Write", "Edit"]:
            file_path = hook_data.get("tool_input", {}).get("file_path", "")
            content = hook_data.get("tool_input", {}).get("content", "")

            if file_path and content:
                learn_file(file_path, content, project)

    # Hook de sessão
    elif hook_type == "session_end":
        summary = hook_data.get("summary", "")
        if summary:
            save_memory("session", summary, category="session_summary", importance=7)

    return {}


def main():
    """Entry point para hook"""
    try:
        # Lê input do stdin
        input_data = sys.stdin.read()
        if input_data:
            hook_data = json.loads(input_data)
            result = process_hook(hook_data)
            print(json.dumps(result))
    except Exception as e:
        # Silently fail - não queremos quebrar o Claude Code
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
