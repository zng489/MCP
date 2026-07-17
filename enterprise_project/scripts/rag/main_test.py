"""
Module: simple_query.py
======================

Script simples para consultar o banco de dados RAG.
"""
import torch # pyright: ignore[reportMissingImports]
import torch.distributed as dist # pyright: ignore[reportMissingImports]
import logging

# Avoid error in environments without distributed support
# Evita erro em ambientes sem suporte distribuído
if not hasattr(dist, 'is_initialized'):
    dist.is_initialized = lambda: False

import os
from sentence_transformers import SentenceTransformer # pyright: ignore[reportMissingImports]
from qdrant_client import QdrantClient # pyright: ignore[reportMissingImports]
import sys

# Adicionar o diretório pai ao path para importar o módulo vector_store
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.append(os.path.join(PROJECT_DIR, "scripts"))
sys.path.append(os.path.join(PROJECT_DIR, "scripts", "rag"))

# Configuração do Qdrant
QDRANT_STORAGE_PATH = os.path.join(PROJECT_DIR, "scripts", "qdrant_db")
QDRANT_COLLECTION_NAME = "knowledge_base_pdfs"  # Este é apenas o nome da coleção, não um caminho

# Carregar modelo de embeddings
print("Carregando modelo de embeddings...")

# Tentar carregar o modelo local
model_path = os.path.join(PROJECT_DIR, "model", "bge-small-en-v1.5")
model = SentenceTransformer(model_path)
print(f"Modelo carregado de: {model_path}")



print("PROJECT_DIR calculado como:", PROJECT_DIR)
print("Caminho completo do Qdrant:", QDRANT_STORAGE_PATH)
print("Esse caminho existe?", os.path.exists(QDRANT_STORAGE_PATH))
print("Tem pasta 'collection'?", os.path.exists(os.path.join(QDRANT_STORAGE_PATH, "collection")))

# Conectar ao Qdrant
print("Conectando ao banco de dados...")
try:
    client = QdrantClient(path=QDRANT_STORAGE_PATH)
    print(f"Conectado ao Qdrant em: {QDRANT_STORAGE_PATH}")

    # Listar coleções disponíveis
    collections = client.get_collections()
    print("Coleções disponíveis:")
    for collection in collections.collections:
        print(f"- {collection.name}")

    # ==============================
    # Consulta
    # ==============================

    query = input("Digite sua consulta: ")
    print(f"\nBuscando por: '{query}'")

    query_embedding = model.encode(query).tolist()

    # Usar search em vez de query_points (API mais recente)
    search_results = client.query_points(
        collection_name=QDRANT_COLLECTION_NAME,
        query=query_embedding,
        limit=5
    ).points

    results = []
    for result in search_results:
        payload = result.payload
        payload["score"] = result.score
        results.append(payload)
    # Mostrar resultados
    print(f"\nEncontrados {len(results)} resultados:")
    print("-" * 50)

    found_docs = set()

    for i, result in enumerate(results):
        doc_name = result.get("source", "Desconhecido")
        found_docs.add(doc_name)

        print(f"\n{i+1}. Documento: {doc_name}")
        print(f"   Similaridade: {result['score']:.4f}")
        print(f"   Trecho: {result['text'][:200]}...")

    print("\n" + "=" * 50)
    print(f"Documentos relevantes encontrados: {len(found_docs)}")
    for doc in found_docs:
        print(f"- {doc}")

except Exception as e:
    print(f"Erro durante a execução: {e}")

finally:
    if client is not None:
        client.close()
        print("\nConexão com Qdrant fechada corretamente.")