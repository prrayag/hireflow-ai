"""Shared NER building blocks: tokenizer, BIO helpers and a BiLSTM-CRF in PyTorch.

Both the training scripts and the Flask runtime import this module, so it must
stay free of Flask/Mongo/Spark imports. The CRF is written from scratch (forward
algorithm for the partition function, Viterbi for decoding) rather than taken
from a library, so every part of the sequence model is visible and testable.
"""

from __future__ import annotations

import re

import torch
from torch import nn


# Entity types learned from SkillSpan (Zhang et al., NAACL 2022):
#   TECH = SkillSpan "knowledge" spans (tools, languages, frameworks, degrees)
#   SOFT = SkillSpan "skill" spans (abilities and behaviours)
LABELS = ["O", "B-TECH", "I-TECH", "B-SOFT", "I-SOFT"]
LABEL_TO_ID = {label: index for index, label in enumerate(LABELS)}

PAD, UNK = "<pad>", "<unk>"

# Punctuation split off the end of a whitespace token. Characters that are part
# of skill names (".", "+", "#", "/") stay attached, so "node.js", "C++", "C#"
# and "CI/CD" survive as single tokens.
_TRAILING = re.compile(r"^(.*?)([,;:!?)\]}\"'.]+)$")
_LEADING = re.compile(r"^([(\[{\"'•●▪*-]+)(.+)$")


def tokenize(text: str) -> list[tuple[str, int, int]]:
    """Split text into (token, start, end) triples in the SkillSpan token style."""
    tokens: list[tuple[str, int, int]] = []
    for match in re.finditer(r"\S+", text):
        word, start = match.group(0), match.start()
        lead = _LEADING.match(word)
        if lead and lead.group(2):
            tokens.append((lead.group(1), start, start + len(lead.group(1))))
            start += len(lead.group(1))
            word = lead.group(2)
        tail = _TRAILING.match(word)
        if tail and tail.group(1):
            core = tail.group(1)
            tokens.append((core, start, start + len(core)))
            tokens.append((tail.group(2), start + len(core), start + len(word)))
        else:
            tokens.append((word, start, start + len(word)))
    return tokens


def merge_skillspan_tags(tags_skill: list[str], tags_knowledge: list[str]) -> list[str]:
    """Combine SkillSpan's two BIO layers into one label sequence.

    The layers overlap on under 1% of tokens; knowledge (TECH) wins there because
    it is what the ranking pipeline consumes.
    """
    labels = []
    for skill, knowledge in zip(tags_skill, tags_knowledge):
        if knowledge != "O":
            labels.append(f"{knowledge}-TECH")
        elif skill != "O":
            labels.append(f"{skill}-SOFT")
        else:
            labels.append("O")
    return repair_bio(labels)


def repair_bio(labels: list[str]) -> list[str]:
    """Turn an I- tag that does not continue an entity of the same type into B-."""
    repaired = []
    previous = "O"
    for label in labels:
        if label.startswith("I-") and previous[2:] != label[2:]:
            label = "B-" + label[2:]
        repaired.append(label)
        previous = label
    return repaired


def bio_spans(labels: list[str]) -> list[tuple[str, int, int]]:
    """Return (type, start_token, end_token_exclusive) entity spans."""
    spans = []
    current_type, start = None, 0
    for index, label in enumerate(list(labels) + ["O"]):
        begins = label.startswith("B-") or (label.startswith("I-") and label[2:] != current_type)
        if current_type and (label == "O" or begins):
            spans.append((current_type, start, index))
            current_type = None
        if begins:
            current_type, start = label[2:], index
    return spans


