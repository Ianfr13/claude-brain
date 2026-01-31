#!/usr/bin/env python3
"""
Pytest Fixtures para Claude Brain Tests

Este arquivo contém fixtures compartilhadas para testes do Claude Brain:
- temp_db: Banco SQLite isolado em diretório temporário
- mock_faiss_index: Mock do índice FAISS para testes sem dependência de ML
- sample_documents: Documentos de teste pré-definidos
- mock_embedding_server: Mock do servidor de embeddings
- brain_cli_runner: Runner para testar comandos CLI

Fixtures auxiliares também incluídas:
- cli_args: Factory para argumentos CLI
- sample_memories/entities/preferences: Dados de teste
- mock_rag_engine/mock_metrics: Mocks para módulos externos
"""

import sys
import json
import tempfile
from pathlib import Path
from typing import Generator, Dict, List, Any
from unittest.mock import Mock, MagicMock, patch
from io import StringIO

import pytest

# Adiciona scripts ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


# ============================================================================
# FIXTURE 1: temp_db - Banco de dados SQLite isolado
# ============================================================================

@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch) -> Generator[Path, None, None]:
    """
    Cria um banco de dados SQLite isolado em diretório temporário.

    Esta fixture é essencial para testes que envolvem o memory_store,
    garantindo isolamento completo entre testes e evitando poluição
    do banco de dados de produção.

    Funcionamento:
    - Cria um novo banco SQLite vazio em tmp_path
    - Aplica patch no DB_PATH do módulo memory_store
    - Inicializa o schema completo do banco (todas as tabelas)
    - Limpa automaticamente após o teste via tmp_path

    Tabelas criadas:
    - memories: Memórias gerais com embeddings
    - decisions: Decisões arquiteturais
    - learnings: Aprendizados de erros
    - entities: Entidades do knowledge graph
    - relations: Relações entre entidades
    - sessions: Contexto de sessões
    - preferences: Preferências do usuário
    - patterns: Padrões de código

    Exemplo de uso:
        def test_salvar_memoria(temp_db):
            from memory_store import save_memory, search_memories

            # temp_db já está configurado como banco padrão
            mem_id = save_memory("test", "conteudo de teste")
            assert mem_id > 0

            results = search_memories(query="teste")
            assert len(results) >= 1

        def test_decisao_com_maturidade(temp_db):
            from memory_store import save_decision, confirm_knowledge

            dec_id = save_decision("Usar FastAPI", reasoning="Performance")
            new_score = confirm_knowledge("decisions", dec_id)
            assert new_score > 0.5

    Args:
        tmp_path: Fixture built-in do pytest para diretórios temporários
        monkeypatch: Fixture built-in para patching de módulos

    Yields:
        Path: Caminho absoluto para o arquivo do banco de dados temporário

    Notes:
        - O banco é criado em memória compartilhada, não em :memory:
        - Cada teste recebe um banco completamente novo
        - Não é necessário cleanup manual - tmp_path faz isso
    """
    # Cria diretório para o banco (simula estrutura real)
    db_dir = tmp_path / "memory"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "brain.db"

    # Patch no módulo memory_store ANTES de usar
    import memory_store
    monkeypatch.setattr(memory_store, "DB_PATH", db_path)

    # Inicializa o banco com schema completo
    memory_store.init_db()

    yield db_path

    # Cleanup é automático via tmp_path fixture


# ============================================================================
# FIXTURE 2: mock_faiss_index - Mock do índice FAISS
# ============================================================================

