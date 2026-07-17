"""
Module: chunking.py
==================

Handles text chunking for the RAG pipeline.
"""

from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

# -------------------------------------------------------------------------
# CHUNKING CONFIGURATION
# -------------------------------------------------------------------------

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def split_text_into_chunks(text: str) -> List[str]:
    """
    Divides text into semantically meaningful chunks for embedding.
    
    Args:
        text: The input text to be chunked
        
    Returns:
        A list of text chunks
        
    Notes:
        Uses RecursiveCharacterTextSplitter which respects semantic boundaries
        by trying to split on paragraph breaks, then line breaks, then sentences,
        and only as a last resort will split on words or characters.
    """
    if not text or not text.strip():
        return []
        
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    return text_splitter.split_text(text)

if __name__ == "__main__":
    # Test functionality
    sample_text = """This is a sample text.
    It has multiple paragraphs.
    
    This is the second paragraph.
    It also has multiple sentences."""
    
    chunks = split_text_into_chunks(sample_text)
    print(f"Generated {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}: {chunk[:50]}...")