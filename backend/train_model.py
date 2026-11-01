<<<<<<< HEAD
# train_model.py — HireFlow AI
# ====================================================================
# This replaces the old Random Forest with a TabTransformer model.
# TabTransformer = Transformer attention on categorical features (like
# Department, JobRole) + regular MLP on numerical features.
#
# We spent like 3 days figuring out the embedding dimensions lol.
# The key insight is: categorical features go through attention layers
# and numerical features are just layer-normalized directly.
# Then we concatenate everything and pass through a small MLP.
# ====================================================================

import os
import json
import ast
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # headless mode so matplotlib doesn't try to open a window
import matplotlib.pyplot as plt
import joblib
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.inspection import permutation_importance

# figure out paths relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH   = os.path.join(BASE_DIR, "data", "Super_Resume_Dataset_Rows_1_to_1000.xlsx")
MODEL_PATH  = os.path.join(BASE_DIR, "tab_transformer.pth")
CONFIG_PATH = os.path.join(BASE_DIR, "model_config.json")
ENC_PATH    = os.path.join(BASE_DIR, "label_encoders.pkl")
CM_PATH     = os.path.join(BASE_DIR, "confusion_matrix.png")
FI_PATH     = os.path.join(BASE_DIR, "feature_importance.png")

print("=" * 60)
print("  HireFlow AI — TabTransformer Training Pipeline")
print("=" * 60)

# ==================================================================
# STEP 1 — Load and clean the dataset
# ==================================================================
print("\n[Step 1] Loading dataset...")
df = pd.read_excel(DATA_PATH)
print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")

# these columns don't help the model — they're either IDs or free text
# that we can't easily tokenize for tabular training
cols_to_drop = [
    "Name", "Email", "Phone", "City", "Gender",
    "Career_Objective", "Education_Institute",
    "Passing_Year", "Responsibility", "Certifications"
]
# only drop columns that actually exist (just in case the Excel changes)
cols_to_drop = [c for c in cols_to_drop if c in df.columns]
df = df.drop(columns=cols_to_drop)
print(f"  After dropping irrelevant columns: {df.shape}")

# skills column looks like: "['Python', 'Java', 'SQL']"
# we need to count how many skills each candidate has
df["Skills"] = df["Skills"].fillna("[]")

def count_skills_in_list(skills_str):
    # try to parse the string as a Python list
    try:
        skill_list = ast.literal_eval(str(skills_str))
        if isinstance(skill_list, list):
            return len(skill_list)
    except:
        pass
    # fallback: just count comma-separated items
    if skills_str and skills_str.strip() not in ["[]", ""]:
        return len([s for s in skills_str.split(",") if s.strip()])
    return 0

df["skills_count"] = df["Skills"].apply(count_skills_in_list)
print(f"  Engineered skills_count. Mean: {df['skills_count'].mean():.1f}")

# ==================================================================
# STEP 2 — Create the target variable
# ==================================================================
print("\n[Step 2] Engineering target variable...")

# fill any missing values in these key columns
df["Experience_Years"] = pd.to_numeric(df["Experience_Years"], errors="coerce").fillna(0)
df["Expected_Salary"]  = pd.to_numeric(df["Expected_Salary"], errors="coerce").fillna(0)

# shortlisted = 1 if experienced AND well-paid candidate (above median salary)
# this is our proxy label since we don't have actual HR decisions in the dataset
median_salary = df["Expected_Salary"].median()
print(f"  Median Expected_Salary: {median_salary}")

df["shortlisted"] = (
    (df["Experience_Years"] > 5) & (df["Expected_Salary"] > median_salary)
).astype(int)

shortlisted_count = df["shortlisted"].sum()
print(f"  Shortlisted: {shortlisted_count} / {len(df)} ({shortlisted_count/len(df)*100:.1f}%)")

# drop salary now — we don't want the model to "cheat" by seeing it
df = df.drop(columns=["Expected_Salary", "Skills"])  # also drop Skills string column

# drop any remaining nulls
df = df.dropna()
print(f"  Final dataset after dropna: {df.shape}")

# ==================================================================
# STEP 3 — Encode categorical features
# ==================================================================
print("\n[Step 3] Label encoding categorical columns...")

# the two categorical columns we care about
# these will go through embedding layers in the TabTransformer
cat_cols = ["Department", "JobRole"]

# fill any missing with "Unknown"
for col in cat_cols:
    df[col] = df[col].fillna("Unknown").astype(str)

