# Contribuindo para Claude Brain

Obrigado por seu interesse em contribuir para o Claude Brain! Este documento orienta o processo.

## Índice

1. [Começando](#começando)
2. [Desenvolvimento](#desenvolvimento)
3. [Testes](#testes)
4. [Code Style](#code-style)
5. [Commit Message](#commit-message)
6. [Pull Request](#pull-request)
7. [Code Review](#code-review)

---

## Começando

### 1. Fork e Clone

```bash
# Fork o repositório (via GitHub UI)

# Clone seu fork
git clone https://github.com/seu-usuario/claude-brain.git
cd claude-brain

# Adicionar upstream
git remote add upstream https://github.com/original/claude-brain.git
```

### 2. Setup Local

```bash
# Criar virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Verificar instalação
python -c "import neo4j, faiss, pytest; print('OK')"
```

### 3. Branches

```bash
# Sempre criar branch nova
git checkout -b feature/seu-feature

# Convenções de nome:
# - feature/novo-componente
# - fix/nome-do-bug
# - docs/atualizacao-doc
# - test/melhorar-teste
# - refactor/nome-componente
```

---

## Desenvolvimento

### Estrutura do Projeto

```
/root/claude-brain/
├── scripts/memory/          # Core implementation
│   ├── base.py             # Base classes + logging
│   ├── ensemble_search.py  # Multi-source search
│   ├── neo4j_wrapper.py    # Graph database
│   ├── query_decomposer.py # LLM decomposition
│   └── ...
├── api/                     # FastAPI endpoints
├── tests/                   # Testes (pytest)
├── docs/                    # Documentação
└── docker-compose.yml       # Stack definition
```

### Adicionando Feature

1. **Criar módulo em scripts/memory/**

```python
# scripts/memory/new_feature.py

import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class NewFeature:
    """Descrição da feature"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        logger.info(f"Inicializando NewFeature com config: {self.config}")

    def do_something(self, input_data: str) -> Dict:
        """
        Faz algo útil.

        Args:
            input_data: Texto de entrada

        Returns:
            Dict com resultado

        Raises:
            ValueError: Se input inválido
        """
        if not input_data:
            raise ValueError("input_data não pode estar vazio")

        logger.debug(f"Processando: {input_data}")
        result = {"status": "ok", "data": input_data}
        return result
```

2. **Adicionar testes em tests/**

```python
# tests/test_new_feature.py

import pytest
from scripts.memory.new_feature import NewFeature

class TestNewFeature:
    """Testes para NewFeature"""

    @pytest.fixture
    def feature(self):
        return NewFeature(config={"test": True})

    def test_init(self, feature):
        assert feature.config["test"] is True

    def test_do_something(self, feature):
        result = feature.do_something("test input")
        assert result["status"] == "ok"
        assert result["data"] == "test input"

    def test_do_something_empty_input(self, feature):
        with pytest.raises(ValueError):
            feature.do_something("")

    @pytest.mark.integration
    def test_integration_with_db(self, feature):
        # Teste que requer DB rodando
        pass
```

3. **Adicionar logs estruturados**

```python
from scripts.memory.base import log_action

# Use log_action para rastrear ações importantes
log_action(
    action="feature_executed",
    project="claude-brain",
    details={"input": input_data, "result": result}
)
```

---

## Testes

### Rodando Testes

```bash
# Todos os testes
python -m pytest tests/ -v

# Teste específico
python -m pytest tests/test_new_feature.py -v

# Com cobertura
python -m pytest tests/ --cov=scripts/memory --cov-report=html

# Apenas testes rápidos (excluir @pytest.mark.integration)
python -m pytest tests/ -m "not integration" -v

# Testes de performance
python -m pytest tests/ -m "performance" -v --durations=10
```

### Estrutura de Teste

```python
import pytest
from unittest.mock import patch, MagicMock

class TestMyFeature:
    """Sempre usar classe para agrupar testes"""

    @pytest.fixture
    def setup(self):
        """Setup compartilhado"""
        return {
            "db": MagicMock(),
            "graph": MagicMock()
        }

    def test_happy_path(self, setup):
        """Teste do fluxo normal"""
        assert True

    def test_error_handling(self, setup):
        """Teste de error"""
        with pytest.raises(ValueError):
            pass

    @pytest.mark.integration
    def test_with_real_db(self):
        """Teste que requer BD real (marca @pytest.mark.integration)"""
        pass

    @pytest.mark.performance
    def test_performance(self):
        """Teste de performance"""
        import time
        start = time.time()
        # operação
        elapsed = time.time() - start
        assert elapsed < 1.0  # Menos de 1 segundo
```

### Cobertura Mínima

- **Novo código**: ≥ 80% cobertura
- **Refactoring**: Manter cobertura existente
- **Documentação**: Sempre incluir docstrings

```bash
# Verificar cobertura por arquivo
coverage report -m scripts/memory/new_feature.py
```

---

## Code Style

### Python Style Guide

Seguimos **PEP 8** + **Black** para formatação.

```bash
# Instalar formatadores
pip install black isort flake8

# Formatar código
black scripts/memory/

# Organizar imports
isort scripts/memory/

# Verificar style
flake8 scripts/memory/
```

### Exemplo de Code Style

```python
"""
Module docstring explain what this module does.

Follows PEP 8 + Black formatting.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration object."""

    timeout: int = 30
    max_retries: int = 3


def process_data(
    data: List[str],
    config: Optional[Config] = None,
) -> Dict[str, int]:
    """
    Process a list of strings.

    Args:
        data: List of strings to process
        config: Optional configuration

    Returns:
        Dictionary with processing results

    Raises:
        ValueError: If data is empty
    """
    if not data:
        raise ValueError("data cannot be empty")

    cfg = config or Config()
    logger.info(f"Processing {len(data)} items with timeout={cfg.timeout}")

    return {"count": len(data), "status": "ok"}
```

### Imports

```python
# Ordem: standard lib → third party → local
import os
import sys
from typing import Dict, List

import numpy as np
import pandas as pd

from scripts.memory.base import log_action
from scripts.memory.ensemble_search import ensemble_search
```

### Type Hints

Sempre use type hints:

```python
# Bom ✓
def search(query: str, limit: int = 10) -> List[Dict]:
    pass

# Ruim ✗
def search(query, limit=10):
    pass
```

---

## Commit Message

### Formato

```
<tipo>: <assunto>

<corpo (opcional)>

<rodapé (opcional)>
```

### Tipos

- **feat**: Nova feature
- **fix**: Bug fix
- **docs**: Mudança em documentação
- **style**: Mudança de formatação (sem impacto funcional)
- **refactor**: Refatoração sem mudança de behavior
- **perf**: Melhoria de performance
- **test**: Adição/mudança de testes
- **ci**: CI/CD changes
- **chore**: Outras mudanças

### Exemplos

```bash
# Feature
git commit -m "feat: add distributed subtasks for parallel search"

# Bug fix
git commit -m "fix: handle Neo4j connection timeout gracefully"

# Documentation
git commit -m "docs: update API.md with new endpoints"

# Com descrição detalhada
git commit -m "refactor: consolidate ensemble search logic

- Merge redundant filtering code
- Improve performance by 30%
- Add caching for repeated queries
"

# Com referência a issue
git commit -m "fix: resolve ConnectionError in Redis sync

Fixes #123
"
```

---

## Pull Request

### Antes de Submeter

1. **Atualizar com upstream**
   ```bash
   git fetch upstream
   git rebase upstream/master
   ```

2. **Rodar testes**
   ```bash
   python -m pytest tests/ -v
   ```

3. **Verificar coverage**
   ```bash
   python -m pytest tests/ --cov=scripts/memory
   ```

4. **Verificar code style**
   ```bash
   black scripts/memory/
   isort scripts/memory/
   flake8 scripts/memory/
   ```

### Abrir PR

1. Push sua branch
   ```bash
   git push origin feature/seu-feature
   ```

2. Ir para GitHub e clicar "Compare & pull request"

3. Preencher template:

```markdown
## Descrição
Breve descrição do que foi feito.

## Tipo de Mudança
- [ ] Feature nova
- [ ] Bug fix
- [ ] Documentação
- [ ] Refactoring

## Checklist
- [ ] Testes adicionados/atualizados
- [ ] Documentação atualizada
- [ ] Code style verificado (black, isort, flake8)
- [ ] Commit messages seguem convenção
- [ ] Nenhum conflito com master

## Testing
Descrever como testar as mudanças.

## Screenshots (se aplicável)
```

---

## Code Review

### Processo

1. **Automático**: CI roda testes e coverage
2. **Código**: Pelo menos 1 reviewer (preferência Opus 4.5)
3. **Aprovação**: ≥ 1 approval + CI passing
4. **Merge**: Squash commits se necessário

### O que Reviewers Checam

- ✅ Testes adequados (≥80% coverage)
- ✅ Sem regressões de performance
- ✅ Documentação completa
- ✅ Code style (black, isort, flake8)
- ✅ Security (sem hardcoded secrets, SQL injection, etc)
- ✅ Tratamento de erro apropriado
- ✅ Logging estruturado

### Responder Feedback

```bash
# Fazer mudanças solicitadas
git add .
git commit -m "refactor: address review feedback"
git push origin feature/seu-feature

# Não forçar push
# Reviewer verá as mudanças adicionais
```

---

## Documentação

Toda feature DEVE ter documentação:

1. **Docstrings Python**
   ```python
   def my_function(arg: str) -> Dict:
       """
       Uma linha descrevendo o que faz.

       Descrição detalhada (opcional).

       Args:
           arg: Descrição do argumento

       Returns:
           Descrição do retorno

       Raises:
           ValueError: Quando arg é inválido
       """
   ```

2. **README / Docs**
   - Atualizar `/root/claude-brain/docs/`
   - Adicionar exemplos de uso
   - Link na documentação principal

3. **Changelog**
   - Adicionar entrada em CHANGELOG.md
   - Manter formato Semantic Versioning

---

## Roadmap

Veja [README.md](README.md) para próximos passos:

- [ ] Dashboard Web (React)
- [ ] Suporte a múltiplos LLMs
- [ ] Sync distribuído
- [ ] Auto-categorização ML
- [ ] Webhooks para eventos

---

## Dúvidas?

- 📖 Ler [ARCHITECTURE.md](ARCHITECTURE.md) para entender design
- 🐛 Abrir [GitHub Issue](https://github.com/your-repo/issues)
- 💬 Discussões em [GitHub Discussions](https://github.com/your-repo/discussions)

---

**Bem-vindo ao projeto! 🚀**

Versão: 1.2.0
Última atualização: 2026-02-04
