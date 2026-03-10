# resume_parser.py - handles extracting text from PDF and DOCX resumes
# we use PyMuPDF (fitz) for PDFs and python-docx for Word files

import fitz  # this is PyMuPDF, the import name is just "fitz" which confused us at first
import docx
import os


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


def parse_resume(filepath):
    """
    Figures out what type of file we're dealing with and calls
    the right parser. We check the extension because PDF and DOCX
    files need completely different libraries to read.
    Returns a dict with the filename and the raw extracted text.
    """
    filename = os.path.basename(filepath)
    extension = os.path.splitext(filepath)[1].lower()

    # we need to check the extension first because trying to open
    # a DOCX with PyMuPDF (or a PDF with python-docx) would crash
    if extension == ".pdf":
        raw_text = parse_pdf(filepath)
    elif extension == ".docx":
        raw_text = parse_docx(filepath)
    else:
        print(f"skipping unsupported file type: {filename}")
        return None

    return {
        "filename": filename,
        "raw_text": raw_text
    }
