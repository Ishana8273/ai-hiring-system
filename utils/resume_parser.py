"""Resume text extraction. Supports PDF (PyPDF2) and plain text."""
from __future__ import annotations

import io
import logging
import re

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_file) -> str:
    """Extract text from a PDF file or file-like object."""
    try:
        from PyPDF2 import PdfReader

        if isinstance(pdf_file, str):
            reader = PdfReader(pdf_file)
        else:
            reader = PdfReader(io.BytesIO(pdf_file.read()))

        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return clean_text("\n".join(parts))
    except ImportError:
        logger.error("PyPDF2 not installed. Run: pip install PyPDF2")
        raise
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        raise


def clean_text(text: str) -> str:
    """Clean and normalize extracted text."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def extract_text_from_upload(uploaded_file) -> str:
    """Extract text from Streamlit UploadedFile, auto-detecting format."""
    filename = uploaded_file.name.lower()
    if filename.endswith(".pdf"):
        logger.info("Processing PDF: %s", uploaded_file.name)
        return extract_text_from_pdf(uploaded_file)
    else:
        logger.info("Processing text: %s", uploaded_file.name)
        content = uploaded_file.read().decode("utf-8", errors="replace")
        return clean_text(content)