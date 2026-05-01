import os
import re
import datetime


SCORING_WEIGHTS = {
    "jd_skill_overlap":   0.22,   # Direct keyword match
    "skills_match":       0.15,   # BERT semantic similarity
    "experience":         0.13,   # Years of WORK experience only
    "certificates":       0.10,   # Relevant certificates
    "contact_info":       0.05,   # Has email, phone, linkedin
    "skills_count":       0.10,   # Raw count of distinct skills
    "project_relevance":  0.15,   # Relevant projects matching JD
    "education_quality":  0.10,   # Degree level + field relevance
}
STRONG_THRESHOLD = 0.5  

# Normalisation cap for experience years
EXPERIENCE_NORM_CAP = 15.0

# Experience floor: fresh grads with 0 detected years still get this baseline
EXPERIENCE_FLOOR = 0.1


SKILL_KEYWORDS = [
    # IT & Software
    "python", "java", "javascript", "sql", "react", "machine learning", "data analysis", "aws", "docker",
    "kubernetes", "git", "html", "css", "node.js", "flask", "tensorflow", "pandas", "mongodb", "rest api",
    "agile", "c++", "c#", "linux", "cloud computing", "rust", "go", "typescript", "ruby", "django", "vue.js",
    "angular", "spring boot", "postgresql", "mysql", "redis", "elasticsearch", "graphql", "microservices",
    "ci/cd", "jenkins", "terraform", "ansible", "azure", "gcp", "data science", "deep learning", "nlp",
    "computer vision", "cybersecurity", "penetration testing", "scrum", "jira",

    # Marketing & Sales
    "seo", "sem", "content marketing", "social media management", "b2b sales", "crm", "google analytics",
    "email marketing", "market research", "brand management", "digital marketing", "ppc", "google ads",
    "facebook ads", "copywriting", "public relations", "salesforce", "hubspot", "lead generation",
    "conversion rate optimization", "a/b testing", "affiliate marketing", "influencer marketing", "event planning",
    "product marketing", "marketing automation", "customer success", "account management", "cold calling",
    "negotiation", "sales presentations", "business development", "market analysis", "competitive intelligence",
    "growth hacking", "e-commerce", "shopify", "wordpress", "adobe creative suite", "graphic design",
    "video editing", "data visualization", "tableau", "communication skills", "b2c sales", "sales strategy",
    "key account management", "churn reduction", "onboarding", "retention strategies",

    # Finance & Accounting
    "accounting", "financial modeling", "budgeting", "forecasting", "excel", "quickbooks", "tax preparation",
    "auditing", "risk management", "payroll", "financial analysis", "cash flow management", "general ledger",
    "accounts payable", "accounts receivable", "reconciliation", "gaap", "ifrs", "corporate finance",
    "investment banking", "portfolio management", "wealth management", "credit analysis", "quantitative analysis",
    "mergers and acquisitions", "due diligence", "private equity", "venture capital", "asset management",
    "financial reporting", "compliance", "sec reporting", "sarbanes-oxley", "erisa", "treasury", "capital budgeting",
    "variance analysis", "cost accounting", "bookkeeping", "xero", "sap", "oracle e-business suite", "power bi",
    "vba", "sql for finance", "data mining", "fraud detection", "anti-money laundering", "kyc", "macroeconomics",

    # Pharma & Healthcare
    "clinical trials", "fda regulations", "gmp", "glp", "quality assurance", "pharmacovigilance", "sop development",
    "biostatistics", "drug development", "patient care", "medical billing", "healthcare administration", "emr",
    "ehr", "epic", "cerner", "hipaa compliance", "medical terminology", "nursing", "triage", "phlebotomy",
    "vital signs", "cpr", "bls", "acls", "infection control", "medication administration", "pharmacology",
    "toxicology", "biochemistry", "molecular biology", "cell culture", "pcr", "elisa", "chromatography", "hplc",
    "mass spectrometry", "medical coding", "icd-10", "cpt coding", "clinical research", "regulatory affairs",
    "medical writing", "data management", "health informatics", "public health", "epidemiology",
    "healthcare consulting", "telehealth", "patient scheduling",

    # Mechanical & Engineering
    "autocad", "solidworks", "cad/cam", "thermodynamics", "hvac", "robotics", "six sigma", "lean manufacturing",
    "fluid mechanics", "project management", "mechanical design", "fea", "ansys", "matlab", "creo", "catia",
    "mechatronics", "plc programming", "automation", "manufacturing engineering", "qa/qc", "root cause analysis",
    "fmea", "dfm", "gd&t", "material science", "metallurgy", "machining", "cnc programming", "welding", "pneumatics",
    "hydraulics", "supply chain management", "inventory control", "logistics", "aerospace engineering",
    "automotive engineering", "civil engineering", "structural analysis", "electrical engineering", "circuit design",
    "pcb design", "microcontrollers", "iot", "systems engineering", "agile hardware", "scada", "hmi",
    "industrial engineering", "ergonomics",

    # HR & Operations
    "talent acquisition", "onboarding", "employee relations", "performance management", "supply chain",
    "logistics", "inventory management", "procurement", "recruiting", "sourcing", "applicant tracking systems",
    "workday", "bamboo hr", "adp", "benefits administration", "compensation", "payroll processing", "hris",
    "organizational development", "training and development", "employee engagement", "diversity and inclusion",
    "conflict resolution", "labor law", "osha compliance", "fmla", "workforce planning", "succession planning",
    "change management", "operations management", "business process improvement", "six sigma green belt",
    "lean methodologies", "kaizen", "facility management", "vendor management", "contract negotiation",
    "strategic planning", "key performance indicators", "okrs", "project coordination", "event management",
    "timeline management", "resource allocation", "budget tracking", "quality control", "customer service",
    "client relations", "dispatching", "fleet management"
]

