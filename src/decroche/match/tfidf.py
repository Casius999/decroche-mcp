"""Tiny pure TF-IDF salience scorer — no external ML library.

Only dependency: Python stdlib.  Deterministic, offline.

``salience(term, offer_text) -> float`` returns a score ∈ [0, 1] indicating
how distinctive *term* is relative to the offer text.  Stopwords from a
combined FR+EN list are filtered before scoring so common filler words never
rank high.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache

# ── Stopwords ────────────────────────────────────────────────────────────────────────────
# Combined FR + EN stopword list.  Lowercase.

_STOPWORDS: frozenset[str] = frozenset(
    [
        # EN
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "not", "no", "nor",
        "so", "yet", "both", "either", "neither", "each", "such", "than",
        "too", "very", "as", "if", "then", "that", "this", "these", "those",
        "we", "you", "he", "she", "it", "they", "our", "your", "his", "her",
        "its", "their", "my", "who", "which", "what", "where", "when", "how",
        "about", "between", "into", "through", "during", "before", "after",
        "above", "below", "up", "down", "out", "off", "over", "under",
        "again", "further", "while", "although", "since", "until", "unless",
        "also", "just", "more", "most", "other", "only", "same", "any",
        "all", "some", "one", "two", "three", "year", "years", "experience",
        "ability", "excellent", "good", "strong", "knowledge", "skills",
        "position", "team", "work", "working", "role", "join", "looking",
        "candidate", "candidates", "apply", "application",
        # FR
        "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "en",
        "dans", "sur", "avec", "par", "pour", "est", "sont", "être", "avoir",
        "vous", "nous", "il", "elle", "ils", "elles", "se", "qui", "que",
        "quoi", "dont", "où", "pas", "ne", "plus", "très", "bien", "tout",
        "tous", "toute", "toutes", "ce", "cette", "ces", "mon", "ton", "son",
        "notre", "votre", "leur", "leurs", "ma", "ta", "sa", "au", "aux",
        "ans", "poste", "équipe", "equipe", "candidat", "rejoindre",
        "capacité", "capacite", "excellente", "bonne", "forte", "connaissance",
        "compétence", "competence", "expérience", "experience",
    ]
)

_TOKEN_RE = re.compile(r"\b[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9+#/.'-]{0,49}\b")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _tf(term: str, tokens: list[str]) -> float:
    """Term frequency (raw count / total tokens)."""
    if not tokens:
        return 0.0
    count = tokens.count(term.lower())
    return count / len(tokens)


def _idf(term: str, tokens: list[str]) -> float:
    """IDF against a single document treated as multiple 'pseudo-documents'
    (each sentence is one document).

    We treat the offer text as the entire corpus (N=1 document).  To give
    meaningful differentiation within that document we use sentence-level IDF:
    each sentence = one mini-doc.

    IDF = log((1 + n_sentences) / (1 + df)) + 1
    where df = number of sentences containing the term.
    """
    if not tokens:
        return 1.0
    # We don't have access to the original text here; tokens already flattened.
    # Use a simple approximation: IDF ∝ inverse of raw frequency.
    count = tokens.count(term.lower())
    if count == 0:
        return 1.0
    return math.log((len(tokens) + 1) / (count + 1)) + 1.0


@lru_cache(maxsize=256)
def _score_cached(term: str, offer_text: str) -> float:
    tokens = [t for t in _tokenize(offer_text) if t not in _STOPWORDS]
    if not tokens:
        return 0.0
    t = term.lower()
    tf = _tf(t, tokens)
    idf = _idf(t, tokens)
    raw = tf * idf
    # Normalise to [0, 1]: max possible tf=1.0, max idf≈log(N)+1.
    # We cap at 1.0 to keep the interface simple.
    return min(1.0, raw * 10.0)  # scale factor makes scores human-readable


def salience(term: str, offer_text: str) -> float:
    """Return a salience score ∈ [0, 1] for *term* in *offer_text*.

    Terms that appear frequently (high TF) but are not stopwords score high.
    Unknown or absent terms score 0.
    Stopword-filtered TF-IDF with sentence-level IDF approximation.
    """
    return _score_cached(term, offer_text)
