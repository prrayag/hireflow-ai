# resume_parser.py - handles extracting text from PDF, DOCX, DOC, and image resumes
# we use PyMuPDF (fitz) for PDFs, python-docx for Word files,
# mammoth for legacy .doc files, and pytesseract + Pillow for image OCR

import fitz  # this is PyMuPDF, the import name is just "fitz" which confused us at first
import docx
import mammoth
import pytesseract
from PIL import Image
import os

# supported file extensions grouped by type
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
DOC_EXTENSIONS = {".doc"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}

# all supported extensions combined (useful for filtering in app.py)
ALL_SUPPORTED_EXTENSIONS = PDF_EXTENSIONS | DOCX_EXTENSIONS | DOC_EXTENSIONS | IMAGE_EXTENSIONS


def parse_pdf(filepath):
    """
    Opens a PDF file and pulls out all the text from every page.
    PyMuPDF makes this pretty straightforward - just loop through pages.
    """
    text = ""
    try:
        doc = fitz.open(filepath)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"error reading PDF {filepath}: {e}")
        text = ""
    return text


def parse_docx(filepath):
    """
    Opens a DOCX file and grabs text from all paragraphs.
    python-docx treats each paragraph as a separate object so we
    just join them all together with newlines.
    """
    text = ""
    try:
        doc = docx.Document(filepath)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
    except Exception as e:
        print(f"error reading DOCX {filepath}: {e}")
        text = ""
    return text


def parse_doc(filepath):
    """
    Opens a legacy .doc file using mammoth.
    Mammoth extracts the raw text content from older Word formats.
    This is pure Python so no external binaries needed (unlike antiword).
    """
    text = ""
    try:
        with open(filepath, "rb") as f:
            result = mammoth.extract_raw_text(f)
            text = result.value
            if result.messages:
                for msg in result.messages:
                    print(f"mammoth warning for {filepath}: {msg}")
    except Exception as e:
        print(f"error reading DOC {filepath}: {e}")
        text = ""
    return text


def parse_image(filepath):
    """
    Uses Tesseract OCR to extract text from image files (PNG, JPG, TIFF, BMP, etc.).
    This is essential for scanned resume documents or screenshot resumes.
    pytesseract is a wrapper around Google's Tesseract-OCR engine.
    """
    text = ""
    try:
        img = Image.open(filepath)
        # convert to RGB if needed (some formats like TIFF can be CMYK or palette-based)
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img)
    except Exception as e:
        print(f"error OCR-ing image {filepath}: {e}")
        text = ""
    return text


def parse_resume(filepath):
    """
    Figures out what type of file we're dealing with and calls
    the right parser. We check the extension because PDF, DOCX, DOC,
    and image files all need completely different libraries to read.
    Returns a dict with the filename and the raw extracted text.
    """
    filename = os.path.basename(filepath)
    extension = os.path.splitext(filepath)[1].lower()

    if extension in PDF_EXTENSIONS:
        raw_text = parse_pdf(filepath)
    elif extension in DOCX_EXTENSIONS:
        raw_text = parse_docx(filepath)
    elif extension in DOC_EXTENSIONS:
        raw_text = parse_doc(filepath)
    elif extension in IMAGE_EXTENSIONS:
        raw_text = parse_image(filepath)
    else:
        print(f"skipping unsupported file type: {filename}")
        return None

    # if we got no text at all (empty file or failed parse), still return
    # the result so it shows up in results (with a score of 0)
    if not raw_text or not raw_text.strip():
        print(f"warning: no text extracted from {filename}")

    return {
        "filename": filename,
        "raw_text": raw_text or ""
    }