# ============================================================
# Section Splitting - Parses resume into logical sections
# ============================================================

# Patterns that identify section headings in resumes
# Supports both standalone headings (e.g., "SKILLS") and
# inline headings with content (e.g., "Skills: Python, Java")
_SECTION_PATTERNS = {
    "work": re.compile(
        r'^\s*(?:work\s*experience|professional\s*experience|employment\s*history|'
        r'employment|work\s*history|career\s*history|career\s*summary|'
        r'professional\s*background|job\s*experience|positions?\s*held|'
        r'relevant\s*experience|internships?\s*(?:&|and)?\s*experience|'
        r'internship|internships|work)\s*:?\s*$',
        re.IGNORECASE
    ),
    "education": re.compile(
        r'^\s*(?:education|academic\s*background|academic\s*qualifications?|'
        r'educational\s*qualifications?|academic\s*details|academic\s*profile|'
        r'qualifications?|scholastic\s*record|degrees?)\s*:?\s*$',
        re.IGNORECASE
    ),
    "projects": re.compile(
        r'^\s*(?:projects?|academic\s*projects?|personal\s*projects?|'
        r'key\s*projects?|major\s*projects?|notable\s*projects?|'
        r'capstone\s*projects?|course\s*projects?|coursework\s*projects?|'
        r'mini\s*projects?|side\s*projects?)\s*:?\s*$',
        re.IGNORECASE
    ),
    "skills": re.compile(
        r'^\s*(?:skills?|technical\s*skills?|core\s*competenc(?:ies|e)|'
        r'key\s*skills?|areas?\s*of\s*expertise|proficienc(?:ies|y)|'
        r'technologies|tools?\s*(?:&|and)?\s*technologies)\s*:?\s*$',
        re.IGNORECASE
    ),
    "certificates": re.compile(
        r'^\s*(?:certifications?|certificates?|licenses?\s*(?:&|and)?\s*certifications?|'
        r'professional\s*certifications?|training|courses)\s*:?\s*$',
        re.IGNORECASE
    ),
    "summary": re.compile(
        r'^\s*(?:summary|objective|profile|about\s*me|personal\s*statement|'
        r'career\s*objective|professional\s*summary)\s*:?\s*$',
        re.IGNORECASE
    ),
}

# Inline section heading pattern: "HEADING: content on same line"
# E.g., "Skills: Python, Java, AWS" or "Experience: 5 years in..."
_INLINE_SECTION_PATTERNS = {
    "work": re.compile(
        r'^\s*(?:work\s*experience|professional\s*experience|employment\s*history|'
        r'employment|work\s*history)\s*:\s*\S',
        re.IGNORECASE
    ),
    "education": re.compile(
        r'^\s*(?:education|academic\s*background|qualifications?)\s*:\s*\S',
        re.IGNORECASE
    ),
    "projects": re.compile(
        r'^\s*(?:projects?|academic\s*projects?|personal\s*projects?|'
        r'key\s*projects?|major\s*projects?)\s*:\s*\S',
        re.IGNORECASE
    ),
    "skills": re.compile(
        r'^\s*(?:skills?|technical\s*skills?|core\s*competenc(?:ies|e)|'
        r'key\s*skills?)\s*:\s*\S',
        re.IGNORECASE
    ),
    "certificates": re.compile(
        r'^\s*(?:certifications?|certificates?|professional\s*certifications?)\s*:\s*\S',
        re.IGNORECASE
    ),
    "summary": re.compile(
        r'^\s*(?:summary|objective|profile|career\s*objective|professional\s*summary)\s*:\s*\S',
        re.IGNORECASE
    ),
}

# Keywords that indicate education context (used as fallback when sections can't be parsed)
_EDUCATION_CONTEXT_KEYWORDS = re.compile(
    r'(?:b\.?tech|m\.?tech|b\.?sc|m\.?sc|b\.?e\b|m\.?e\b|b\.?a\b|m\.?a\b|b\.?com|m\.?com|'
    r'bachelor|master|ph\.?d|diploma|degree|university|college|institute|'
    r'school|gpa|cgpa|percentage|semester|graduated|graduation|'
    r'higher\s*secondary|hsc|ssc|10th|12th|board|cbse|icse|'
    r'mba|bba|bca|mca|enrolled)',
    re.IGNORECASE
)

# Keywords that indicate project context
_PROJECT_CONTEXT_KEYWORDS = re.compile(
    r'(?:project|capstone|mini[\s\-]?project|course\s*work|coursework|'
    r'hackathon|competition|challenge|assignment|thesis|dissertation|'
    r'research\s*paper|paper\s*titled|paper\s*on)',
    re.IGNORECASE
)

# Keywords that indicate actual work/employment context
_WORK_CONTEXT_KEYWORDS = re.compile(
    r'(?:worked\s*(?:at|for|with|as)|employed\s*(?:at|by)|'
    r'job\s*(?:title|role|position)|designation|company|organization|'
    r'responsibilities|role\s*(?:and|&)\s*responsibilities|'
    r'key\s*responsibilities|duties|reporting\s*to|'
    r'full[\s\-]?time|part[\s\-]?time|contract|freelance|'
    r'team\s*(?:lead|leader|manager|member|size)|managed\s*a\s*team|'
    r'pvt\.?\s*ltd|private\s*limited|inc\.?|corp\.?|llc|'
    r'technologies|solutions|services|consulting|'
    r'software\s*(?:engineer|developer)|analyst|manager|'
    r'developer|engineer|consultant|associate|executive|'
    r'intern\s+at|interned\s+at)',
    re.IGNORECASE
)

