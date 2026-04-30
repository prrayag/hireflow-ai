<<<<<<< HEAD
# candidate_scorer.py — HireFlow AI
# ====================================================================
# Hybrid scoring pipeline using TabTransformer + Vector Similarity + TF-IDF.
# 
# Score breakdown (out of 100):
#   Component 1: TabTransformer prediction probability   → 0 to 40
#   Component 2: Vector similarity (cosine of embeddings)→ 0 to 35
#   Component 3: TF-IDF text cosine similarity            → 0 to 25
#
# If tab_transformer.pth is missing → falls back to keyword matching.
# Anomaly detection (Isolation Forest style) is preserved exactly.
# ====================================================================

import os
import re
import json
import statistics
import numpy as np
import joblib

# TF-IDF for text-based scoring (Component 3)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# we import resume_features to extract candidate fields
from resume_features import (
    SKILL_KEYWORDS,
    extract_name_from_filename,
    get_matched_skills,
    get_jd_skills,
    compute_jd_overlap,
    extract_candidate_info,     # new function we're adding to resume_features.py
)

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH   = os.path.join(BASE_DIR, "tab_transformer.pth")
CONFIG_PATH  = os.path.join(BASE_DIR, "model_config.json")
ENC_PATH     = os.path.join(BASE_DIR, "label_encoders.pkl")

# these get loaded once at startup
_model          = None
_model_config   = None
_label_encoders = None
_model_ready    = False   # True only when ALL three files loaded correctly

# ── lazy imports for torch (only if model exists) ──────────────────
_torch = None
_nn    = None


def _load_torch():
    """Import torch lazily so the app doesn't crash if torch isn't installed."""
    global _torch, _nn
    if _torch is None:
        try:
            import torch
            import torch.nn as nn
            _torch = torch
            _nn    = nn
        except ImportError:
            print("[scorer] torch not installed! Falling back to keyword scoring.")
    return _torch is not None


# ── TabTransformer model definition (must match train_model.py exactly) ────────

def _build_model(config):
    """
    Rebuilds the TabTransformer from the saved config.
    We have to define the architecture here too so we can load the weights.
    This is the same class as in train_model.py — if you change one, change both!
    """
    if not _load_torch():
        return None
    
    torch = _torch
    nn    = _nn
    
    embed_dim      = config["embedding_dim"]
    num_heads      = config["num_heads"]
    num_layers     = config["num_layers"]
    cat_vocab_sizes = config["cat_vocab_sizes"]
    num_num        = config["num_num_features"]
    num_cat        = config["num_cat_features"]
    
    class _MHSelfAttention(nn.Module):
        def __init__(self, d, h):
            super().__init__()
            self.h           = h
            self.head_dim    = d // h
            self.scale       = self.head_dim ** -0.5
            self.qkv_proj    = nn.Linear(d, 3 * d)
            self.out_proj    = nn.Linear(d, d)
            self.dropout_l   = nn.Dropout(0.1)
            self.norm        = nn.LayerNorm(d)
        
        def forward(self, x):
            B, S, D = x.shape
            qkv = self.qkv_proj(x)
            q, k, v = qkv.chunk(3, dim=-1)
            def reshape(t):
                return t.view(B, S, self.h, self.head_dim).transpose(1, 2)
            q, k, v = reshape(q), reshape(k), reshape(v)
            w = torch.matmul(q, k.transpose(-2, -1)) * self.scale
            w = torch.softmax(w, dim=-1)
            w = self.dropout_l(w)
            out = torch.matmul(w, v)
            out = out.transpose(1, 2).contiguous().view(B, S, D)
            out = self.out_proj(out)
            return self.norm(x + out)
    
    class _TabTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed_dim = embed_dim
            self.num_cat   = num_cat
            self.num_num   = num_num
            
            self.embeddings = nn.ModuleList([
                nn.Embedding(vs + 1, embed_dim) for vs in cat_vocab_sizes
            ])
            self.attention_layers = nn.ModuleList([
                _MHSelfAttention(embed_dim, num_heads) for _ in range(num_layers)
            ])
            self.num_norm = nn.LayerNorm(num_num)
            combined_dim  = num_cat * embed_dim + num_num
            self.mlp = nn.Sequential(
                nn.Linear(combined_dim, 64), nn.ReLU(), nn.Dropout(0.1),
                nn.Linear(64, 32), nn.ReLU(),
                nn.Linear(32, 1), nn.Sigmoid()
            )
            self.embedding_layer = nn.Sequential(
                nn.Linear(combined_dim, 64), nn.ReLU(), nn.Dropout(0.1),
                nn.Linear(64, 32), nn.ReLU()
            )
        
        def _get_combined(self, x_cat, x_num):
            cat_embeds = [emb(x_cat[:, i]) for i, emb in enumerate(self.embeddings)]
            cat_stack  = torch.stack(cat_embeds, dim=1)
            for attn in self.attention_layers:
                cat_stack = attn(cat_stack)
            cat_flat   = cat_stack.view(cat_stack.size(0), -1)
            num_normed = self.num_norm(x_num)
            return torch.cat([cat_flat, num_normed], dim=1)
        
        def forward(self, x_cat, x_num):
            return self.mlp(self._get_combined(x_cat, x_num)).squeeze(1)
        
        def get_embedding(self, x_cat, x_num):
            return self.embedding_layer(self._get_combined(x_cat, x_num))
    
    return _TabTransformer()