@pytest.fixture
def mock_faiss_index() -> Generator[Dict[str, Any], None, None]:
    """
    Mock do índice FAISS para testes sem dependência de ML/embeddings.

    Esta fixture permite testar funcionalidades de busca semântica sem
    carregar modelos de ML pesados (como sentence-transformers), tornando
    os testes muito mais rápidos e determinísticos.

    Componentes mockados:
    - faiss.IndexFlatIP: Índice de busca por inner product
    - SentenceTransformer: Modelo de embeddings
    - Funções load_faiss_index e get_model do faiss_rag

    Estrutura do mock:
    - index: MagicMock do índice FAISS com ntotal e search()
    - metadata: Dict com 'texts' e 'meta' simulando dados reais
    - search_results: Lista configurável de resultados de busca
    - embeddings: Vetores de embedding mockados (384 dimensões)

    Exemplo de uso:
        def test_busca_semantica(mock_faiss_index):
            # Configura resultados personalizados
            mock_faiss_index['search_results'] = [
                {'score': 0.95, 'text': 'Python é ótimo', 'source': 'doc.md'}
            ]

            from faiss_rag import semantic_search
            results = semantic_search("python")
            assert len(results) >= 1
            assert results[0]['score'] > 0.9

        def test_busca_por_tipo(mock_faiss_index):
            # Mock já tem documentos de tipos diferentes
            from faiss_rag import semantic_search
            results = semantic_search("config", doc_type="markdown")
            assert all(r['doc_type'] == 'markdown' for r in results)

    Yields:
        Dict[str, Any]: Dicionário com componentes do mock:
            - index: Mock do índice FAISS
            - metadata: Metadados simulados
            - search_results: Lista de resultados (modificável)
            - embeddings: Embeddings mockados

    Notes:
        - Dimensão dos embeddings: 384 (all-MiniLM-L6-v2)
        - Scores simulados variam de 0.55 a 0.85
        - Tipos de documentos: markdown, python
    """
    # Estrutura do mock com dados realistas
    mock_data = {
        'index': MagicMock(),
        'metadata': {
            'texts': [
                'Documento de teste sobre Python e programação',
                'Configuração de ambiente virtual com venv',
                'Troubleshooting de erros comuns em projetos'
            ],
            'meta': [
                {'source': '/test/doc1.md', 'doc_type': 'markdown', 'position': 0},
                {'source': '/test/doc2.py', 'doc_type': 'python', 'position': 0},
                {'source': '/test/doc3.md', 'doc_type': 'markdown', 'position': 0}
            ]
        },
        'search_results': [
            {
                'chunk_id': '0',
                'score': 0.85,
                'text': 'Documento de teste sobre Python e programação',
                'source': '/test/doc1.md',
                'doc_type': 'markdown'
            }
        ],
        'embeddings': [[0.1] * 384]  # Dimensão do all-MiniLM-L6-v2
    }

    # Configura comportamento do mock do índice
    mock_data['index'].ntotal = len(mock_data['metadata']['texts'])
    mock_data['index'].search.return_value = (
        [[0.85, 0.70, 0.55]],  # distances (scores de similaridade)
        [[0, 1, 2]]            # indices dos documentos
    )

    # Aplica patches no módulo faiss_rag
    with patch('faiss_rag.load_faiss_index') as mock_load, \
         patch('faiss_rag.get_model') as mock_model:

        mock_load.return_value = (mock_data['index'], mock_data['metadata'])

        # Mock do modelo de embeddings
        mock_encoder = MagicMock()
        mock_encoder.encode.return_value = [[0.1] * 384]
        mock_model.return_value = mock_encoder

        yield mock_data


# ============================================================================
# FIXTURE 3: sample_documents - Documentos de teste
# ============================================================================

