"""
Generate context-aware skill embeddings (used by gap analysis "similar skills").
Run once: python generate_skill_context.py  ->  skill_context.json
"""

import json
import os

from sentence_transformers import SentenceTransformer
from skill_catalog import SKILL_CONTEXT

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

embeddings = {
    skill: model.encode(text).tolist() for skill, text in SKILL_CONTEXT.items()
}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skill_context.json')
with open(out_path, 'w') as f:
    json.dump(embeddings, f)

print(f"Created skill_context.json with {len(embeddings)} skills")
