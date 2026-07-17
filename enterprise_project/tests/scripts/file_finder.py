"""
Module: build_knowledge_base.py
===============================

Orchestrates the processing of files with centralized logging.

HOW LOGGING WORKS:
-----------------

1. LOGGER IMPORT:
   - Imports get_logger() from shared.logging module
   - Adds 'src' to sys.path to access the enterprise_project package

2. INITIALIZATION:
   logger = get_logger(__name__, log_file="process_files.log")
   
   Parameters:
   - __name__: Module name (used to identify message source)
   - log_file: Name of the file where logs will be saved in 'project_root/logs/'

3. LOG OUTPUT:
   - Console: appears in real-time in the terminal
   - File: saved in 'logs/process_files.log' (created automatically)

4. LOG LEVELS USED:
   - logger.warning(): for warnings (e.g., directory not found)
   - logger.info(): for general information (e.g., processing started)
   - logger.debug(): for details (e.g., file processed)

5. LOG FORMAT:
   Console: "2023-05-15 14:30:45 | INFO | Starting file search..."
   File: "2023-05-15 14:30:45 | INFO | process_files:35 | Starting search..."
   (The file includes function and line where the log was generated)

6. EXECUTION FLOW:
   build_knowledge_base.py executes
   → logger records actions in console AND in logs/process_files.log
   → you see in real-time + maintain history in the file

EXAMPLE USAGE IN ANOTHER SCRIPT:
------------------------------
from enterprise_project.shared.logging import get_logger  # type: ignore[reportMissingImports]
logger = get_logger(__name__, log_file="my_script.log")
logger.info("Something happened")
"""

from collections.abc import Iterator
from pathlib import Path
import os
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from enterprise_project.shared.logging import get_logger

logger = get_logger(__name__, log_file="knowledge_base.log")


def get_static_dir() -> Path:
    """Returns the directory where files should be located. Creates it if it doesn't exist."""
    static_dir = Path(__file__).resolve().parent.parent / "static" / "files"

    if not static_dir.exists():
        logger.warning(f"Directory not found. Creating: {static_dir}")
        static_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directory created: {static_dir}")

    return static_dir


def populate_knowledge_base_from_file(format: str) -> Iterator[Path]:
    """
    Main function that orchestrates the flow.
    Checks and lists files with the specified extension.
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

if __name__ == "__main__":
    # Test functionality
    for path in populate_knowledge_base_from_file("pdf"):
        print(path)