"""
Utilities for extracting and chunking text from uploaded documents.
"""

import re
from io import BytesIO

import PyPDF2


def clean_extracted_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]
    return '\n'.join(lines).strip()


def extract_text_from_pdf(file_content: bytes, max_pages: int = 200) -> list[tuple[int, str]]:
    """Extract text from a PDF, capped at max_pages to prevent OOM on huge files."""
    pages: list[tuple[int, str]] = []
    try:
        pdf_file = PyPDF2.PdfReader(BytesIO(file_content))
        total_pages = len(pdf_file.pages)
        if total_pages > max_pages:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                f"PDF has {total_pages} pages; extracting only first {max_pages}."
            )
        for page_num, page in enumerate(pdf_file.pages[:max_pages], start=1):
            try:
                text = page.extract_text()
                if text and text.strip():
                    cleaned = clean_extracted_text(text)
                    if cleaned:
                        pages.append((page_num, cleaned))
            except Exception as e:
                print(f"  Warning: Error extracting text from page {page_num}: {e}")
        if not pages:
            raise ValueError("No text could be extracted from any page")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to read PDF: {e}") from e
    return pages


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    if not text or not text.strip():
        return []
    text = text.strip()
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            window_start = max(start, end - 200)
            window = text[window_start:end]
            split_offset = None
            idx = window.rfind('\n\n')
            if idx != -1:
                split_offset = window_start + idx + 2
            if split_offset is None:
                matches = list(re.finditer(r'[.!?](?:\s|$)', window))
                if matches:
                    split_offset = window_start + matches[-1].end()
            if split_offset is None:
                idx = window.rfind(' ')
                if idx != -1:
                    split_offset = window_start + idx + 1
            if split_offset is None or split_offset <= start:
                split_offset = end
            chunk = text[start:split_offset].strip()
            if chunk:
                chunks.append(chunk)
            start = max(start + 1, split_offset - overlap)
        else:
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            break
    if len(chunks) > 1:
        merged = [chunks[0]]
        for i in range(1, len(chunks) - 1):
            if len(chunks[i]) < 100:
                merged[-1] = merged[-1] + ' ' + chunks[i]
            else:
                merged.append(chunks[i])
        merged.append(chunks[-1])
        chunks = merged
    return chunks
