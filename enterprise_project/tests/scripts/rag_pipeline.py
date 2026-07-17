
import os
import torch
import torch.distributed as dist
from typing import List
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models

# Avoid error in environments without distributed support
if not hasattr(dist, 'is_initialized'):
    dist.is_initialized = lambda: False

# Import local modules
from scripts.rag.file_finder import populate_knowledge_base_from_file
from scripts.rag.pdf_text_extractor import extrair_texto_do_pdf_com_easyocr
from scripts.rag.text_chunker import split_text_into_chunks
from scripts.rag.vector_store import create_and_store_embeddings, QDRANT_STORAGE_PATH, QDRANT_COLLECTION_NAME

def main_embedding_generator():
    """
    Main function that orchestrates the embedding generation pipeline:
    1. Initialize models and clients
    2. Create Qdrant collection if it doesn't exist
    3. Process each PDF file:
       a. Extract text
       b. Split into chunks
       c. Generate embeddings
       d. Store in vector database
    """
    print("="*50)
    print("🚀 STARTING KNOWLEDGE BASE BUILDING PIPELINE 🚀")
    print("="*50)
    
    # Initialize the embedding model
    # Use a relative path or environment variable for better portability
    model_path = os.path.join(os.path.dirname(__file__), '..', 'model', 'bge-small-en-v1.5')
    embedding_model = SentenceTransformer(model_path)
    
    # Initialize Qdrant client
    qdrant_client = QdrantClient(path=QDRANT_STORAGE_PATH)
    
    # Create collection if it doesn't exist
    try:
        qdrant_client.get_collection(collection_name=QDRANT_COLLECTION_NAME)
        print(f"   -> Collection '{QDRANT_COLLECTION_NAME}' already exists.")
    except Exception:
        print(f"   -> Creating new collection: '{QDRANT_COLLECTION_NAME}'")
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=embedding_model.get_sentence_embedding_dimension(),
                distance=models.Distance.COSINE
            )
        )
    
    # Process each PDF file
    pdf_files = list(populate_knowledge_base_from_file("pdf"))
    print(f"\n2. Found {len(pdf_files)} files to process.")
    
    for i, pdf_path in enumerate(pdf_files):
        filename = os.path.basename(pdf_path)
        print(f"\n--- Processing file {i+1}/{len(pdf_files)}: {filename} ---")
        
        # Step 1: Extract text
        print("   -> Extracting text...")
        extracted_text = extrair_texto_do_pdf_com_easyocr(pdf_path)
        if not extracted_text.strip():
            print("   -> ⚠️ No text extracted. Skipping to next file.")
            continue
        
        # Step 2: Split into chunks
        print("   -> Splitting into chunks...")
        chunks = split_text_into_chunks(extracted_text)
        if not chunks:
            print("   -> ⚠️ No chunks generated. Skipping to next file.")
            continue
        print(f"   -> Text split into {len(chunks)} chunks.")
        
        # Step 3: Create and store embeddings
        print("   -> Generating embeddings and saving to Qdrant...")
        create_and_store_embeddings(
            chunks,
            str(pdf_path),
            embedding_model,
            qdrant_client
        )
        print(f"   -> ✅ '{filename}' processed and stored successfully.")
    
    # Close the Qdrant client
    qdrant_client.close()
    
    print("\n="*50)
    print("🎉 PIPELINE COMPLETED! Your knowledge base has been updated. 🎉")
    print("="*50)

if __name__ == "__main__":
    main_embedding_generator()