def _load_models():
    """Load TabTransformer weights, config, and label encoders on first call."""
    global _model, _model_config, _label_encoders, _model_ready
    if _model_ready:
        return True
    
    # check all files exist
    if not all(os.path.exists(p) for p in [MODEL_PATH, CONFIG_PATH, ENC_PATH]):
        missing = [p for p in [MODEL_PATH, CONFIG_PATH, ENC_PATH] if not os.path.exists(p)]
        print(f"[scorer] Missing model files: {missing}")
        print("[scorer]  -> Falling back to keyword scoring. Run train_model.py to enable TabTransformer.")
        return False
    
    try:
        with open(CONFIG_PATH) as f:
            _model_config = json.load(f)
        
        _label_encoders = joblib.load(ENC_PATH)
        
        model = _build_model(_model_config)
        if model is None:
            return False
        
        # load state dict — map_location='cpu' so it works on M1/M2 Macs too
        state_dict = _torch.load(MODEL_PATH, map_location="cpu")
        model.load_state_dict(state_dict)
        model.eval()  # inference mode
        
        _model      = model
        _model_ready = True
        print("[scorer] TabTransformer loaded successfully! Hybrid scoring active.")
        return True
    
    except Exception as e:
        print(f"[scorer] Failed to load TabTransformer: {e}")
        print("[scorer]  -> Falling back to keyword scoring.")
        return False


def _encode_categorical(department, job_role):
    """
    Encode Department and JobRole using saved label encoders.
    Falls back to 0 if the value wasn't seen during training.
    """
    def safe_encode(le, value):
        try:
            return le.transform([str(value)])[0]
        except ValueError:
            # unseen label — use 0 as fallback index
            return 0
    
    dept_enc = safe_encode(_label_encoders["Department"], department)
    role_enc = safe_encode(_label_encoders["JobRole"],    job_role)
    return dept_enc, role_enc


def _get_tab_score(info):
    """
    Component 1: Run TabTransformer and get shortlisting probability (0 to 1).
    Returns the raw probability × 40 to get the 0-40 component score.
    """
    if not _model_ready:
        return 0.0
    
    torch = _torch
    
    try:
        dep_enc, role_enc = _encode_categorical(
            info.get("department", "Unknown"),
            info.get("job_role",   "Unknown")
        )
        
        exp_years   = float(info.get("experience_years", 0) or 0)
        skills_cnt  = float(len(info.get("skills", [])))
        
        x_cat = torch.tensor([[dep_enc, role_enc]], dtype=torch.long)
        x_num = torch.tensor([[exp_years, skills_cnt]], dtype=torch.float32)
        
        with torch.no_grad():
            prob = _model(x_cat, x_num).item()  # 0.0 to 1.0
        
        # The model is trained on a strict label (exp>5 AND high salary),
        # so junior resumes get near-zero probability even if they're good.
        # We blend: 60% model probability + 40% profile-completeness bonus.
        # Completeness = how filled-in the resume is (skills count, experience, etc.)
        # This gives realistic mid-range scores for all candidates.
        max_expected_skills = 20.0
        skills_bonus    = min(skills_cnt / max_expected_skills, 1.0)
        exp_bonus       = min(exp_years / 10.0, 1.0)           # normalize to 10yr max
        has_email_bonus = 0.1 if info.get("email") else 0.0
        has_edu_bonus   = 0.1 if info.get("education") else 0.0
        
        completeness = (skills_bonus * 0.5 + exp_bonus * 0.3 + has_email_bonus + has_edu_bonus)
        completeness = min(completeness, 1.0)
        
        blended_prob = 0.6 * prob + 0.4 * completeness
        return blended_prob * 40.0
    
    except Exception as e:
        print(f"[scorer] TabTransformer inference error: {e}")
        return 0.0


