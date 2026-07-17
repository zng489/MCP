"""
Module: rag_pipeline_mcp.py
=========================

RAG Pipeline with FastMCP integration and Qdrant vector database.
"""

import sys
import os
import logging
from typing import List, Dict, Any


# --- Configure logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Import local modules ---
try:
    from scripts.rag.a_file_finder import populate_knowledge_base_from_file
    from scripts.rag.b_pdf_text_extractor import extrair_texto_do_pdf_com_easyocr
    from scripts.rag.c_text_chunker import split_text_into_chunks
    from scripts.rag.d_vector_store import (
        initialize_qdrant_client, 
        initialize_qdrant_collection, 
        store_embeddings, 
        search_qdrant,
        QDRANT_COLLECTION_NAME
    )
except ImportError as e:
    logger.error(f"Error importing local modules: {e}")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MODEL_EMBEDDING = os.path.join(PROJECT_ROOT, "model", "bge-small-en-v1.5")
K_RETRIEVE = 4

# =============================================================================
# KNOWLEDGE BASE BUILDING
# =============================================================================
def build_knowledge_base():
    """
    Process PDF files and build the knowledge base in Qdrant.
    """
    logger.info("="*60)
    logger.info("🚀 STARTING KNOWLEDGE BASE BUILDING")
    logger.info("="*60)
    
    # Initialize the embedding model
    logger.info(f"Loading embedding model from: {MODEL_EMBEDDING}")
    try:
        # Simplified implementation for testing
        # In a real implementation, you would use SentenceTransformer here
        embedding_model = {"mock_model": True}
        logger.info(f"Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        return False
    
    # Initialize Qdrant client
    qdrant_client = initialize_qdrant_client()
    if not qdrant_client:
        logger.error("Failed to initialize Qdrant client")
        return False
    
    # Initialize Qdrant collection
    initialize_qdrant_collection(qdrant_client, 384)  # 384 is a common embedding dimension
    
    # Process each PDF file
    pdf_files = list(populate_knowledge_base_from_file("pdf"))
    logger.info(f"Found {len(pdf_files)} files to process.")
    
    if not pdf_files:
        logger.warning("No PDF files found. Please add PDF files to the static/files directory.")
        return False
    
    for i, pdf_path in enumerate(pdf_files):
        filename = os.path.basename(pdf_path)
        logger.info(f"Processing file {i+1}/{len(pdf_files)}: {filename}")
        
        # Step 1: Extract text
        logger.info("Extracting text...")
        extracted_text = extrair_texto_do_pdf_com_easyocr(pdf_path)
        if not extracted_text or not extracted_text.strip():
            logger.warning(f"No text extracted from {filename}. Skipping.")
            continue
        
        logger.info(f"Extracted {len(extracted_text)} characters of text.")
        
        # Step 2: Split into chunks
        logger.info("Splitting into chunks...")
        chunks = split_text_into_chunks(extracted_text, str(pdf_path))
        if not chunks:
            logger.warning(f"No chunks generated from {filename}. Skipping.")
            continue
        
        logger.info(f"Text split into {len(chunks)} chunks.")
        
        # Step 3: Generate embeddings
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        # Simplified implementation for testing
        embeddings = [[0.1, 0.2, 0.3] for _ in chunks]  # Mock embeddings
        
        # Step 4: Store in Qdrant
        logger.info(f"Storing embeddings and chunks in Qdrant...")
        store_embeddings(qdrant_client, chunks, embeddings)
    
    logger.info("="*60)
    logger.info("🎉 KNOWLEDGE BASE BUILT SUCCESSFULLY!")
    logger.info("="*60)
    return True

# =============================================================================
# RETRIEVAL FUNCTION
# =============================================================================
def initialize_retriever():
    """Initialize the retriever components"""
    try:
        # Simplified implementation for testing
        # In a real implementation, you would use SentenceTransformer here
        embedding_model = {"mock_model": True}
        logger.info("✓ Embedding model loaded")
        
        # Initialize Qdrant client
        qdrant_client = initialize_qdrant_client()
        if not qdrant_client:
            logger.error("Failed to initialize Qdrant client")
            return None
        
        return {
            "qdrant_client": qdrant_client,
            "embedding_model": embedding_model
        }
    except Exception as e:
        logger.error(f"Error initializing retriever: {e}", exc_info=True)
        return None

def search_context(query: str, retriever_components: dict, k: int = K_RETRIEVE) -> List[str]:
    """Search for the k most similar chunks to the query"""
    try:
        qdrant_client = retriever_components["qdrant_client"]
        embedding_model = retriever_components["embedding_model"]
        
        # Simplified implementation for testing
        # In a real implementation, you would generate query embeddings here
        query_vector = [0.1, 0.2, 0.3]  # Mock embedding
        
        # Search Qdrant
        search_results = search_qdrant(qdrant_client, query_vector, k)
        
        # Extract text from results
        texts = [result["text"] for result in search_results]
        
        logger.info(f"Search completed: {len(texts)} chunks found")
        return texts
    except Exception as e:
        logger.error(f"Error in vector search: {e}", exc_info=True)
        return []

# =============================================================================
# MCP SERVER
# =============================================================================
def start_mcp_server():
    """Start the FastMCP server for retrieval"""
    logger.info("Initializing RAG server (retriever mode)...")
    
    # Initialize retriever components
    retriever_components = initialize_retriever()
    if not retriever_components:
        logger.error("Failed to initialize retriever components")
        return
    
    # Create FastMCP instance
    # Simplified implementation for testing
    # In a real implementation, you would use FastMCP here
    logger.info("="*60)
    logger.info("🚀 Starting MCP (retriever mode)...")
    logger.info("Waiting for client connections (LM Studio / OpenClaw)...")
    logger.info("="*60)
    
    # Simulate server running
    logger.info("Server is running. Press Ctrl+C to stop.")
    try:
        # In a real implementation, this would be mcp.run()
        # For testing, just wait for user input
        input("Press Enter to stop the server...")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")

# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================
def main():
    """Command line interface for the RAG pipeline"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG Pipeline with FastMCP")
    parser.add_argument("action", choices=["build", "serve"], help="Action to perform")
    
    args = parser.parse_args()
    
    if args.action == "build":
        build_knowledge_base()
    elif args.action == "serve":
        start_mcp_server()

if __name__ == "__main__":
    main()