@pytest.fixture
def sample_documents(tmp_path: Path) -> Generator[Dict[str, Any], None, None]:
    """
    Cria documentos de teste em diretório temporário para indexação.

    Esta fixture fornece arquivos reais em disco que podem ser usados
    para testar funcionalidades de indexação, parsing e busca do RAG.
    Os documentos simulam a estrutura real de um projeto.

    Arquivos criados:
    - README.md: Documentação markdown com seções típicas
    - example.py: Código Python com classes e funções
    - config.yaml: Arquivo de configuração YAML
    - data.json: Dados estruturados em JSON

    Exemplo de uso:
        def test_indexar_markdown(sample_documents):
            from rag_engine import index_file

            md_file = sample_documents['files']['markdown']
            result = index_file(str(md_file))

            assert result is not None
            assert result.get('chunk_count', 0) > 0

        def test_indexar_diretorio(sample_documents):
            from rag_engine import index_directory

            doc_dir = sample_documents['dir']
            count = index_directory(str(doc_dir))

            assert count >= 4  # 4 arquivos criados

        def test_conteudo_documentos(sample_documents):
            # Acessa conteúdo diretamente para assertions
            md_content = sample_documents['contents']['markdown']
            assert 'Troubleshooting' in md_content
            assert 'ModuleNotFoundError' in md_content

    Yields:
        Dict[str, Any]: Dicionário com:
            - dir: Path do diretório contendo os documentos
            - files: Dict[str, Path] mapeando tipo -> caminho do arquivo
            - contents: Dict[str, str] mapeando tipo -> conteúdo textual

    Notes:
        - Arquivos são criados com encoding UTF-8
        - Conteúdo inclui termos comuns para testes de busca
        - Estrutura simula documentação real de projeto
    """
    # Cria diretório de documentos
    docs_dir = tmp_path / "test_docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Conteúdos de exemplo representativos
    contents = {
        'markdown': """# Documentação de Teste

## Introdução
Este é um documento de teste para o Claude Brain.
O sistema oferece memória persistente e busca semântica.

## Configuração
Para configurar o ambiente:
1. Instale as dependências com `pip install -r requirements.txt`
2. Configure o banco de dados SQLite
3. Execute os testes com `pytest`

## Troubleshooting
Se encontrar erros de ModuleNotFoundError, ative o venv primeiro:
```bash
source .venv/bin/activate
```

## API Reference
O sistema expõe comandos via CLI:
- `brain remember`: Salva memórias
- `brain search`: Busca semântica
- `brain decide`: Registra decisões
""",
        'python': '''#!/usr/bin/env python3
"""Módulo de teste para Claude Brain

Este módulo demonstra padrões de código Python
usados no projeto Claude Brain.
"""

from typing import Optional, List

def hello_world() -> str:
    """Função de exemplo que retorna saudação.

    Returns:
        str: Mensagem de saudação
    """
    return "Hello, World!"


class TestClass:
    """Classe de teste para demonstrar estrutura.

    Attributes:
        value: Valor inteiro armazenado
    """

    def __init__(self, value: int):
        """Inicializa a classe com um valor.

        Args:
            value: Valor inicial
        """
        self.value = value

    def process(self) -> str:
        """Processa o valor e retorna string formatada.

        Returns:
            str: Valor processado
        """
        return f"Processed: {self.value}"

    def search(self, query: str) -> List[str]:
        """Busca items relacionados à query.

        Args:
            query: Termo de busca

        Returns:
            List[str]: Resultados encontrados
        """
        return [f"Result for {query}"]


if __name__ == "__main__":
    print(hello_world())
''',
        'yaml': """# Configuração de teste para Claude Brain
# Este arquivo demonstra estrutura YAML típica

project:
  name: claude-brain-test
  version: 1.0.0
  description: Sistema de memória persistente

database:
  path: /tmp/test.db
  type: sqlite
  pool_size: 5

features:
  - rag_search
  - memory_store
  - knowledge_graph
  - embeddings

logging:
  level: INFO
  format: "%(asctime)s - %(levelname)s - %(message)s"

api:
  host: localhost
  port: 8000
  debug: true
""",
        'json': """{
    "name": "test-document",
    "type": "config",
    "version": "1.0.0",
    "settings": {
        "debug": true,
        "max_tokens": 2000,
        "embedding_dim": 384
    },
    "features": [
        "semantic_search",
        "memory_persistence",
        "knowledge_graph"
    ],
    "metadata": {
        "created_at": "2024-01-01T00:00:00Z",
        "author": "test"
    }
}
"""
    }

    # Cria arquivos físicos
    files = {}

    files['markdown'] = docs_dir / "README.md"
    files['markdown'].write_text(contents['markdown'], encoding='utf-8')

    files['python'] = docs_dir / "example.py"
    files['python'].write_text(contents['python'], encoding='utf-8')

    files['yaml'] = docs_dir / "config.yaml"
    files['yaml'].write_text(contents['yaml'], encoding='utf-8')

    files['json'] = docs_dir / "data.json"
    files['json'].write_text(contents['json'], encoding='utf-8')

    yield {
        'dir': docs_dir,
        'files': files,
        'contents': contents
    }


