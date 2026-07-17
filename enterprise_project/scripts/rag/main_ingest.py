"""
Module: main_ingest.py
======================

Incremental ingestion pipeline: detects new/modified PDFs and updates Qdrant.
"""

import torch  # pyright: ignore[reportMissingImports]
import torch.distributed as dist  # pyright: ignore[reportMissingImports]

if not hasattr(dist, "is_initialized"):
    dist.is_initialized = lambda: False

import os
import sys
import logging
from pathlib import Path

from sentence_transformers import SentenceTransformer  # pyright: ignore[reportMissingImports]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from a_file_finder import populate_knowledge_base_from_file
from b_pdf_text_extractor import extrair_texto_do_pdf_com_easyocr
from c_text_chunker import split_text_into_chunks
from d_vector_store import (
    initialize_qdrant_client,
    initialize_qdrant_collection,
    store_embeddings,
    delete_by_source,
    get_collection_info,
)
from e_metadata_tracker import (
    is_pdf_processed,
    mark_pdf_as_processed,
    get_processed_count,
    load_metadata,
    calculate_file_hash,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
MODEL_PATH = os.path.join(PROJECT_DIR, "model", "bge-small-en-v1.5")


def get_new_or_modified_pdfs():
    """Returns list of PDF paths that are new or modified since last run."""
    metadata = load_metadata()
    new_pdfs = []
    modified_pdfs = []

    for pdf_path in populate_knowledge_base_from_file("pdf"):
        pdf_name = os.path.basename(str(pdf_path))
        if pdf_name not in metadata["processed_pdfs"]:
            new_pdfs.append(pdf_path)
        elif not is_pdf_processed(str(pdf_path)):
            modified_pdfs.append(pdf_path)

    return new_pdfs, modified_pdfs


def ingest_pdf(pdf_path, model, client):
    """Process a single PDF: extract -> chunk -> embed -> store."""
    pdf_name = os.path.basename(str(pdf_path))
    logger.info(f"Processing: {pdf_name}")

    text = extrair_texto_do_pdf_com_easyocr(str(pdf_path))
    if not text.strip():
        logger.warning(f"No text extracted from {pdf_name}, skipping.")
        return 0

    chunks = split_text_into_chunks(text, source_file=str(pdf_path))
    if not chunks:
        logger.warning(f"No chunks generated from {pdf_name}, skipping.")
        return 0

    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    store_embeddings(client, chunks, embeddings)
    mark_pdf_as_processed(str(pdf_path), len(chunks))
    return len(chunks)


def run_ingestion():
    """Main ingestion pipeline with incremental update support."""
    new_pdfs, modified_pdfs = get_new_or_modified_pdfs()

    if not new_pdfs and not modified_pdfs:
        logger.info("No new or modified PDFs found. Database is up to date.")
        return

    logger.info(f"Found {len(new_pdfs)} new PDF(s) and {len(modified_pdfs)} modified PDF(s)")

    logger.info(f"Loading embedding model from: {MODEL_PATH}")
    model = SentenceTransformer(MODEL_PATH)

    client = initialize_qdrant_client()
    if client is None:
        logger.error("Could not connect to Qdrant. Aborting.")
        return

    vector_size = model.get_sentence_embedding_dimension()
    initialize_qdrant_collection(client, vector_size)

    total_chunks = 0

    for pdf_path in modified_pdfs:
        pdf_name = os.path.basename(str(pdf_path))
        logger.info(f"Re-indexing modified PDF: {pdf_name}")
        delete_by_source(client, pdf_name)
        chunks = ingest_pdf(pdf_path, model, client)
        total_chunks += chunks

    for pdf_path in new_pdfs:
        chunks = ingest_pdf(pdf_path, model, client)
        total_chunks += chunks

    info = get_collection_info(client)
    logger.info(f"Ingestion complete. Total chunks added: {total_chunks}")
    logger.info(f"Collection status: {info}")
    logger.info(f"Total PDFs tracked: {get_processed_count()}")


if __name__ == "__main__":
    run_ingestion()
