#!/usr/bin/env python3
"""
Claude Brain - Embedding Server
Mantém modelo em memória para respostas instantâneas
"""

import json
import socket
import threading
from pathlib import Path

# Configuração
SOCKET_PATH = "/tmp/claude-brain-embeddings.sock"
MODEL_NAME = "all-MiniLM-L6-v2"

# Global
_model = None
_lock = threading.Lock()


def load_model():
    """Carrega modelo uma vez"""
    global _model
    if _model is None:
        import warnings
        warnings.filterwarnings("ignore")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        print(f"✓ Modelo {MODEL_NAME} carregado")
    return _model


def encode(texts):
    """Gera embeddings"""
    model = load_model()
    with _lock:
        return model.encode(texts).tolist()


def handle_client(conn):
    """Processa requisição do cliente"""
    try:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break

        if data:
            request = json.loads(data.decode().strip())
            texts = request.get("texts", [])

            if texts:
                embeddings = encode(texts)
                response = json.dumps({"embeddings": embeddings})
            else:
                response = json.dumps({"error": "No texts provided"})

            conn.sendall(response.encode() + b"\n")
    except Exception as e:
        error_response = json.dumps({"error": str(e)})
        conn.sendall(error_response.encode() + b"\n")
    finally:
        conn.close()


def start_server():
    """Inicia servidor de embeddings"""
    # Remove socket antigo
    socket_path = Path(SOCKET_PATH)
    if socket_path.exists():
        socket_path.unlink()

    # Pré-carrega modelo
    print("Carregando modelo...")
    load_model()

    # Inicia servidor
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(5)

    print(f"✓ Servidor rodando em {SOCKET_PATH}")
    print("  Use: brain-server stop para parar")

    try:
        while True:
            conn, _ = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn,))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\nParando servidor...")
    finally:
        server.close()
        socket_path.unlink()


def get_embeddings_fast(texts):
    """Cliente - pega embeddings do servidor (fallback para local)"""
    socket_path = Path(SOCKET_PATH)

    if not socket_path.exists():
        # Fallback: carrega local
        return encode(texts)

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(5)
        client.connect(SOCKET_PATH)

        request = json.dumps({"texts": texts}) + "\n"
        client.sendall(request.encode())

        data = b""
        while True:
            chunk = client.recv(4096)
            if not chunk or b"\n" in data:
                break
            data += chunk

        client.close()

        response = json.loads(data.decode().strip())
        if "error" in response:
            raise Exception(response["error"])

        return response["embeddings"]

    except Exception as e:
        # Fallback: carrega local
        return encode(texts)


def is_server_running():
    """Verifica se socket do servidor existe"""
    return Path(SOCKET_PATH).exists()


def health_check() -> dict:
    """Verifica saúde do servidor de embeddings.

    Retorna:
        Dict com status e detalhes:
        - healthy: bool indicando se servidor está saudável
        - socket_exists: bool se o socket existe
        - can_connect: bool se conseguiu conectar
        - can_embed: bool se conseguiu gerar embedding
        - latency_ms: float tempo de resposta em ms
        - error: str mensagem de erro se houver
    """
    import time

    result = {
        "healthy": False,
        "socket_exists": False,
        "can_connect": False,
        "can_embed": False,
        "latency_ms": None,
        "error": None
    }

    socket_path = Path(SOCKET_PATH)
    result["socket_exists"] = socket_path.exists()

    if not result["socket_exists"]:
        result["error"] = "Socket não existe"
        return result

    try:
        start = time.time()
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(5)
        client.connect(SOCKET_PATH)
        result["can_connect"] = True

        # Tenta gerar embedding de teste
        request = json.dumps({"texts": ["health check"]}) + "\n"
        client.sendall(request.encode())

        data = b""
        while True:
            chunk = client.recv(4096)
            if not chunk or b"\n" in data:
                break
            data += chunk

        client.close()
        result["latency_ms"] = round((time.time() - start) * 1000, 2)

        response = json.loads(data.decode().strip())
        if "embeddings" in response and len(response["embeddings"]) > 0:
            result["can_embed"] = True
            result["healthy"] = True
        else:
            result["error"] = "Resposta sem embeddings"

    except socket.timeout:
        result["error"] = "Timeout ao conectar"
    except ConnectionRefusedError:
        result["error"] = "Conexão recusada"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "start":
            start_server()
        elif sys.argv[1] == "status":
            if is_server_running():
                print("✓ Servidor rodando")
            else:
                print("✗ Servidor parado")
        elif sys.argv[1] == "test":
            print("Testando embeddings...")
            import time
            start = time.time()
            emb = get_embeddings_fast(["teste de velocidade"])
            elapsed = time.time() - start
            print(f"✓ Embedding gerado em {elapsed:.3f}s")
            print(f"  Dimensões: {len(emb[0])}")
        elif sys.argv[1] == "health":
            result = health_check()
            if result["healthy"]:
                print(f"✓ Servidor saudável (latência: {result['latency_ms']}ms)")
            else:
                print(f"✗ Servidor não saudável: {result['error']}")
                print(f"  Socket existe: {result['socket_exists']}")
                print(f"  Pode conectar: {result['can_connect']}")
    else:
        print("Uso: embedding_server.py [start|status|test]")
