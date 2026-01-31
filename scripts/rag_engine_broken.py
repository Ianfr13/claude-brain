#!/usr/bin/env python3
"""
Claude Brain - RAG Engine
Sistema de Retrieval Augmented Generation para memória semântica
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Paths
BRAIN_DIR = Path("/root/claude-brain")
RAG_DIR = BRAIN_DIR / "rag"
CHUNKS_DIR = RAG_DIR / "chunks"
INDEX_FILE = RAG_DIR / "index.json"

# Configuração
CHUNK_SIZE = 500  # caracteres por chunk
CHUNK_OVERLAP = 50
TOP_K = 5  # resultados por busca


def ensure_dirs():
    """Cria diretórios necessários"""
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Divide texto em chunks com overlap"""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Tenta quebrar em limite de sentença
        if end < len(text):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            if break_point > chunk_size * 0.5:
                chunk = chunk[:break_point + 1]
                end = start + break_point + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return chunks


def compute_hash(text: str) -> str:
    """Computa hash do texto"""
    return hashlib.md5(text.encode()).hexdigest()[:12]


def load_index() -> Dict:
    """Carrega índice de documentos"""
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {"documents": {}, "chunks": {}}


def save_index(index: Dict):
    """Salva índice de documentos"""
    INDEX_FILE.write_text(json.dumps(index, indent=2))


def index_document(content: str, source: str, doc_type: str = "generic",
                   metadata: dict = None) -> Dict:
    """Indexa um documento no sistema RAG"""
    ensure_dirs()
    index = load_index()

    doc_hash = compute_hash(content)

    # Verifica se já existe
    if doc_hash in index["documents"]:
        print(f"Documento já indexado: {source}")
        return index["documents"][doc_hash]

    # Cria chunks
    chunks = chunk_text(content)
    chunk_ids = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_hash}_{i}"
        chunk_data = {
            "id": chunk_id,
            "text": chunk,
            "source": source,
            "doc_type": doc_type,
            "position": i,
            "total_chunks": len(chunks),
            "metadata": metadata or {},
            "indexed_at": datetime.now().isoformat()
        }

        # Salva chunk
        chunk_file = CHUNKS_DIR / f"{chunk_id}.json"
        chunk_file.write_text(json.dumps(chunk_data, indent=2))
        chunk_ids.append(chunk_id)

        # Adiciona ao índice
        index["chunks"][chunk_id] = {
            "source": source,
            "doc_type": doc_type,
            "preview": chunk[:100]
        }

    # Adiciona documento ao índice
    doc_info = {
        "source": source,
        "doc_type": doc_type,
        "chunk_count": len(chunks),
        "chunk_ids": chunk_ids,
        "metadata": metadata or {},
        "indexed_at": datetime.now().isoformat()
    }
    index["documents"][doc_hash] = doc_info
    save_index(index)

    print(f"✓ Indexado: {source} ({len(chunks)} chunks)")
    return doc_info


def index_file(filepath: str, doc_type: str = None) -> Optional[Dict]:
    """Indexa um arquivo"""
    path = Path(filepath)
    if not path.exists():
        print(f"Arquivo não encontrado: {filepath}")
        return None

    # Detecta tipo
    if doc_type is None:
        ext = path.suffix.lower()
        type_map = {
            ".md": "markdown",
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".txt": "text"
        }
        doc_type = type_map.get(ext, "generic")

    content = path.read_text(errors='ignore')
    return index_document(content, str(path), doc_type, {"filename": path.name})


def index_directory(dirpath: str, extensions: List[str] = None,
                    recursive: bool = True) -> int:
    """Indexa todos os arquivos de um diretório"""
    if extensions is None:
        extensions = [".md", ".py", ".js", ".ts", ".txt", ".yaml", ".yml"]

    path = Path(dirpath)
    if not path.exists():
        print(f"Diretório não encontrado: {dirpath}")
        return 0

    count = 0
    pattern = "**/*" if recursive else "*"

    for ext in extensions:
        for file in path.glob(f"{pattern}{ext}"):
            if ".git" in str(file) or "__pycache__" in str(file):
                continue
            result = index_file(str(file))
            if result:
                count += 1

    print(f"\n✓ Total indexado: {count} arquivos")
    return count