def _get_candidate_embedding(info):
    """
    Get the 32-dim embedding vector for a candidate.
    Used for vector similarity scoring in Component 2.
    """
    if not _model_ready:
        return None
    
    torch = _torch
    
    try:
        dep_enc, role_enc = _encode_categorical(
            info.get("department", "Unknown"),
            info.get("job_role",   "Unknown")
        )
        exp_years  = float(info.get("experience_years", 0) or 0)
        skills_cnt = float(len(info.get("skills", [])))
        
        x_cat = torch.tensor([[dep_enc, role_enc]], dtype=torch.long)
        x_num = torch.tensor([[exp_years, skills_cnt]], dtype=torch.float32)
        
        with torch.no_grad():
            embedding = _model.get_embedding(x_cat, x_num)  # (1, 32)
        
        return embedding.numpy()[0]  # return as numpy array
    
    except Exception as e:
        print(f"[scorer] Embedding error: {e}")
        return None


# cache for JD embeddings — avoids recomputing for each resume in a batch
_jd_embedding_cache = {}

def _get_jd_embedding(job_description):
    """
    Creates a synthetic JD embedding by averaging embeddings of candidates
    whose skills best match the JD keywords. This is our 'JD reference vector'.
    
    The idea: instead of embedding raw text (that's what BERT does), we create
    a tabular feature vector for the JD by treating it like a 'super-candidate'
    with all the skills mentioned in the JD and typical experience.
    """
    if not _model_ready:
        return None
    
    # simple cache so we don't recompute for every resume in the same batch
    if job_description in _jd_embedding_cache:
        return _jd_embedding_cache[job_description]
    
    torch = _torch
    
    try:
        # extract skill keywords from JD
        jd_skills = get_jd_skills(job_description)
        
        # create a synthetic 'JD candidate' with:
        # - Unknown department and role (since JD doesn't always specify)
        # - 5 years experience (mid-level, as a neutral assumption)
        # - skills count = number of skills in JD
        dep_enc,  role_enc = _encode_categorical("Unknown", "Unknown")
        exp_years  = 5.0  # neutral mid-level assumption
        skills_cnt = float(len(jd_skills)) if jd_skills else 5.0
        
        x_cat = torch.tensor([[dep_enc, role_enc]], dtype=torch.long)
        x_num = torch.tensor([[exp_years, skills_cnt]], dtype=torch.float32)
        
        with torch.no_grad():
            jd_emb = _model.get_embedding(x_cat, x_num).numpy()[0]
        
        _jd_embedding_cache[job_description] = jd_emb
        return jd_emb
    
    except Exception as e:
        print(f"[scorer] JD embedding error: {e}")
        return None


def _get_vector_score(candidate_emb, jd_emb):
    """
    Component 2: Cosine similarity between candidate embedding and JD embedding.
    Returns similarity × 35 to get the 0-35 component score.
    """
    if candidate_emb is None or jd_emb is None:
        return 0.0
    
    # cosine similarity using numpy
    dot     = np.dot(candidate_emb, jd_emb)
    norm_c  = np.linalg.norm(candidate_emb)
    norm_j  = np.linalg.norm(jd_emb)
    
    if norm_c == 0 or norm_j == 0:
        return 0.0
    
    sim = dot / (norm_c * norm_j)
    # cosine sim can be in [-1, 1], clip to [0, 1]
    sim = float(np.clip(sim, 0.0, 1.0))
    
    return sim * 35.0