# ============================================================================
# FIXTURE 4: mock_embedding_server - Mock do servidor de embeddings
# ============================================================================

@pytest.fixture
def mock_embedding_server() -> Generator[Mock, None, None]:
    """
    Mock do servidor de embeddings para testes sem servidor real rodando.

    O embedding_server.py fornece um servidor Unix socket que mantém o
    modelo de embeddings em memória para respostas rápidas. Esta fixture
    permite testar código que depende do servidor sem precisar iniciá-lo.

    Comportamentos mockados:
    - is_server_running(): Retorna mock_server.is_running
    - get_embeddings_fast(): Retorna mock_server.embeddings
    - health_check(): Retorna mock_server.health_status

    Atributos configuráveis:
    - embeddings: Lista de vetores de embedding (384 dims cada)
    - is_running: bool indicando se servidor está "ativo"
    - health_status: dict com detalhes de saúde do servidor

    Exemplo de uso:
        def test_gerar_embedding(mock_embedding_server):
            # Usa configuração padrão
            from embedding_server import get_embeddings_fast

            result = get_embeddings_fast(["texto de teste"])
            assert len(result) == 1
            assert len(result[0]) == 384

        def test_servidor_offline(mock_embedding_server):
            # Simula servidor offline
            mock_embedding_server.is_running = False
            mock_embedding_server.health_status['healthy'] = False
            mock_embedding_server.health_status['error'] = 'Socket não existe'

            from embedding_server import is_server_running, health_check
            assert not is_server_running()
            assert not health_check()['healthy']

        def test_embeddings_customizados(mock_embedding_server):
            # Configura embeddings específicos para o teste
            custom_embedding = [0.5] * 384
            mock_embedding_server.embeddings = [custom_embedding]

            from embedding_server import get_embeddings_fast
            result = get_embeddings_fast(["teste"])
            assert result[0] == custom_embedding

    Yields:
        Mock: Objeto mock configurável com atributos:
            - embeddings: Lista de embeddings a retornar
            - is_running: Status do servidor
            - health_status: Dict completo de health check

    Notes:
        - Dimensão padrão: 384 (compatível com all-MiniLM-L6-v2)
        - Latência mockada: 50ms
        - Socket path: /tmp/claude-brain-embeddings.sock
    """
    mock_server = Mock()

    # Configuração padrão simulando servidor saudável
    mock_server.embeddings = [[0.1] * 384]  # Dimensão do all-MiniLM-L6-v2
    mock_server.is_running = True
    mock_server.health_status = {
        'healthy': True,
        'socket_exists': True,
        'can_connect': True,
        'can_embed': True,
        'latency_ms': 50.0,
        'error': None
    }

    # Aplica patches nas funções do módulo
    with patch('embedding_server.is_server_running') as mock_running, \
         patch('embedding_server.get_embeddings_fast') as mock_embed, \
         patch('embedding_server.health_check') as mock_health:

        # Configura side_effects para usar valores do mock_server
        mock_running.side_effect = lambda: mock_server.is_running
        mock_embed.side_effect = lambda texts: mock_server.embeddings[:len(texts)]
        mock_health.side_effect = lambda: mock_server.health_status

        yield mock_server


# ============================================================================
# FIXTURE 5: brain_cli_runner - Runner para testes de CLI
# ============================================================================

