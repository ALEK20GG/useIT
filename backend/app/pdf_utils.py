"""
Utility functions for PDF processing.
"""

import os
import re
from io import BytesIO
from pathlib import Path
from typing import List

import PyPDF2


def save_pdf(file_content: bytes, filename: str, pdfs_dir: str = "pdfs") -> str:
    """
    Save a PDF file to the specified directory.
    
    Args:
        file_content: The PDF file bytes
        filename: The original filename
        pdfs_dir: Directory where PDFs should be saved (can be absolute or relative path)
        
    Returns:
        The absolute path where the PDF was saved
    """
    # Ensure the pdfs directory exists
    pdf_path = Path(pdfs_dir)
    pdf_path.mkdir(parents=True, exist_ok=True)
    
    # Sanitize filename to avoid path traversal issues
    safe_filename = os.path.basename(filename)
    if not safe_filename.lower().endswith('.pdf'):
        safe_filename += '.pdf'
    
    # Save the file
    file_path = pdf_path / safe_filename
    with open(file_path, 'wb') as f:
        f.write(file_content)
    
    return str(file_path.absolute())


def clean_extracted_text(text: str) -> str:
    """
    Clean and normalize extracted text from PDF.
    
    Removes excessive whitespace, normalizes line breaks, and fixes common extraction issues.
    """
    if not text:
        return ""
    
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    
    # Remove empty lines
    lines = [line for line in lines if line]
    
    # Rejoin with single newline (preserve paragraph structure)
    text = '\n'.join(lines)
    
    return text.strip()


def extract_text_from_pdf(file_content: bytes) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        file_content: The PDF file bytes
        
    Returns:
        The extracted text from all pages (cleaned and normalized)
    """
    text_parts: List[str] = []
    
    try:
        # PyPDF2 needs a file-like object, so we wrap bytes in BytesIO
        pdf_stream = BytesIO(file_content)
        pdf_file = PyPDF2.PdfReader(pdf_stream)
        
        print(f"  PDF has {len(pdf_file.pages)} pages")
        
        for page_num, page in enumerate(pdf_file.pages, start=1):
            try:
                text = page.extract_text()
                if text and text.strip():
                    # Clean the extracted text
                    cleaned_text = clean_extracted_text(text)
                    if cleaned_text:
                        text_parts.append(cleaned_text)
            except Exception as e:
                # Log but continue with other pages
                print(f"  Warning: Error extracting text from page {page_num}: {e}")
                continue
        
        if not text_parts:
            raise ValueError("No text could be extracted from any page")
            
    except Exception as e:
        raise ValueError(f"Failed to read PDF: {e}") from e
    
    # Join pages with double newline (paragraph separator)
    full_text = "\n\n".join(text_parts)
    
    if not full_text.strip():
        raise ValueError("PDF contains no extractable text after cleaning")
    
    print(f"  Extracted {len(full_text)} characters of text")
    
    return full_text


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Split text into overlapping chunks for embedding.
    
    Args:
        text: The text to chunk
        chunk_size: Maximum size of each chunk (in characters)
        overlap: Number of characters to overlap between chunks
        
    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks: List[str] = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Try to break at a sentence boundary if possible
        if end < len(text):
            # Look for sentence endings in the last 100 chars
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            
            if break_point > chunk_size - 200:  # If we find a good break point
                chunk = chunk[:break_point + 1]
                end = start + break_point + 1
        
        chunks.append(chunk.strip())
        start = end - overlap  # Overlap with next chunk
    
    return chunks


def extract_text_from_pdf_file(file_path: Path | str) -> str:
    """
    Extract text content from a PDF file on disk.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        The extracted text from all pages
    """
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise ValueError(f"PDF file not found: {file_path}")
    
    with open(pdf_path, 'rb') as f:
        file_content = f.read()
    
    return extract_text_from_pdf(file_content)