class CRF(nn.Module):
    """Linear-chain conditional random field over emission scores."""

    def __init__(self, num_tags: int):
        super().__init__()
        self.num_tags = num_tags
        self.start_transitions = nn.Parameter(torch.empty(num_tags).uniform_(-0.1, 0.1))
        self.end_transitions = nn.Parameter(torch.empty(num_tags).uniform_(-0.1, 0.1))
        # transitions[i, j] is the score of moving from tag i to tag j.
        self.transitions = nn.Parameter(torch.empty(num_tags, num_tags).uniform_(-0.1, 0.1))

    def neg_log_likelihood(self, emissions: torch.Tensor, tags: torch.Tensor,
                           mask: torch.Tensor) -> torch.Tensor:
        """Mean negative log-likelihood. Shapes: (B, T, K), (B, T), (B, T) bool."""
        return (self._log_partition(emissions, mask) - self._path_score(emissions, tags, mask)).mean()

    def _path_score(self, emissions, tags, mask):
        batch = torch.arange(emissions.size(0), device=emissions.device)
        score = self.start_transitions[tags[:, 0]] + emissions[batch, 0, tags[:, 0]]
        for t in range(1, emissions.size(1)):
            step = self.transitions[tags[:, t - 1], tags[:, t]] + emissions[batch, t, tags[:, t]]
            score = score + step * mask[:, t]
        last_tags = tags[batch, mask.sum(1) - 1]
        return score + self.end_transitions[last_tags]

    def _log_partition(self, emissions, mask):
        alpha = self.start_transitions + emissions[:, 0]
        for t in range(1, emissions.size(1)):
            scores = alpha.unsqueeze(2) + self.transitions.unsqueeze(0) + emissions[:, t].unsqueeze(1)
            alpha = torch.where(mask[:, t].unsqueeze(1), torch.logsumexp(scores, dim=1), alpha)
        return torch.logsumexp(alpha + self.end_transitions, dim=1)

    def decode(self, emissions: torch.Tensor, mask: torch.Tensor) -> list[list[int]]:
        """Viterbi decoding of the highest-scoring tag sequence for each item."""
        score = self.start_transitions + emissions[:, 0]
        history = []
        for t in range(1, emissions.size(1)):
            candidates = score.unsqueeze(2) + self.transitions.unsqueeze(0)
            best, indices = candidates.max(dim=1)
            next_score = best + emissions[:, t]
            score = torch.where(mask[:, t].unsqueeze(1), next_score, score)
            history.append(indices)
        score = score + self.end_transitions
        lengths = mask.sum(1).tolist()
        paths = []
        for item in range(emissions.size(0)):
            best_tag = int(score[item].argmax())
            path = [best_tag]
            for indices in reversed(history[:lengths[item] - 1]):
                best_tag = int(indices[item, best_tag])
                path.append(best_tag)
            paths.append(list(reversed(path)))
        return paths


class BiLSTMCRF(nn.Module):
    """Word embeddings + character CNN -> BiLSTM -> CRF (Lample et al., 2016 style)."""

    def __init__(self, word_vocab_size: int, char_vocab_size: int, num_tags: int,
                 word_dim: int = 100, char_dim: int = 30, char_filters: int = 50,
                 hidden_dim: int = 128, dropout: float = 0.5):
        super().__init__()
        self.word_embedding = nn.Embedding(word_vocab_size, word_dim, padding_idx=0)
        self.char_embedding = nn.Embedding(char_vocab_size, char_dim, padding_idx=0)
        # The character CNN gives the model a representation for words it never
        # saw in training (new frameworks, typos), which word embeddings cannot.
        self.char_cnn = nn.Conv1d(char_dim, char_filters, kernel_size=3, padding=1)
        self.dropout = nn.Dropout(dropout)
        self.lstm = nn.LSTM(word_dim + char_filters, hidden_dim, batch_first=True,
                            bidirectional=True)
        self.emissions = nn.Linear(hidden_dim * 2, num_tags)
        self.crf = CRF(num_tags)

    def _emission_scores(self, words, chars, mask):
        batch, steps, max_chars = chars.shape
        char_vectors = self.char_embedding(chars.view(batch * steps, max_chars)).transpose(1, 2)
        char_features = torch.relu(self.char_cnn(char_vectors)).max(dim=2).values
        features = torch.cat([self.word_embedding(words),
                              char_features.view(batch, steps, -1)], dim=2)
        lengths = mask.sum(1).cpu()
        packed = nn.utils.rnn.pack_padded_sequence(self.dropout(features), lengths,
                                                   batch_first=True, enforce_sorted=False)
        output, _ = self.lstm(packed)
        output, _ = nn.utils.rnn.pad_packed_sequence(output, batch_first=True,
                                                     total_length=steps)
        return self.emissions(self.dropout(output))

    def loss(self, words, chars, tags, mask):
        return self.crf.neg_log_likelihood(self._emission_scores(words, chars, mask), tags, mask)

    def predict(self, words, chars, mask) -> tuple[list[list[int]], list[list[float]]]:
        """Viterbi tags plus a per-token confidence (softmax of the emission scores)."""
        emissions = self._emission_scores(words, chars, mask)
        paths = self.crf.decode(emissions, mask)
        probabilities = torch.softmax(emissions, dim=2)
        confidences = [[float(probabilities[i, t, tag]) for t, tag in enumerate(path)]
                       for i, path in enumerate(paths)]
        return paths, confidences


