"""
Pre-processing (project documentation Section 5.1, Step 2)
-------------------------------------------------------------
tokenization -> stopword removal -> lemmatization.

Lemmatization is used instead of stemming so extracted terms stay
human-readable in the explainability UI (see design doc Section 5.1):
stemming "managing" -> "manag" looks broken on screen, lemmatizing
"managing" -> "manage" reads naturally.
"""

from __future__ import annotations
import re

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

try:
    _STOPWORDS = set(stopwords.words("english"))
except LookupError:
    nltk.download("stopwords", quiet=True)
    _STOPWORDS = set(stopwords.words("english"))

try:
    _LEMMATIZER = WordNetLemmatizer()
    _LEMMATIZER.lemmatize("test")
except LookupError:
    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)
    _LEMMATIZER = WordNetLemmatizer()

# Common resume boilerplate that isn't a real NLTK stopword but adds noise.
_EXTRA_NOISE = {"resume", "cv", "curriculum", "vitae", "page", "confidential", "references", "available"}


def clean_text(text: str) -> str:
    """Light normalization: lowercase, strip emails/phones/urls, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"\S+@\S+\.\S+", " ", text)  # emails
    text = re.sub(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", " ", text)  # US-style phone numbers
    text = re.sub(r"https?://\S+", " ", text)  # urls
    text = re.sub(r"[^a-z0-9+#./\- ]", " ", text)  # keep tech-relevant punctuation (c++, c#, node.js)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_and_lemmatize(text: str) -> list[str]:
    """Full pipeline: clean -> tokenize -> stopword removal -> lemmatize."""
    cleaned = clean_text(text)
    try:
        tokens = word_tokenize(cleaned)
    except LookupError:
        nltk.download("punkt", quiet=True)
        nltk.download("punkt_tab", quiet=True)
        tokens = word_tokenize(cleaned)
    result = []
    for tok in tokens:
        if len(tok) <= 1:
            continue
        if tok in _STOPWORDS or tok in _EXTRA_NOISE:
            continue
        result.append(_LEMMATIZER.lemmatize(tok))
    return result


def preprocess_for_vectorizer(text: str) -> str:
    """Returns a cleaned, lemmatized string (space-joined) -- the form TF-IDF expects."""
    return " ".join(tokenize_and_lemmatize(text))
