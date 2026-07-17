"""
Module: vector_store.py
====================

Handles vector database operations using Qdrant.
"""

import os
import uuid
from typing import List, Dict, Any
import torch # pyright: ignore[reportMissingImports]
import torch.distributed as dist # pyright: ignore[reportMissingImports]
import logging

# Avoid error in environments without distributed support
# Evita erro em ambientes sem suporte distribuído
if not hasattr(dist, "is_initialized"):
    dist.is_initialized = lambda: False
 
from sentence_transformers import SentenceTransformer # pyright: ignore[reportMissingImports]
from qdrant_client import QdrantClient, models # pyright: ignore[reportMissingImports]

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Qdrant Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
QDRANT_STORAGE_PATH = os.path.join(PROJECT_DIR, "qdrant_db")
QDRANT_COLLECTION_NAME = "knowledge_base_pdfs"


def initialize_qdrant_client():
    """Initialize and return a Qdrant client"""
    try:
        client = QdrantClient(path=QDRANT_STORAGE_PATH)
        logger.info(f"Connected to Qdrant at {QDRANT_STORAGE_PATH}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        return None


def initialize_qdrant_collection(client: QdrantClient, vector_size: int):
    """
    Creates the Qdrant collection if it doesn't exist.

    Args:
        client: Initialized Qdrant client
        vector_size: Dimension of the embedding vectors
    """
    try:
        # Check if collection exists
        client.get_collection(collection_name=QDRANT_COLLECTION_NAME)
        logger.info(f"Collection '{QDRANT_COLLECTION_NAME}' already exists.")
    except Exception:
        logger.info(f"Creating new collection: '{QDRANT_COLLECTION_NAME}'")
        client.create_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=vector_size, distance=models.Distance.COSINE
            ),
        )
        logger.info(f"Collection '{QDRANT_COLLECTION_NAME}' created successfully.")


def store_embeddings(
    client: QdrantClient, chunks: List[Dict[str, Any]], embeddings: List[List[float]]
):
    """
    Stores embeddings and chunks in Qdrant.

    Args:
        client: Initialized Qdrant client
        chunks: List of chunk dictionaries with text and metadata
        embeddings: List of embedding vectors
    """
    if not chunks or not embeddings:
        logger.warning("No chunks or embeddings to store")
        return

    try:
        # Prepare points for Qdrant
        points = [
            models.PointStruct(id=str(uuid.uuid4()), vector=embedding, payload=chunk)
            for chunk, embedding in zip(chunks, embeddings)
        ]

        # Store in Qdrant
        client.upsert(collection_name=QDRANT_COLLECTION_NAME, points=points, wait=True)

        logger.info(f"Successfully stored {len(chunks)} embeddings in Qdrant")

    except Exception as e:
        logger.error(f"Error storing embeddings in Qdrant: {e}")


def get_indexed_sources(client: QdrantClient) -> set:
    """
    Returns set of source files already indexed in Qdrant.
    """
    try:
        sources = set()
        offset = None
        while True:
            points, next_offset = client.scroll(
                collection_name=QDRANT_COLLECTION_NAME,
                offset=offset,
                limit=1000,
                with_payload=["source"],
            )
            for point in points:
                if point.payload and "source" in point.payload:
                    sources.add(point.payload["source"])
            if next_offset is None:
                break
            offset = next_offset
        return sources
    except Exception as e:
        logger.error(f"Error getting indexed sources: {e}")
        return set()


def delete_by_source(client: QdrantClient, source: str):
    """
    Deletes all vectors from a specific source file.
    """
    try:
        client.delete(
            collection_name=QDRANT_COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source", match=models.MatchValue(value=source)
                        )
                    ]
                )
            ),
            wait=True,
        )
        logger.info(f"Deleted vectors from source: {source}")
    except Exception as e:
        logger.error(f"Error deleting vectors for {source}: {e}")


def delete_collection(client: QdrantClient):
    """
    Deletes the entire collection (useful for full re-index).
    """
    try:
        client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)
        logger.info(f"Collection '{QDRANT_COLLECTION_NAME}' deleted.")
    except Exception as e:
        logger.error(f"Error deleting collection: {e}")


def get_collection_info(client: QdrantClient) -> Dict[str, Any]:
    """
    Returns info about the collection (point count, etc).
    """
    try:
        info = client.get_collection(collection_name=QDRANT_COLLECTION_NAME)
        return {
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.name,
        }
    except Exception as e:
        logger.error(f"Error getting collection info: {e}")
        return {}


def search_qdrant(
    client: QdrantClient, query_vector: List[float], top_k: int = 4
) -> List[Dict[str, Any]]:
    """
    Searches Qdrant for similar vectors.

    Args:
        client: Initialized Qdrant client
        query_vector: The query embedding vector
        top_k: Number of results to return

    Returns:
        List of dictionaries with search results
    """
    try:
        search_results = client.search(
            collection_name=QDRANT_COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
        )

        results = []
        for result in search_results:
            # Extract payload and add score
            payload = result.payload
            payload["score"] = result.score
            results.append(payload)

        return results

    except Exception as e:
        logger.error(f"Error searching Qdrant: {e}")
        return []
