"""
Module: pdf_text_extractor.py
===========================

Extracts text from PDF files using a hybrid approach combining native text extraction and OCR.
"""

import os
import fitz  # pyright: ignore[reportMissingImports]
from pathlib import Path
from pdf2image import convert_from_path  # pyright: ignore[reportMissingImports]
import easyocr  # pyright: ignore[reportMissingImports]
import numpy as np # pyright: ignore[reportMissingImports]
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extrair_texto_do_pdf_com_easyocr(pdf_path):
    """
    Extracts text from a PDF using a hybrid approach:
    1. Tries to extract native text with PyMuPDF (fitz).
    2. If a page has little text (indicating it's an image), applies OCR with EasyOCR.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted text as a string
    """
    logger.info(f"Processing file: {os.path.basename(pdf_path)}")

    try:
        doc = fitz.open(pdf_path)
        final_text = ""

        # Initialize EasyOCR reader as None.
        # It will only be loaded into memory if actually needed.
        reader = None

        # for fruta in frutas:  # Isto é iteração
        for page_num, page in enumerate(doc):
            # 1. Try to extract native text
            text = page.get_text("text").strip()
            print(text)
            # 2. Check if the page is likely an image (little or no text)
            # The threshold of '15' can be adjusted as needed.
            if len(text) < 15:
                logger.info(
                    f"Page {page_num + 1} has little native text. Applying OCR..."
                )

                # Load the EasyOCR model only the first time it's needed
                if reader is None:
                    logger.info("Loading EasyOCR model into memory...")
                    reader = easyocr.Reader(
                        ["pt", "en"]
                    )  # Languages: Portuguese and English

                # Convert the specific PDF page to an image
                try:
                    images = convert_from_path(
                        pdf_path,
                        first_page=page_num + 1,
                        last_page=page_num + 1,
                        dpi=200,  # Increasing DPI can improve OCR accuracy
                    )

                    if images:
                        image_np = np.array(images[0])

                        # Use EasyOCR to extract text from the image
                        ocr_result = reader.readtext(image_np, detail=0, paragraph=True)

                        ocr_text = "\n".join(ocr_result)
                        final_text += ocr_text + "\n"
                except Exception as e:
                    logger.error(
                        f"Error during OCR processing on page {page_num + 1}: {e}"
                    )
                    # If OCR fails, try to use whatever native text we have
                    final_text += text + "\n"

            else:
                # 3. If the page has native text, use it
                logger.info(f"Page {page_num + 1} has native text.")
                final_text += text + "\n"

        # Close the PDF file to release resources
        doc.close()
        return final_text

    except Exception as e:
        logger.error(f"Error processing {os.path.basename(pdf_path)}: {e}")
        return ""

