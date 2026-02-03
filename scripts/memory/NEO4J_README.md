# Neo4j Wrapper - Documentação Completa

Wrapper para integração com Neo4j Graph Database no Claude Brain.

## Índice

1. [Instalação](#instalação)
2. [Uso Básico](#uso-básico)
3. [API Completa](#api-completa)
4. [Queries Otimizadas](#queries-otimizadas)
5. [Sincronização SQLite](#sincronização-sqlite)
6. [Error Handling](#error-handling)
7. [Testes](#testes)
8. [Exemplos](#exemplos)

---

## Instalação

### Dependências

```bash
# Neo4j Python driver (versão 5.15.0)
pip install neo4j==5.15.0

# Para testes
pip install pytest pytest-mock
```

### Neo4j Server

Certifique-se de ter Neo4j rodando:

```bash
# Docker
docker run -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# Local
brew install neo4j
neo4j start
```

---

## Uso Básico

### Inicializar e Conectar

```python
from neo4j_wrapper import Neo4jGraph

# Criar instância
graph = Neo4jGraph(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

# Conectar
graph.connect()

# Fazer operações...

# Fechar
graph.close()
```

### Context Manager (Recomendado)

```python
from contextlib import contextmanager

@contextmanager
def get_graph():
    graph = Neo4jGraph(uri="...", user="...", password="...")
    graph.connect()
    try:
        yield graph
    finally:
        graph.close()

# Usar
with get_graph() as graph:
    graph.add_node("Decision", "dec_001", {"title": "Use Redis"})
```

---

## API Completa

### Lifecycle

#### `connect() -> None`

Estabelece conexão com servidor Neo4j.

```python
graph = Neo4jGraph(uri="bolt://localhost:7687", user="neo4j", password="pw")
graph.connect()  # Levanta Neo4jConnectionError se falhar
```

Erros possíveis:
- `AuthError`: Credenciais inválidas
- `ServiceUnavailable`: Neo4j não está rodando
- `Neo4jConnectionError`: Erro genérico de conexão

---

#### `close() -> None`

Fecha conexão. Seguro chamar múltiplas vezes.

```python
graph.close()  # OK chamar mesmo se não conectado
```

---

### Operações CRUD

#### `add_node(node_type, node_id, properties) -> Dict`

Cria ou atualiza um nó.

```python
node = graph.add_node(
    node_type="Decision",
    node_id="dec_001",
    properties={
        "title": "Use Redis for caching",
        "confidence": 0.9,
        "created_by": "claude"
    }
)

# Retorna: {"id": "dec_001", "title": "...", "created_at": "...", ...}
```

Parâmetros:
- `node_type` (str): Label do nó (Decision, Learning, Error, etc)
- `node_id` (str): ID único
- `properties` (dict, opcional): Propriedades adicionais

Erros:
- `ValueError`: Se node_type ou node_id vazios
- `Neo4jQueryError`: Se query falhar

---

#### `add_edge(from_id, to_id, relation, weight) -> Dict`

Cria ou atualiza uma aresta entre dois nós.

```python
edge = graph.add_edge(
    from_id="dec_001",
    to_id="concept_redis",
    relation="uses",
    weight=0.95
)

# Retorna: {"weight": 0.95, "updated_at": "...", ...}
```

Parâmetros:
- `from_id` (str): ID do nó de origem
- `to_id` (str): ID do nó de destino
- `relation` (str): Tipo da relação (uses, resolves, depends_on, etc)
- `weight` (float): Peso 0.0-1.0 (default: 1.0)

Erros:
- `ValueError`: Se parâmetros vazios ou weight fora de intervalo
- `Neo4jQueryError`: Se query falhar

---

#### `get_node(node_id) -> Optional[Dict]`

Recupera um nó específico.

```python
node = graph.get_node("dec_001")
# {"id": "dec_001", "title": "...", ...}

node = graph.get_node("nonexistent")
# None
```

---

#### `delete_node(node_id) -> int`

Deleta um nó e todas suas arestas.

```python
deleted_count = graph.delete_node("dec_001")
# 0 ou 1
```

---

### Queries Otimizadas

#### `traverse(start_id, relation, depth) -> List[Dict]`

Faz traversal no grafo a partir de um nó inicial.

```python
# Buscar todos os nós relacionados
results = graph.traverse(
    start_id="dec_001",
    relation="uses",  # Optional: filtrar por tipo
    depth=2           # Profundidade máxima
)

# Retorna lista de dicts, ordenada por distância
# [
#   {"id": "concept_1", "distance": 1},
#   {"id": "concept_2", "distance": 2},
# ]
```

Parâmetros:
- `start_id` (str): ID do nó inicial
- `relation` (str, opcional): Filtrar por tipo de relação
- `depth` (int): 1-5, profundidade máxima

---

#### `shortest_path(source_id, target_id) -> Optional[Tuple]`

Encontra o caminho mais curto entre dois nós.

```python
result = graph.shortest_path("dec_001", "concept_redis")

if result:
    path, distance = result
    # path = ["dec_001", "node_2", "concept_redis"]
    # distance = 2
else:
    # Nenhum caminho encontrado
    pass
```

---

#### `pagerank(top_k) -> List[Tuple]`

Calcula PageRank dos nós (requer GDS plugin).

```python
rankings = graph.pagerank(top_k=10)
# [
#   ("dec_001", 0.95),
#   ("dec_002", 0.80),
#   ...
# ]
```

**Nota**: Requer Neo4j com Graph Data Science plugin instalado.

---

### Sincronização

#### `sync_from_sqlite(db_path, clear_existing) -> Dict`

Sincroniza dados de SQLite para Neo4j.

```python
stats = graph.sync_from_sqlite(
    db_path="/root/claude-brain/memory/brain.db",
    clear_existing=False
)

# Retorna: {
#   "nodes_created": 42,
#   "edges_created": 15,
#   "errors": 0
# }
```

Processa:
- Tabela `decisions` → Nodes com label "Decision"
- Tabela `learnings` → Nodes com label "Learning"
- Cria arestas automáticas

---

### Utilidades

#### `health_check() -> bool`

Verifica se conexão está viva.

```python
if graph.health_check():
    print("Conectado!")
else:
    print("Conexão perdida")
```

---

#### `get_stats() -> Dict`

Recupera estatísticas do grafo.

```python
stats = graph.get_stats()
# {
#   "node_count": 50,
#   "edge_count": 120,
#   "node_types": {
#     "Decision": 25,
#     "Learning": 15,
#     "Error": 10
#   }
# }
```

---

## Error Handling

### Hierarquia de Exceções

```
Exception
└── Neo4jWrapperError (base customizada)
    ├── Neo4jConnectionError
    ├── Neo4jQueryError
    └── Neo4jSyncError
```

### Tratamento Recomendado

```python
from neo4j_wrapper import (
    Neo4jGraph,
    Neo4jConnectionError,
    Neo4jQueryError,
    Neo4jSyncError,
)

try:
    graph = Neo4jGraph(uri="bolt://localhost:7687", user="neo4j", password="pw")
    graph.connect()

except Neo4jConnectionError as e:
    print(f"Erro de conexão: {e}")
    # Implementar fallback ou retry

except Neo4jQueryError as e:
    print(f"Erro na query: {e}")
    # Log e usar cache se disponível

except Neo4jSyncError as e:
    print(f"Erro na sincronização: {e}")
    # Tentar novamente depois

finally:
    graph.close()
```

---

## Testes

### Rodar Suite Completa

```bash
pytest test_neo4j_wrapper.py -v
```

### Rodar Teste Específico

```bash
pytest test_neo4j_wrapper.py::TestCRUDOperations::test_add_node_success -v
```

### Com Coverage

```bash
pip install pytest-cov
pytest test_neo4j_wrapper.py --cov=neo4j_wrapper --cov-report=html
```

### Testes Inline

```python
# No módulo existem testes que podem ser rodados diretamente:
python -c "from neo4j_wrapper import _test_neo4j_wrapper; _test_neo4j_wrapper()"
```

---

## Exemplos

### Exemplo 1: Criar Grafo de Decisões

```python
from neo4j_wrapper import Neo4jGraph

graph = Neo4jGraph(uri="bolt://localhost:7687", user="neo4j", password="pw")
graph.connect()

# Criar decisões
dec1 = graph.add_node("Decision", "dec_001", {
    "title": "Use Redis for caching",
    "confidence": 0.9
})

dec2 = graph.add_node("Decision", "dec_002", {
    "title": "Implement async tasks",
    "confidence": 0.8
})

# Criar conceitos
concept1 = graph.add_node("Concept", "concept_redis", {
    "description": "In-memory data store"
})

# Conectar
graph.add_edge("dec_001", "concept_redis", "uses", weight=0.95)
graph.add_edge("dec_001", "dec_002", "depends_on", weight=0.7)

graph.close()
```

---

### Exemplo 2: Buscar Relações

```python
# Encontrar todas as decisões que usam Redis
results = graph.traverse("concept_redis", relation="uses", depth=2)
print(f"Encontradas {len(results)} decisões relacionadas")

# Caminho mais curto
path, distance = graph.shortest_path("dec_001", "dec_099")
if path:
    print(f"Caminho: {' → '.join(path)} (distância: {distance})")
```

---

### Exemplo 3: Sincronizar SQLite

```python
# Inicializar grafo
graph = Neo4jGraph(uri="bolt://localhost:7687", user="neo4j", password="pw")
graph.connect()

# Sincronizar banco de decisões
stats = graph.sync_from_sqlite(
    db_path="/root/claude-brain/memory/brain.db",
    clear_existing=False
)

print(f"Criados: {stats['nodes_created']} nós")
print(f"Erros: {stats['errors']}")

# Ver estatísticas
graph_stats = graph.get_stats()
print(f"Grafo tem {graph_stats['node_count']} nós totais")

graph.close()
```

---

### Exemplo 4: Error Handling

```python
from neo4j_wrapper import (
    Neo4jGraph,
    Neo4jConnectionError,
    Neo4jQueryError,
)

def safe_query(graph, query_func, *args, **kwargs):
    """Wrapper para queries com retry"""
    retries = 3
    for attempt in range(retries):
        try:
            return query_func(*args, **kwargs)
        except Neo4jConnectionError:
            if attempt < retries - 1:
                print(f"Tentativa {attempt + 1} falhou, retry...")
                graph.close()
                graph.connect()
            else:
                raise
        except Neo4jQueryError as e:
            print(f"Query error: {e}")
            raise

graph = Neo4jGraph(uri="bolt://localhost:7687", user="neo4j", password="pw")
graph.connect()

try:
    result = safe_query(graph, graph.get_node, "dec_001")
    print(f"Nó: {result}")
except Neo4jConnectionError:
    print("Neo4j indisponível após 3 tentativas")
finally:
    graph.close()
```

---

## Performance

### Recomendações

1. **Connection Pooling**: Driver Neo4j já faz isso automaticamente
2. **Batch Operations**: Use múltiplas queries em uma transação
3. **Indexes**: Crie índices para campos frequentemente consultados
4. **Depth Limit**: Mantenha `depth` entre 1-3 para queries rápidas

### Benchmark

Com Neo4j local (31GB RAM):
- `add_node`: ~1-5ms
- `add_edge`: ~1-5ms
- `traverse(depth=2)`: ~10-50ms (depende do tamanho do grafo)
- `pagerank(top_k=10)`: ~100-500ms (com GDS)

---

## Logging

O módulo usa `logging` padrão Python:

```python
import logging

# Ver logs detalhados
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('neo4j_wrapper')
logger.setLevel(logging.DEBUG)

graph = Neo4jGraph(...)
graph.connect()  # Mostrará logs de conexão
```

---

## Troubleshooting

### Erro: "Neo4j indisponível"

```python
# Verificar se Neo4j está rodando
graph = Neo4jGraph(...)
if not graph.health_check():
    print("Neo4j não está respondendo")
    # Iniciar Neo4j
    # docker run neo4j:latest
```

### Erro: "Credenciais inválidas"

```python
# Verificar credenciais padrão
# user: neo4j
# password: (definido no inicio, padrão "password")

# Resetar senha:
# docker exec <container> cypher-shell -u neo4j -p password
# CALL dbms.security.changePassword("newpassword")
```

### Erro: "GDS não disponível"

```python
# PageRank requer Graph Data Science plugin
# Ver: https://neo4j.com/docs/graph-data-science/current/installation/

# Se não tiver GDS, usar só traversal e shortest_path
```

---

## Próximos Passos

- Integrar com Brain Job Queue
- Adicionar batch operations
- Implementar cache distribuído
- Suporte a multi-tenancy

---

## Referências

- [Neo4j Python Driver](https://neo4j.com/docs/api/python-driver/current/)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/current/)
- [GDS Documentation](https://neo4j.com/docs/graph-data-science/current/)
