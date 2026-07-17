"""
Module: metadata_tracker.py
===========================

Tracks which PDF files have already been processed to enable incremental updates.
"""

import json
import hashlib
import os
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

METADATA_FILE = "processed_pdfs.json"


def get_metadata_path() -> Path:
    """Returns the path to the metadata JSON file."""
    return Path(__file__).resolve().parent / METADATA_FILE


def calculate_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of a file to detect changes."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def load_metadata() -> Dict:
    """Load the metadata of processed PDFs."""
    metadata_path = get_metadata_path()
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_pdfs": {}}


def save_metadata(metadata: Dict) -> None:
    """Save the metadata of processed PDFs."""
    metadata_path = get_metadata_path()
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def is_pdf_processed(pdf_path: str) -> bool:
    """Check if a PDF has already been processed and hasn't changed."""
    metadata = load_metadata()
    pdf_name = os.path.basename(pdf_path)

    if pdf_name not in metadata["processed_pdfs"]:
        return False

    current_hash = calculate_file_hash(pdf_path)
    stored_hash = metadata["processed_pdfs"][pdf_name].get("hash", "")

    return current_hash == stored_hash


def mark_pdf_as_processed(pdf_path: str, chunks_count: int) -> None:
    """Mark a PDF as processed with its metadata."""
    metadata = load_metadata()
    pdf_name = os.path.basename(pdf_path)

    metadata["processed_pdfs"][pdf_name] = {
        "hash": calculate_file_hash(pdf_path),
        "chunks_count": chunks_count,
        "path": str(pdf_path)
    }

    save_metadata(metadata)
    logger.info(f"Marked '{pdf_name}' as processed ({chunks_count} chunks)")


def get_processed_count() -> int:
    """Get the number of processed PDFs."""
    metadata = load_metadata()
    return len(metadata["processed_pdfs"])


def clear_metadata() -> None:
    """Clear all metadata (use before full rebuild)."""
    metadata_path = get_metadata_path()
    if metadata_path.exists():
        metadata_path.unlink()
    logger.info("Metadata cleared")
