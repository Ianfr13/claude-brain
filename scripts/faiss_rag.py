#!/usr/bin/env python3
"""
Claude Brain - FAISS RAG Engine
Busca semântica usando FAISS (sem ChromaDB)

Features:
- Auto-rebuild: Reconstrói índice automaticamente quando documentos mudam
- Cache de queries com TTL
- Logging de operações de rebuild
"""

import os
import json
import time
import logging
import hashlib
import fcntl
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("faiss_rag")

# Paths
BRAIN_DIR = Path("/root/claude-brain")
RAG_DIR = BRAIN_DIR / "rag"
FAISS_DIR = RAG_DIR / "faiss"
INDEX_FILE = RAG_DIR / "index.json"
FAISS_INDEX_FILE = FAISS_DIR / "index.faiss"
FAISS_META_FILE = FAISS_DIR / "metadata.json"
REBUILD_STATE_FILE = FAISS_DIR / "rebuild_state.json"

# Configuração
TOP_K = 5
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2
AUTO_REBUILD_ENABLED = True  # Flag global para habilitar/desabilitar auto-rebuild

# Limites de indexação
MAX_DOCUMENTS = 100       # Máximo de documentos a indexar
MAX_DOC_SIZE = 20000      # Tamanho máximo por documento (20KB)
CHUNK_SIZE = 1500         # Tamanho de cada chunk para embeddings
MIN_CHUNK_LENGTH = 100    # Tamanho mínimo de chunk para ser indexado

# Global model (carregado uma vez)
_model = None
_faiss_index = None
_faiss_metadata = None
CACHE_MAX_SIZE = 100
CACHE_FILE = RAG_DIR / "query_cache.json"  # Legacy fallback
CACHE_DIR = RAG_DIR / "diskcache"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 horas

# Cache backend: "redis", "diskcache", or "json" (legacy)
_cache_backend = None
_cache_instance = None
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_PREFIX = "brain:query:"


def _init_cache_backend():
    """Inicializa o backend de cache (Redis > diskcache > JSON).

    Tenta Redis primeiro, depois diskcache, e por ultimo JSON como fallback.
    """
    global _cache_backend, _cache_instance

    if _cache_backend is not None:
        return _cache_backend, _cache_instance

    # Tenta Redis primeiro
    try:
        import redis
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        _cache_backend = "redis"
        _cache_instance = r
        logger.info("Cache backend: Redis")
        return _cache_backend, _cache_instance
    except Exception as e:
        logger.debug(f"Redis nao disponivel: {e}")

    # Tenta diskcache (SQLite-backed)
    try:
        import diskcache
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache = diskcache.Cache(
            str(CACHE_DIR),
            size_limit=50 * 1024 * 1024,  # 50MB max
            eviction_policy="least-recently-used",
        )
        _cache_backend = "diskcache"
        _cache_instance = cache
        logger.info("Cache backend: diskcache (SQLite)")
        return _cache_backend, _cache_instance
    except Exception as e:
        logger.warning(f"diskcache nao disponivel: {e}")

    # Fallback para JSON (legado)
    _cache_backend = "json"
    _cache_instance = None
    logger.warning("Cache backend: JSON (fallback, performance reduzida)")
    return _cache_backend, _cache_instance


def cache_get(key: str) -> Optional[dict]:
    """Obtem valor do cache.

    Args:
        key: Chave de cache (query:doc_type:limit)

    Returns:
        Dict com resultados ou None se nao encontrado/expirado
    """
    backend, instance = _init_cache_backend()

    try:
        if backend == "redis":
            data = instance.get(f"{REDIS_PREFIX}{key}")
            if data:
                return json.loads(data)
            return None

        elif backend == "diskcache":
            result = instance.get(key)
            return result  # diskcache retorna None se expirado

        else:  # json fallback
            cache = _load_json_cache()
            if key in cache:
                entry = cache[key]
                if isinstance(entry, dict) and "data" in entry and "timestamp" in entry:
                    if time.time() - entry["timestamp"] < CACHE_TTL_SECONDS:
                        return entry["data"]
            return None

    except Exception as e:
        logger.warning(f"Erro ao ler cache ({backend}): {e}")
        return None


