# candidate_scorer.py - scores and ranks candidates based on keyword matching
# this is our simple version of what would eventually be a real ML model

import os
import re
import statistics
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# these are the skills we look for in resumes
# we picked common tech skills that show up in most CS job postings
SKILL_KEYWORDS = [
    "python", "java", "javascript", "sql", "react",
    "machine learning", "data analysis", "aws", "docker", "kubernetes",
    "git", "html", "css", "node.js", "flask",
    "tensorflow", "pandas", "mongodb", "rest api", "agile"
]


def score_candidate(parsed_data, job_description=None):
    """
    Takes the parsed resume data and calculates a score.
    If a job_description is provided, we use TF-IDF and cosine similarity
    (a simple ML approach) to compare the resume to the job description.
    Otherwise, we fall back to simple keyword matching.
    
    Also extracts the candidate's name from the filename.
    """
    raw_text = parsed_data["raw_text"].lower()
    filename = parsed_data["filename"]

    # check which skills appear in the resume text
    # we keep this so we can still display matched skills on the dashboard
    matched_skills = []
    for skill in SKILL_KEYWORDS:
        if skill in raw_text:
            matched_skills.append(skill)

    # Use TF-IDF if we have a job description, else fallback to keyword matching
    if job_description and job_description.strip():
        # TF-IDF converts text into vectors (lists of numbers) based on word importance.
        # Cosine similarity then checks the angle between these vectors. 
        # A higher similarity means the resume closely matches the job description!
        vectorizer = TfidfVectorizer()
        try:
            tfidf_matrix = vectorizer.fit_transform([job_description.lower(), raw_text])
            # Getting the similarity score between the 1st item (job desc) and 2nd item (resume)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            # Convert to a percentage out of 100, rounded to 1 decimal
            score = round(similarity * 100, 1)
        except ValueError:
            # Fallback if text is completely empty and TF-IDF breaks
            total_keywords = len(SKILL_KEYWORDS)
            score = round((len(matched_skills) / total_keywords) * 100, 1)
    else:
        # calculate score as percentage - simple but it works for our prototype fallback
        total_keywords = len(SKILL_KEYWORDS)
        score = round((len(matched_skills) / total_keywords) * 100, 1)

    # try to get a name from the filename
    name = extract_name_from_filename(filename)

    return {
        "name": name,
        "score": score,
        "matched_skills": matched_skills,
        "filename": filename,
        "raw_text": raw_text  # We store this temporarily for the anomaly check later
    }


def extract_name_from_filename(filename):
    """
    Pulls a candidate name out of the filename.
    We strip the extension, remove common words like 'resume' and 'cv',
    replace underscores/hyphens with spaces, and title-case it.
    It's not perfect but works for most naming conventions.
    """
    # remove the file extension
    name = os.path.splitext(filename)[0]

    # remove common words that aren't part of the name, and strip out numbers
    name = re.sub(r'(?i)(resume|cv|_resume|_cv|\d+)', '', name)

    # replace underscores and hyphens with spaces
    name = name.replace("_", " ").replace("-", " ")

    # clean up extra spaces and title case it
    name = " ".join(name.split()).title().strip()

    # if we end up with an empty string just use the filename
    if not name:
        name = filename

    return name


def rank_candidates(candidates_list):
    """
    Sorts candidates by their score (highest first) and adds
    a rank number to each one. Pretty straightforward sorting.
    """
    # sort by score, highest score = rank 1
    sorted_candidates = sorted(candidates_list, key=lambda x: x["score"], reverse=True)

    # add rank numbers starting from 1
    for i, candidate in enumerate(sorted_candidates):
        candidate["rank"] = i + 1

    return sorted_candidates


def detect_anomalies(candidates_list):
    """
    Runs an anomaly check on the full batch after all resumes are parsed.
    We calculate the 'skills_length' (len of raw_text) for each resume.
    If it's more than 2 standard deviations above the batch mean, 
    we flag it as an anomaly (suspected keyword stuffing!).
    """
    if not candidates_list:
        return candidates_list

    # Get raw_text lengths for the whole batch
    lengths = [len(c["raw_text"]) for c in candidates_list]
    mean_len = statistics.mean(lengths)
    
    # We need at least 2 resumes to get a standard deviation
    if len(lengths) > 1:
        std_len = statistics.stdev(lengths)
    else:
        std_len = 0.0

    threshold = mean_len + (2 * std_len)

    # Flag anything above the threshold
    for candidate in candidates_list:
        candidate_len = len(candidate["raw_text"])
        
        # Only check anomalies if there is a deviance in the batch
        if std_len > 0 and candidate_len > threshold:
            candidate["is_anomaly"] = True
            candidate["anomaly_reason"] = "Suspected keyword stuffing: resume text length is statistically abnormal for this batch."
        else:
            candidate["is_anomaly"] = False
            candidate["anomaly_reason"] = ""
            
        # Optional cleanup so we don't send huge strings to the frontend
        candidate.pop("raw_text", None)

    return candidates_list
