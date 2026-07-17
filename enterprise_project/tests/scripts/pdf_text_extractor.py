"""
Module: extract_text_from_pdf.py
===============================

Extracts text from PDF files using a hybrid approach combining native text extraction and OCR.

Process flow:
------------
1. Try to extract native text from each page
2. If a page has little text (likely an image/scan), apply OCR
3. Combine all extracted text
"""

import os
import fitz  # PyMuPDF
from pathlib import Path
from pdf2image import convert_from_path
import easyocr
import numpy as np

# Optional Poppler path configuration
# POPPLER_PATH = r"path/to/poppler/bin"  # Uncomment and set if needed

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
    print(f"🚀 Processing file: {os.path.basename(pdf_path)}")
    
    try:
        doc = fitz.open(pdf_path)
        final_text = ""
        
        # Initialize EasyOCR reader as None.
        # It will only be loaded into memory if actually needed.
        reader = None 
        
        for page_num, page in enumerate(doc):
            # 1. Try to extract native text
            text = page.get_text("text").strip()
            
            # 2. Check if the page is likely an image (little or no text)
            # The threshold of '15' can be adjusted as needed.
            if len(text) < 15:
                print(f"   -> Page {page_num+1} has little native text. Applying OCR with EasyOCR...")
                
                # Load the EasyOCR model only the first time it's needed
                if reader is None:
                    print("   -> (Loading EasyOCR model into memory...)")
                    reader = easyocr.Reader(['pt', 'en'])  # Languages: Portuguese and English

                # Convert the specific PDF page to an image
                # Using first_page and last_page is much more efficient than converting the entire PDF
                try:
                    # Uncomment the poppler_path parameter if needed
                    images = convert_from_path(
                        pdf_path,
                        first_page=page_num + 1,
                        last_page=page_num + 1,
                        dpi=200  # Increasing DPI can improve OCR accuracy
                        # poppler_path=POPPLER_PATH
                    )
                    
                    if images:
                        image_np = np.array(images[0])
                        
                        # Use EasyOCR to extract text from the image
                        # detail=0 returns only the text, paragraph=True groups lines into paragraphs
                        ocr_result = reader.readtext(image_np, detail=0, paragraph=True)
                        
                        ocr_text = "\n".join(ocr_result)
                        final_text += ocr_text + "\n"
                except Exception as e:
                    print(f"   -> ⚠️ Error during OCR processing on page {page_num+1}: {e}")
                    # If OCR fails, try to use whatever native text we have
                    final_text += text + "\n"
                
            else:
                # 3. If the page has native text, use it
                print(f"   -> Page {page_num+1} has native text.")
                final_text += text + "\n"
                
        # Close the PDF file to release resources
        doc.close()
        return final_text

    except Exception as e:
        print(f"❌ Error processing {os.path.basename(pdf_path)} → {e}")
        return ""

if __name__ == "__main__":
    # Test functionality with a sample PDF if available
    import sys
    if len(sys.argv) > 1:
        sample_pdf = sys.argv[1]
        if os.path.exists(sample_pdf):
            text = extrair_texto_do_pdf_com_easyocr(sample_pdf)
            print(f"\nExtracted {len(text)} characters of text")
            print(f"Sample: {text[:200]}...")
        else:
            print(f"File not found: {sample_pdf}")
    else:
        print("Usage: python extract_text_from_pdf.py path/to/sample.pdf")