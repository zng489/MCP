"""
Module: query_knowledge_base.py
============================

Searches the vector database for relevant information based on user queries.
"""

import os
import torch
import torch.distributed as dist
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

# Avoid error in environments without distributed support
if not hasattr(dist, 'is_initialized'):
    dist.is_initialized = lambda: False

# --- Configuration ---
# Use relative path for better portability
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EMBEDDING_MODEL_PATH = os.path.join(SCRIPT_DIR, '..', 'model', 'bge-small-en-v1.5')
QDRANT_STORAGE_PATH = os.path.join(SCRIPT_DIR, '..', 'qdrant_db')
QDRANT_COLLECTION_NAME = "knowledge_base_pdfs"

def search_knowledge_base(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Searches the knowledge base for chunks relevant to the query.
    
    Args:
        query: The user's question or query
        top_k: Number of results to return
        
    Returns:
        List of dictionaries with the most relevant chunks and their metadata
    """
    try:
        # Initialize the embedding model (same used during ingestion)
        model = SentenceTransformer(EMBEDDING_MODEL_PATH)
        
        # Connect to local Qdrant
        qdrant_client = QdrantClient(path=QDRANT_STORAGE_PATH)
        
        # Convert the query to a vector
        query_vector = model.encode(query).tolist()
        
        # Search for the most similar chunks
        search_results = qdrant_client.query_points(
            collection_name=QDRANT_COLLECTION_NAME,
            query=query_vector,
            limit=top_k
        ).points

        # Format the results
        formatted_results = []
        for result in search_results:
            formatted_results.append({
                "text": result.payload["text"],
                "source": result.payload["source"],
                "score": result.score
            })
        
        # Close the client
        qdrant_client.close()
        
        return formatted_results
        
    except Exception as e:
        print(f"Error searching knowledge base: {e}")
        return []

if __name__ == "__main__":
    user_query = input("Enter your question: ")
    results = search_knowledge_base(user_query)
    
    print(f"\nResults for: '{user_query}'\n")
    for i, result in enumerate(results):
        print(f"Result {i+1} (Score: {result['score']:.4f}):")
        print(f"Source: {result['source']}")
        print(f"Text: {result['text'][:200]}...")  # Show first 200 characters
        print("-" * 50)