def cache_set(key: str, value: dict) -> bool:
    """Armazena valor no cache.

    Args:
        key: Chave de cache
        value: Dados a armazenar (lista de resultados)

    Returns:
        True se sucesso, False caso contrario
    """
    backend, instance = _init_cache_backend()

    try:
        if backend == "redis":
            instance.setex(
                f"{REDIS_PREFIX}{key}",
                CACHE_TTL_SECONDS,
                json.dumps(value, ensure_ascii=False)
            )
            return True

        elif backend == "diskcache":
            instance.set(key, value, expire=CACHE_TTL_SECONDS)
            return True

        else:  # json fallback
            cache = _load_json_cache()
            cache[key] = {"data": value, "timestamp": time.time()}
            _save_json_cache(cache)
            return True

    except Exception as e:
        logger.warning(f"Erro ao escrever cache ({backend}): {e}")
        return False


def cache_clear() -> bool:
    """Limpa todo o cache.

    Returns:
        True se sucesso, False caso contrario
    """
    backend, instance = _init_cache_backend()

    try:
        if backend == "redis":
            keys = instance.keys(f"{REDIS_PREFIX}*")
            if keys:
                instance.delete(*keys)
            logger.info("Cache Redis limpo")
            return True

        elif backend == "diskcache":
            instance.clear()
            logger.info("Cache diskcache limpo")
            return True

        else:  # json fallback
            if CACHE_FILE.exists():
                CACHE_FILE.unlink()
            logger.info("Cache JSON limpo")
            return True

    except Exception as e:
        logger.warning(f"Erro ao limpar cache ({backend}): {e}")
        return False


def cache_stats() -> dict:
    """Retorna estatisticas do cache.

    Returns:
        Dict com estatisticas do cache
    """
    backend, instance = _init_cache_backend()

    try:
        if backend == "redis":
            keys = instance.keys(f"{REDIS_PREFIX}*")
            return {
                "backend": "redis",
                "entries": len(keys),
                "url": REDIS_URL.split("@")[-1] if "@" in REDIS_URL else REDIS_URL,
            }

        elif backend == "diskcache":
            return {
                "backend": "diskcache",
                "entries": len(instance),
                "size_bytes": instance.volume(),
                "path": str(CACHE_DIR),
            }

        else:  # json fallback
            cache = _load_json_cache()
            return {
                "backend": "json",
                "entries": len(cache),
                "path": str(CACHE_FILE),
            }

    except Exception as e:
        return {"backend": backend, "error": str(e)}


def _load_json_cache() -> dict:
    """Carrega cache JSON legado."""
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text())
            current_time = time.time()
            cleaned_cache = {}

            for key, value in cache.items():
                if isinstance(value, list):
                    cleaned_cache[key] = {"data": value, "timestamp": current_time}
                elif isinstance(value, dict) and "data" in value and "timestamp" in value:
                    if current_time - value["timestamp"] < CACHE_TTL_SECONDS:
                        cleaned_cache[key] = value

            return cleaned_cache
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Erro ao carregar cache JSON: {e}")
    return {}


def _save_json_cache(cache: dict):
    """Salva cache JSON legado."""
    if len(cache) > CACHE_MAX_SIZE:
        sorted_keys = sorted(
            cache.keys(),
            key=lambda k: cache[k].get("timestamp", 0) if isinstance(cache[k], dict) else 0
        )
        for k in sorted_keys[:len(cache) - CACHE_MAX_SIZE]:
            del cache[k]

    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(cache, f, ensure_ascii=False)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# Funcoes de compatibilidade (deprecated, usar cache_* diretamente)