def simple_search(query: str, doc_type: str = None,
                  limit: int = TOP_K) -> List[Dict]:
    """Busca simples por palavras-chave (fallback sem embeddings)"""
    index = load_index()
    query_words = set(query.lower().split())
    results = []

    for chunk_id, chunk_info in index["chunks"].items():
        if doc_type and chunk_info["doc_type"] != doc_type:
            continue

        # Carrega chunk completo
        chunk_file = CHUNKS_DIR / f"{chunk_id}.json"
        if not chunk_file.exists():
            continue

        chunk_data = json.loads(chunk_file.read_text())
        chunk_text = chunk_data["text"].lower()

        # Score baseado em palavras encontradas
        score = sum(1 for word in query_words if word in chunk_text)
        if score > 0:
            results.append({
                "chunk_id": chunk_id,
                "score": score,
                "text": chunk_data["text"],
                "source": chunk_data["source"],
                "doc_type": chunk_data["doc_type"]
            })

    # Ordena por score
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def semantic_search(query: str, doc_type: str = None,
                    limit: int = TOP_K) -> List[Dict]:
    """
    Busca semântica usando embeddings
    Requer: pip install sentence-transformers chromadb
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        # Inicializa modelo e ChromaDB
        model = SentenceTransformer('all-MiniLM-L6-v2')
        client = chromadb.PersistentClient(path=str(RAG_DIR / "chromadb"))
        collection = client.get_or_create_collection("claude_brain")

        # Busca
        query_embedding = model.encode(query).tolist()

        where_filter = {"doc_type": doc_type} if doc_type else None
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where_filter
        )

        formatted = []
        for i, (doc_id, distance, document, metadata) in enumerate(zip(
            results['ids'][0],
            results['distances'][0],
            results['documents'][0],
            results['metadatas'][0]
        )):
            formatted.append({
                "chunk_id": doc_id,
                "score": 1 - distance,  # Converte distância para similaridade
                "text": document,
                "source": metadata.get("source", "unknown"),
                "doc_type": metadata.get("doc_type", "generic")
            })

        return formatted

    except ImportError:
        print("ChromaDB/SentenceTransformers não instalados. Usando busca simples.")
        return simple_search(query, doc_type, limit)


def search(query: str, doc_type: str = None,
           limit: int = TOP_K, semantic: bool = True) -> List[Dict]:
    """Interface unificada de busca"""
    if semantic:
        return semantic_search(query, doc_type, limit)
    return simple_search(query, doc_type, limit)


def build_embeddings():
    """Constrói embeddings para todos os chunks indexados"""
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        print("Construindo embeddings...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        client = chromadb.PersistentClient(path=str(RAG_DIR / "chromadb"))

        # Deleta collection existente para rebuild
        try:
            client.delete_collection("claude_brain")
        except:
            pass

        collection = client.create_collection("claude_brain")

        index = load_index()
        documents = []
        metadatas = []
        ids = []

        for chunk_id in index["chunks"]:
            chunk_file = CHUNKS_DIR / f"{chunk_id}.json"
            if not chunk_file.exists():
                continue

            chunk_data = json.loads(chunk_file.read_text())
            documents.append(chunk_data["text"])
            metadatas.append({
                "source": chunk_data["source"],
                "doc_type": chunk_data["doc_type"]
            })
            ids.append(chunk_id)

        if documents:
            print(f"Gerando embeddings para {len(documents)} chunks...")
            embeddings = model.encode(documents).tolist()

            # Adiciona em batches
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                end = min(i + batch_size, len(documents))
                collection.add(
                    documents=documents[i:end],
                    embeddings=embeddings[i:end],
                    metadatas=metadatas[i:end],
                    ids=ids[i:end]
                )
                print(f"  Batch {i//batch_size + 1}: {end} chunks")

        print(f"✓ Embeddings construídos para {len(documents)} chunks")

    except ImportError as e:
        print(f"Erro: {e}")
        print("Instale: pip install sentence-transformers chromadb")


def get_stats() -> Dict:
    """Retorna estatísticas do RAG"""
    index = load_index()
    return {
        "documents": len(index["documents"]),
        "chunks": len(index["chunks"]),
        "sources": list(set(c["source"] for c in index["chunks"].values()))[:10]
    }


def get_context_for_query(query: str, max_tokens: int = 2000) -> str:
    """Retorna contexto formatado para o Claude baseado na query"""
    results = search(query, limit=5)

    if not results:
        return "Nenhum contexto relevante encontrado na memória."

    output = ["## Contexto Relevante da Memória\n"]
    token_estimate = 0

    for r in results:
        chunk_text = f"\n### Fonte: {r['source']}\n{r['text']}\n"
        chunk_tokens = len(chunk_text) // 4  # Estimativa grosseira

        if token_estimate + chunk_tokens > max_tokens:
            break

        output.append(chunk_text)
        token_estimate += chunk_tokens

    return "\n".join(output)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: rag_engine.py <comando> [args]")
        print("\nComandos:")
        print("  index-file <arquivo>           - Indexa um arquivo")
        print("  index-dir <diretório>          - Indexa um diretório")
        print("  search <query>                 - Busca por query")
        print("  context <query>                - Retorna contexto formatado")
        print("  build-embeddings               - Constrói embeddings (requer chromadb)")
        print("  stats                          - Mostra estatísticas")
        sys.exit(1)

    cmd = sys.argv[1]
    ensure_dirs()

    if cmd == "index-file":
        if len(sys.argv) < 3:
            print("Uso: index-file <arquivo>")
            sys.exit(1)
        index_file(sys.argv[2])

    elif cmd == "index-dir":
        if len(sys.argv) < 3:
            print("Uso: index-dir <diretório>")
            sys.exit(1)
        index_directory(sys.argv[2])

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Uso: search <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        results = search(query)
        print(f"\n🔍 Resultados para: '{query}'\n")
        for r in results:
            print(f"[Score: {r['score']:.2f}] {r['source']}")
            print(f"  {r['text'][:150]}...\n")

    elif cmd == "context":
        if len(sys.argv) < 3:
            print("Uso: context <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        context = get_context_for_query(query)
        print(context)

    elif cmd == "build-embeddings":
        build_embeddings()

    elif cmd == "stats":
        stats = get_stats()
        print("\n📊 Estatísticas do RAG:")
        print(f"  Documentos: {stats['documents']}")
        print(f"  Chunks: {stats['chunks']}")
        print(f"  Fontes: {len(stats['sources'])}")

    else:
        print(f"Comando desconhecido: {cmd}")
        sys.exit(1)
