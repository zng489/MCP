"""
Module: text_chunker.py
=====================

Handles text chunking for the RAG pipeline.
"""

from typing import List, Dict
import logging
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter # pyright: ignore[reportMissingImports]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# CHUNKING CONFIGURATION
# -------------------------------------------------------------------------

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def split_text_into_chunks(text: str, source_file: str = None) -> List[Dict[str, str]]:
    """
    Divides text into semantically meaningful chunks for embedding.
    
    Args:
        text: The input text to be chunked
        source_file: Source filename for traceability
        
    Returns:
        A list of dictionaries containing text chunks and metadata
        
    Notes:
        Uses RecursiveCharacterTextSplitter which respects semantic boundaries
        by trying to split on paragraph breaks, then line breaks, then sentences,
        and only as a last resort will split on words or characters.
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for chunking")
        return []
    
    # Use RecursiveCharacterTextSplitter for intelligent chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    # Split the text into chunks
    chunks = text_splitter.split_text(text)
    
    # Add metadata to chunks
    result = []
    for i, chunk in enumerate(chunks):
        chunk_dict = {
            "text": chunk,
            "chunk_index": i
        }
        if source_file:
            chunk_dict["source"] = os.path.basename(source_file)
        
        result.append(chunk_dict)
    
    logger.info(f"Split text into {len(result)} chunks")
    return result

'''
if __name__ == "__main__":
    # Test functionality
    sample_text = """This is a sample text.
    
    It has multiple paragraphs.
    
    This is the second paragraph.
    It also has multiple sentences."""
    
    chunks = split_text_into_chunks(sample_text)
    print(f"Generated {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}: {chunk['text'][:50]}...")

'''