label_encoders = {}
for col in cat_cols:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col])
    label_encoders[col] = le
    print(f"  {col}: {len(le.classes_)} unique values")

# save encoders so candidate_scorer.py can use them
joblib.dump(label_encoders, ENC_PATH)
print(f"  Saved label encoders to {ENC_PATH}")

# ==================================================================
# STEP 4 — Define the TabTransformer model
# ==================================================================
print("\n[Step 4] Building TabTransformer architecture...")

# hyperparameters — took us a while to settle on these
EMBED_DIM    = 32   # each categorical feature gets a 32-dim embedding
NUM_HEADS    = 4    # multi-head attention with 4 heads
NUM_LAYERS   = 2    # 2 Transformer encoder layers
NUM_CAT      = len(cat_cols)    # 2 categorical features
NUM_NUM      = 2                # 2 numerical features: Experience_Years, skills_count
DROPOUT      = 0.1
BATCH_SIZE   = 32
EPOCHS       = 30
LR           = 0.001

# number of unique values per categorical column (for embedding table size)
cat_vocab_sizes = [len(label_encoders[col].classes_) for col in cat_cols]

class MultiHeadSelfAttention(nn.Module):
    """
    Simple multi-head self-attention block.
    We implemented this ourselves instead of using nn.TransformerEncoderLayer
    so we understand what's actually happening inside the Transformer.
    
    Input:  (batch, seq_len, embed_dim)   — seq_len = number of cat features
    Output: (batch, seq_len, embed_dim)
    """
    def __init__(self, embed_dim, num_heads, dropout=0.1):
        super().__init__()
        # embed_dim must be divisible by num_heads
        assert embed_dim % num_heads == 0, "embed_dim must be divisible by num_heads"
        
        self.num_heads = num_heads
        self.head_dim  = embed_dim // num_heads
        self.scale     = self.head_dim ** -0.5  # scaling factor from "Attention is All You Need"
        
        # single weight matrix that projects input to Q, K, V all at once
        self.qkv_proj  = nn.Linear(embed_dim, 3 * embed_dim)
        self.out_proj   = nn.Linear(embed_dim, embed_dim)
        self.dropout_l  = nn.Dropout(dropout)
        self.norm       = nn.LayerNorm(embed_dim)
    
    def forward(self, x):
        batch, seq, d_model = x.shape
        
        # project to Q, K, V
        qkv = self.qkv_proj(x)  # (batch, seq, 3 * embed_dim)
        # split into 3 chunks: Q, K, V
        q, k, v = qkv.chunk(3, dim=-1)
        
        # reshape to (batch, num_heads, seq, head_dim)
        def reshape_for_heads(t):
            return t.view(batch, seq, self.num_heads, self.head_dim).transpose(1, 2)
        
        q, k, v = reshape_for_heads(q), reshape_for_heads(k), reshape_for_heads(v)
        
        # scaled dot-product attention
        # attn_weights shape: (batch, num_heads, seq, seq)
        attn_weights = torch.matmul(q, k.transpose(-2, -1)) * self.scale
        attn_weights = torch.softmax(attn_weights, dim=-1)
        attn_weights = self.dropout_l(attn_weights)
        
        # apply attention to values
        attn_out = torch.matmul(attn_weights, v)  # (batch, heads, seq, head_dim)
        
        # merge heads back: (batch, seq, embed_dim)
        attn_out = attn_out.transpose(1, 2).contiguous().view(batch, seq, d_model)
        attn_out = self.out_proj(attn_out)
        
        # residual connection + layer norm (same as original Transformer paper)
        return self.norm(x + attn_out)


