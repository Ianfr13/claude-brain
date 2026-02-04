#!/usr/bin/env python3
"""
Claude Brain - Query Decomposer Module

Decompõe queries complexas em sub-queries semânticas usando:
1. OpenRouter API (preferred) - com multiple model suporte
2. Fallback Claude Haiku (local via Anthropic)

Sistema de decomposição:
- Analisa query para identificar componentes
- Gera sub-queries otimizadas para busca RAG
- Retorna resultado estruturado com pontuação de confiança

Logging detalhado para debug e auditoria.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
import requests

# ============ LOGGING ============

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Handler para console
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ============ DATA STRUCTURES ============

@dataclass
class SubQuery:
    """Sub-query individual gerada pela decomposição"""
    query: str
    type: str  # "semantic", "entity", "temporal", "relational"
    confidence: float  # 0.0 - 1.0
    weight: float  # importância relativa
    tags: List[str]  # tags para categorização

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return asdict(self)


@dataclass
class DecompositionResult:
    """Resultado da decomposição de query"""
    original_query: str
    sub_queries: List[SubQuery]
    decomposition_confidence: float  # confiança geral
    provider: str  # "openrouter" ou "anthropic"
    model_used: str
    timestamp: str
    processing_time_ms: float
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        data = asdict(self)
        data['sub_queries'] = [sq.to_dict() for sq in self.sub_queries]
        return data


# ============ CONSTANTS ============

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS = [
    "nvidia/nemotron-nano-9b-v2:free",  # fast
    "openrouter/auto",  # auto-routing
]

# ============ INPUT VALIDATION ============

def sanitize_query(query: str, max_len: int = 500) -> str:
    """Sanitiza query para prevenir injection e overflow.

    Args:
        query: Query a sanitizar
        max_len: Comprimento máximo permitido (default: 500)

    Returns:
        Query sanitizada

    Raises:
        ValueError: Se query exceder max_len ou for inválida
    """
    if not query or not isinstance(query, str):
        raise ValueError("Query deve ser uma string não-vazia")

    query = query.strip()

    if len(query) > max_len:
        raise ValueError(f"Query excede limite de {max_len} caracteres ({len(query)} recebidos)")

    # Remove caracteres de controle e normaliza espaço
    query = " ".join(query.split())

    logger.debug(f"Query sanitizada: {len(query)} chars")
    return query


DECOMPOSITION_PROMPT = """Você é um especialista em decomposição semântica de queries.

Analyze a seguinte query e decomponha-a em sub-queries otimizadas para busca RAG:

QUERY: {query}

Retorne um JSON com a seguinte estrutura:
{{
  "sub_queries": [
    {{
      "query": "sub-query específica",
      "type": "semantic|entity|temporal|relational",
      "confidence": 0.95,
      "weight": 1.0,
      "tags": ["tag1", "tag2"]
    }}
  ],
  "decomposition_confidence": 0.85,
  "reasoning": "Breve explicação da decomposição"
}}

Regras:
1. type: semantic (busca de conceitos), entity (entidades nomeadas), temporal (tempo), relational (relações)
2. confidence: quão certo está desta sub-query (0.0-1.0)
3. weight: importância relativa (soma deve ser ~3-5)
4. Máximo 5 sub-queries
5. Retorne APENAS o JSON válido, sem markdown ou explicação extra

Analise agora:"""


# ============ OPENROUTER INTEGRATION ============

class OpenRouterDecomposer:
    """Interface para OpenRouter API"""

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.base_url = OPENROUTER_API_URL
        self.models = OPENROUTER_MODELS

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY não configurada")
            self.available = False
        else:
            self.available = True
            logger.info("OpenRouter configurada com sucesso")

    def decompose(self, query: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        Decomposição via OpenRouter

        Args:
            query: Query a decompor
            timeout: Timeout em segundos

        Returns:
            Dict com sub_queries ou None se erro
        """
        if not self.available:
            logger.warning("OpenRouter não disponível - pulando")
            return None

        # Valida e sanitiza query
        try:
            query = sanitize_query(query)
        except ValueError as e:
            logger.error(f"Query inválida: {e}")
            return None

        prompt = DECOMPOSITION_PROMPT.format(query=query)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://claude-brain.local",
            "X-Title": "Claude Brain Query Decomposer",
        }

        payload = {
            "model": self.models[0],  # usa primeiro modelo
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
        }

        try:
            logger.info(f"Enviando para OpenRouter: modelo={self.models[0]}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=timeout
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"OpenRouter respondeu com status 200")

            # Extrai conteúdo da resposta
            if "choices" not in result or not result["choices"]:
                logger.error(f"Resposta inválida de OpenRouter: {result}")
                return None

            content = result["choices"][0]["message"]["content"]
            logger.debug(f"Conteúdo bruto: {content}")

            # Parse JSON
            try:
                decomposition = json.loads(content)
                logger.info(f"Decomposição bem-sucedida: {len(decomposition.get('sub_queries', []))} sub-queries")
                return decomposition
            except json.JSONDecodeError as e:
                logger.error(f"JSON inválido de OpenRouter: {e}")
                logger.debug(f"Tentando extrair JSON do conteúdo...")
                # Tenta extrair JSON do conteúdo (se tiver markdown, etc)
                import re
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    try:
                        decomposition = json.loads(match.group(0))
                        logger.info("JSON extraído com sucesso após limpeza")
                        return decomposition
                    except json.JSONDecodeError:
                        logger.error("JSON ainda inválido após limpeza")
                        return None
                return None

        except requests.Timeout:
            logger.error(f"OpenRouter timeout após {timeout}s")
            return None
        except requests.ConnectionError as e:
            logger.error(f"Erro de conexão com OpenRouter: {e}")
            return None
        except requests.HTTPError as e:
            logger.error(f"HTTP error de OpenRouter: {e}")
            logger.debug(f"Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao chamar OpenRouter: {e}")
            return None


