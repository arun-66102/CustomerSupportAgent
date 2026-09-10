"""
Data loader for the AppleSupport brand from the TWCS dataset.
Reconstructs multi-turn conversations and caches them to JSON.
"""

import os
import json
import re
import pandas as pd
from pathlib import Path

# Paths: loader.py is at backend/src/preprocessing/loader.py
# .parent = preprocessing, .parent.parent = src, .parent.parent.parent = backend
# .parent×4 = Brand_Chatbot (project root where twcs/ lives)
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent   # d:\Brand_Chatbot\backend
PROJECT_ROOT = BACKEND_DIR.parent                             # d:\Brand_Chatbot
RAW_CSV = PROJECT_ROOT / "twcs" / "twcs.csv"
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"
PROCESSED_FILE = PROCESSED_DIR / "apple_conversations.json"

BRAND = "AppleSupport"


def clean_tweet_text(text: str) -> str:
    """Remove @mentions, URLs, HTML entities, and extra whitespace."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_and_process_data() -> list[dict]:
    """
    Load the full TWCS CSV, filter to AppleSupport, reconstruct conversations,
    and return a list of conversation dicts.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Return cached version if it exists
    if PROCESSED_FILE.exists():
        print(f"[Loader] Loading cached conversations from {PROCESSED_FILE}")
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"[Loader] Processing raw CSV: {RAW_CSV} ...")
    if not RAW_CSV.exists():
        raise FileNotFoundError(f"Dataset not found at {RAW_CSV}")

    # Load only necessary columns
    df = pd.read_csv(
        RAW_CSV,
        usecols=["tweet_id", "author_id", "inbound", "text",
                 "response_tweet_id", "in_response_to_tweet_id"],
        dtype={"tweet_id": str, "in_response_to_tweet_id": str,
               "response_tweet_id": str, "author_id": str},
        low_memory=False
    )

    # Filter to AppleSupport brand responses that have in_response_to_tweet_id
    brand_df = df[
        (df["author_id"] == BRAND) & 
        (df["in_response_to_tweet_id"].notna()) & 
        (df["in_response_to_tweet_id"] != "") &
        (df["in_response_to_tweet_id"] != "nan")
    ].copy()

    # Fast hash lookup or merge
    merged = pd.merge(
        brand_df,
        df[["tweet_id", "text"]],
        left_on="in_response_to_tweet_id",
        right_on="tweet_id",
        suffixes=("_brand", "_cust")
    )

    conversations = []
    seen_pairs = set()

    for _, row in merged.iterrows():
        cust_text = clean_tweet_text(str(row.get("text_cust", "")))
        brand_text = clean_tweet_text(str(row.get("text_brand", "")))

        # Filter out empty or very short texts
        if len(cust_text) < 10 or len(brand_text) < 10:
            continue

        brand_id = str(row["tweet_id_brand"])
        cust_id = str(row["in_response_to_tweet_id"])
        pair_key = f"{cust_id}_{brand_id}"
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        conversations.append({
            "conversation_id": brand_id,
            "customer_tweet_id": cust_id,
            "brand_tweet_id": brand_id,
            "customer_message": cust_text,
            "brand_response": brand_text,
        })

    print(f"[Loader] Extracted {len(conversations)} Apple Support conversation pairs.")

    # Cache to disk
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(conversations, f, ensure_ascii=False, indent=2)
    print(f"[Loader] Saved to {PROCESSED_FILE}")

    return conversations


if __name__ == "__main__":
    convs = load_and_process_data()
    print(f"Total conversations loaded: {len(convs)}")
    for c in convs[:3]:
        print(c)
