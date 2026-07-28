import numpy as np

MIN_CORRELATION_SCORE = 30

# Per-model cosine calibration: (floor, ceiling). Cosine is not uniformly
# distributed over 0..1 and the distribution is model-specific, so these are
# measured by scripts/measure_calibration.py rather than guessed.
#
# PROVISIONAL. Measured 2026-07-27 over 171 pairs of AI-written node summaries:
# unrelated 0.30-0.46, related 0.47-0.62, near-duplicate 0.93-0.96. That data
# separates related from unrelated by only 0.005, because summaries share
# AI-written boilerplate that inflates cross-topic similarity. Re-measure against
# message-text embeddings before trusting these for scoring.
CALIBRATION: dict[str, tuple[float, float]] = {
    # All-message centroids. Kept only so pre-existing records stay readable; new
    # conversations are scored with the `/user` variant below.
    "bge-small-en-v1.5@384": (0.46, 0.95),
    # User-messages-only centroids. Measured 2026-07-28 on labelled pairs of real
    # conversation text: unrelated 0.469, related 0.620, near-duplicate 0.93. The
    # ceiling is 0.85 rather than 0.95 so a genuinely related pair lands near 41
    # instead of scraping the 30 threshold. Two labelled points only — re-measure
    # once more clean conversations exist.
    "bge-small-en-v1.5@384/user": (0.46, 0.85),
}
DEFAULT_CALIBRATION = (0.46, 0.85)


def cosine(left: list[float], right: list[float]) -> float:
    """Cosine similarity between two dense vectors."""
    a = np.asarray(left, dtype=np.float32)
    b = np.asarray(right, dtype=np.float32)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(a, b) / denominator)


def cosine_to_score(similarity: float, model_id: str) -> int:
    """Map a raw cosine onto the 0..100 correlation_score scale."""
    floor, ceiling = CALIBRATION.get(model_id, DEFAULT_CALIBRATION)
    if ceiling <= floor:
        return 0
    normalized = (similarity - floor) / (ceiling - floor)
    return max(0, min(100, round(normalized * 100)))


def top_k_scores(
    similarities: dict[str, float], model_id: str, top_k: int
) -> dict[str, int]:
    """Score the top-k most similar peers, keeping explicit sub-threshold prunes."""
    ranked = sorted(similarities.items(), key=lambda item: item[1], reverse=True)
    return {
        peer_id: cosine_to_score(similarity, model_id)
        for peer_id, similarity in ranked[:top_k]
    }