def load_query_cache() -> dict:
    """DEPRECATED: Use cache_get() diretamente.

    Mantido para compatibilidade com codigo legado.
    """
    return _load_json_cache()


def save_query_cache(cache: dict):
    """DEPRECATED: Use cache_set() diretamente.

    Mantido para compatibilidade com codigo legado.
    """
    _save_json_cache(cache)


def invalidate_query_cache():
    """Invalida o cache de queries (chamado apos rebuild)."""
    cache_clear()


def get_model():
    """Carrega modelo de embeddings (singleton)"""
    global _model
    if _model is None:
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def ensure_dirs():
    """Cria diretórios necessários"""
    FAISS_DIR.mkdir(parents=True, exist_ok=True)


def load_doc_index() -> Dict:
    """Carrega índice de documentos"""
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {"documents": {}}


def load_rebuild_state() -> Dict:
    """Carrega estado do último rebuild."""
    if REBUILD_STATE_FILE.exists():
        try:
            return json.loads(REBUILD_STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Erro ao carregar estado de rebuild: {e}")
    return {}


def save_rebuild_state(state: Dict):
    """Salva estado do rebuild."""
    ensure_dirs()
    REBUILD_STATE_FILE.write_text(json.dumps(state, indent=2))


def compute_documents_hash(doc_index: Dict) -> str:
    """Computa hash dos documentos para detectar mudanças.

    Considera:
    - Lista de documentos (hashes) em ordem determinística
    - Timestamps de modificação dos arquivos fonte

    NOTA: Hash é determinístico pois sort() garante ordem consistente
    """
    hash_data = []

    # IMPORTANTE: sorted() garante ordem determinística
    for doc_hash, doc_info in sorted(doc_index.get("documents", {}).items()):
        source = doc_info.get("source", "")
        source_path = Path(source)

        # Inclui hash do documento
        hash_data.append(doc_hash)

        # Inclui timestamp de modificação do arquivo (se existir)
        if source_path.exists():
            try:
                mtime = source_path.stat().st_mtime
                hash_data.append(f"{source}:{mtime}")
            except (OSError, IOError) as e:
                logger.warning(f"Erro ao obter mtime de {source}: {e}")
                hash_data.append(source)

    # Gera hash combinado (SHA256 para integridade)
    # Ordem é determinística por causa de sorted()
    combined = "|".join(hash_data)
    return hashlib.sha256(combined.encode()).hexdigest()


def is_index_stale() -> Tuple[bool, str]:
    """Verifica se o índice FAISS está obsoleto.

    Retorna:
        Tuple[bool, str]: (está_obsoleto, motivo)

    Critérios para índice obsoleto:
    1. Índice não existe
    2. rebuild_state.json não foi criado (primeira execução ou erro anterior)
    3. index.json foi modificado após o índice FAISS
    4. Hash dos documentos mudou desde o último rebuild
    5. Algum arquivo fonte foi modificado após o índice
    """
    # Verifica se índice existe
    if not FAISS_INDEX_FILE.exists() or not FAISS_META_FILE.exists():
        return True, "Índice FAISS não existe"

    # CRÍTICO: Se rebuild_state.json não existe, índice nunca foi construído
    # adequadamente (primeira execução ou erro anterior)
    if not REBUILD_STATE_FILE.exists():
        return True, "rebuild_state.json não existe (primeira construção?)"

    # Timestamp do índice FAISS
    faiss_mtime = FAISS_INDEX_FILE.stat().st_mtime

    # Verifica se index.json foi modificado após o índice
    if INDEX_FILE.exists():
        index_mtime = INDEX_FILE.stat().st_mtime
        if index_mtime > faiss_mtime:
            return True, f"index.json modificado ({datetime.fromtimestamp(index_mtime).strftime('%Y-%m-%d %H:%M:%S')})"

    # Carrega estado do último rebuild
    rebuild_state = load_rebuild_state()
    last_hash = rebuild_state.get("documents_hash", "")

    # Se last_hash não foi salvo (erro anterior ou corrupção), rebuilda
    if not last_hash:
        return True, "Hash anterior não encontrado em rebuild_state.json"

    # Computa hash atual dos documentos
    doc_index = load_doc_index()
    current_hash = compute_documents_hash(doc_index)

    # Compara hashes
    if current_hash != last_hash:
        return True, f"Hash dos documentos mudou ({current_hash[:8]}... vs {last_hash[:8]}...)"

    # Verifica se algum arquivo fonte foi modificado após o índice
    for doc_hash, doc_info in doc_index.get("documents", {}).items():
        source = doc_info.get("source", "")
        source_path = Path(source)

        if source_path.exists():
            try:
                source_mtime = source_path.stat().st_mtime
                if source_mtime > faiss_mtime:
                    return True, f"Arquivo modificado: {source}"
            except (OSError, IOError) as e:
                logger.warning(f"Erro ao verificar mtime de {source}: {e}")

    return False, "Índice está atualizado"


def check_and_rebuild(force: bool = False) -> Dict:
    """Verifica se precisa rebuild e executa se necessário.

    Args:
        force: Se True, força rebuild mesmo se índice estiver atualizado

    Returns:
        Dict com status da operação
    """
    if force:
        logger.info("Rebuild forçado solicitado")
        return build_faiss_index(force=True, log_rebuild=True)

    if not AUTO_REBUILD_ENABLED:
        return {"status": "skipped", "reason": "Auto-rebuild desabilitado"}

    is_stale, reason = is_index_stale()

    if is_stale:
        logger.info(f"Índice obsoleto detectado: {reason}")
        return build_faiss_index(force=True, log_rebuild=True)

    return {"status": "current", "reason": reason}


def clear_index_cache():
    """Limpa cache em memória do índice FAISS."""
    global _faiss_index, _faiss_metadata
    _faiss_index = None
    _faiss_metadata = None


def load_faiss_index(auto_rebuild: bool = True):
    """Carrega índice FAISS e metadados.

    Args:
        auto_rebuild: Se True, verifica e reconstrói índice se necessário
    """
    global _faiss_index, _faiss_metadata

    # Verifica auto-rebuild antes de carregar
    if auto_rebuild and AUTO_REBUILD_ENABLED:
        is_stale, reason = is_index_stale()
        if is_stale:
            logger.info(f"Auto-rebuild ativado: {reason}")
            clear_index_cache()
            build_faiss_index(force=True, log_rebuild=True)

    if _faiss_index is not None:
        return _faiss_index, _faiss_metadata

    if FAISS_INDEX_FILE.exists() and FAISS_META_FILE.exists():
        import faiss
        _faiss_index = faiss.read_index(str(FAISS_INDEX_FILE))
        with open(FAISS_META_FILE, 'r', encoding='utf-8') as f:
            _faiss_metadata = json.load(f)
        return _faiss_index, _faiss_metadata

    return None, None


def save_faiss_index(index, metadata):
    """Salva índice FAISS e metadados com tratamento de erro.

    Garante que globais são atualizados APENAS após sucesso da escrita.
    """
    global _faiss_index, _faiss_metadata
    import faiss

    ensure_dirs()

    try:
        # Escreve arquivos com sucesso antes de atualizar cache global
        faiss.write_index(index, str(FAISS_INDEX_FILE))
        with open(FAISS_META_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False)

        # APENAS após sucesso de ambas as escritas, atualiza globais
        _faiss_index = index
        _faiss_metadata = metadata

    except (IOError, OSError, Exception) as e:
        logger.error(f"Erro ao salvar índice FAISS: {e}")
        # Garante que globais permanecem None em caso de erro
        _faiss_index = None
        _faiss_metadata = None
        raise


def build_faiss_index(force: bool = False, log_rebuild: bool = False) -> Dict:
    """Constrói índice FAISS a partir dos documentos indexados.

    Args:
        force: Se True, reconstrói mesmo se índice existir
        log_rebuild: Se True, loga informações detalhadas sobre o rebuild
    """
    import faiss

    if not force:
        index, meta = load_faiss_index(auto_rebuild=False)
        if index is not None:
            return {"status": "exists", "count": index.ntotal}

    start_time = time.time()

    if log_rebuild:
        logger.info("=" * 50)
        logger.info("INICIANDO REBUILD DO ÍNDICE FAISS")
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("Construindo índice FAISS...")
    doc_index = load_doc_index()

    if not doc_index.get("documents"):
        return {"status": "error", "message": "Nenhum documento indexado"}

    model = get_model()
    texts = []
    metadata = []

    # Prioriza markdown e limita total de documentos
    priority_types = ["markdown", "python", "yaml"]
    docs_list = sorted(
        doc_index["documents"].items(),
        key=lambda x: (0 if x[1].get("doc_type") in priority_types else 1, x[0])
    )[:MAX_DOCUMENTS]

    processed_files = 0
    skipped_files = 0

    for doc_hash, doc_info in docs_list:
        source = doc_info.get("source", "")
        source_path = Path(source)

        if not source_path.exists():
            skipped_files += 1
            continue

        try:
            content = source_path.read_text(errors='ignore')
            # Limita tamanho do documento
            if len(content) > MAX_DOC_SIZE:
                content = content[:MAX_DOC_SIZE]
            # Divide em chunks
            for i in range(0, len(content), CHUNK_SIZE):
                chunk = content[i:i+CHUNK_SIZE]
                if len(chunk.strip()) > MIN_CHUNK_LENGTH:
                    texts.append(chunk)
                    metadata.append({
                        "source": source,
                        "doc_type": doc_info.get("doc_type", "generic"),
                        "position": i
                    })
            processed_files += 1
        except Exception as e:
            print(f"  Erro em {source}: {e}")
            skipped_files += 1
            continue

    if not texts:
        return {"status": "error", "message": "Nenhum texto para indexar"}

    print(f"  Gerando embeddings para {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True)
    embeddings = embeddings.astype('float32')

    # Cria índice FAISS
    index = faiss.IndexFlatIP(EMBEDDING_DIM)  # Inner Product (cosine similarity com normalização)
    faiss.normalize_L2(embeddings)  # Normaliza para cosine similarity
    index.add(embeddings)

    # Salva estado do rebuild ANTES de save_faiss_index para garantir atomicidade
    # Se save falhar, rebuild_state não é atualizado
    current_hash = compute_documents_hash(doc_index)
    rebuild_state = {
        "documents_hash": current_hash,
        "last_rebuild": datetime.now().isoformat(),
        "chunks_count": index.ntotal,
        "documents_processed": processed_files,
        "documents_skipped": skipped_files
    }

    # Salva índice (se falhar, rebuild_state não é salvo)
    save_faiss_index(index, {"texts": texts, "meta": metadata})

    # Salva rebuild_state APÓS sucesso do save_faiss_index
    save_rebuild_state(rebuild_state)

    # Invalida cache de queries após rebuild
    invalidate_query_cache()

    elapsed_time = time.time() - start_time

    if log_rebuild:
        logger.info(f"Documentos processados: {processed_files}")
        logger.info(f"Documentos ignorados: {skipped_files}")
        logger.info(f"Chunks gerados: {index.ntotal}")
        logger.info(f"Tempo de rebuild: {elapsed_time:.2f}s")
        logger.info(f"Hash dos documentos: {current_hash}")
        logger.info("REBUILD CONCLUÍDO COM SUCESSO")
        logger.info("=" * 50)

    print(f"  Índice FAISS criado com {index.ntotal} vetores")
    return {
        "status": "created" if not force else "rebuilt",
        "count": index.ntotal,
        "elapsed_seconds": round(elapsed_time, 2),
        "documents_processed": processed_files
    }


def semantic_search(query: str, doc_type: str = None, limit: int = TOP_K, auto_rebuild: bool = True) -> List[Dict]:
    """Busca semantica usando FAISS com cache persistente (Redis/diskcache).

    Args:
        query: Termo de busca
        doc_type: Filtrar por tipo de documento (markdown, python, etc)
        limit: Numero maximo de resultados (default: TOP_K=5)
        auto_rebuild: Se True, verifica e reconstroi indice se necessario

    Returns:
        Lista de dicts com keys: score, text, source, doc_type

    Performance:
        - Cache hit: ~1ms (Redis) ou ~5ms (diskcache)
        - Cache miss: ~200-500ms (embedding + FAISS search)
    """
    import faiss

    # Check persistent cache (Redis > diskcache > JSON)
    cache_key = f"{query}:{doc_type}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit para: {cache_key[:50]}...")
        return cached

    index, metadata = load_faiss_index(auto_rebuild=auto_rebuild)
    if index is None:
        # Tenta construir
        result = build_faiss_index(log_rebuild=True)
        if result["status"] == "error":
            return []
        index, metadata = load_faiss_index(auto_rebuild=False)

    model = get_model()
    query_embedding = model.encode([query]).astype('float32')
    faiss.normalize_L2(query_embedding)

    # Busca mais resultados se filtrar por tipo
    search_k = limit * 3 if doc_type else limit

    distances, indices = index.search(query_embedding, min(search_k, index.ntotal))

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0:
            continue

        meta = metadata["meta"][idx]
        if doc_type and meta["doc_type"] != doc_type:
            continue

        results.append({
            "chunk_id": f"{idx}",
            "score": float(dist),  # Ja e similaridade (inner product normalizado)
            "text": metadata["texts"][idx],
            "source": meta["source"],
            "doc_type": meta["doc_type"]
        })

        if len(results) >= limit:
            break

    # Save to persistent cache (Redis > diskcache > JSON)
    cache_set(cache_key, results)

    return results


def get_context_for_query(query: str, max_tokens: int = 2000) -> str:
    """Retorna contexto formatado para o Claude baseado na query"""
    results = semantic_search(query, limit=5)

    if not results:
        return "Nenhum contexto relevante encontrado na memória."

    output = ["## Contexto Relevante da Memória\n"]
    token_estimate = 0

    for r in results:
        chunk_text = f"\n### Fonte: {r['source']}\n{r['text']}\n"
        chunk_tokens = len(chunk_text) // 4

        if token_estimate + chunk_tokens > max_tokens:
            break

        output.append(chunk_text)
        token_estimate += chunk_tokens

    return "\n".join(output)


def get_stats() -> Dict:
    """Retorna estatisticas do indice FAISS e cache."""
    index, metadata = load_faiss_index(auto_rebuild=False)
    doc_index = load_doc_index()
    rebuild_state = load_rebuild_state()

    if index is None:
        return {
            "documents": len(doc_index.get("documents", {})),
            "chunks": 0,
            "faiss_status": "nao construido",
            "cache": cache_stats(),
        }

    sources = set(m["source"] for m in metadata["meta"])
    doc_types = set(m["doc_type"] for m in metadata["meta"])

    # Verifica se indice esta obsoleto
    is_stale, stale_reason = is_index_stale()

    return {
        "documents": len(doc_index.get("documents", {})),
        "chunks": index.ntotal,
        "sources": list(sources)[:10],
        "doc_types": list(doc_types),
        "faiss_status": "ativo",
        "last_rebuild": rebuild_state.get("last_rebuild", "desconhecido"),
        "is_stale": is_stale,
        "stale_reason": stale_reason if is_stale else None,
        "auto_rebuild_enabled": AUTO_REBUILD_ENABLED,
        "cache": cache_stats(),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: faiss_rag.py <comando> [args]")
        print("\nComandos:")
        print("  build              - Constroi indice FAISS (se nao existir)")
        print("  rebuild            - Reconstroi indice FAISS (forca rebuild)")
        print("  check              - Verifica se indice esta obsoleto")
        print("  auto-rebuild       - Verifica e reconstroi se necessario")
        print("  search <query>     - Busca semantica")
        print("  context <query>    - Retorna contexto formatado")
        print("  stats              - Mostra estatisticas")
        print("  cache-stats        - Mostra estatisticas do cache")
        print("  cache-clear        - Limpa o cache de queries")
        print("  benchmark <query>  - Testa performance do cache")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "build":
        result = build_faiss_index()
        print(f"Resultado: {result}")

    elif cmd == "rebuild":
        result = build_faiss_index(force=True, log_rebuild=True)
        print(f"Resultado: {result}")

    elif cmd == "check":
        is_stale, reason = is_index_stale()
        if is_stale:
            print(f"Índice OBSOLETO: {reason}")
        else:
            print(f"Índice ATUALIZADO: {reason}")

        # Mostra informações adicionais
        rebuild_state = load_rebuild_state()
        if rebuild_state:
            print(f"\nÚltimo rebuild: {rebuild_state.get('last_rebuild', 'N/A')}")
            print(f"Chunks: {rebuild_state.get('chunks_count', 'N/A')}")
            print(f"Docs processados: {rebuild_state.get('documents_processed', 'N/A')}")

    elif cmd == "auto-rebuild":
        result = check_and_rebuild()
        print(f"Resultado: {result}")

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Uso: search <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        results = semantic_search(query)
        print(f"\nResultados para: '{query}'\n")
        for r in results:
            print(f"[{r['score']:.3f}] {r['source']}")
            print(f"  {r['text'][:150]}...\n")

    elif cmd == "context":
        if len(sys.argv) < 3:
            print("Uso: context <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        context = get_context_for_query(query)
        print(context)

    elif cmd == "stats":
        stats = get_stats()
        print("\nEstatisticas FAISS RAG:")
        for k, v in stats.items():
            if k == "cache":
                print(f"  {k}:")
                for ck, cv in v.items():
                    print(f"    {ck}: {cv}")
            else:
                print(f"  {k}: {v}")

    elif cmd == "cache-stats":
        stats = cache_stats()
        print("\nEstatisticas do Cache:")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif cmd == "cache-clear":
        cache_clear()
        print("Cache limpo com sucesso!")

    elif cmd == "benchmark":
        if len(sys.argv) < 3:
            print("Uso: benchmark <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])

        # Limpa cache primeiro
        cache_clear()

        # Primeira busca (cold cache)
        start = time.time()
        results1 = semantic_search(query)
        cold_time = (time.time() - start) * 1000

        # Segunda busca (warm cache)
        start = time.time()
        results2 = semantic_search(query)
        warm_time = (time.time() - start) * 1000

        # Terceira busca (confirma cache)
        start = time.time()
        results3 = semantic_search(query)
        warm_time2 = (time.time() - start) * 1000

        print(f"\nBenchmark para: '{query}'")
        print(f"  Resultados: {len(results1)}")
        print(f"\n  Cold cache (sem cache): {cold_time:.2f}ms")
        print(f"  Warm cache (com cache): {warm_time:.2f}ms")
        print(f"  Warm cache 2:           {warm_time2:.2f}ms")
        print(f"\n  Speedup: {cold_time/warm_time:.1f}x")
        print(f"  Reducao latencia: {((cold_time-warm_time)/cold_time)*100:.1f}%")

        stats = cache_stats()
        print(f"\n  Cache backend: {stats.get('backend', 'unknown')}")

    else:
        print(f"Comando desconhecido: {cmd}")
        sys.exit(1)
