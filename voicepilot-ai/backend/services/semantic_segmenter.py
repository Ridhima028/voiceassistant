"""
Turns Whisper's raw, pause-based segments into semantically coherent chunks.

Whisper (via its VAD) breaks audio into segments purely based on silence —
it has no idea whether two adjacent segments are part of the same sentence,
the same thought, or completely unrelated topics. This module re-groups
those raw segments using two signals together:

  1. Pause length between segments  — a long silence often (but not always)
     marks a real break.
  2. Semantic similarity of the text — if the next segment is talking about
     something different, it's a break even if the pause was short. If it's
     continuing the same idea, it's NOT a break even if the pause was long
     (e.g. the speaker paused mid-sentence to think).

A chunk also has a hard max-duration cap, so one very consistent topic
doesn't turn into a five-minute unreadable block.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

# Loaded once at import time and reused across every transcription —
# loading it per-request would be slow and wasteful.
_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        # all-MiniLM-L6-v2: small (~80MB), fast on CPU, good enough for
        # sentence-level similarity. Not meant to be a top-tier embedding
        # model — just good enough to tell "same topic" from "new topic".
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def semantic_chunk(
    raw_segments: list[dict],
    similarity_threshold: float = 0.55,
    max_pause_seconds: float = 1.5,
    max_chunk_duration: float = 25.0,
) -> list[dict]:
    """
    raw_segments: list of {"start": float, "end": float, "text": str},
    exactly what stt_service.transcribe_audio() already returns.

    Returns the same shape, but re-grouped into semantically coherent
    chunks instead of Whisper's raw pause-based ones.
    """
    if not raw_segments:
        return []

    if len(raw_segments) == 1:
        return [dict(raw_segments[0])]

    model = _get_embedder()
    texts = [seg["text"] for seg in raw_segments]
    embeddings = model.encode(texts, convert_to_numpy=True)

    chunks: list[dict] = []

    current = {
        "start": raw_segments[0]["start"],
        "end": raw_segments[0]["end"],
        "text": raw_segments[0]["text"],
    }
    # Running average embedding of everything merged into the current
    # chunk so far — comparing against the *chunk's* meaning as a whole,
    # not just the immediately previous sentence.
    current_embedding_sum = embeddings[0].copy()
    current_embedding_count = 1

    for i in range(1, len(raw_segments)):
        seg = raw_segments[i]
        seg_embedding = embeddings[i]

        pause = seg["start"] - current["end"]
        prospective_duration = seg["end"] - current["start"]

        avg_embedding = current_embedding_sum / current_embedding_count
        similarity = _cosine_similarity(avg_embedding, seg_embedding)

        should_break = (
            pause > max_pause_seconds
            or similarity < similarity_threshold
            or prospective_duration > max_chunk_duration
        )

        if should_break:
            chunks.append(current)
            current = {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
            }
            current_embedding_sum = seg_embedding.copy()
            current_embedding_count = 1
        else:
            current["end"] = seg["end"]
            current["text"] = f"{current['text']} {seg['text']}"
            current_embedding_sum += seg_embedding
            current_embedding_count += 1

    chunks.append(current)
    return chunks