# Education degree patterns for quality scoring
_DEGREE_PATTERNS = {
    "phd": re.compile(r'\b(?:ph\.?d|doctorate|doctor\s*of\s*philosophy)\b', re.IGNORECASE),
    "masters": re.compile(
        r'\b(?:m\.?tech|m\.?sc|m\.?s\b|m\.?e\b|m\.?a\b|m\.?com|mba|mca|'
        r'master(?:\'?s)?(?:\s*of|\s*in|\s*degree)?)\b',
        re.IGNORECASE
    ),
    "bachelors": re.compile(
        r'\b(?:b\.?tech|b\.?sc|b\.?s\b|b\.?e\b|b\.?a\b|b\.?com|bba|bca|'
        r'bachelor(?:\'?s)?(?:\s*of|\s*in|\s*degree)?)\b',
        re.IGNORECASE
    ),
    "diploma": re.compile(
        r'\b(?:diploma|associate(?:\'?s)?\s*degree|certificate\s*program)\b',
        re.IGNORECASE
    ),
}

# Degree level scores
_DEGREE_SCORES = {
    "phd": 1.0,
    "masters": 0.8,
    "bachelors": 0.6,
    "diploma": 0.4,
}

# JD-related term expansion for common role descriptions
_JD_RELATED_TERMS = {
    "web development": ["html", "css", "javascript", "react", "angular", "vue.js", "node.js", "django", "flask"],
    "full stack": ["html", "css", "javascript", "react", "node.js", "sql", "mongodb", "postgresql", "mysql"],
    "frontend": ["html", "css", "javascript", "react", "angular", "vue.js", "typescript"],
    "backend": ["node.js", "python", "java", "sql", "mongodb", "postgresql", "flask", "django", "spring boot"],
    "devops": ["docker", "kubernetes", "jenkins", "ci/cd", "terraform", "ansible", "aws", "azure", "gcp"],
    "data engineer": ["sql", "python", "pandas", "data analysis", "data science", "tensorflow"],
    "mobile development": ["react", "javascript", "typescript", "flutter", "swift"],
}


# ============================================================
# Section Splitting
# ============================================================

def split_resume_sections(text):
    """
    Splits resume raw text into named sections based on common headings.
    Returns a dict like:
        {"work": "...", "education": "...", "projects": "...", "other": "..."}
    Supports both standalone headings and inline "HEADING: content" patterns.
    If no clear sections found, uses keyword-based context detection as fallback.
    """
    text = str(text)
    lines = text.split('\n')

    sections = {
        "work": [],
        "education": [],
        "projects": [],
        "skills": [],
        "certificates": [],
        "summary": [],
        "other": [],
    }

    current_section = "other"
    section_found = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            sections[current_section].append(line)
            continue

        # Check if this line is a standalone section heading
        matched_section = None
        for section_name, pattern in _SECTION_PATTERNS.items():
            if pattern.match(stripped):
                matched_section = section_name
                section_found = True
                break

        if matched_section:
            current_section = matched_section
        else:
            # Check for inline headings like "Skills: Python, Java"
            inline_matched = None
            for section_name, pattern in _INLINE_SECTION_PATTERNS.items():
                if pattern.match(stripped):
                    inline_matched = section_name
                    section_found = True
                    break

            if inline_matched:
                current_section = inline_matched
                # Extract the content after the colon and add it to the section
                colon_pos = stripped.find(':')
                if colon_pos >= 0:
                    content_after = stripped[colon_pos + 1:].strip()
                    if content_after:
                        sections[current_section].append(content_after)
            else:
                sections[current_section].append(line)

    # Convert lists to strings
    result = {k: '\n'.join(v) for k, v in sections.items()}
    result["_sections_found"] = section_found

    return result


# ============================================================
# Context Detection Helpers
# ============================================================

def is_education_context(surrounding_text):
    """Check if the surrounding text (a few lines around a date range) is education-related."""
    return bool(_EDUCATION_CONTEXT_KEYWORDS.search(surrounding_text))


def is_project_context(surrounding_text):
    """Check if the surrounding text is project-related."""
    return bool(_PROJECT_CONTEXT_KEYWORDS.search(surrounding_text))


def is_work_context(surrounding_text):
    """Check if the surrounding text is work/employment-related."""
    return bool(_WORK_CONTEXT_KEYWORDS.search(surrounding_text))


# ============================================================
# Feature Extraction
# ============================================================

def count_skills(matched_skills):
    """Returns the raw count of matched skills."""
    if isinstance(matched_skills, list):
        return len(matched_skills)
    # Handle pandas NaN or raw text
    import pandas as pd
    if pd.isna(matched_skills):
        return 0
    text = str(matched_skills).lower()
    count = 0
    for s in SKILL_KEYWORDS:
        pattern = r'\b' + re.escape(s) + r'\b'
        if re.search(pattern, text):
            count += 1
    return count


def has_contact_info(text):
    """Returns 1 if the text contains an email, phone number, or LinkedIn URL."""
    text = str(text).lower()
    has_email    = bool(re.search(r'[\w\.-]+@[\w\.-]+', text))
    has_phone    = bool(re.search(r'[\+\(]?[1-9][0-9 .\-\(\)]{8,}[0-9]', text))
    has_linkedin = 'linkedin.com' in text
    return 1 if (has_email or has_phone or has_linkedin) else 0


