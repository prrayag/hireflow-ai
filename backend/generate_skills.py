"""
Generate skill embeddings (bare names) used to match messy skill spellings
("nodejs", "postgres") to the canonical vocabulary.

Run once, and again whenever skill_catalog.py changes:
    python generate_skills.py            -> skills.json
    python generate_skill_context.py     -> skill_context.json
"""

import json
import os

from sentence_transformers import SentenceTransformer
from skill_catalog import SKILL_VOCAB, ALIASES

print("[HireFlow] Loading Sentence-BERT model...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Canonical skills plus their official alias names, so both spellings are matchable
names = list(dict.fromkeys(SKILL_VOCAB + list(ALIASES.keys())))
skill_embeddings = {name: model.encode(name).tolist() for name in names}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills.json')
with open(out_path, 'w') as f:
    json.dump(skill_embeddings, f)

print(f"Created skills.json with {len(skill_embeddings)} skill embeddings")