@pytest.fixture
def brain_cli_runner(temp_db: Path, monkeypatch) -> Generator[callable, None, None]:
    """
    Runner para testar comandos CLI do Claude Brain de forma isolada.

    Esta fixture encapsula a execução do brain_cli.py, capturando
    stdout/stderr e retornando resultados estruturados. Usa o banco
    temporário da fixture temp_db para isolamento.

    Funcionalidades:
    - Executa comandos como se fossem chamados via terminal
    - Captura stdout e stderr separadamente
    - Retorna código de saída (exit_code)
    - Captura exceções não tratadas
    - Usa banco de dados temporário automaticamente

    Formato do resultado:
    {
        'exit_code': int,      # 0 = sucesso, >0 = erro
        'stdout': str,         # Saída padrão capturada
        'stderr': str,         # Saída de erro capturada
        'exception': Exception # Exceção se houve erro não tratado
    }

    Exemplo de uso:
        def test_comando_remember(brain_cli_runner):
            result = brain_cli_runner(['remember', 'Memória de teste'])

            assert result['exit_code'] == 0
            assert 'Memória salva' in result['stdout']
            assert result['exception'] is None

        def test_comando_decide_com_opcoes(brain_cli_runner):
            result = brain_cli_runner([
                'decide', 'Usar pytest para testes',
                '--project', 'claude-brain',
                '--reason', 'Framework mais popular e robusto'
            ])

            assert result['exit_code'] == 0
            assert 'Decisão salva' in result['stdout']

        def test_comando_learn_com_contexto(brain_cli_runner):
            result = brain_cli_runner([
                'learn', 'ImportError',
                '--solution', 'pip install pacote',
                '--context', 'Ao importar módulo externo',
                '--cause', 'Pacote não instalado no venv'
            ])

            assert result['exit_code'] == 0

        def test_comando_invalido(brain_cli_runner):
            result = brain_cli_runner(['comando_inexistente'])
            # Deve mostrar help ou erro
            assert 'help' in result['stdout'].lower() or result['exit_code'] != 0

        def test_search_sem_resultados(brain_cli_runner):
            result = brain_cli_runner(['search', 'xyz_nao_existe_abc'])
            assert result['exit_code'] == 0
            assert 'Nenhum resultado' in result['stdout']

    Args:
        temp_db: Fixture que configura banco temporário (dependência)
        monkeypatch: Fixture para patching de sys.argv

    Yields:
        Callable[[List[str]], Dict[str, Any]]: Função que executa comandos CLI
            - Recebe: Lista de argumentos (ex: ['remember', 'texto'])
            - Retorna: Dict com exit_code, stdout, stderr, exception

    Notes:
        - Cores ANSI são preservadas no stdout
        - stdin é simulado como não-interativo
        - Cada chamada usa o mesmo banco temp_db
        - Comandos são executados no mesmo processo
    """
    from contextlib import redirect_stdout, redirect_stderr

    def run_cli(args: List[str]) -> Dict[str, Any]:
        """
        Executa comando CLI com os argumentos fornecidos.

        Args:
            args: Lista de argumentos do comando (sem 'brain' no início)
                  Exemplo: ['remember', 'texto'] para 'brain remember texto'

        Returns:
            Dict com resultados da execução:
            - exit_code: Código de saída (0 = sucesso)
            - stdout: Saída padrão capturada
            - stderr: Saída de erro capturada
            - exception: Exceção se houve erro não tratado
        """
        import brain_cli

        result = {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'exception': None
        }

        # Captura streams de saída
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        # Simula sys.argv como se fosse chamado do terminal
        original_argv = sys.argv
        sys.argv = ['brain'] + args

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                brain_cli.main()
        except SystemExit as e:
            # Comando terminou com sys.exit()
            result['exit_code'] = e.code if e.code is not None else 0
        except Exception as e:
            # Erro não tratado
            result['exception'] = e
            result['exit_code'] = 1
        finally:
            # Restaura argv e captura output
            sys.argv = original_argv
            result['stdout'] = stdout_capture.getvalue()
            result['stderr'] = stderr_capture.getvalue()

        return result

    yield run_cli


# ============================================================================
# FIXTURES AUXILIARES
# ============================================================================

@pytest.fixture
def mock_stdout():
    """
    Captura stdout para verificar output de funções.

    Uso:
        def test_print_output(mock_stdout):
            print("Hello")
            mock_stdout.seek(0)
            assert "Hello" in mock_stdout.read()
    """
    captured = StringIO()
    with patch('sys.stdout', captured):
        yield captured


@pytest.fixture
def mock_stdin():
    """
    Mock de stdin para simular input do usuário em testes.

    Uso:
        def test_confirmacao(mock_stdin):
            with mock_stdin("s\\n"):
                resposta = input("Confirma? ")
                assert resposta == "s"
    """
    def _mock_stdin(input_text: str):
        return patch('sys.stdin', StringIO(input_text))
    return _mock_stdin