def has_work_experience(text):
    """
    Returns 1 if ACTUAL work experience is found (not education or project timelines).
    Uses section-aware parsing: only looks for experience indicators in the work section.
    Falls back to context-based detection if sections can't be parsed.
    """
    text = str(text)
    sections = split_resume_sections(text)

    work_text = sections.get("work", "").lower()

    if sections["_sections_found"] and work_text.strip():
        # Section headers were found and we have work section content
        has_keywords = bool(re.search(
            r'(worked at|employed at|years of experience|work experience|'
            r'professional experience|job role|designation|responsibilities)',
            work_text
        ))
        has_dates = bool(re.search(
            r'(20[0-2][0-9]\s*[-–to]+\s*(20[0-2][0-9]|present|now|current))',
            work_text
        ))
        return 1 if (has_keywords or has_dates) else 0

    # Fallback: no clear section headers found — use full text but with context filtering
    text_lower = text.lower()
    lines = text_lower.split('\n')

    for i, line in enumerate(lines):
        # Look for date ranges in this line
        if re.search(r'(20[0-2][0-9]\s*[-–to]+\s*(20[0-2][0-9]|present|now|current))', line):
            # Evaluate context only on the current line to prevent overlapping with adjacent OCR blocks
            context = line

            # Only count as experience if it's work context, not education or project
            if is_education_context(context) or is_project_context(context):
                continue
            if is_work_context(context):
                return 1
            # If no clear context, still check if it's NOT education/project
            if not is_education_context(context) and not is_project_context(context):
                if re.search(r'(pvt|ltd|inc|corp|llc|company|firm|technologies|solutions|services)', context):
                    return 1

    # Also check for explicit "X years of experience" pattern anywhere
    if re.search(r'\d+\s*\+?\s*years?\s+of\s+(?:work\s+)?experience', text_lower):
        return 1
    if re.search(r'(worked at|employed at|working at|employment history)', text_lower):
        return 1

    return 0


def extract_experience_years(text):
    """
    Extracts years of WORK experience only.
    Ignores education timelines (degree durations) and project timelines.
    Uses section-aware parsing when possible, falls back to context detection.
    """
    text = str(text)
    current_year = datetime.datetime.now().year
    sections = split_resume_sections(text)

    work_text = sections.get("work", "")

    # Strategy 1: If we have a clear work section, use only that
    if sections["_sections_found"] and work_text.strip():
        work_lower = work_text.lower()

        # Look for explicit "X years of experience"
        match = re.search(r'(\d+)\s*\+?\s*years?\s*(of\s+)?(work\s+)?(experience)?', work_lower)
        if match:
            return min(int(match.group(1)), 25)

        # Sum up date ranges in the work section only
        total_years = 0
        date_ranges = re.finditer(
            r'(20[0-2][0-9])[\s\-to–]+(?:[a-z]+\s+)?(20[0-2][0-9]|present|now|current)',
            work_lower
        )
        for dr in date_ranges:
            start_year = int(dr.group(1))
            end_str = dr.group(2)
            end_year = current_year if end_str in ['present', 'now', 'current'] else int(end_str)
            if end_year >= start_year:
                total_years += max(end_year - start_year, 1)

        if total_years > 0:
            return min(total_years, 25)
        
        # If strategy 1 found 0 years but a work section existed, 
        # fall through to strategy 2 (entire document scan) just in case
        # OCR scrambled the sections.

    # Strategy 2: Fallback — context-based filtering on full text
    text_lower = text.lower()

    # First check for explicit "X years of experience" (high confidence)
    match = re.search(r'(\d+)\s*\+?\s*years?\s+of\s+(?:work\s+)?experience', text_lower)
    if match:
        return min(int(match.group(1)), 25)

    # Now process date ranges with context awareness
    lines = text_lower.split('\n')
    total_years = 0

    for i, line in enumerate(lines):
        date_ranges = list(re.finditer(
            r'(20[0-2][0-9])[\s\-to–]+(?:[a-z]+\s+)?(20[0-2][0-9]|present|now|current)',
            line
        ))

        if not date_ranges:
            continue

        # Evaluate context only on the current line to prevent overlapping with adjacent OCR blocks
        context = line

        # Skip education and project timelines
        if is_education_context(context):
            continue
        if is_project_context(context):
            continue

        # Count this date range as work experience
        for dr in date_ranges:
            start_year = int(dr.group(1))
            end_str = dr.group(2)
            end_year = current_year if end_str in ['present', 'now', 'current'] else int(end_str)
            if end_year >= start_year:
                total_years += max(end_year - start_year, 1)

    if total_years > 0:
        return min(total_years, 25)

    return 0


# ============================================================
# Project Extraction & Splitting
# ============================================================

def extract_projects(text):
    """
    Extracts individual project descriptions from the resume.
    Returns a list of project text strings.
    """
    text = str(text)
    sections = split_resume_sections(text)

    project_text = sections.get("projects", "")

    if sections["_sections_found"] and project_text.strip():
        # We have a clear projects section — split it into individual projects
        return split_individual_projects(project_text)

    # Fallback: look for project-like blocks in the full text
    projects = []
    lines = text.split('\n')

    in_project = False
    current_project = []

    for line in lines:
        stripped = line.strip().lower()

        # Detect project headings like "Project: XYZ" or "Project Title: XYZ"
        if re.match(r'(?:project\s*(?:title|name)?\s*[:–\-])', stripped):
            if current_project:
                projects.append('\n'.join(current_project))
            current_project = [line]
            in_project = True
        elif in_project:
            # Check if we've hit a new section heading (exit project block)
            is_heading = False
            for pattern in _SECTION_PATTERNS.values():
                if pattern.match(line.strip()):
                    is_heading = True
                    break
            if is_heading:
                if current_project:
                    projects.append('\n'.join(current_project))
                    current_project = []
                in_project = False
            else:
                current_project.append(line)

    if current_project:
        projects.append('\n'.join(current_project))

    return projects


