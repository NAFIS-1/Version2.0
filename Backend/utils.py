import os
import fitz # PyMuPDF
import docx
from fastapi import HTTPException, status
from config import ALLOWED_EXTENSIONS

def allowed_file(filename: str) -> bool:
    """Checks if a file's extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts all text from a PDF file."""
    text = ""
    try:
        with fitz.open(file_path) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text()
    except Exception as e:
        print(f"Error extracting text from PDF {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting text from PDF: {e}"
        )
    return text

def extract_text_from_docx(file_path: str) -> str:
    """Extracts all text from a DOCX file."""
    try:
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"Error extracting text from DOCX {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting text from DOCX: {e}"
        )