# ============ GEMINI FALLBACK ============

class GeminiDecomposer:
    """Fallback para Google Gemini via OpenRouter API"""

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.model = "google/gemini-2.5-flash-lite-preview-09-2025"
        self.base_url = OPENROUTER_API_URL

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY não configurada")
            self.available = False
        else:
            self.available = True
            logger.info("Gemini configurada com sucesso (fallback)")

    def decompose(self, query: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        Decomposição via Google Gemini (OpenRouter)

        Args:
            query: Query a decompor
            timeout: Timeout em segundos

        Returns:
            Dict com sub_queries ou None se erro
        """
        if not self.available:
            logger.warning("Gemini não disponível - pulando")
            return None

        # Valida e sanitiza query
        try:
            query = sanitize_query(query)
        except ValueError as e:
            logger.error(f"Query inválida: {e}")
            return None

        prompt = DECOMPOSITION_PROMPT.format(query=query)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://claude-brain.local",
            "X-Title": "Claude Brain Query Decomposer",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
        }

        try:
            logger.info(f"Enviando para Gemini: modelo={self.model}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=timeout
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"Gemini respondeu com status 200")

            # Extrai conteúdo da resposta
            if "choices" not in result or not result["choices"]:
                logger.error(f"Resposta inválida de Gemini: {result}")
                return None

            content = result["choices"][0]["message"]["content"]
            logger.debug(f"Conteúdo bruto: {content}")

            # Parse JSON
            try:
                decomposition = json.loads(content)
                logger.info(f"Decomposição bem-sucedida: {len(decomposition.get('sub_queries', []))} sub-queries")
                return decomposition
            except json.JSONDecodeError as e:
                logger.error(f"JSON inválido de Gemini: {e}")
                logger.debug(f"Tentando extrair JSON do conteúdo...")
                import re
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    try:
                        decomposition = json.loads(match.group(0))
                        logger.info("JSON extraído com sucesso após limpeza")
                        return decomposition
                    except json.JSONDecodeError:
                        logger.error("JSON ainda inválido após limpeza")
                        return None
                return None

        except requests.Timeout:
            logger.error(f"Gemini timeout após {timeout}s")
            return None
        except requests.ConnectionError as e:
            logger.error(f"Erro de conexão com Gemini: {e}")
            return None
        except requests.HTTPError as e:
            logger.error(f"HTTP error de Gemini: {e}")
            logger.debug(f"Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao chamar Gemini: {e}")
            return None


# ============ MAIN DECOMPOSER ============

class QueryDecomposer:
    """Orquestrador principal com fallback automático"""

    def __init__(self):
        self.openrouter = OpenRouterDecomposer()
        self.gemini = GeminiDecomposer()

        # Log disponibilidade
        logger.info(f"OpenRouter disponível: {self.openrouter.available}")
        logger.info(f"Gemini disponível: {self.gemini.available}")

        if not self.openrouter.available and not self.gemini.available:
            logger.warning("NENHUM PROVIDER DISPONÍVEL!")

    def decompose(self, query: str) -> DecompositionResult:
        """
        Decomposição com fallback automático

        Strategy:
        1. Tenta OpenRouter (preferred)
        2. Se falhar, tenta Anthropic (fallback)
        3. Se ambos falharem, retorna erro

        Args:
            query: Query a decompor

        Returns:
            DecompositionResult estruturado
        """
        import time
        start_time = time.time()

        # Valida query
        try:
            query = sanitize_query(query)
        except ValueError as e:
            logger.error(f"Query inválida: {e}")
            return DecompositionResult(
                original_query=query,
                sub_queries=[],
                decomposition_confidence=0.0,
                provider="none",
                model_used="none",
                timestamp=datetime.now().isoformat(),
                processing_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )

        logger.info(f"Iniciando decomposição: '{query}'")

        # Tentativa 1: OpenRouter
        if self.openrouter.available:
            logger.info("Tentativa 1: OpenRouter")
            decomposition = self.openrouter.decompose(query)
            if decomposition:
                result = self._build_result(
                    query=query,
                    decomposition=decomposition,
                    provider="openrouter",
                    model=self.openrouter.models[0],
                    start_time=start_time
                )
                logger.info(f"Sucesso com OpenRouter")
                return result
            logger.warning("OpenRouter falhou, tentando fallback...")

        # Tentativa 2: Gemini (fallback)
        if self.gemini.available:
            logger.info("Tentativa 2: Gemini (fallback)")
            decomposition = self.gemini.decompose(query)
            if decomposition:
                result = self._build_result(
                    query=query,
                    decomposition=decomposition,
                    provider="gemini",
                    model=self.gemini.model,
                    start_time=start_time
                )
                logger.info(f"Sucesso com Gemini (fallback)")
                return result
            logger.warning("Gemini também falhou")

        # Ambos falharam
        logger.error("AMBOS os providers falharam!")
        return DecompositionResult(
            original_query=query,
            sub_queries=[],
            decomposition_confidence=0.0,
            provider="none",
            model_used="none",
            timestamp=datetime.now().isoformat(),
            processing_time_ms=(time.time() - start_time) * 1000,
            error="Nenhum provider disponível ou ambos falharam"
        )

    def _build_result(
        self,
        query: str,
        decomposition: Dict[str, Any],
        provider: str,
        model: str,
        start_time: float
    ) -> DecompositionResult:
        """Constrói DecompositionResult a partir de decomposition"""
        import time

        # Parse sub-queries
        sub_queries = []
        for sq_data in decomposition.get("sub_queries", []):
            try:
                sq = SubQuery(
                    query=sq_data.get("query", ""),
                    type=sq_data.get("type", "semantic"),
                    confidence=float(sq_data.get("confidence", 0.5)),
                    weight=float(sq_data.get("weight", 1.0)),
                    tags=sq_data.get("tags", [])
                )
                sub_queries.append(sq)
            except Exception as e:
                logger.warning(f"Erro ao parsear sub-query: {e}")
                continue

        return DecompositionResult(
            original_query=query,
            sub_queries=sub_queries,
            decomposition_confidence=float(decomposition.get("decomposition_confidence", 0.5)),
            provider=provider,
            model_used=model,
            timestamp=datetime.now().isoformat(),
            processing_time_ms=(time.time() - start_time) * 1000
        )


# ============ CONVENIENCE FUNCTION ============

def decompose_query(query: str) -> DecompositionResult:
    """
    Função de conveniência para decomposição

    Usage:
        result = decompose_query("minha query complexa")
        print(result.sub_queries)
    """
    decomposer = QueryDecomposer()
    return decomposer.decompose(query)


# ============ CLI & TESTING ============

if __name__ == "__main__":
    import sys

    # Configurar logging para test
    logging.basicConfig(level=logging.DEBUG)

    # Query de teste
    test_queries = [
        "Como implementar cache Redis com TTL de 24 horas?",
        "Qual é a diferença entre decision e learning no brain?",
        "Implementar autenticação com JWT em FastAPI",
    ]

    if len(sys.argv) > 1:
        test_query = " ".join(sys.argv[1:])
    else:
        test_query = test_queries[0]

    print(f"\n{'='*70}")
    print(f"TEST: Query Decomposer")
    print(f"{'='*70}")
    print(f"Query: {test_query}\n")

    result = decompose_query(test_query)

    print(f"\n{'='*70}")
    print(f"RESULTADO:")
    print(f"{'='*70}")
    print(f"Provider: {result.provider}")
    print(f"Modelo: {result.model_used}")
    print(f"Tempo: {result.processing_time_ms:.2f}ms")
    print(f"Confiança geral: {result.decomposition_confidence:.2f}")
    print(f"\nSub-queries ({len(result.sub_queries)}):")

    for i, sq in enumerate(result.sub_queries, 1):
        print(f"\n  {i}. [{sq.type}] {sq.query}")
        print(f"     Confiança: {sq.confidence:.2f} | Peso: {sq.weight:.2f}")
        print(f"     Tags: {', '.join(sq.tags)}")

    if result.error:
        print(f"\nErro: {result.error}")

    print(f"\n{'='*70}\n")

    # Output JSON
    print("JSON Output:")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