class TabTransformerModel(nn.Module):
    """
    TabTransformer for tabular resume classification.
    
    Architecture:
        1. Each categorical feature → Embedding layer → (batch, embed_dim)
        2. Stack all cat embeddings → (batch, num_cat, embed_dim)
        3. Pass through N Transformer attention layers
        4. Flatten cat embeddings → (batch, num_cat * embed_dim)
        5. Numerical features → LayerNorm → (batch, num_num)
        6. Concat cat + num → (batch, num_cat * embed_dim + num_num)
        7. MLP: Linear → ReLU → Dropout → Linear → ReLU → Linear → Sigmoid
    """
    def __init__(self, cat_vocab_sizes, embed_dim, num_heads, num_layers,
                 num_num_features, dropout=0.1):
        super().__init__()
        
        self.embed_dim = embed_dim
        self.num_cat   = len(cat_vocab_sizes)
        self.num_num   = num_num_features
        
        # one embedding table per categorical feature
        # +1 vocab size for safety (handles unseen categories during inference)
        self.embeddings = nn.ModuleList([
            nn.Embedding(vocab_size + 1, embed_dim)
            for vocab_size in cat_vocab_sizes
        ])
        
        # stack of Transformer attention blocks
        self.attention_layers = nn.ModuleList([
            MultiHeadSelfAttention(embed_dim, num_heads, dropout)
            for _ in range(num_layers)
        ])
        
        # layer norm for numerical features (standard practice in TabTransformer)
        self.num_norm = nn.LayerNorm(num_num_features)
        
        # combined dimension after flattening cat embeddings + numerical
        combined_dim = self.num_cat * embed_dim + num_num_features
        
        # final MLP classifier head
        self.mlp = nn.Sequential(
            nn.Linear(combined_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
        
        # we also want the 32-dim embedding for vector similarity
        # this is the intermediate representation before the final sigmoid
        self.embedding_layer = nn.Sequential(
            nn.Linear(combined_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU()
        )
    
    def _get_combined_features(self, x_cat, x_num):
        """
        Shared feature extraction used by both forward() and get_embedding().
        Returns the combined representation before the final classifier.
        """
        # embed each categorical feature separately
        # each embedding: (batch, embed_dim)
        cat_embeds = [emb(x_cat[:, i]) for i, emb in enumerate(self.embeddings)]
        
        # stack into (batch, num_cat, embed_dim) for attention
        cat_stack = torch.stack(cat_embeds, dim=1)
        
        # pass through attention layers
        for attn_layer in self.attention_layers:
            cat_stack = attn_layer(cat_stack)
        
        # flatten: (batch, num_cat * embed_dim)
        cat_flat = cat_stack.view(cat_stack.size(0), -1)
        
        # normalize numerical features
        num_normed = self.num_norm(x_num)
        
        # concatenate categorical + numerical
        combined = torch.cat([cat_flat, num_normed], dim=1)
        return combined
    
    def forward(self, x_cat, x_num):
        """Standard forward pass — returns probability (0 to 1)."""
        combined = self._get_combined_features(x_cat, x_num)
        out = self.mlp(combined)
        return out.squeeze(1)
    
    def get_embedding(self, x_cat, x_num):
        """
        Returns the 32-dimensional embedding vector for a candidate.
        This is used for vector similarity scoring in candidate_scorer.py.
        We use the second-to-last MLP layer output (before final sigmoid).
        """
        combined = self._get_combined_features(x_cat, x_num)
        embedding = self.embedding_layer(combined)
        return embedding


# ==================================================================
# STEP 5 — Prepare data tensors
# ==================================================================
print("\n[Step 5] Preparing data for training...")

# split features and target
X = df.drop(columns=["shortlisted"])
y = df["shortlisted"].values

# separate categorical and numerical features
# order matters here — must match what candidate_scorer.py sends
x_cat_data = X[cat_cols].values.astype(np.int64)
x_num_data = X[["Experience_Years", "skills_count"]].values.astype(np.float32)
y_data = y.astype(np.float32)

# train/test split
x_cat_train, x_cat_test, x_num_train, x_num_test, y_train, y_test = train_test_split(
    x_cat_data, x_num_data, y_data,
    test_size=0.2, random_state=42, stratify=y_data
)

print(f"  Train: {len(y_train)} samples, Test: {len(y_test)} samples")
print(f"  Positive class rate (train): {y_train.mean():.2%}")

# convert to PyTorch tensors
x_cat_train_t = torch.tensor(x_cat_train, dtype=torch.long)
x_num_train_t = torch.tensor(x_num_train, dtype=torch.float32)
y_train_t     = torch.tensor(y_train, dtype=torch.float32)

x_cat_test_t  = torch.tensor(x_cat_test, dtype=torch.long)
x_num_test_t  = torch.tensor(x_num_test, dtype=torch.float32)
y_test_t      = torch.tensor(y_test, dtype=torch.float32)

# DataLoader for batching
train_dataset = TensorDataset(x_cat_train_t, x_num_train_t, y_train_t)
train_loader  = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)

# ==================================================================
# STEP 6 — Train the model
# ==================================================================
print("\n[Step 6] Training TabTransformer...")

model     = TabTransformerModel(cat_vocab_sizes, EMBED_DIM, NUM_HEADS, NUM_LAYERS, NUM_NUM, DROPOUT)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)
criterion = nn.BCELoss()  # Binary Cross Entropy for binary classification

model.train()
for epoch in range(1, EPOCHS + 1):
    epoch_loss = 0.0
    for x_cat_batch, x_num_batch, y_batch in train_loader:
        optimizer.zero_grad()
        preds = model(x_cat_batch, x_num_batch)
        loss  = criterion(preds, y_batch)
        loss.backward()
        optimizer.step()
        epoch_loss += loss.item()
    
    avg_loss = epoch_loss / len(train_loader)
    if epoch % 5 == 0:
        print(f"  Epoch {epoch:2d}/{EPOCHS} | Loss: {avg_loss:.4f}")

print("  Training complete!")

# ==================================================================
# STEP 7 — Evaluate
# ==================================================================
print("\n[Step 7] Evaluating on test set...")

model.eval()
with torch.no_grad():
    y_proba = model(x_cat_test_t, x_num_test_t).numpy()
    y_pred  = (y_proba >= 0.5).astype(int)

acc = accuracy_score(y_test, y_pred)
print(f"  Accuracy: {acc:.4f}")
print("\n  Classification Report:")
print(classification_report(y_test, y_pred, target_names=["Not Shortlisted", "Shortlisted"]))

# confusion matrix plot
cm = confusion_matrix(y_test, y_pred)
fig, ax = plt.subplots(figsize=(6, 5))
im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
plt.colorbar(im)
ax.set(xticks=[0, 1], yticks=[0, 1],
       xticklabels=["Not Shortlisted", "Shortlisted"],
       yticklabels=["Not Shortlisted", "Shortlisted"],
       ylabel="True Label", xlabel="Predicted Label",
       title="TabTransformer — Confusion Matrix")
# add text annotations inside the boxes
for i in range(2):
    for j in range(2):
        ax.text(j, i, str(cm[i, j]), ha='center', va='center',
                color='white' if cm[i, j] > cm.max() / 2 else 'black', fontsize=14)
plt.tight_layout()
plt.savefig(CM_PATH, dpi=150)
plt.close()
print(f"  Confusion matrix saved: {CM_PATH}")

# ==================================================================
# STEP 8 — Approximate Feature Importance via Permutation
# ==================================================================
# Since TabTransformer doesn't have native feature importance like Random Forest,
# we approximate it using permutation importance — we shuffle one feature at a time
# and measure how much accuracy drops. More drop = more important feature.
print("\n[Step 8] Computing permutation feature importance...")

def model_predict(x_cat_np, x_num_np):
    """Helper to run model inference from numpy arrays."""
    with torch.no_grad():
        x_cat_t = torch.tensor(x_cat_np, dtype=torch.long)
        x_num_t = torch.tensor(x_num_np, dtype=torch.float32)
        preds   = model(x_cat_t, x_num_t).numpy()
    return (preds >= 0.5).astype(int)

feature_names = cat_cols + ["Experience_Years", "skills_count"]
baseline_acc  = accuracy_score(y_test, model_predict(x_cat_test, x_num_test))
importance_scores = []

for i, feat_name in enumerate(feature_names):
    # shuffle this feature across all test samples
    shuffled_cat = x_cat_test.copy()
    shuffled_num = x_num_test.copy()
    
    if i < len(cat_cols):
        # it's a categorical feature — shuffle the i-th column
        np.random.shuffle(shuffled_cat[:, i])
    else:
        # it's a numerical feature
        num_i = i - len(cat_cols)
        np.random.shuffle(shuffled_num[:, num_i])
    
    perm_acc = accuracy_score(y_test, model_predict(shuffled_cat, shuffled_num))
    # importance = how much accuracy dropped when this feature was randomized
    importance_scores.append(baseline_acc - perm_acc)
    print(f"  {feat_name}: importance = {baseline_acc - perm_acc:.4f}")

# plot feature importance bar chart
fig, ax = plt.subplots(figsize=(8, 5))
colors = ['#3b7ef8' if s > 0 else '#ff6b6b' for s in importance_scores]
ax.barh(feature_names, importance_scores, color=colors)
ax.axvline(0, color='black', linewidth=0.8)
ax.set_xlabel("Accuracy Drop when Feature is Shuffled\n(higher = more important)")
ax.set_title("TabTransformer — Permutation Feature Importance")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(FI_PATH, dpi=150)
plt.close()
print(f"  Feature importance chart saved: {FI_PATH}")

# ==================================================================
# STEP 9 — Save everything
# ==================================================================
print("\n[Step 9] Saving model and config...")

# save model weights
torch.save(model.state_dict(), MODEL_PATH)
print(f"  Model saved: {MODEL_PATH}")

# save config so candidate_scorer.py knows the architecture to rebuild
model_config = {
    "embedding_dim":    EMBED_DIM,
    "num_heads":        NUM_HEADS,
    "num_layers":       NUM_LAYERS,
    "num_cat_features": NUM_CAT,
    "num_num_features": NUM_NUM,
    "cat_vocab_sizes":  cat_vocab_sizes,
    "cat_cols":         cat_cols,
    "num_cols":         ["Experience_Years", "skills_count"]
}
with open(CONFIG_PATH, "w") as f:
    json.dump(model_config, f, indent=2)
print(f"  Model config saved: {CONFIG_PATH}")

print("\n" + "=" * 60)
print("  TabTransformer saved successfully")
print(f"  Accuracy: {acc:.2%}")
print(f"  Files: tab_transformer.pth, model_config.json, label_encoders.pkl")
=======
# train_model.py - HireFlow-AI ML Training Pipeline
# ==================================================================
# Trains a Random Forest classifier on XLSX + JSON resume data.
# Uses Sentence-BERT for semantic skill/certificate matching.
# Generates: model.pkl, confusion_matrix.png, feature_importance.png
#
# Shared extraction logic lives in resume_features.py.
# ==================================================================

import os
import json
import re
import sys
import datetime
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless environments
import matplotlib.pyplot as plt
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sentence_transformers import SentenceTransformer, util

# Import shared extraction & config from the DRY module
from resume_features import (
    SCORING_WEIGHTS,
    STRONG_THRESHOLD,
    EXPERIENCE_NORM_CAP,
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
    split_individual_projects,
    extract_education_quality,
    extract_certificate_mentions,
)

print("=" * 60)
print("  HireFlow-AI Model Training Pipeline")
print("=" * 60)

# ------------------------------------------------------------------
# PATHS
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # one level up from backend/

XLSX_PATH = os.path.join(PROJECT_ROOT, "Super_Resume_Dataset_Rows_1_to_1000.xlsx")
JSON_PATH = os.path.join(BASE_DIR, "candidates_data.json")
MODEL_OUTPUT = os.path.join(BASE_DIR, "model.pkl")
CM_OUTPUT = os.path.join(BASE_DIR, "confusion_matrix.png")
FI_OUTPUT = os.path.join(BASE_DIR, "feature_importance.png")

# ==================================================================
# STEP 1: Load Sentence-BERT
# ==================================================================
print("\n[Step 1] Loading Sentence-BERT model (all-MiniLM-L6-v2)...")
bert_model = SentenceTransformer('all-MiniLM-L6-v2')
print("  BERT model loaded.")


# ==================================================================
# STEP 2: Feature Extraction Helpers (BERT-dependent)
# ==================================================================

def score_project_relevance(text, jd_embedding):
    """Scores project relevance against JD using BERT."""
    projects = extract_projects(text)
    if not projects:
        return 0.0
    try:
        project_embeddings = bert_model.encode(projects, convert_to_tensor=True)
        cosine_scores = util.cos_sim(project_embeddings, jd_embedding).cpu().numpy().flatten()
        RELEVANCE_THRESHOLD = 0.3
        relevant_scores = [float(s) for s in cosine_scores if s > RELEVANCE_THRESHOLD]
        if relevant_scores:
            avg_score = sum(relevant_scores) / len(relevant_scores)
            boost = min(len(relevant_scores) * 0.05, 0.15)
            return min(avg_score + boost, 1.0)
        return 0.0
    except Exception as e:
        print(f"  Warning: project scoring error: {e}")
        return 0.0


def get_certificate_relevance(text, jd_embedding):
    """Extracts certificate mentions and scores against JD via BERT."""
    cert_matches = extract_certificate_mentions(text)
    if not cert_matches:
        return 0.0
    try:
        cert_embeddings = bert_model.encode(cert_matches, convert_to_tensor=True)
        cosine_scores = util.cos_sim(cert_embeddings, jd_embedding)
        scores = cosine_scores.cpu().numpy().flatten()
        relevant_scores = [float(s) for s in scores if s > 0.3]
        if not relevant_scores:
            return 0.0
        return min(sum(relevant_scores), 1.0)
    except Exception as e:
        print(f"  Warning: cert scoring error: {e}")
        return 0.0


# ==================================================================
# STEP 3: Load Data (XLSX + JSON)
# ==================================================================
print("\n[Step 3] Loading data sources...")

# --- 3A: Load XLSX ---
df_excel = pd.DataFrame()
if os.path.exists(XLSX_PATH):
    print(f"  Loading Excel: {XLSX_PATH}")
    df_excel = pd.read_excel(XLSX_PATH)
    print(f"  Excel rows: {len(df_excel)}")

    # Build a synthetic raw_text from Excel columns for feature extraction
    skills_col = df_excel["Skills"].fillna("")
    certs_col = df_excel["Certifications"].fillna("") if "Certifications" in df_excel.columns else pd.Series([""] * len(df_excel))
    exp_col = df_excel["Experience_Years"].astype(str) + " years experience"
    email_col = df_excel["Email"].fillna("") if "Email" in df_excel.columns else pd.Series([""] * len(df_excel))
    phone_col = df_excel["Phone"].astype(str).fillna("") if "Phone" in df_excel.columns else pd.Series([""] * len(df_excel))

    df_excel["raw_text"] = (
        skills_col.astype(str) + " " +
        certs_col.astype(str) + " " +
        exp_col.astype(str) + " " +
        email_col.astype(str) + " " +
        phone_col.astype(str)
    )

    # Add education column if exists for education quality scoring
    if "Education" in df_excel.columns:
        df_excel["raw_text"] = df_excel["raw_text"] + " " + df_excel["Education"].fillna("").astype(str)

    # Use the JobRole as the JD for training
    df_excel["job_description"] = df_excel["JobRole"].fillna("software engineer")
    df_excel["is_excel"] = True
else:
    print(f"  WARNING: Excel file not found at {XLSX_PATH}")

# --- 3B: Load JSON ---
df_json = pd.DataFrame()
if os.path.exists(JSON_PATH):
    print(f"  Loading JSON: {JSON_PATH}")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    json_rows = []
    for batch in data.get("batches", []):
        jd = batch.get("job_description", "software engineer")
        for cand in batch.get("candidates", []):
            raw_text = cand.get("raw_text", "")
            if not raw_text or not raw_text.strip():
                continue  # skip entries with no text
            json_rows.append({
                "filename": cand.get("filename", ""),
                "raw_text": raw_text,
                "job_description": jd,
                "skills_list": cand.get("matched_skills", []),
                "is_excel":    False
            })

    df_json = pd.DataFrame(json_rows)
    if not df_json.empty:
        before = len(df_json)
        df_json = df_json.drop_duplicates(subset=["filename"])
        after = len(df_json)
        print(f"  JSON resumes: {before} -> {after} (after dedup)")
else:
    print(f"  No JSON file at {JSON_PATH} (that's OK for first training)")

# --- 3C: Merge ---
df = pd.concat([df_excel, df_json], ignore_index=True)
print(f"\n  Total combined samples: {len(df)}")

if len(df) == 0:
    print("\nERROR: No training data found!")
    print(f"  Expected Excel at: {XLSX_PATH}")
    print(f"  Expected JSON at : {JSON_PATH}")
    sys.exit(1)

# ==================================================================
# STEP 4: Feature Engineering
# ==================================================================
print("\n[Step 4] Extracting features...")

# 4A: Skill count
def _get_skills_count(row):
    if row.get("is_excel", False) and "Skills" in row and pd.notna(row.get("Skills")):
        return count_skills(row["Skills"])
    elif "skills_list" in row and isinstance(row.get("skills_list"), list):
        return len(row["skills_list"])
    return count_skills(str(row.get("raw_text", "")))

df["skills_count"] = df.apply(_get_skills_count, axis=1)

# 4B: Has WORK experience (section-aware, ignores education/project timelines)
df["has_experience"] = df["raw_text"].astype(str).apply(has_work_experience)

# 4C: Has contact info
df["has_contact"] = df["raw_text"].astype(str).apply(has_contact_info)

# 4D: Experience years (section-aware)
def _get_years(row):
    if row.get("is_excel", False) and "Experience_Years" in row:
        try:
            val = row["Experience_Years"]
            if pd.notna(val):
                return min(int(float(val)), 25)
        except (ValueError, TypeError):
            pass
    return extract_experience_years(str(row.get("raw_text", "")))

df["experience_years"] = df.apply(_get_years, axis=1)

# 4E: Education quality
def _get_education_quality(row):
    raw = str(row.get("raw_text", ""))
    jd = str(row.get("job_description", ""))
    return extract_education_quality(raw, jd)

df["education_quality"] = df.apply(_get_education_quality, axis=1)

# 4F: Semantic matching via BERT (the slow step)
print("  Computing Sentence-BERT embeddings (this may take a minute)...")

jd_texts = df["job_description"].astype(str).tolist()
resume_texts = df["raw_text"].astype(str).tolist()

# Encode in batches for memory efficiency
BATCH_SIZE = 64
print(f"  Encoding {len(jd_texts)} JD texts...")
jd_embeddings = bert_model.encode(jd_texts, convert_to_tensor=True, batch_size=BATCH_SIZE, show_progress_bar=False)
print(f"  Encoding {len(resume_texts)} resume texts...")
resume_embeddings = bert_model.encode(resume_texts, convert_to_tensor=True, batch_size=BATCH_SIZE, show_progress_bar=False)

skills_match_scores = []
cert_relevance_scores = []
project_relevance_scores = []

print("  Scoring semantic similarity + project relevance...")
for i in range(len(df)):
    # Skill match: resume text vs JD
    sim = util.cos_sim(resume_embeddings[i], jd_embeddings[i]).item()
    norm_sim = min(max((sim - 0.1) * 1.5, 0.0), 1.0)
    skills_match_scores.append(norm_sim)

    # Certificate match: individual certs vs JD
    cert_rel = get_certificate_relevance(df.iloc[i]["raw_text"], jd_embeddings[i])
    cert_relevance_scores.append(cert_rel)

    # Project relevance: individual projects vs JD
    proj_rel = score_project_relevance(df.iloc[i]["raw_text"], jd_embeddings[i])
    project_relevance_scores.append(proj_rel)

    if (i + 1) % 200 == 0:
        print(f"    Processed {i + 1}/{len(df)}...")

df["skills_match_score"] = skills_match_scores
df["certificate_relevance"] = cert_relevance_scores
df["project_relevance"] = project_relevance_scores
print("  Semantic features done!")

print("  Feature extraction complete!")
print(f"    skills_match_score   : mean={df['skills_match_score'].mean():.3f}, std={df['skills_match_score'].std():.3f}")
print(f"    certificate_relevance: mean={df['certificate_relevance'].mean():.3f}, std={df['certificate_relevance'].std():.3f}")
print(f"    project_relevance    : mean={df['project_relevance'].mean():.3f}, std={df['project_relevance'].std():.3f}")
print(f"    education_quality    : mean={df['education_quality'].mean():.3f}, std={df['education_quality'].std():.3f}")
print(f"    skills_count         : mean={df['skills_count'].mean():.1f}")
print(f"    experience_years     : mean={df['experience_years'].mean():.1f}")
print(f"    has_experience       : {df['has_experience'].sum()}/{len(df)}")
print(f"    has_contact          : {df['has_contact'].sum()}/{len(df)}")

# ==================================================================
# STEP 5: Generate Pseudo-Labels
# ==================================================================
print("\n[Step 5] Generating target labels via quality formula...")

# Use consistent normalisation cap from config
df["exp_score"] = (df["experience_years"] / EXPERIENCE_NORM_CAP).clip(upper=1.0)
df["skills_score_norm"] = (df["skills_count"] / 15.0).clip(upper=1.0)

df["quality_score"] = (
    (df["skills_match_score"]    * SCORING_WEIGHTS["skills_match"]) +
    (df["exp_score"]             * SCORING_WEIGHTS["experience"]) +
    (df["certificate_relevance"] * SCORING_WEIGHTS["certificates"]) +
    (df["has_contact"]           * SCORING_WEIGHTS["contact_info"]) +
    (df["skills_score_norm"]     * SCORING_WEIGHTS["skills_count"]) +
    (df["project_relevance"]     * SCORING_WEIGHTS["project_relevance"]) +
    (df["education_quality"]     * SCORING_WEIGHTS["education_quality"])
)

current_threshold = STRONG_THRESHOLD
df["shortlisted"] = (df["quality_score"] >= current_threshold).astype(int)

strong_count = df["shortlisted"].sum()
weak_count = (df["shortlisted"] == 0).sum()

# Auto-adjust threshold if labels are too imbalanced
if strong_count < 5 or weak_count < 5:
    print(f"  Warning: Default threshold {current_threshold} gave {strong_count} Strong, {weak_count} Weak.")
    print("  Auto-adjusting to top 25% as Strong...")
    current_threshold = df["quality_score"].quantile(0.75)
    df["shortlisted"] = (df["quality_score"] >= current_threshold).astype(int)
    strong_count = df["shortlisted"].sum()
    weak_count = (df["shortlisted"] == 0).sum()
    print(f"  New threshold: {current_threshold:.3f}")

print(f"  Label distribution: {strong_count} Strong (1), {weak_count} Weak (0)")
print(f"  Quality score stats: mean={df['quality_score'].mean():.3f}, "
      f"min={df['quality_score'].min():.3f}, max={df['quality_score'].max():.3f}")

# ==================================================================
# STEP 6: Train Random Forest
# ==================================================================
print("\n[Step 6] Training Random Forest model...")

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
X = df[feature_cols].copy()
y = df["shortlisted"].copy()

# Fill any NaN that might have slipped through
X = X.fillna(0)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    min_samples_split=5,
    class_weight="balanced",  # handles class imbalance
    random_state=42
)
model.fit(X_train, y_train)
print("  Training complete!")

