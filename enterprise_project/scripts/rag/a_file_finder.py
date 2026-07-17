"""
Module: file_finder.py
=====================

Finds and lists files for processing in the RAG pipeline.
"""

from collections.abc import Iterator
from pathlib import Path
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_static_dir() -> Path:
    """
    Returns the directory where files should be located. Creates it if it doesn't exist.
    
    Returns:
        Path object pointing to the static files directory
    """
    # Modificado para apontar para o diretório static/files na raiz do projeto
    # em vez de scripts/static/files
    # static_dir = Path(__file__).resolve().parent.parent / "static" / "files"
    static_dir = Path(__file__).resolve().parent.parent.parent / "static" / "files"

    if not static_dir.exists():
        logger.warning(f"Directory not found. Creating: {static_dir}")
        static_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directory created: {static_dir}")

    return static_dir

def populate_knowledge_base_from_file(format: str) -> Iterator[Path]:
    """
    Finds files with the specified extension in the static directory.
    
    Args:
        format: File extension to search for (e.g., "pdf")
        
    Yields:
        Path objects for each matching file
    """
    logger.info(f"Starting search for {format.upper()} files...")
    static_dir = get_static_dir()
    logger.info(f"Looking for files in: {static_dir}")

    files = list(static_dir.glob(f"*.{format}"))

    if not files:
        logger.warning(f"No files with extension '{format}' found.")

    logger.info(f"{len(files)} file(s) found.")

    for path in files:  
        logger.debug(f"Processing: {path.name}")
        yield path  # generator produces each path

"""
1
if __name__ == "__main__":
    # Test functionality
    print("Testing file_finder.py")
    print(f"Static directory: {get_static_dir()}")
    for path in populate_knowledge_base_from_file("pdf"):
        print(f"Found file: {path}")
"""
