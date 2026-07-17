"""
Module: qdrant.py
===============

Handles vector database operations for storing and retrieving embeddings.
"""

import os
import uuid
from typing import List
import torch
import torch.distributed as dist

# Avoid error in environments without distributed support
if not hasattr(dist, 'is_initialized'):
    dist.is_initialized = lambda: False

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models

# --- Qdrant Configuration (Embedded Mode) ---
# Path to the folder where the local vector database will be stored
QDRANT_STORAGE_PATH = os.path.join(os.path.dirname(__file__), '..', 'qdrant_db')
QDRANT_COLLECTION_NAME = "knowledge_base_pdfs"

def create_and_store_embeddings(chunks: List[str], source_filename: str, model: SentenceTransformer, qdrant_client: QdrantClient):
    """
    Creates embeddings and stores them in Qdrant.
    
    Args:
        chunks: List of text chunks to embed
        source_filename: Original source filename for traceability
        model: SentenceTransformer model for generating embeddings
        qdrant_client: Initialized Qdrant client
        
    Notes:
        This is a "side effect" function - its primary purpose is to perform an action
        (saving data to Qdrant), not to calculate or produce a value to be used elsewhere.
    """
    if not chunks:
        print(f"Warning: No chunks provided for {source_filename}")
        return
        
    try:
        # Generate embeddings for all chunks
        embeddings = model.encode(chunks, show_progress_bar=True)
        
        # Prepare points for Qdrant
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding.tolist(),
                payload={
                    "text": chunk, 
                    "source": source_filename,
                    "chunk_index": i
                }
            )
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        
        # Store in Qdrant
        qdrant_client.upsert(
            collection_name=QDRANT_COLLECTION_NAME,
            points=points,
            wait=True
        )
        
        print(f"Successfully stored {len(chunks)} embeddings for {os.path.basename(source_filename)}")
        
    except Exception as e:
        print(f"Error storing embeddings: {e}")

def initialize_qdrant_collection(qdrant_client: QdrantClient, vector_size: int):
    """
    Creates the Qdrant collection if it doesn't exist.
    
    Args:
        qdrant_client: Initialized Qdrant client
        vector_size: Dimension of the embedding vectors
    """
    try:
        # Check if collection exists
        qdrant_client.get_collection(collection_name=QDRANT_COLLECTION_NAME)
        print(f"Collection '{QDRANT_COLLECTION_NAME}' already exists.")
    except Exception:
        print(f"Creating new collection: '{QDRANT_COLLECTION_NAME}'")
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE
            )
        )
        print(f"Collection '{QDRANT_COLLECTION_NAME}' created successfully.")

if __name__ == "__main__":
    # Test functionality
    print(f"Qdrant storage path: {QDRANT_STORAGE_PATH}")
    print(f"Qdrant collection name: {QDRANT_COLLECTION_NAME}")