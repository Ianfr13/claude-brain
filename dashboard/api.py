#!/usr/bin/env python3
"""
Claude Brain - API HTTP
Serve dados do Brain para o Dashboard
"""

import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

# Adiciona path dos scripts
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from memory_store import (
    get_stats, get_decisions, get_all_learnings, get_all_preferences,
    get_entity_graph, search_memories
)
from metrics import get_effectiveness, get_daily_report, get_recent_actions

# Tenta importar FAISS RAG
try:
    from faiss_rag import semantic_search
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    from rag_engine import search as simple_search


class BrainAPIHandler(BaseHTTPRequestHandler):
    """Handler para requisicoes da API"""

    def _set_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _json_response(self, data, status=200):
        self._set_headers(status)
        self.wfile.write(json.dumps(data, default=str, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self._set_headers(204)

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Helper para pegar parametros
        def get_param(name, default=None, type_func=str):
            if name in params:
                return type_func(params[name][0])
            return default

        try:
            # Rotas
            if path == '/api/stats':
                self._json_response(get_stats())

            elif path == '/api/effectiveness':
                self._json_response(get_effectiveness())

            elif path == '/api/decisions':
                limit = get_param('limit', 10, int)
                project = get_param('project')
                decisions = get_decisions(project=project, limit=limit)
                self._json_response(decisions)

            elif path == '/api/learnings':
                limit = get_param('limit', 20, int)
                learnings = get_all_learnings(limit=limit)
                self._json_response(learnings)

            elif path == '/api/preferences':
                prefs = get_all_preferences(min_confidence=0.3)
                self._json_response(prefs)

            elif path == '/api/search':
                query = get_param('q', '')
                limit = get_param('limit', 5, int)
                doc_type = get_param('type')

                if HAS_FAISS:
                    results = semantic_search(query, doc_type=doc_type, limit=limit)
                else:
                    results = simple_search(query, doc_type=doc_type, limit=limit)

                self._json_response(results)

            elif path == '/api/memories':
                query = get_param('q')
                mem_type = get_param('type')
                limit = get_param('limit', 10, int)
                memories = search_memories(query=query, type=mem_type, limit=limit)
                self._json_response(memories)

            elif path.startswith('/api/graph/'):
                entity_name = path.replace('/api/graph/', '')
                graph = get_entity_graph(entity_name)
                if graph:
                    self._json_response(graph)
                else:
                    self._json_response({'error': 'Entity not found'}, 404)

            elif path == '/api/daily':
                days = get_param('days', 7, int)
                report = get_daily_report(days=days)
                self._json_response(report)

            elif path == '/api/actions':
                limit = get_param('limit', 20, int)
                actions = get_recent_actions(limit=limit)
                self._json_response(actions)

            elif path == '/api/health':
                self._json_response({'status': 'ok', 'faiss': HAS_FAISS})

            elif path == '/' or path == '/index.html':
                # Serve o dashboard
                self._serve_dashboard()

            else:
                self._json_response({'error': 'Not found'}, 404)

        except Exception as e:
            print(f"Error handling {path}: {e}")
            self._json_response({'error': str(e)}, 500)

    def _serve_dashboard(self):
        """Serve o arquivo index.html"""
        dashboard_path = Path(__file__).parent / 'index.html'
        if dashboard_path.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(dashboard_path.read_bytes())
        else:
            self._json_response({'error': 'Dashboard not found'}, 404)

    def log_message(self, format, *args):
        """Customiza log"""
        print(f"[API] {args[0]}")


def run_server(port=8765):
    """Inicia o servidor"""
    # Security: Bind apenas em localhost para evitar exposição externa
    server = HTTPServer(('127.0.0.1', port), BrainAPIHandler)
    print(f"""
╔══════════════════════════════════════════════════════════╗
║          Claude Brain API Server                         ║
╠══════════════════════════════════════════════════════════╣
║  Dashboard: http://localhost:{port}/                      ║
║  API Base:  http://localhost:{port}/api/                  ║
║                                                          ║
║  Endpoints:                                              ║
║    GET /api/stats        - Estatisticas gerais           ║
║    GET /api/effectiveness- Metricas de eficacia          ║
║    GET /api/decisions    - Decisoes recentes             ║
║    GET /api/learnings    - Aprendizados                  ║
║    GET /api/preferences  - Preferencias                  ║
║    GET /api/search?q=    - Busca semantica               ║
║    GET /api/graph/<name> - Knowledge graph               ║
║    GET /api/health       - Health check                  ║
║                                                          ║
║  FAISS: {'Ativo' if HAS_FAISS else 'Inativo (usando busca simples)'}                             ║
╚══════════════════════════════════════════════════════════╝
    """)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[API] Servidor encerrado")
        server.shutdown()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Claude Brain API Server')
    parser.add_argument('-p', '--port', type=int, default=8765, help='Porta do servidor')
    args = parser.parse_args()

    run_server(args.port)
