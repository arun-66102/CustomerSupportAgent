"""
Builds a TF-IDF vector index over all Apple Support customer messages.
The index is used for semantic retrieval of similar historical conversations.
"""

import sys
import json
import pickle
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sklearn.feature_extraction.text import TfidfVectorizer

INDEX_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "index"  # backend/data/index
INDEX_FILE = INDEX_DIR / "tfidf_index.pkl"

_index_data = None  # {"vectorizer": ..., "matrix": ..., "conversations": [...]}


def build_index(conversations: list[dict], force_rebuild: bool = False) -> dict:
    """
    Build a TF-IDF index from conversation pairs.
    
    Args:
        conversations: List of dicts with 'customer_message', 'brand_response', etc.
        force_rebuild: If True, rebuild even if cached index exists.
    
    Returns:
        index_data dict with vectorizer, matrix, and conversations.
    """
    global _index_data

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    if not force_rebuild and INDEX_FILE.exists():
        print(f"[Index] Loading cached index from {INDEX_FILE}")
        with open(INDEX_FILE, "rb") as f:
            _index_data = pickle.load(f)
        print(f"[Index] Loaded index with {len(_index_data['conversations'])} entries.")
        return _index_data

    print(f"[Index] Building TF-IDF index over {len(conversations)} conversations...")

    # Use customer messages as the index corpus
    corpus = [c["customer_message"] for c in conversations]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=20000,
        sublinear_tf=True,
        min_df=1,
        analyzer="word"
    )

    matrix = vectorizer.fit_transform(corpus)

    _index_data = {
        "vectorizer": vectorizer,
        "matrix": matrix,
        "conversations": conversations
    }

    with open(INDEX_FILE, "wb") as f:
        pickle.dump(_index_data, f)
    print(f"[Index] Built and saved index. Shape: {matrix.shape}")

    return _index_data


def get_index() -> dict | None:
    """Return the loaded index, or None if not yet built."""
    global _index_data
    if _index_data is None and INDEX_FILE.exists():
        with open(INDEX_FILE, "rb") as f:
            _index_data = pickle.load(f)
    return _index_data


def rebuild_index(conversations: list[dict]) -> dict:
    """Force a full index rebuild."""
    return build_index(conversations, force_rebuild=True)
