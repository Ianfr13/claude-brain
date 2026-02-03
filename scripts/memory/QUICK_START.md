# Neo4j Wrapper - Quick Start

Guia rápido para começar a usar o Neo4j Wrapper.

## Instalação (30 segundos)

```bash
# 1. Instalar dependência
pip install neo4j==5.15.0

# 2. Iniciar Neo4j (Docker)
docker run -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# 3. Verificar
curl http://localhost:7474
```

## Hello World (1 minuto)

```python
from neo4j_wrapper import Neo4jGraph

# Conectar
graph = Neo4jGraph(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)
graph.connect()

# Criar nó
graph.add_node("Decision", "dec_001", {"title": "Use Redis"})

# Criar aresta
graph.add_node("Concept", "redis", {"description": "Cache store"})
graph.add_edge("dec_001", "redis", "uses", weight=0.95)

# Buscar
node = graph.get_node("dec_001")
print(node)

# Fechar
graph.close()
```

## Operações Comuns

### Criar Nó

```python
graph.add_node(
    node_type="Decision",           # ou Learning, Error, Concept, etc
    node_id="dec_001",              # ID único
    properties={"title": "Use Redis", "confidence": 0.9}
)
```

### Criar Relação

```python
graph.add_edge(
    from_id="dec_001",
    to_id="redis",
    relation="uses",                # ou resolves, depends_on, etc
    weight=0.95                     # 0.0-1.0
)
```

### Buscar Nó

```python
node = graph.get_node("dec_001")
if node:
    print(node["title"])
```

### Traversal (Busca em Profundidade)

```python
# Todos os conceitos usados por dec_001
results = graph.traverse("dec_001", relation="uses", depth=2)
for node in results:
    print(node["id"])
```

### Caminho Mais Curto

```python
path, distance = graph.shortest_path("dec_001", "redis")
if path:
    print(f"Caminho: {' → '.join(path)}")
    print(f"Distância: {distance}")
```

### Sincronizar SQLite

```python
stats = graph.sync_from_sqlite("/root/claude-brain/memory/brain.db")
print(f"Criados: {stats['nodes_created']} nós")
print(f"Erros: {stats['errors']}")
```

### Estatísticas

```python
stats = graph.get_stats()
print(f"Nós: {stats['node_count']}")
print(f"Arestas: {stats['edge_count']}")
print(f"Por tipo: {stats['node_types']}")
```

## Error Handling

```python
from neo4j_wrapper import (
    Neo4jGraph,
    Neo4jConnectionError,
    Neo4jQueryError,
)

try:
    graph = Neo4jGraph(uri="...", user="...", password="...")
    graph.connect()
    # Operações...
except Neo4jConnectionError as e:
    print(f"Erro de conexão: {e}")
except Neo4jQueryError as e:
    print(f"Erro na query: {e}")
finally:
    graph.close()
```

## Context Manager (Recomendado)

```python
from contextlib import contextmanager

@contextmanager
def get_graph():
    graph = Neo4jGraph(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password"
    )
    graph.connect()
    try:
        yield graph
    finally:
        graph.close()

# Usar
with get_graph() as graph:
    graph.add_node("Decision", "dec_001", {"title": "Use Redis"})
    # Conexão fechada automaticamente
```

## Testes

```bash
# Rodar todos os testes
pytest scripts/memory/test_neo4j_wrapper.py -v

# Teste específico
pytest scripts/memory/test_neo4j_wrapper.py::TestCRUDOperations::test_add_node_success -v

# Com coverage
pytest scripts/memory/test_neo4j_wrapper.py --cov=neo4j_wrapper
```

## Logging

```python
import logging

# Ativar logs detalhados
logging.basicConfig(level=logging.DEBUG)

graph = Neo4jGraph(...)
graph.connect()  # Mostra logs de conexão
```

## Troubleshooting

| Problema | Solução |
|----------|---------|
| "Neo4j indisponível" | `docker run neo4j:latest` |
| "Credenciais inválidas" | Verificar user/password padrão |
| "GDS não disponível" | Instalar Graph Data Science plugin |
| "Connection timeout" | Aumentar timeout: `Neo4jGraph(..., timeout=60)` |

## Próximo Passo

Ler documentação completa em `NEO4J_README.md` (600+ linhas).

---

**Status**: ✅ Pronto para produção
**Versão**: 1.0.0
**Última atualização**: 2026-02-03