def _get_tfidf_score(raw_text, job_description):
    """
    Component 3: TF-IDF cosine similarity between resume text and JD text.
    Returns similarity × 25 to get the 0-25 component score.
    Falls back to 0 if JD is empty.
    """
    if not job_description or not job_description.strip():
        return 0.0
    
    try:
        vectorizer = TfidfVectorizer(stop_words='english', max_features=500)
        tfidf_matrix = vectorizer.fit_transform([raw_text, job_description])
        
        sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(sim) * 25.0
    
    except Exception as e:
        print(f"[scorer] TF-IDF scoring error: {e}")
        return 0.0


# ==================================================================
# Main Scoring Function
# ==================================================================

def score_candidate(parsed_data, job_description=None):
    """
    Main function — called for every resume during a batch upload.
    
    Returns a dict with all score components and extracted candidate info.
    Falls back to keyword scoring if TabTransformer is not available.
    """
    # try to load model on first call
    ml_available = _load_models()
    
    raw_text = parsed_data.get("raw_text", "")
    filename = parsed_data.get("filename", "resume.pdf")
    jd       = job_description or ""
    
    # extract structured info from resume text
    info = extract_candidate_info(raw_text)

    # validate name quality — fall back to filename if OCR produced garbage
    # (e.g. single-letter tokens like "F Ee Rudra" from scanned PDFs)
    extracted_name = info.get("name", "")
    name_words = extracted_name.split()
    name_looks_bad = (
        not extracted_name or
        any(len(w) <= 1 for w in name_words) or   # single char tokens
        len(extracted_name) < 3                     # ridiculously short
    )
    if name_looks_bad:
        info["name"] = extract_name_from_filename(filename, raw_text=None)  # filename only
    elif not info.get("name"):
        info["name"] = extract_name_from_filename(filename, raw_text=raw_text)


    # also get matched skills for dashboard display
    matched_skills = get_matched_skills(raw_text)
    if info.get("skills"):
        # merge — prefer the structured skills list if we extracted it
        all_skills = list(set(info["skills"]) | set(matched_skills))
    else:
        all_skills = matched_skills
        info["skills"] = matched_skills
    
    # JD skill overlap (for filtering/display)
    jd_skills = get_jd_skills(jd)
    jd_overlap = compute_jd_overlap(matched_skills, jd_skills)
    jd_matched = [s for s in matched_skills if s in set(jd_skills)]
    
    # ── HYBRID SCORING ─────────────────────────────────────────────
    if ml_available:
        # Component 1: TabTransformer (0 to 40)
        tab_score = _get_tab_score(info)

        if jd:
            # Component 2: Vector similarity (0 to 35) — only meaningful with a JD
            cand_emb   = _get_candidate_embedding(info)
            jd_emb     = _get_jd_embedding(jd)
            raw_vec_score = _get_vector_score(cand_emb, jd_emb)
            
            # Similar to TF-IDF, Vector Similarity can penalize the candidate if the JD is 
            # just a short list of skills (due to differences in embedded feature counts).
            # We blend exact keyword overlap here too.
            overlap_vec = jd_overlap * 35.0
            vec_score = max(raw_vec_score, (raw_vec_score + overlap_vec) / 2)

            # Component 3: TF-IDF (0 to 25) — only meaningful with a JD
            raw_tfidf = _get_tfidf_score(raw_text, jd)
            
            # If the JD is very short (like a list of keywords), TF-IDF gets diluted by the 
            # length of the resume. We blend the exact keyword overlap to fix this.
            # jd_overlap is a ratio (0.0 to 1.0) of how many JD skills the candidate has.
            overlap_score = jd_overlap * 25.0
            
            # Take the better of the two, or a blend, so keyword-only JDs don't get penalized.
            tfidf_score = max(raw_tfidf, overlap_score)
        else:
            # ── No JD: use profile richness to fill the 60-point JD budget ──
            # We score based on how complete and skill-rich the candidate is.
            # This gives meaningful relative scores between candidates.

            # Skills count signal: more skills → higher score (cap at 30)
            skills_count   = len(all_skills)
            skills_signal  = min(skills_count / 20.0, 1.0)  # 20 skills = max

            # Education level signal
            edu_text = (info.get("education") or "").lower()
            if any(k in edu_text for k in ["phd", "ph.d", "doctor"]):
                edu_signal = 1.0
            elif any(k in edu_text for k in ["m.tech", "mba", "m.s.", "master", "msc", "mca"]):
                edu_signal = 0.85
            elif any(k in edu_text for k in ["b.tech", "b.e.", "bsc", "bca", "bachelor", "be "]):
                edu_signal = 0.7
            elif any(k in edu_text for k in ["diploma", "polytechnic"]):
                edu_signal = 0.5
            else:
                edu_signal = 0.4

            # Experience signal (cap at 15 yrs)
            exp_years     = float(info.get("experience_years") or 0)
            exp_signal    = min(exp_years / 10.0, 1.0)

            # Contact completeness signal
            has_email = 1 if info.get("email") else 0
            has_phone = 1 if info.get("phone") else 0
            contact_signal = (has_email + has_phone) / 2.0

            # Keyword richness: matched skills from the keyword list
            # normalised to a realistic cap of 15 known keywords
            keyword_richness = min(len(matched_skills) / 15.0, 1.0)

            # Combine: weight more towards skills and education
            composite = (
                skills_signal    * 0.35 +
                edu_signal       * 0.25 +
                exp_signal       * 0.20 +
                contact_signal   * 0.10 +
                keyword_richness * 0.10
            )
            
            # Boost the baseline by 0.2 to prevent overly harsh scores for partial/junior resumes
            composite = min(max(composite + 0.20, 0.0), 1.0)

            vec_score   = round(composite * 35.0, 1)
            tfidf_score = round(composite * 25.0, 1)

        # total score out of 100
        total_score = round(tab_score + vec_score + tfidf_score, 1)

    else:
        # ── FALLBACK: Keyword scoring ───────────────────────────────
        # if no ML model, just use JD overlap × 100
        tab_score   = 0.0
        vec_score   = 0.0
        tfidf_score = 0.0
        
        if jd_skills:
            total_score = round(jd_overlap * 100, 1)
        else:
            total = len(SKILL_KEYWORDS)
            total_score = round((len(matched_skills) / total) * 100, 1) if total > 0 else 0.0
    
    # shortlisted if score >= 45 (lowered from 60 because TabTransformer is very strict on junior profiles)
    shortlisted = total_score >= 55.0
    
    return {
        "name":                   info.get("name", "Unknown"),
        "email":                  info.get("email", ""),
        "phone":                  info.get("phone", ""),
        "score":                  total_score,
        "shortlisted":            shortlisted,
        "tab_transformer_score":  round(tab_score,   1),
        "vector_similarity_score": round(vec_score,  1),
        "tfidf_score":            round(tfidf_score, 1),
        "skills":                 all_skills,
        "matched_skills":         matched_skills,   # kept for backward compat
        "jd_matched_skills":      jd_matched,
        "experience_years":       info.get("experience_years", 0),
        "education":              info.get("education", ""),
        "department":             info.get("department", ""),
        "job_role":               info.get("job_role", ""),
        "filename":               filename,
        "raw_text":               raw_text,   # kept temporarily for anomaly detection
        # kept for backward compat with old dashboard fields
        "has_relevant_cert":      False,
        "project_relevance_score": 0.0,
        "relevant_projects_count": 0,
        "education_quality":      0.0,
    }


