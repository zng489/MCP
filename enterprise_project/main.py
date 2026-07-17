#!/usr/bin/env python3
"""
RAG Pipeline with FastMCP Runner
==============================

A unified interface for running the RAG pipeline with FastMCP integration.
"""

import os
import sys
import argparse
from pathlib import Path

# Get the absolute path of the current script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Get the project root directory (parent of current directory)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

# Add scripts directory to path
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
sys.path.append(SCRIPTS_DIR)

# Print debug information
print(f"Current directory: {CURRENT_DIR}")
print(f"Project root: {PROJECT_ROOT}")
print(f"Scripts directory: {SCRIPTS_DIR}")
print(f"Python path: {sys.path}")

# Now we can import from scripts
try:
    # Import directly from the modules (not using scripts. prefix)
    from rag_pipeline_mcp import build_knowledge_base as build_kb
    from rag_pipeline_mcp import start_mcp_server as start_server_mcp
    
    # Verify imports worked
    print("✅ Successfully imported RAG pipeline modules")
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    
    # Check if the file exists
    rag_file_path = os.path.join(SCRIPTS_DIR, "rag_pipeline_mcp.py")
    if os.path.exists(rag_file_path):
        print(f"✅ File exists: {rag_file_path}")
    else:
        print(f"❌ File does not exist: {rag_file_path}")
    
    # List files in scripts directory
    print("\nFiles in scripts directory:")
    try:
        for file in os.listdir(SCRIPTS_DIR):
            print(f"  - {file}")
    except Exception as e:
        print(f"  Error listing directory: {e}")
    
    sys.exit(1)

def build_knowledge_base():
    """Build the knowledge base from PDF files."""
    print("="*60)
    print("🚀 BUILDING KNOWLEDGE BASE")
    print("="*60)
    build_kb()

def start_server():
    """Start the FastMCP server for retrieval."""
    print("="*60)
    print("🚀 STARTING FASTMCP SERVER")
    print("="*60)
    start_server_mcp()

def main():
    parser = argparse.ArgumentParser(description="RAG Pipeline with FastMCP and Qdrant")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Build knowledge base command
    build_parser = subparsers.add_parser("build", help="Build the knowledge base from PDF files")
    
    # Start server command
    serve_parser = subparsers.add_parser("serve", help="Start the FastMCP server for retrieval")
    
    args = parser.parse_args()
    
    if args.command == "build":
        build_knowledge_base()
    elif args.command == "serve":
        start_server()
    else:
        parser.print_help()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        import traceback
        traceback.print_exc()