def encode_transformer_batch(tokenizer, token_lists: list[list[str]], max_length: int = 256,
                             label_lists: list[list[str]] | None = None):
    """Tokenize pre-split words; only the first sub-word of each word is labelled.

    Returns the tokenizer encoding plus, per item, the sub-word position of each
    word's first piece (None when the word was truncated away).
    """
    encoding = tokenizer(token_lists, is_split_into_words=True, truncation=True,
                         max_length=max_length, padding=True, return_tensors="pt")
    first_piece, labels = [], []
    for i in range(len(token_lists)):
        positions: list[int | None] = [None] * len(token_lists[i])
        row_labels = [-100] * encoding["input_ids"].shape[1]
        previous = None
        for position, word in enumerate(encoding.word_ids(batch_index=i)):
            if word is not None and word != previous:
                positions[word] = position
                if label_lists is not None:
                    row_labels[position] = LABEL_TO_ID[label_lists[i][word]]
            previous = word
        first_piece.append(positions)
        labels.append(row_labels)
    if label_lists is not None:
        encoding["labels"] = torch.tensor(labels)
    return encoding, first_piece


def transformer_predict(model, tokenizer, token_lists: list[list[str]], device="cpu",
                        batch_size: int = 32, max_length: int = 256):
    """Return (labels, confidences) per word for a token-classification model."""
    model.eval()
    all_labels, all_confidences = [], []
    with torch.no_grad():
        for start in range(0, len(token_lists), batch_size):
            batch = token_lists[start:start + batch_size]
            encoding, first_piece = encode_transformer_batch(tokenizer, batch, max_length)
            inputs = {k: v.to(device) for k, v in encoding.items()}
            probabilities = torch.softmax(model(**inputs).logits, dim=2).cpu()
            for i, positions in enumerate(first_piece):
                labels, confidences = [], []
                for position in positions:
                    if position is None:
                        labels.append("O")
                        confidences.append(1.0)
                    else:
                        best = int(probabilities[i, position].argmax())
                        labels.append(LABELS[best])
                        confidences.append(float(probabilities[i, position, best]))
                all_labels.append(repair_bio(labels))
                all_confidences.append(confidences)
    return all_labels, all_confidences


def encode_bilstm_batch(token_lists: list[list[str]], word_to_id: dict[str, int],
                        char_to_id: dict[str, int], max_word_chars: int = 20):
    """Pad a batch of token lists into word ids, char ids and a mask."""
    steps = max(len(tokens) for tokens in token_lists)
    words = torch.zeros(len(token_lists), steps, dtype=torch.long)
    chars = torch.zeros(len(token_lists), steps, max_word_chars, dtype=torch.long)
    mask = torch.zeros(len(token_lists), steps, dtype=torch.bool)
    unk_word, unk_char = word_to_id[UNK], char_to_id[UNK]
    for i, tokens in enumerate(token_lists):
        for t, token in enumerate(tokens):
            words[i, t] = word_to_id.get(token.lower(), unk_word)
            for c, char in enumerate(token[:max_word_chars]):
                chars[i, t, c] = char_to_id.get(char, unk_char)
            mask[i, t] = True
    return words, chars, mask