@pytest.fixture
def mock_isatty():
    """
    Mock para sys.stdout.isatty() - simula terminal vs pipe.

    Útil para testar código que comporta diferente em terminal vs pipe
    (como cores ANSI que são desabilitadas em pipes).

    Uso:
        def test_sem_cores_em_pipe(mock_isatty):
            with mock_isatty(is_tty=False):
                # Código que desabilita cores quando não é tty
                pass
    """
    def _mock_isatty(is_tty: bool = True):
        mock = MagicMock(return_value=is_tty)
        return patch('sys.stdout.isatty', mock)
    return _mock_isatty


@pytest.fixture
def cli_args():
    """
    Factory para criar argumentos de CLI simulados.

    Útil para testar funções cmd_* diretamente sem passar pelo parser.

    Uso:
        def test_cmd_remember(cli_args, temp_db):
            from brain_cli import cmd_remember
            args = cli_args(text=["Minha", "memória"])
            cmd_remember(args)
    """
    class MockArgs:
        def __init__(self, **kwargs):
            # Defaults para todos os argumentos possíveis
            defaults = {
                'text': None, 'decision': None, 'error': None, 'query': None,
                'solution': None, 'project': None, 'reason': None,
                'alternatives': None, 'fact': False, 'prevention': None,
                'context': None, 'cause': None, 'message': None, 'type': None,
                'limit': None, 'category': None, 'importance': None,
                'path': None, 'no_recursive': False, 'tokens': None,
                'source': None, 'name': None, 'relation': None, 'entity': None,
                'pref': None, 'pattern': None, 'language': None,
                'feedback': None, 'dry_run': False, 'table': None, 'id': None,
                'new': None, 'force': False, 'threshold': 0.8, 'execute': False
            }
            # Aplica defaults
            for k, v in defaults.items():
                setattr(self, k, v)
            # Override com valores fornecidos
            for k, v in kwargs.items():
                setattr(self, k, v)

    return MockArgs