# ==================================================================
# Ranking
# ==================================================================

def rank_candidates(candidates_list):
    """Sort by score descending and add rank numbers."""
    sorted_list = sorted(candidates_list, key=lambda x: x["score"], reverse=True)
    for i, c in enumerate(sorted_list):
        c["rank"] = i + 1
    return sorted_list


# ==================================================================
# Anomaly Detection
# ==================================================================

def detect_anomalies(candidates_list):
    """
    Flags candidates with statistically abnormal resume length.
    This is a proxy for keyword stuffing — stuffed resumes tend to be
    much longer than genuine ones in the same batch.
    
    We use mean + 2 standard deviations as the threshold.
    (Same logic as before — keeping this untouched as required.)
    """
    if not candidates_list:
        return candidates_list
    
    lengths  = [len(c.get("raw_text", "")) for c in candidates_list]
    mean_len = statistics.mean(lengths)
    
=======
# candidate_scorer.py - scores and ranks candidates using Random Forest ML Model + NLP Semantic Matching
# ============================================================================================
# This module handles the scoring of individual resumes against a Job Description.
# PATH A: If model.pkl exists -> uses Random Forest + Sentence-BERT (full ML pipeline)
# PATH B: If model.pkl is missing -> falls back to simple keyword matching
#
# Shared extraction logic (section splitting, project extraction, skill matching, etc.)
# lives in resume_features.py to avoid duplication with train_model.py.
# ============================================================================================

