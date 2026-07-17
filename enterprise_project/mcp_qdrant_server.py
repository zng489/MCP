# =============================================================================
# MCP RETRIEVER - SOMENTE BUSCA (Qdrant já existente)
# =============================================================================
import torch # pyright: ignore[reportMissingImports]
import torch.distributed as dist # pyright: ignore[reportMissingImports]
import logging
# Avoid error in environments without distributed support
# Evita erro em ambientes sem suporte distribuído
if not hasattr(dist, 'is_initialized'):
    dist.is_initialized = lambda: False
import os
import sys
import numpy as np # pyright: ignore[reportMissingImports]
from typing import List
from sentence_transformers import SentenceTransformer # pyright: ignore[reportMissingImports]
from qdrant_client import QdrantClient # pyright: ignore[reportMissingImports]
from fastmcp import FastMCP # pyright: ignore[reportMissingImports]

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
# Caminho exato para o modelo (sem fallback para modelo remoto)
MODEL_PATH = r"C:\Users\Yuan\Desktop\git_hub\ai_engineering\llmops\project_llmops\enterprise_project\model\bge-small-en-v1.5"

# Configuração do Qdrant - ajuste conforme necessário
QDRANT_STORAGE_PATH = r"C:\Users\Yuan\Desktop\git_hub\ai_engineering\llmops\project_llmops\enterprise_project\scripts\qdrant_db"
QDRANT_COLLECTION_NAME = "knowledge_base_pdfs"  # Este é apenas o nome da coleção, não um caminho

# Configurações adicionais
K_RETRIEVE = 5  # Número de trechos a recuperar

# =============================================================================
# LOG
# =============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# INICIALIZAÇÃO
# =============================================================================
def inicializar_sistema():
    """Inicializa o modelo de embedding e a conexão com o Qdrant"""
    
    # Carregar modelo de embeddings
    logger.info("🔎 Carregando modelo de embedding...")
    
    # Verificar se o modelo existe no caminho especificado
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Modelo não encontrado em: {MODEL_PATH}")
        raise FileNotFoundError(f"Modelo não encontrado em: {MODEL_PATH}")
    
    # Carregar o modelo do caminho especificado
    logger.info(f"Usando modelo em: {MODEL_PATH}")
    embedding_model = SentenceTransformer(MODEL_PATH)
    logger.info("✓ Modelo de embeddings carregado com sucesso")

    # Conectar ao Qdrant
    logger.info("📦 Conectando ao Qdrant local...")
    
    # Verificar se o caminho existe
    if not os.path.exists(QDRANT_STORAGE_PATH):
        logger.error(f"Caminho do Qdrant não encontrado: {QDRANT_STORAGE_PATH}")
        raise FileNotFoundError(f"Caminho do Qdrant não encontrado: {QDRANT_STORAGE_PATH}")
    
    # Conexão local via arquivo
    client = QdrantClient(path=QDRANT_STORAGE_PATH)
    logger.info(f"Conectado ao Qdrant local em: {QDRANT_STORAGE_PATH}")

    # Verificação opcional
    collections = [c.name for c in client.get_collections().collections]
    
    if QDRANT_COLLECTION_NAME not in collections:
        raise ValueError(f"Collection '{QDRANT_COLLECTION_NAME}' não encontrada no Qdrant.")
    
    logger.info("✅ Conectado com sucesso.")
    
    # Informações de diagnóstico
    #print("Caminho do modelo:", MODEL_PATH)
    #print("Modelo existe?", os.path.exists(MODEL_PATH))
    #print("Caminho completo do Qdrant:", QDRANT_STORAGE_PATH)
    #print("Qdrant existe?", os.path.exists(QDRANT_STORAGE_PATH))
    #print("Tem pasta 'collection'?", os.path.exists(os.path.join(QDRANT_STORAGE_PATH, "collection")))
    
    return embedding_model, client

# =============================================================================
# FUNÇÃO DE BUSCA
# =============================================================================
def buscar_contexto(pergunta: str, embedding_model, client, k: int = K_RETRIEVE) -> List[str]:
    """Busca os k trechos mais similares à pergunta"""
    try:
        # Gerar embedding da pergunta
        query_embedding = embedding_model.encode([pergunta]).astype(np.float32)
        
        # Usar query_points em vez de search
        search_results = client.query_points(
            collection_name=QDRANT_COLLECTION_NAME,
            query=query_embedding[0].tolist(),
            limit=k
        ).points
        
        resultados = []
        
        for result in search_results:
            texto = result.payload.get("text")  # ajuste se seu payload usa outro campo
            if texto:
                resultados.append(texto)
        
        logger.info(f"Busca concluída: {len(resultados)} trechos encontrados")
        return resultados
        
    except Exception as e:
        logger.error(f"Erro na busca vetorial: {e}", exc_info=True)
        return []

# =============================================================================
# MCP SERVER
# =============================================================================
def iniciar_servidor_mcp(embedding_model, client):
    """Inicia o servidor MCP com a ferramenta de busca configurada"""
    
    mcp = FastMCP(name="Retriever Qdrant MCP")
    @mcp.tool(
        description="""
        Use esta ferramenta sempre que precisar buscar informações
        na base vetorial (runbooks, documentação técnica ou base interna).
        Retorna apenas os trechos mais relevantes.
        """
    )
    def buscar_runbook(pergunta: str) -> str:
        """
        Retorna trechos relevantes do Qdrant.
        NÃO gera resposta final.
        """
        
        logger.info(f"Pergunta recebida: {pergunta[:120]}")
        
        contextos = buscar_contexto(pergunta, embedding_model, client)
        
        if not contextos:
            return "Nenhum trecho relevante encontrado."
        
        resposta = "\n\n".join(
            f"─── Trecho {i+1} ───\n{ctx.strip()}"
            for i, ctx in enumerate(contextos)
        )
        
        logger.info("✓ Contexto retornado ao modelo principal")
        return resposta
    
    logger.info("🚀 Iniciando MCP Retriever conectado ao Qdrant...")
    mcp.run()

# =============================================================================
# START
# =============================================================================
if __name__ == "__main__":
    try:
        # Inicializar o sistema
        embedding_model, client = inicializar_sistema()
        
        # Iniciar o servidor MCP
        iniciar_servidor_mcp(embedding_model, client)
    except KeyboardInterrupt:
        logger.info("Servidor interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro ao iniciar o servidor: {e}", exc_info=True)
    finally:
        # Fechar conexão com o Qdrant se necessário
        if 'client' in locals():
            client.close()
            logger.info("Conexão com Qdrant fechada")