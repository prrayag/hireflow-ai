"""Resume text extraction and metadata parsing.

Moved out of app.api_upload (where these were nested functions) so the parsing
logic can be unit-tested and reused by the evaluation scripts. The regex
strategies are unchanged; experience now also understands month/year ranges,
and skills are enriched by the NER model in ner_parser.
"""

from __future__ import annotations

import io
import re
from datetime import datetime

import fitz  # PyMuPDF

from dl_pipeline import experience_from_date_ranges, extract_skills
from ner_parser import parse_skills

ocr_reader = None


def process_file_content(filename, file_bytes):
    global ocr_reader
    text = ""
    filename_lower = filename.lower()
    if filename_lower.endswith('.pdf'):
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                text += page.get_text()
        except Exception as e:
            print(f"Error parsing PDF {filename}: {e}")
    elif filename_lower.endswith(('.jpg', '.jpeg', '.png')):
        try:
            import easyocr
            # Lazily initialize to avoid macOS fork safety crash with PyTorch
            if ocr_reader is None:
                ocr_reader = easyocr.Reader(['en'], gpu=False)
            result = ocr_reader.readtext(file_bytes, detail=0)
            text = " ".join(result)
        except Exception as e:
            print(f"Error parsing Image {filename}: {e}")

    elif filename_lower.endswith('.txt'):
        try:
            text = file_bytes.decode('utf-8', errors='ignore')
        except Exception:
            pass
    elif filename_lower.endswith('.docx'):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([p.text for p in doc.paragraphs if p.text])
        except Exception as e:
            print(f"Error parsing DOCX {filename}: {e}")
    return text


def extract_experience_years(text):
    """Years of experience using the original regex strategies plus date ranges."""
    text_lower = text.lower()
    exp = 0

    # Strategy 1: Explicit "X years of experience" or "X+ years experience"
    exp_match = re.search(r'(\d+\.?\d*)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp\b)', text_lower)
    if exp_match:
        exp = int(float(exp_match.group(1)))

    # Strategy 2: "experience of X years"
    if exp == 0:
        exp_match2 = re.search(r'(?:experience|exp)\s+(?:of\s+)?(\d+\.?\d*)\+?\s*(?:years?|yrs?)', text_lower)
        if exp_match2:
            exp = int(float(exp_match2.group(1)))

    # Strategy 3: "with X years" (common in summaries like "Engineer with 6 years")
    if exp == 0:
        exp_match3 = re.search(r'with\s+(\d+\.?\d*)\+?\s*(?:years?|yrs?)', text_lower)
        if exp_match3:
            exp = int(float(exp_match3.group(1)))

    # Strategy 4: Standalone "X years" near job-related context
    if exp == 0:
        exp_match4 = re.search(r'(\d+\.?\d*)\+?\s*(?:years?|yrs?)\s+(?:in|of|at|as|working|building|developing|designing|managing)', text_lower)
        if exp_match4:
            exp = int(float(exp_match4.group(1)))

    # Strategy 5: Sum the work date ranges ("Jan 2019 - Mar 2022", "06/2019 - Present"),
    # merging overlaps and skipping the education section. The previous year-only
    # pattern missed ranges with a month before the end year, which left
    # candidates at 0 years.
    if exp == 0:
        exp = experience_from_date_ranges(text)

    # Strategy 6 (original fallback): career span from year-only ranges.
    # Use SPAN (latest end - earliest start) NOT sum, to avoid inflation
    if exp == 0:
        date_ranges = re.findall(r'(20\d{2})\s*(?:-|to|–|—)\s*(20\d{2}|present|now|current)', text_lower)
        if date_ranges:
            all_starts = []
            all_ends = []
            for start, end in date_ranges:
                s = int(start)
                e = datetime.now().year if end in ['present', 'now', 'current'] else int(end)

                # Only consider work-era dates (after 2010) to skip education

                if s >= 2010 and e >= s:
                    all_starts.append(s)
                    all_ends.append(e)
            if all_starts and all_ends:
                exp = max(all_ends) - min(all_starts)

    if exp > 25: exp = 25 # sanity cap
    return exp


def extract_metadata(text):
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    email = email_match.group(0) if email_match else "Not Found"

    # A phone number needs at least 10 digits; this skips year ranges such as
    # "2014 - 2018" that the same pattern also matches.
    phone = next((m.group(0) for m in re.finditer(r'\+?\d[\d\s-]{8,14}\d', text)
                  if sum(ch.isdigit() for ch in m.group(0)) >= 10), "Not Found")

    # Canonical aliases are shared with JD gap analysis (for example,
    # k8s -> Kubernetes and sklearn -> scikit-learn).
    found_skills = extract_skills(text)
    text_lower = text.lower()

    # Education extraction (heuristic)
    edu = "Not Found"
    if "b.tech" in text_lower or "b.e" in text_lower or "bachelor" in text_lower or "b.sc" in text_lower or "b.des" in text_lower or "b.e." in text_lower:
        edu = "Bachelor's Degree"
    if "m.tech" in text_lower or "master" in text_lower or "mba" in text_lower or "m.sc" in text_lower or "m.s." in text_lower:
        edu = "Master's Degree"

    # Deep-learning skill extraction: the NER model adds skills the dictionary
    # does not know; dictionary matches are always kept.
    parsed = parse_skills(text, found_skills)

    return {
        "email": email,
        "phone": phone,
        "skills": parsed["skills"] if parsed["skills"] else ["N/A"],
        "education": edu,
        "experience": extract_experience_years(text),
        "ner_skills": parsed["ner_skills"],
        "ner_only_skills": parsed["ner_only_skills"],
        "soft_skills": parsed["soft_skills"],
        "skill_parser": parsed["skill_parser"],
    }