@pytest.fixture
def sample_memories(temp_db):
    """
    Popula o banco temporário com memórias de exemplo.

    Cria dados de teste em todas as tabelas principais,
    útil para testar buscas e listagens.

    Uso:
        def test_buscar_memorias(sample_memories):
            from memory_store import search_memories
            results = search_memories(query="teste")
            assert len(results) >= 1

    Returns:
        Dict com IDs dos registros criados
    """
    from memory_store import save_memory, save_decision, get_db

    mem_id = save_memory(
        "test",
        "Memoria de teste para unit tests",
        category="testing",
        importance=7
    )

    dec_id = save_decision(
        "Usar pytest para testes",
        reasoning="Framework mais popular e bem documentado",
        project="claude-brain"
    )

    # Insere learning direto no banco para evitar problemas de schema
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO learnings (error_type, solution, prevention, project)
            VALUES (?, ?, ?, ?)
        ''', ("ModuleNotFoundError", "pip install <pacote>",
              "Verificar requirements.txt antes de rodar", "claude-brain"))
        learn_id = c.lastrowid

    return {
        "memory_id": mem_id,
        "decision_id": dec_id,
        "learning_id": learn_id
    }


@pytest.fixture
def sample_entities(temp_db):
    """
    Popula o banco com entidades e relações do knowledge graph.

    Uso:
        def test_grafo_entidade(sample_entities):
            from memory_store import get_entity_graph
            graph = get_entity_graph("claude-brain")
            assert len(graph['outgoing']) >= 2
    """
    from memory_store import save_entity, save_relation

    save_entity("python", "language", "Linguagem de programação")
    save_entity("pytest", "framework", "Framework de testes Python")
    save_entity("claude-brain", "project", "Sistema de memória inteligente")

    save_relation("claude-brain", "python", "uses")
    save_relation("claude-brain", "pytest", "uses")

    return {
        "entities": ["python", "pytest", "claude-brain"],
        "relations": [
            ("claude-brain", "python", "uses"),
            ("claude-brain", "pytest", "uses")
        ]
    }


@pytest.fixture
def sample_preferences(temp_db):
    """
    Popula o banco com preferências de usuário.

    Uso:
        def test_preferencias(sample_preferences):
            from memory_store import get_preference
            assert get_preference("test_framework") == "pytest"
    """
    from memory_store import save_preference

    save_preference("test_framework", "pytest", confidence=0.9)
    save_preference("language", "python", confidence=0.85)
    save_preference("editor", "vscode", confidence=0.7)

    return ["test_framework", "language", "editor"]


@pytest.fixture
def mock_rag_engine():
    """
    Mock do módulo rag_engine para testes isolados do CLI.

    Mocka funções de indexação e busca para evitar I/O real.

    Uso:
        def test_comando_search(mock_rag_engine, brain_cli_runner):
            result = brain_cli_runner(['search', 'python'])
            assert 'Test content' in result['stdout']
    """
    with patch('brain_cli.index_file') as mock_index_file, \
         patch('brain_cli.index_directory') as mock_index_dir, \
         patch('brain_cli.search') as mock_search, \
         patch('brain_cli.get_context_for_query') as mock_context:

        mock_index_file.return_value = {'chunk_count': 5}
        mock_index_dir.return_value = 10
        mock_search.return_value = [
            {'source': 'test.py', 'text': 'Test content about Python', 'score': 0.85}
        ]
        mock_context.return_value = "Contexto relevante para a query de teste"

        yield {
            'index_file': mock_index_file,
            'index_directory': mock_index_dir,
            'search': mock_search,
            'context': mock_context
        }


@pytest.fixture
def mock_metrics():
    """
    Mock do módulo metrics para testes sem side-effects.

    Uso:
        def test_comando_useful(mock_metrics, brain_cli_runner):
            result = brain_cli_runner(['useful'])
            mock_metrics['mark_useful'].assert_called_once()
    """
    with patch('brain_cli.log_action') as mock_log, \
         patch('brain_cli.mark_useful') as mock_useful, \
         patch('brain_cli.get_effectiveness') as mock_eff, \
         patch('brain_cli.print_dashboard') as mock_dash:

        mock_eff.return_value = {
            'total_actions': 100,
            'rated_actions': 50,
            'effectiveness_pct': 80
        }

        yield {
            'log_action': mock_log,
            'mark_useful': mock_useful,
            'get_effectiveness': mock_eff,
            'print_dashboard': mock_dash
        }


@pytest.fixture
def clean_env(monkeypatch):
    """
    Limpa variáveis de ambiente que podem afetar testes de ML.

    Remove variáveis como HF_HUB_OFFLINE, TOKENIZERS_PARALLELISM
    que podem interferir com comportamento dos modelos.

    Uso:
        def test_modelo_online(clean_env):
            # Testa com ambiente limpo
            pass
    """
    env_vars = [
        'HF_HUB_OFFLINE',
        'TOKENIZERS_PARALLELISM',
        'CUDA_VISIBLE_DEVICES',
        'TRANSFORMERS_OFFLINE'
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def mock_rag_index(tmp_path: Path) -> Generator[Dict[str, Any], None, None]:
    """
    Cria índice RAG mockado (index.json) com dados de teste.

    Útil para testar funções que lêem o índice sem fazer indexação real.

    Uso:
        def test_carregar_indice(mock_rag_index, monkeypatch):
            import faiss_rag
            monkeypatch.setattr(faiss_rag, "INDEX_FILE", mock_rag_index['index_path'])
            doc_index = faiss_rag.load_doc_index()
            assert len(doc_index['documents']) == 2
    """
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir(parents=True, exist_ok=True)

    index_data = {
        "documents": {
            "abc123": {
                "source": "/test/doc1.md",
                "doc_type": "markdown",
                "indexed_at": "2024-01-01T00:00:00"
            },
            "def456": {
                "source": "/test/doc2.py",
                "doc_type": "python",
                "indexed_at": "2024-01-01T00:00:00"
            }
        }
    }

    index_path = rag_dir / "index.json"
    index_path.write_text(json.dumps(index_data, indent=2))

    yield {
        'index_path': index_path,
        'rag_dir': rag_dir,
        'documents': index_data['documents']
    }