import os
import re
import hashlib
import statistics
import joblib
import pandas as pd
from sentence_transformers import SentenceTransformer, util

# Import shared extraction & config from the DRY module
from resume_features import (
    SCORING_WEIGHTS,
    STRONG_THRESHOLD,
    EXPERIENCE_NORM_CAP,
    EXPERIENCE_FLOOR,
    SKILL_KEYWORDS,
    split_resume_sections,
    is_education_context,
    is_project_context,
    is_work_context,
    count_skills,
    has_contact_info,
    has_work_experience,
    extract_experience_years,
    extract_projects,
    get_matched_skills,
    get_jd_skills,
    compute_jd_overlap,
    extract_education_quality,
    extract_certificate_mentions,
    extract_name_from_filename,
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(_BASE_DIR, "model.pkl")

_model      = None
_bert_model = None

# JD embedding cache — avoids re-encoding the same JD for every resume in a batch
_jd_cache = {"hash": None, "embedding": None}


def _load_models():
    """Loads Random Forest and BERT model into memory if not already loaded."""
    global _model, _bert_model
    if _model is None:
        try:
            _model = joblib.load(MODEL_PATH)
            print("[candidate_scorer] Random Forest model loaded successfully!")
        except FileNotFoundError:
            print("[candidate_scorer] model.pkl not found! Will fall back to keyword scoring.")
            print("  To enable ML scoring, run: python train_model.py")

    if _bert_model is None and _model is not None:
        print("[candidate_scorer] Loading Sentence-BERT model...")
        _bert_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("[candidate_scorer] Sentence-BERT ready!")


def _get_jd_embedding(job_description):
    """
    Returns the BERT embedding for the JD, using a cache so we only encode it once
    per unique JD string (saves ~50ms per resume in a batch).
    """
    global _jd_cache
    jd_hash = hashlib.md5(job_description.encode('utf-8')).hexdigest()

    if _jd_cache["hash"] == jd_hash and _jd_cache["embedding"] is not None:
        return _jd_cache["embedding"]

    jd_embedding = _bert_model.encode([job_description], convert_to_tensor=True)[0]
    _jd_cache["hash"] = jd_hash
    _jd_cache["embedding"] = jd_embedding
    return jd_embedding


# ============================================================
# Semantic Scoring (BERT-based)
# ============================================================

def _score_project_relevance(raw_text, job_description):
    """
    Extracts projects from the resume and scores each against the JD
    using Sentence-BERT cosine similarity.

    Returns:
        project_score (float): 0.0 - 1.0, how relevant the best projects are to the JD
        relevant_count (int): number of projects with similarity > 0.3
    """
    if _bert_model is None:
        return 0.0, 0

    projects = extract_projects(raw_text)

    if not projects:
        return 0.0, 0

    if not job_description or not job_description.strip():
        job_description = "software engineer developer"

    try:
        jd_embedding = _get_jd_embedding(job_description)
        project_embeddings = _bert_model.encode(projects, convert_to_tensor=True)

        cosine_scores = util.cos_sim(project_embeddings, jd_embedding).cpu().numpy().flatten()

        # Only count projects with meaningful relevance (> 0.3 similarity)
        RELEVANCE_THRESHOLD = 0.3
        relevant_scores = [float(s) for s in cosine_scores if s > RELEVANCE_THRESHOLD]
        relevant_count = len(relevant_scores)

        if relevant_scores:
            # Use the average of relevant scores, capped at 1.0
            avg_score = sum(relevant_scores) / len(relevant_scores)
            # Boost slightly for having multiple relevant projects
            boost = min(relevant_count * 0.05, 0.15)
            project_score = min(avg_score + boost, 1.0)
            return project_score, relevant_count

        return 0.0, 0

    except Exception as e:
        print(f"[candidate_scorer] Project scoring error: {e}")
        return 0.0, 0


def _get_semantic_features(raw_text, job_description):
    """
    Uses Sentence-BERT to compute:
    1. Overall skill/resume meaning vs Job Description  → skills_match_score (0-1)
    2. Certificate relevance vs Job Description         → cert_relevance_score (0-1)
    """
    if not job_description or not job_description.strip():
        job_description = "software engineer developer"

    raw_text = str(raw_text).lower()

    # Pre-embed JD (cached)
    jd_embedding = _get_jd_embedding(job_description)

    # 1. Overall Skills Semantic Score
    resume_embedding = _bert_model.encode([raw_text], convert_to_tensor=True)[0]

    # Overall semantic similarity (normalized)
    sim = util.cos_sim(resume_embedding, jd_embedding).item()
    # Normalize: raw BERT cosine for long texts is usually 0.1-0.8
    skills_match_score = min(max((sim - 0.1) * 1.5, 0.0), 1.0)

    # 2. Certificate Relevance Score — uses broadened extraction
    cert_matches = extract_certificate_mentions(raw_text)

    cert_relevance_score = 0.0
    if cert_matches:
        try:
            cert_embeddings = _bert_model.encode(cert_matches, convert_to_tensor=True)
            cosine_scores = util.cos_sim(cert_embeddings, jd_embedding).cpu().numpy().flatten()
            # Only count certificates with meaningful relevance (> 0.1 similarity)
            relevant_scores = [float(s) for s in cosine_scores if s > 0.1]
            if relevant_scores:
                # Sum of relevant scores, capped at 1.0
                cert_relevance_score = min(sum(relevant_scores), 1.0)
        except Exception as e:
            print(f"[candidate_scorer] Certificate scoring error: {e}")
            cert_relevance_score = 0.0

    return skills_match_score, cert_relevance_score


# ============================================================
# Main Scoring Function
# ============================================================

def score_candidate(parsed_data, job_description=None):
    """
    Main scoring function. Called for every resume.
    Uses Random Forest + Sentence-BERT to give an AI confidence score (0-100%).
    Falls back to keyword matching if model files are not available.
    """
    _load_models()

    raw_text = parsed_data["raw_text"]
    filename = parsed_data["filename"]
    name = extract_name_from_filename(filename)

    # Always compute baseline skill matches (for dashboard display)
    matched_skills = get_matched_skills(raw_text)

    # Compute JD-specific skill overlap
    jd_skills = get_jd_skills(job_description)
    jd_overlap = compute_jd_overlap(matched_skills, jd_skills)

    # Find which of the candidate's skills directly match the JD (for highlighting)
    jd_matched_skills = [s for s in matched_skills if s in set(jd_skills)]

    # Initialize variables for return values so they exist even if ML fails
    exp_years = extract_experience_years(raw_text)
    cert_score = 0.0
    project_score = 0.0
    relevant_projects = 0
    edu_score = extract_education_quality(raw_text, job_description)

    # -------------------------------------------------------
    # PATH A: ML pipeline is loaded
    # -------------------------------------------------------
    if _model is not None and _bert_model is not None:
        skills_count = count_skills(matched_skills)
        has_exp = has_work_experience(raw_text)
        has_contact = has_contact_info(raw_text)
        exp_years = extract_experience_years(raw_text)

        # NLP Semantic scores
        sm_score, cert_score = _get_semantic_features(raw_text, job_description)

        # Project relevance scoring
        project_score, relevant_projects = _score_project_relevance(raw_text, job_description)

        # Education quality
        edu_score = extract_education_quality(raw_text, job_description)

        # Features ordered EXACTLY as trained in train_model.py
        feature_cols = [
            "skills_match_score",
            "skills_count",
            "has_experience",
            "certificate_relevance",
            "has_contact",
            "experience_years",
            "project_relevance",
            "education_quality"
        ]

        X_infer = pd.DataFrame(
            [[sm_score, skills_count, has_exp, cert_score, has_contact, exp_years, project_score, edu_score]],
            columns=feature_cols
        )

        # Predict probability of being a "Strong" candidate
        try:
            proba = _model.predict_proba(X_infer)[0]       # [prob_weak, prob_strong]
            ml_signal = float(proba[1])
        except Exception as e:
            print(f"[candidate_scorer] ML prediction warning (feature mismatch?): {e}")
            print("  Falling back to deterministic scoring only.")
            ml_signal = 0.5  # neutral fallback

        # Normalise experience with floor for fresh graduates
        exp_norm = min(exp_years / EXPERIENCE_NORM_CAP, 1.0)
        if exp_years == 0 and (skills_count >= 5 or project_score > 0.3):
            exp_norm = EXPERIENCE_FLOOR  # Don't completely zero out strong fresh grads

        # Calculate deterministic quality score with rebalanced weights
        quality_score = (
            (jd_overlap * SCORING_WEIGHTS["jd_skill_overlap"]) +
            (sm_score * SCORING_WEIGHTS["skills_match"]) +
            (exp_norm * SCORING_WEIGHTS["experience"]) +
            (cert_score * SCORING_WEIGHTS["certificates"]) +
            (has_contact * SCORING_WEIGHTS["contact_info"]) +
            (min(skills_count / 15.0, 1.0) * SCORING_WEIGHTS["skills_count"]) +
            (project_score * SCORING_WEIGHTS["project_relevance"]) +
            (edu_score * SCORING_WEIGHTS["education_quality"])
        )

        # Blend: deterministic score dominates (80%), ML provides a supporting signal (20%)
        combined_score = (quality_score * 0.80) + (ml_signal * 0.20)
        score = round(combined_score * 100, 1)

    # -------------------------------------------------------
    # PATH B: ML Model is missing (Fallback to keyword match)
    # -------------------------------------------------------
    else:
        # When no ML model, still use JD overlap if available
        if jd_skills:
            score = round(jd_overlap * 100, 1)
        else:
            total = len(SKILL_KEYWORDS)
            score = round((len(matched_skills) / total) * 100, 1) if total > 0 else 0.0

    return {
        "name":           name,
        "score":          score,
        "matched_skills": matched_skills,
        "jd_matched_skills": jd_matched_skills,
        "experience_years": exp_years,
        "has_relevant_cert": bool(cert_score > 0.0),
        "project_relevance_score": round(project_score, 3),
        "relevant_projects_count": relevant_projects,
        "education_quality": round(edu_score, 2),
        "filename": filename,
        "raw_text": raw_text  # Kept temporarily for anomaly detection
    }


# ============================================================
# Ranking
# ============================================================

def rank_candidates(candidates_list):
    """Sorts candidates by score (highest first) and assigns rank numbers."""
    sorted_candidates = sorted(candidates_list, key=lambda x: x["score"], reverse=True)

    for i, candidate in enumerate(sorted_candidates):
        candidate["rank"] = i + 1
    return sorted_candidates


# ============================================================
# Anomaly Detection
# ============================================================

def detect_anomalies(candidates_list):
    """Flags resumes that are statistically abnormally long (keyword stuffing check)."""
    if not candidates_list:
        return candidates_list

    # Get raw_text lengths for the whole batch
    lengths = [len(c.get("raw_text", "")) for c in candidates_list]
    mean_len = statistics.mean(lengths)

    # We need at least 2 resumes to get a standard deviation
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
    if len(lengths) > 1:
        std_len = statistics.stdev(lengths)
    else:
        std_len = 0.0
<<<<<<< HEAD
    
    threshold = mean_len + (2 * std_len)
    
    for candidate in candidates_list:
        cand_len = len(candidate.get("raw_text", ""))
        
        if std_len > 0 and cand_len > threshold:
            candidate["is_anomaly"]     = True
            candidate["anomaly_reason"] = (
                "Suspected keyword stuffing: resume text length is statistically "
                "abnormal for this batch."
            )
        else:
            candidate["is_anomaly"]     = False
            candidate["anomaly_reason"] = ""
        
        # remove raw_text before sending to frontend — it's too large
        candidate.pop("raw_text", None)
    
=======

    threshold = mean_len + (2 * std_len)

    for candidate in candidates_list:
        candidate_len = len(candidate.get("raw_text", ""))

        if std_len > 0 and candidate_len > threshold:
            candidate["is_anomaly"]     = True
            candidate["anomaly_reason"] = "Suspected keyword stuffing: resume text length is statistically abnormal for this batch."
        else:
            candidate["is_anomaly"]     = False
            candidate["anomaly_reason"] = ""

        # Remove raw_text before sending to frontend
        candidate.pop("raw_text", None)

>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
    return candidates_list