print(f"  Training samples: {len(X_train)}")
print(f"  Testing samples : {len(X_test)}")

# ==================================================================
# STEP 7: Evaluate
# ==================================================================
print("\n[Step 7] Evaluating model...")

y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print(f"\n  Test Accuracy: {accuracy:.4f} ({accuracy * 100:.2f}%)")
print("\n  Classification Report:")
print(classification_report(
    y_test, y_pred,
    labels=[0, 1],
    target_names=["Weak", "Strong"],
    zero_division=0
))

# Cross-validation for more robust metric
print("  Running 5-fold cross-validation...")
cv_scores = cross_val_score(model, X, y, cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42), scoring='accuracy')
print(f"  CV Accuracy: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

# --- Confusion Matrix Plot ---
cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
fig, ax = plt.subplots(figsize=(6, 5))
im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
plt.colorbar(im, ax=ax)
ax.set_xlabel("Predicted", fontsize=12)
ax.set_ylabel("True", fontsize=12)
ax.set_title(f"Confusion Matrix (Threshold={current_threshold:.2f})", fontsize=14)
ax.set_xticks([0, 1])
ax.set_yticks([0, 1])
ax.set_xticklabels(["Weak", "Strong"])
ax.set_yticklabels(["Weak", "Strong"])
for i in range(cm.shape[0]):
    for j in range(cm.shape[1]):
        color = "white" if cm[i, j] > cm.max() / 2 else "black"
        ax.text(j, i, str(cm[i, j]), ha="center", va="center", color=color, fontsize=14)
plt.tight_layout()
plt.savefig(CM_OUTPUT, dpi=150)
plt.close()
print(f"  Saved: {CM_OUTPUT}")

# --- Feature Importance Plot ---
importances = model.feature_importances_
sorted_idx = np.argsort(importances)
sorted_features = [feature_cols[i] for i in sorted_idx]
sorted_importances = importances[sorted_idx]

fig, ax = plt.subplots(figsize=(8, 5))
colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(sorted_features)))
bars = ax.barh(sorted_features, sorted_importances, color=colors)
ax.set_xlabel("Importance Score", fontsize=12)
ax.set_title("Feature Importance - Random Forest", fontsize=14)
for bar, val in zip(bars, sorted_importances):
    ax.text(val + 0.005, bar.get_y() + bar.get_height() / 2,
            f"{val:.3f}", va="center", fontsize=10)
plt.tight_layout()
plt.savefig(FI_OUTPUT, dpi=150)
plt.close()
print(f"  Saved: {FI_OUTPUT}")

# ==================================================================
# STEP 8: Save Model
# ==================================================================
print("\n[Step 8] Saving model...")
joblib.dump(model, MODEL_OUTPUT)
print(f"  Saved: {MODEL_OUTPUT}")

# ==================================================================
# DONE
# ==================================================================
print("\n" + "=" * 60)
print("  Training Complete!")
print("=" * 60)
print(f"  Artifacts:")
print(f"    model.pkl              - Random Forest (200 trees, max_depth=10)")
print(f"    confusion_matrix.png   - Test set confusion matrix")
print(f"    feature_importance.png - Feature importance chart")
print(f"  Features: {', '.join(feature_cols)}")
print(f"  Test Accuracy: {accuracy * 100:.2f}%")
print(f"  CV Accuracy:   {cv_scores.mean() * 100:.2f}% +/- {cv_scores.std() * 100:.2f}%")
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
print("=" * 60)
