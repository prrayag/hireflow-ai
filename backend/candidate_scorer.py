# candidate_scorer.py - scores and ranks candidates based on keyword matching
# this is our simple version of what would eventually be a real ML model

import os
import re

# these are the skills we look for in resumes
# we picked common tech skills that show up in most CS job postings
SKILL_KEYWORDS = [
    "python", "java", "javascript", "sql", "react",
    "machine learning", "data analysis", "aws", "docker", "kubernetes",
    "git", "html", "css", "node.js", "flask",
    "tensorflow", "pandas", "mongodb", "rest api", "agile"
]


def score_candidate(parsed_data):
    """
    Takes the parsed resume data and checks how many of our
    skill keywords appear in the text. Score is calculated as
    a percentage of matched keywords out of total keywords.
    
    Also tries to extract the candidate's name from the filename
    since we don't have a proper name extraction model yet.
    """
    raw_text = parsed_data["raw_text"].lower()
    filename = parsed_data["filename"]

    # check which skills appear in the resume text
    matched_skills = []
    for skill in SKILL_KEYWORDS:
        if skill in raw_text:
            matched_skills.append(skill)

    # calculate score as percentage - simple but it works for our prototype
    total_keywords = len(SKILL_KEYWORDS)
    score = round((len(matched_skills) / total_keywords) * 100, 1)

    # try to get a name from the filename
    # e.g. "john_doe_resume.pdf" becomes "John Doe"
    name = extract_name_from_filename(filename)

    return {
        "name": name,
        "score": score,
        "matched_skills": matched_skills,
        "filename": filename
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

    # remove common words that aren't part of the name
    name = re.sub(r'(?i)(resume|cv|_resume|_cv)', '', name)

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
