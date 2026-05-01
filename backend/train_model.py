# train_model.py — HireFlow AI
# ====================================================================
# TabTransformer training pipeline.
# TabTransformer = Transformer attention on categorical features (like
# Department, JobRole) + regular MLP on numerical features.
#
# The target label is now a composite "quality score" instead of the
# old binary (experience>5 AND salary>median) which was way too strict
# and caused all junior candidates to score near zero.
#
# New label logic:
#   - experience_norm (0-1) weighted 40%
#   - skills_count_norm (0-1) weighted 35%
#   - salary_percentile (0-1) weighted 25%
#   - shortlisted = 1 if composite >= 0.40
#
# This produces a more balanced dataset and realistic predictions.
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
# STEP 2 — Create the target variable (IMPROVED)
# ==================================================================
print("\n[Step 2] Engineering target variable (composite quality score)...")

# fill any missing values in these key columns
df["Experience_Years"] = pd.to_numeric(df["Experience_Years"], errors="coerce").fillna(0)
df["Expected_Salary"]  = pd.to_numeric(df["Expected_Salary"], errors="coerce").fillna(0)

# Composite quality scoring — much more balanced than the old binary label
# which required BOTH experience>5 AND salary>median (too strict)

# Normalize experience: cap at 15 years, so 7.5 years = 0.5
exp_norm = (df["Experience_Years"].clip(0, 15) / 15.0)

# Normalize skills count: cap at 15 skills
skills_norm = (df["skills_count"].clip(0, 15) / 15.0)

# Salary percentile (rank-based, 0 to 1)
salary_pctile = df["Expected_Salary"].rank(pct=True).fillna(0.5)

# Composite score: weighted average
composite = (
    exp_norm    * 0.40 +
    skills_norm * 0.35 +
    salary_pctile * 0.25
)

# Shortlisted if composite >= 0.40 (more balanced threshold)
df["shortlisted"] = (composite >= 0.40).astype(int)

shortlisted_count = df["shortlisted"].sum()
print(f"  Composite score range: {composite.min():.3f} to {composite.max():.3f}")
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

# hyperparameters
EMBED_DIM    = 32   # each categorical feature gets a 32-dim embedding
NUM_HEADS    = 4    # multi-head attention with 4 heads
NUM_LAYERS   = 2    # 2 Transformer encoder layers
NUM_CAT      = len(cat_cols)    # 2 categorical features
NUM_NUM      = 2                # 2 numerical features: Experience_Years, skills_count
DROPOUT      = 0.1
BATCH_SIZE   = 32
EPOCHS       = 50   # increased from 30 for better convergence
LR           = 0.001

# number of unique values per categorical column (for embedding table size)
cat_vocab_sizes = [len(label_encoders[col].classes_) for col in cat_cols]

class MultiHeadSelfAttention(nn.Module):
    """
    Simple multi-head self-attention block.
    Input:  (batch, seq_len, embed_dim)   — seq_len = number of cat features
    Output: (batch, seq_len, embed_dim)
    """
    def __init__(self, embed_dim, num_heads, dropout=0.1):
        super().__init__()
        assert embed_dim % num_heads == 0, "embed_dim must be divisible by num_heads"
        
        self.num_heads = num_heads
        self.head_dim  = embed_dim // num_heads
        self.scale     = self.head_dim ** -0.5
        
        self.qkv_proj  = nn.Linear(embed_dim, 3 * embed_dim)
        self.out_proj   = nn.Linear(embed_dim, embed_dim)
        self.dropout_l  = nn.Dropout(dropout)
        self.norm       = nn.LayerNorm(embed_dim)
    
    def forward(self, x):
        batch, seq, d_model = x.shape
        
        qkv = self.qkv_proj(x)
        q, k, v = qkv.chunk(3, dim=-1)
        
        def reshape_for_heads(t):
            return t.view(batch, seq, self.num_heads, self.head_dim).transpose(1, 2)
        
        q, k, v = reshape_for_heads(q), reshape_for_heads(k), reshape_for_heads(v)
        
        attn_weights = torch.matmul(q, k.transpose(-2, -1)) * self.scale
        attn_weights = torch.softmax(attn_weights, dim=-1)
        attn_weights = self.dropout_l(attn_weights)
        
        attn_out = torch.matmul(attn_weights, v)
        attn_out = attn_out.transpose(1, 2).contiguous().view(batch, seq, d_model)
        attn_out = self.out_proj(attn_out)
        
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
        
        self.embeddings = nn.ModuleList([
            nn.Embedding(vocab_size + 1, embed_dim)
            for vocab_size in cat_vocab_sizes
        ])
        
        self.attention_layers = nn.ModuleList([
            MultiHeadSelfAttention(embed_dim, num_heads, dropout)
            for _ in range(num_layers)
        ])
        
        self.num_norm = nn.LayerNorm(num_num_features)
        
        combined_dim = self.num_cat * embed_dim + num_num_features
        
        self.mlp = nn.Sequential(
            nn.Linear(combined_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
        
        self.embedding_layer = nn.Sequential(
            nn.Linear(combined_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU()
        )
    
    def _get_combined_features(self, x_cat, x_num):
        cat_embeds = [emb(x_cat[:, i]) for i, emb in enumerate(self.embeddings)]
        cat_stack = torch.stack(cat_embeds, dim=1)
        for attn_layer in self.attention_layers:
            cat_stack = attn_layer(cat_stack)
        cat_flat = cat_stack.view(cat_stack.size(0), -1)
        num_normed = self.num_norm(x_num)
        combined = torch.cat([cat_flat, num_normed], dim=1)
        return combined
    
    def forward(self, x_cat, x_num):
        combined = self._get_combined_features(x_cat, x_num)
        out = self.mlp(combined)
        return out.squeeze(1)
    
    def get_embedding(self, x_cat, x_num):
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
criterion = nn.BCELoss()

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
    if epoch % 10 == 0 or epoch == 1:
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
print("\n[Step 8] Computing permutation feature importance...")

def model_predict(x_cat_np, x_num_np):
    with torch.no_grad():
        x_cat_t = torch.tensor(x_cat_np, dtype=torch.long)
        x_num_t = torch.tensor(x_num_np, dtype=torch.float32)
        preds   = model(x_cat_t, x_num_t).numpy()
    return (preds >= 0.5).astype(int)

feature_names = cat_cols + ["Experience_Years", "skills_count"]
baseline_acc  = accuracy_score(y_test, model_predict(x_cat_test, x_num_test))
importance_scores = []

for i, feat_name in enumerate(feature_names):
    shuffled_cat = x_cat_test.copy()
    shuffled_num = x_num_test.copy()
    
    if i < len(cat_cols):
        np.random.shuffle(shuffled_cat[:, i])
    else:
        num_i = i - len(cat_cols)
        np.random.shuffle(shuffled_num[:, num_i])
    
    perm_acc = accuracy_score(y_test, model_predict(shuffled_cat, shuffled_num))
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

# verify label_encoders.pkl was saved
if os.path.exists(ENC_PATH):
    print(f"  Label encoders verified: {ENC_PATH}")
else:
    print(f"  WARNING: Label encoders file NOT found at {ENC_PATH}!")

print("\n" + "=" * 60)
print("  TabTransformer saved successfully")
print(f"  Accuracy: {acc:.2%}")
print(f"  Files: tab_transformer.pth, model_config.json, label_encoders.pkl")
print("=" * 60)