def split_individual_projects(project_section_text):
    """
    Splits a project section into individual projects.
    Uses bullet points, numbered lists, date ranges, title-case heuristics,
    or fallback chunking.
    """
    lines = project_section_text.split('\n')
    projects = []
    current_project = []

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if current_project:
                proj_text = '\n'.join(current_project)
                if len(proj_text.strip()) > 15:
                    projects.append(proj_text)
                current_project = []
            continue

        # Extended bullet characters incl. corrupted ones like ò, and _
        bullet_pattern = r'^(?:[\u2022\u2023\u25E6\u2043\u2219•●○◦►▸▹\-\*ò_~]\s*|\d+[\.\\)]\s+|(?:project\s*(?:\d+|[a-z])?\s*[:–\-])|(?:title\s*[:–\-]))'
        is_bullet = bool(re.match(bullet_pattern, stripped, re.IGNORECASE))

        # Does it contain a date range on this line? (common for project headers)
        has_date_range = bool(re.search(r'(?:20[0-2][0-9]\s*[-to–]+\s*(?:20[0-2][0-9]|present|now|current|developing))', stripped, re.IGNORECASE))

        # Title-case heuristic: short line, mostly title-cased words, after a blank line
        # E.g., "E-commerce Website" or "AI Chatbot System"
        is_title_case = False
        if len(stripped) < 80 and not is_bullet and not has_date_range:
            words = stripped.split()
            # At least 2 words, most of them capitalized (ignoring small words)
            small_words = {'a', 'an', 'the', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by', '&', '-', '–'}
            if len(words) >= 2:
                cap_words = [w for w in words if w.lower() in small_words or w[0].isupper()]
                if len(cap_words) >= len(words) * 0.7:
                    # Check that the previous line was blank or this is the first line
                    prev_blank = (idx == 0) or (not lines[idx - 1].strip())
                    if prev_blank:
                        is_title_case = True

        is_new_project = is_bullet or has_date_range or is_title_case

        if is_new_project and current_project:
            proj_text = '\n'.join(current_project)
            if len(proj_text.strip()) > 15:
                projects.append(proj_text)
            current_project = [line]
        else:
            current_project.append(line)

    if current_project:
        proj_text = '\n'.join(current_project)
        if len(proj_text.strip()) > 15:
            projects.append(proj_text)

    # Fallback chunking if we STILL only have 1 giant project
    if len(projects) <= 1 and len(project_section_text.strip()) > 300:
        chunks = []
        curr = []
        for line in lines:
            if not line.strip():
                continue
            curr.append(line)
            # ~300 chars per chunk to avoid Sentence-BERT truncation
            if sum(len(l) for l in curr) > 300:
                chunks.append('\n'.join(curr))
                curr = []
        if curr:
            chunks.append('\n'.join(curr))
        return chunks

    if not projects and len(project_section_text.strip()) > 15:
        projects = [project_section_text]

    return projects


# ============================================================
# Skill Matching
# ============================================================

def get_matched_skills(raw_text):
    """Finds which baseline skills are explicitly in the text (for dashboard display).
    Uses word-boundary regex to prevent false positives like 'go' matching 'google'."""
    text_lower = raw_text.lower()
    matched = []
    for s in SKILL_KEYWORDS:
        # Build a word-boundary pattern. re.escape handles special chars like c++, c#, etc.
        pattern = r'\b' + re.escape(s) + r'\b'
        if re.search(pattern, text_lower):
            matched.append(s)
    return matched


def get_jd_skills(job_description):
    """Extracts which SKILL_KEYWORDS are mentioned in the JD itself.
    Also extracts related terms from role descriptions and simple n-grams."""
    if not job_description or not job_description.strip():
        return []

    jd_lower = job_description.lower()
    jd_skills = []

    # 1. Match against the vocabulary
    for s in SKILL_KEYWORDS:
        pattern = r'\b' + re.escape(s) + r'\b'
        if re.search(pattern, jd_lower):
            jd_skills.append(s)

    # 2. Expand related terms via role description mapping
    for phrase, related_skills in _JD_RELATED_TERMS.items():
        if phrase in jd_lower:
            for skill in related_skills:
                if skill not in jd_skills:
                    jd_skills.append(skill)

    # 3. Extract n-grams from JD that look like skill/tool names
    #    (2-3 word phrases that are title-cased or contain technical patterns)
    jd_words = re.findall(r'[A-Za-z][A-Za-z0-9\+\#\.\-/]{1,}', job_description)
    for i in range(len(jd_words)):
        # Bigrams
        if i + 1 < len(jd_words):
            bigram = f"{jd_words[i]} {jd_words[i+1]}".lower()
            if bigram not in jd_skills and len(bigram) > 5:
                # Only add if it looks technical (not common English)
                common_words = {'the', 'and', 'for', 'with', 'has', 'have', 'are', 'was', 'will', 'can',
                               'should', 'must', 'our', 'their', 'this', 'that', 'from', 'into', 'also',
                               'need', 'looking', 'seeking', 'required', 'preferred', 'experience', 'years',
                               'strong', 'good', 'excellent', 'ability', 'team', 'work', 'working'}
                if jd_words[i].lower() not in common_words and jd_words[i+1].lower() not in common_words:
                    # Check if it matches something in any resume (skip for now, just add)
                    pass  # n-gram expansion is handled by BERT similarity instead

    return jd_skills


def compute_jd_overlap(matched_skills, jd_skills):
    """Computes what fraction of JD-required skills are found in the resume.
    Returns a score from 0.0 to 1.0."""
    if not jd_skills:
        return 0.0

    matched_set = set(matched_skills)
    jd_set = set(jd_skills)

    overlap = matched_set & jd_set

    # Score: fraction of JD skills found in resume
    return len(overlap) / len(jd_set)


# ============================================================
# Education Quality Scoring
# ============================================================

def extract_education_quality(text, job_description=""):
    """
    Scores the candidate's education quality from 0.0 to 1.0.
    Considers:
    - Degree level (PhD=1.0, Masters=0.8, Bachelors=0.6, Diploma=0.4, None=0.0)
    - Field relevance to the JD (bonus if the degree field matches JD keywords)

    Returns a float score between 0.0 and 1.0.
    """
    text = str(text)
    sections = split_resume_sections(text)

    # Prefer the education section, but fall back to full text
    edu_text = sections.get("education", "")
    if not edu_text.strip():
        edu_text = text

    edu_lower = edu_text.lower()

    # Find the highest degree level
    degree_score = 0.0
    for degree_name, pattern in _DEGREE_PATTERNS.items():
        if pattern.search(edu_lower):
            candidate_score = _DEGREE_SCORES[degree_name]
            if candidate_score > degree_score:
                degree_score = candidate_score

    # Field relevance bonus: check if the education text mentions JD-related terms
    field_bonus = 0.0
    if job_description and job_description.strip():
        jd_lower = job_description.lower()
        jd_words = set(re.findall(r'\b[a-z]{3,}\b', jd_lower))
        edu_words = set(re.findall(r'\b[a-z]{3,}\b', edu_lower))

        # Remove very common words
        stop_words = {'the', 'and', 'for', 'with', 'has', 'have', 'are', 'was', 'will', 'can',
                      'from', 'this', 'that', 'not', 'but', 'also', 'any', 'all', 'been', 'more',
                      'years', 'year', 'experience', 'required', 'preferred'}
        jd_words -= stop_words
        edu_words -= stop_words

        if jd_words:
            overlap = jd_words & edu_words
            if len(overlap) >= 2:
                field_bonus = 0.2  # Meaningful field overlap
            elif len(overlap) >= 1:
                field_bonus = 0.1

    return min(degree_score + field_bonus, 1.0)


# ============================================================
# Certificate Extraction (Broadened Patterns)
# ============================================================

def extract_certificate_mentions(text):
    """
    Extracts certificate/certification mentions from resume text.
    Uses both regex patterns and section-based extraction.
    Returns a list of certificate text strings.
    """
    text_lower = str(text).lower()
    sections = split_resume_sections(text)
    cert_matches = []

    # Pattern-based extraction from full text
    cert_patterns = [
        r'((?:aws[\s\-]?certified|certified|certification|certificate|'
        r'coursera|udemy|google[\s\-]?cloud|azure[\s\-]?certified|'
        r'professional\s*certificate|nanodegree|specialization|'
        r'licensed|registered)[^\n.,;]*)',
    ]
    for pattern in cert_patterns:
        for m in re.finditer(pattern, text_lower):
            cert_text = m.group(1).strip()
            if len(cert_text) > 5:
                cert_matches.append(cert_text)

    # Section-based extraction: if we have a certificates section, extract lines from it
    cert_section = sections.get("certificates", "").strip()
    if cert_section:
        for line in cert_section.split('\n'):
            line = line.strip()
            if len(line) > 5 and line.lower() not in [c.lower() for c in cert_matches]:
                cert_matches.append(line)

    return cert_matches


def extract_name_from_text(raw_text):
    """
    Tries to pull the candidate's name from the very top of their resume text.
    Most resumes start with the person's name on the first 1-2 lines.
    We skip blank lines, contact info lines (emails, phone numbers, URLs), and
    lines that look like section headers. Whatever is left and is short enough
    is assumed to be the name.
    """
    if not raw_text:
        return None

    lines = raw_text.strip().split('\n')

    # Patterns we want to SKIP - these are NOT a person's name
    skip_patterns = re.compile(
        r'([@\d\(\)\+]|linkedin|github|http|www\.|gmail|yahoo|hotmail|'
        r'resume|curriculum vitae|cv |portfolio|objective|summary|profile|'
        r'address|phone|email|mobile|contact)',
        re.IGNORECASE
    )

    # Sections headings that must NEVER be treated as a name
    _SECTION_HEADER_BLACKLIST = {
        "education", "experience", "skills", "projects", "objective",
        "summary", "profile", "contact", "references", "certifications",
        "achievements", "awards", "languages", "interests", "hobbies",
        "work", "employment", "qualifications", "internship", "internships",
        "activity", "activities", "courses", "coursework", "publications",
        "personal info", "personal information", "personal details",
        "employment history", "work experience", "professional experience",
        "professional background", "internship experience", "academic projects",
        "technical skills", "core competencies",
    }

    for line in lines[:10]:  # Only look at the first 10 lines
        line = line.strip()

        # Skip blank or very short lines
        if len(line) < 2:
            continue

        # Skip lines that match contact/section patterns
        if skip_patterns.search(line):
            continue

        # Skip lines that are too long to be a name (> 50 chars)
        if len(line) > 50:
            continue

        words = line.split()

        # Skip lines that exactly match a section heading (case-insensitive)
        if line.strip().lower() in _SECTION_HEADER_BLACKLIST:
            continue
        
        # Skip lines that START WITH a section heading word (e.g. "Certifications ...")
        first_word = words[0].lower().rstrip(':')
        if first_word in {
            "education", "experience", "skills", "projects", "objective",
            "summary", "profile", "contact", "references", "certifications",
            "achievements", "awards", "languages", "interests", "hobbies",
            "work", "employment", "qualifications", "internships", "courses",
            "publications", "activities", "coursework"
        }:
            continue

        # If it looks like 1-4 words of mostly letters, it's probably a name
        if 1 <= len(words) <= 4 and re.match(r'^[A-Za-z][A-Za-z\s\.\-]+$', line):
            return line.title()

    return None


def extract_name_from_filename(filename, raw_text=None):
    """
    Extracts a readable candidate name.
    STEP 1: Try reading from resume text (top lines) — most accurate.
    STEP 2: Fall back to cleaning the filename.
    """
    # Step 1: Try resume text first
    if raw_text:
        name_from_text = extract_name_from_text(raw_text)
        if name_from_text:
            return name_from_text

    # Step 2: Clean the filename
    name = os.path.splitext(filename)[0]

    # Strip the UUID/hash prefix added by our uploader (e.g. '24f0f992_')
    name = re.sub(r'^[0-9a-f]{6,}_', '', name, flags=re.IGNORECASE)

    # Remove common noise words
    name = re.sub(r'(?i)\b(resume|cv|curriculum|vitae|application|applicant|file|doc|updated?|final|new)\b', '', name)

    # Remove leftover digits and special characters except spaces/hyphens
    name = re.sub(r'[^A-Za-z\s\-]', ' ', name)

    # Replace hyphens/underscores with spaces
    name = name.replace('-', ' ').replace('_', ' ')

    # Collapse whitespace and title-case
    name = ' '.join(name.split()).title().strip()

    return name if name else filename


# ==================================================================
# NEW: extract_candidate_info — pulls all structured fields from text
# Added for the TabTransformer / hybrid scoring pipeline
# ==================================================================

# Degree keywords to look for in education section
_DEGREE_KEYWORDS = [
    "phd", "ph.d", "doctorate", "doctor of",
    "m.tech", "m.e.", "m.s.", "master of", "mba", "mca", "m.sc", "msc", "m.com",
    "b.tech", "b.e.", "b.s.", "b.sc", "bsc", "bca", "b.com", "bcom", "b.a.", "ba",
    "bachelor of", "bachelor's", "be ", "degree",
    "diploma", "polytechnic",
]

# Department keywords — used to infer department from text
_DEPT_KEYWORDS = {
    "IT":           ["software", "developer", "engineer", "programming", "computer science",
                     "data science", "machine learning", "ai", "artificial intelligence",
                     "web developer", "backend", "frontend", "full stack", "devops", "cloud",
                     "cybersecurity", "database", "python", "java", "javascript"],
    "HR":           ["human resources", "hr manager", "hr executive", "talent acquisition",
                     "recruitment", "payroll", "employee relations", "hrbp", "workforce"],
    "Finance":      ["finance", "accounting", "accountant", "financial analyst", "cpa",
                     "tax", "audit", "bookkeeping", "chartered accountant", "ca ", "cfa"],
    "Marketing":    ["marketing", "digital marketing", "seo", "content", "social media",
                     "brand", "advertising", "market research", "campaign"],
    "Sales":        ["sales", "business development", "account manager", "sales executive",
                     "client acquisition", "lead generation", "b2b", "b2c"],
    "Healthcare":   ["doctor", "nurse", "physician", "medical", "clinical", "pharmacy",
                     "healthcare", "hospital", "patient care", "mbbs"],
    "Engineering":  ["mechanical", "civil", "electrical", "electronics", "manufacturing",
                     "autocad", "solidworks", "hvac", "robotics", "aerospace"],
    "Operations":   ["operations", "supply chain", "logistics", "warehouse", "procurement",
                     "vendor management", "inventory", "project manager"],
}

# Common job title patterns
_JOB_ROLE_PATTERNS = [
    r'(senior|junior|lead|principal|associate|chief|head of|vp of|director of)?\s*'
    r'(software engineer|developer|data scientist|data analyst|ml engineer|'
    r'product manager|project manager|business analyst|ui/ux designer|devops engineer|'
    r'cloud engineer|full stack developer|backend developer|frontend developer|'
    r'marketing manager|sales executive|hr manager|financial analyst|'
    r'accountant|operations manager|supply chain analyst|content writer|'
    r'graphic designer|qa engineer|test engineer|network engineer|'
    r'data engineer|ai engineer|research analyst)',
]




def extract_candidate_info(raw_text):
    """
    Extracts all structured fields from raw resume text.
    Returns a clean dictionary with all fields candidate_scorer.py needs.

    Fields: name, email, phone, experience_years, education, skills,
            department, job_role
    """
    text = str(raw_text or "")
    text_lower = text.lower()

    # ── 1. Email ─────────────────────────────────────────────────────
    email = ""
    email_match = re.search(
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.?[A-Za-z]{2,}\b',
        text
    )
    if email_match:
        email = email_match.group(0).strip()

    # ── 2. Phone ─────────────────────────────────────────────────────
    phone = ""
    # Try +91 format first, then plain 10-digit Indian number
    phone_match = re.search(
        r'(?:\+91[\s\-]?)?[6-9]\d{9}',
        text
    )
    if not phone_match:
        phone_match = re.search(
            r'\b(?:\+\d{1,3}[\s\-]?)?\(?\d{3,5}\)?[\s\-]?\d{3,5}[\s\-]?\d{3,4}\b',
            text
        )
    if phone_match:
        phone = phone_match.group(0).strip()

    # ── 3. Experience years ───────────────────────────────────────────
    # reuse the existing extractor
    experience_years = extract_experience_years(text)

    # ── 4. Education ──────────────────────────────────────────────────
    education = ""
    _CLEAN_DEGREE_WORDS = [
        "phd", "ph.d", "ph,d", "doctorate", "doctor of",
        "m.tech", "m.e.", "m.s.", "m.s", "m,s", "master of", "mba", "mca", "m.sc", "msc",
        "b.tech", "b.e.", "b.s.", "b.s", "b,s", "b.sc", "bsc", "bca", "b.com", "bcom",
        "bachelor of", "bachelor's", "bachelor",
        "diploma", "polytechnic",
        "diploma", "polytechnic",
    ]
    for deg in _CLEAN_DEGREE_WORDS:
        if deg in text_lower:
            idx = text_lower.find(deg)
            # Grab the full line that contains this degree keyword
            line_start = text.rfind('\n', 0, idx) + 1
            line_end   = text.find('\n', idx)
            if line_end == -1:
                line_end = len(text)
            full_line = text[line_start:line_end].strip()
            # Clean/shorten: remove years, "present", "–", and arrows
            full_line = re.sub(r'\d{4}\s*[-–—]\s*(?:present|current|\d{4})?', '', full_line, flags=re.IGNORECASE)
            full_line = re.sub(r'\s+', ' ', full_line).strip()
            # Remove trailing punctuation or stray "-"
            full_line = full_line.strip(' ,;–—-')
            if len(full_line) > 3:
                education = full_line
                if deg in ["phd", "ph.d", "doctorate", "m.tech", "mba", "m.s."]:
                    break  # stop at highest degree

    # ── 5. Skills ─────────────────────────────────────────────────────
    # Strategy: Use keyword matching (from SKILL_KEYWORDS) as the primary source,
    # since that's a curated, clean list. Then supplement with section-based
    # extraction for skills not in our keyword list (but with strict filtering).
    
    # Primary: keyword-matched skills (always clean)
    keyword_skills = get_matched_skills(text)
    
    # Supplement: try to extract from the skills section header
    section_skills = []
    skills_section_match = re.search(
        r'(?:technical\s*skills?|skills?|core\s*competencies?|key\s*skills?)'
        r'\s*[:\-]?\s*\n([\s\S]{10,500}?)(?:\n\s*(?:EDUCATION|EXPERIENCE|PROJECTS|'
        r'CERTIFICATIONS|WORK|EMPLOYMENT|OBJECTIVE|SUMMARY|PROFESSIONAL)\b|\Z)',
        text, re.IGNORECASE
    )
    if skills_section_match:
        skills_text = skills_section_match.group(1)
        # Strip sub-headings like "Programming Languages:", "Frameworks:", etc.
        skills_text = re.sub(
            r'^[A-Za-z\s/&()]{4,40}:\s*',
            '',
            skills_text,
            flags=re.MULTILINE
        )
        raw_skills = re.split(r'[,|\n•\-;/\t]+', skills_text)
        
        # Strict noise filters for section-extracted skills
        _noise_blacklist = {
            "education", "experience", "skills", "projects", "objective",
            "summary", "profile", "contact", "references", "certifications",
            "achievements", "awards", "languages", "interests", "hobbies",
            "work", "employment", "qualifications", "internships", "courses",
            "personal details", "personal information", "work experience",
            "professional experience", "technical skills", "core competencies",
        }
        _noise_verbs = re.compile(
            r'\b(developed|maintained|collaborated|managed|designed|implemented|'
            r'created|built|worked|led|analyzed|prepared|delivered|functional|'
            r'quality|software\.|applications|responsible|high quality|'
            r'participated|contributed|utilized|conducted|ensured|assisted)\b',
            re.IGNORECASE
        )
        _noise_edu = re.compile(
            r'\b(b\.s\.|m\.s\.|ph\.d|bachelor|master|university|college|institute|'
            r'school|degree|diploma|graduated)\b', re.IGNORECASE
        )
        _noise_company = re.compile(
            r'\b(LLC|Inc|Corp|Ltd|Solutions|Technologies|Services|Company|Pvt|'
            r'Enterprises|Group|Partners|Global|Associates)\b', re.IGNORECASE
        )
        
        for s in raw_skills:
            s = s.strip()
            if len(s) < 2 or len(s) > 25:
                continue
            if s.lower() in _noise_blacklist:
                continue
            if ':' in s:
                continue
            if _noise_verbs.search(s):
                continue
            if _noise_edu.search(s):
                continue
            if _noise_company.search(s):
                continue
            if re.match(r'^\d{4}', s):  # starts with a year
                continue
            if s.endswith(')'):  # "Engineer (2015"
                continue
            if len(s.split()) > 4:  # real skills are max 4 words
                continue
            section_skills.append(s)
    
    # Merge: keyword skills first, then unique section skills
    keyword_set_lower = {s.lower() for s in keyword_skills}
    skills = list(keyword_skills)
    for s in section_skills:
        if s.lower() not in keyword_set_lower:
            skills.append(s)
            keyword_set_lower.add(s.lower())
    skills = skills[:30]  # cap at 30 to keep it manageable

    # Fall back to keyword matching if nothing was extracted at all
    if not skills:
        skills = get_matched_skills(text)

    # ── 6. Department (inferred from text keywords) ───────────────────
    department = "Unknown"
    dept_scores = {}
    for dept, keywords in _DEPT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            dept_scores[dept] = score
    if dept_scores:
        department = max(dept_scores, key=dept_scores.get)

    # ── 7. Job Role ───────────────────────────────────────────────────
    job_role = ""

    # Strategy A: The job title is almost always on line 2 of a resume
    # (right under the name) — look for it in the first 5 lines
    first_lines = text.strip().split('\n')[:8]
    _title_pattern = re.compile(
        r'\b(software\s+developer|software\s+engineer|data\s+scientist|data\s+analyst|'
        r'ml\s+engineer|ai\s+engineer|data\s+engineer|full[\s\-]stack\s+developer|'
        r'backend\s+developer|frontend\s+developer|web\s+developer|'
        r'mobile\s+developer|android\s+developer|ios\s+developer|'
        r'devops\s+engineer|cloud\s+engineer|security\s+engineer|'
        r'product\s+manager|project\s+manager|business\s+analyst|'
        r'ui[/\s]ux\s+designer|graphic\s+designer|'
        r'marketing\s+manager|content\s+writer|'
        r'hr\s+manager|hr\s+executive|talent\s+acquisition|'
        r'financial\s+analyst|accountant|operations\s+manager|'
        r'qa\s+engineer|test\s+engineer|network\s+engineer|'
        r'research\s+analyst|system\s+administrator|database\s+administrator)\b',
        re.IGNORECASE
    )
    for line in first_lines[1:5]:  # skip line 0 (the name)
        m = _title_pattern.search(line)
        if m:
            job_role = m.group(0).strip().title()
            break

    # Strategy B: Fall back to searching the whole document
    if not job_role:
        m = _title_pattern.search(text)
        if m:
            job_role = m.group(0).strip().title()

    # ── 8. Name (reuse existing function) ────────────────────────────
    name = extract_name_from_text(text) or ""

    return {
        "name":             name,
        "email":            email,
        "phone":            phone,
        "experience_years": experience_years,
        "education":        education,
        "skills":           skills,
        "department":       department,
        "job_role":         job_role,
    }
