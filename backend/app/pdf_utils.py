"""
Utility functions for PDF processing.
"""

import os
import re
from io import BytesIO
from pathlib import Path

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


def extract_text_from_pdf(file_content: bytes) -> list[tuple[int, str]]:
    """
    Extract text content from a PDF file, returning per-page tuples.
    
    Args:
        file_content: The PDF file bytes
        
    Returns:
        A list of (page_number, page_text) tuples (1-based page numbers).
        Pages with no extractable text are skipped.
        
    Raises:
        ValueError: If no pages have extractable text or the PDF cannot be read.
    """
    pages: list[tuple[int, str]] = []
    
    try:
        # PyPDF2 needs a file-like object, so we wrap bytes in BytesIO
        pdf_stream = BytesIO(file_content)
        pdf_file = PyPDF2.PdfReader(pdf_stream)
        
        print(f"  PDF has {len(pdf_file.pages)} pages")
        
        for page_num, page in enumerate(pdf_file.pages, start=1):
            try:
                text = page.extract_text()
                if text and text.strip():
                    cleaned_text = clean_extracted_text(text)
                    if cleaned_text:
                        pages.append((page_num, cleaned_text))
            except Exception as e:
                # Log but continue with other pages
                print(f"  Warning: Error extracting text from page {page_num}: {e}")
                continue
        
        if not pages:
            raise ValueError("No text could be extracted from any page")
            
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to read PDF: {e}") from e
    
    total_chars = sum(len(text) for _, text in pages)
    print(f"  Extracted {total_chars} characters of text across {len(pages)} pages")
    
    return pages


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    Split text into overlapping chunks, preferring natural boundaries.

    Priority: paragraph boundary (\\n\\n) > sentence boundary (. ! ?) > whitespace > hard split
    Chunks shorter than 100 chars are merged into the previous chunk (except the last).
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            # Look for a split point in the last 200 chars of the window
            window_start = max(start, end - 200)
            window = text[window_start:end]

            split_offset = None

            # 1. Try paragraph boundary (\n\n)
            idx = window.rfind('\n\n')
            if idx != -1:
                split_offset = window_start + idx + 2  # after the \n\n

            # 2. Try sentence boundary (. ! ? followed by space or end)
            if split_offset is None:
                matches = list(re.finditer(r'[.!?](?:\s|$)', window))
                if matches:
                    last_match = matches[-1]
                    split_offset = window_start + last_match.end()

            # 3. Try whitespace
            if split_offset is None:
                idx = window.rfind(' ')
                if idx != -1:
                    split_offset = window_start + idx + 1

            # 4. Hard split
            if split_offset is None or split_offset <= start:
                split_offset = end

            chunk = text[start:split_offset].strip()
            if chunk:
                chunks.append(chunk)
            start = max(start + 1, split_offset - overlap)
        else:
            # Last chunk
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            break

    # Merge chunks shorter than 100 chars into the previous chunk (except the last)
    if len(chunks) > 1:
        merged = [chunks[0]]
        for i in range(1, len(chunks) - 1):
            if len(chunks[i]) < 100:
                merged[-1] = merged[-1] + ' ' + chunks[i]
            else:
                merged.append(chunks[i])
        merged.append(chunks[-1])  # always keep the last chunk
        chunks = merged

    return chunks


def extract_text_from_pdf_file(file_path: Path | str) -> list[tuple[int, str]]:
    """
    Extract text content from a PDF file on disk.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        A list of (page_number, page_text) tuples (1-based page numbers).
    """
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise ValueError(f"PDF file not found: {file_path}")
    
    with open(pdf_path, 'rb') as f:
        file_content = f.read()
    
    return extract_text_from_pdf(file_content)

