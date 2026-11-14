"""Rule-based resume metadata parser (the original app.py logic, moved out unchanged
so the NER parser, the app and the evaluation can all call the same code)."""

import re
from datetime import datetime

from dl_pipeline import extract_skills


def extract_metadata(text):
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    email = email_match.group(0) if email_match else "Not Found"

    phone_match = re.search(r'\+?\d[\d\s-]{8,14}\d', text)
    phone = phone_match.group(0) if phone_match else "Not Found"


    # Comprehensive keyword-based skill extraction (from GitHub repo)

    # Comprehensive keyword-based skill extraction

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


    # Experience extraction (multi-strategy heuristic from GitHub repo)

    # Experience extraction (multi-strategy heuristic)

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

    # Strategy 5 (Fallback): Compute career span from date ranges
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

    return {
        "email": email,
        "phone": phone,
        "skills": found_skills if found_skills else ["N/A"],
        "education": edu,
        "experience": exp
    }
