import numpy as np

MIN_CORRELATION_SCORE = 30

# Score by rank position: 1st closest peer, 2nd, and so on. Line thickness in the graph
# therefore means "this is my Nth closest conversation" rather than an absolute
# similarity, which saturates within a single project.
RANK_SCORES = (95, 80, 65, 50, 42, 38, 34, 31)

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
    # OpenAI embeddings. Measured 2026-07-31 over the 32 live conversations, scoring them
    # exactly as production does (user-message centroids), then looking at each
    # conversation's top-3 peers - the only similarities that decide a link:
    #   closest peer per conversation: min 0.252, median 0.634
    #   top-3 peers overall:           min 0.244, median 0.594
    # Cosine runs lower here than with bge, so the inherited 0.46 floor was scoring 8 of 96
    # top-3 peers as 0 - an explicit prune instruction - and one conversation lost even its
    # closest peer. Floors of 0.30, 0.35 and 0.40 all keep the same 96.9%: nothing sits in
    # that band, and the two links below it (0.244, 0.252) are the "closest of very few"
    # case the floor exists to reject. 0.40 is the top of that empty band.
    "text-embedding-3-small@1536": (0.40, 0.85),
    "text-embedding-3-small@1536/user": (0.40, 0.85),
}
# bge-derived, and only reached by a model with no entry above. A model whose cosine runs
# lower than bge's will over-prune until it is measured - see scripts/measure_calibration.py.
DEFAULT_CALIBRATION = (0.46, 0.85)


def cosine(left: list[float], right: list[float]) -> float:
    """Cosine similarity between two dense vectors, or 0.0 if they are not comparable.

    Changing the embedding model changes the vector width, so during a re-index the
    collection holds both. Multiplying a 384-dimension vector by a 1536-dimension one raises,
    which would take down every search that touched a stale chunk; treating it as unrelated
    lets retrieval degrade to whatever is already migrated.
    """
    if not left or not right or len(left) != len(right):
        return 0.0

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


def prune_score_if_unrelated(similarity: float, model_id: str) -> int | None:
    """0 when an existing peer has drifted below the floor, else None.

    None means "say nothing about this peer", which the projects service reads as retain.
    An edge therefore survives while either conversation still considers the other close,
    and is only pruned once the similarity itself collapses. Re-scoring these peers by
    absolute cosine instead would saturate high and defeat the top-k bound.
    """
    floor, _ = CALIBRATION.get(model_id, DEFAULT_CALIBRATION)
    return 0 if similarity < floor else None


def top_k_scores(
    similarities: dict[str, float], model_id: str, top_k: int
) -> dict[str, int]:
    """Score a conversation's closest peers by rank, not by absolute cosine.

    Within a single project every conversation shares the project's vocabulary, so
    absolute cosine saturates: measured across 15 conversations about one project it
    ranged 0.64-0.99, which links 80% of all possible pairs and produces an unreadable
    graph. Rank is invariant to that shift — it asks which peers are this conversation's
    closest, not whether 0.87 is a high number.

    The calibration floor is still applied as a gate, so a peer that is genuinely
    unrelated is not linked merely for being the closest of very few. Peers below the
    floor are returned with score 0, which acts as an explicit prune instruction rather
    than silence.
    """
    floor, _ = CALIBRATION.get(model_id, DEFAULT_CALIBRATION)
    ranked = sorted(similarities.items(), key=lambda item: item[1], reverse=True)

    scores: dict[str, int] = {}
    for rank, (peer_id, similarity) in enumerate(ranked[:top_k]):
        if similarity < floor:
            scores[peer_id] = 0
            continue
        scores[peer_id] = (
            RANK_SCORES[rank] if rank < len(RANK_SCORES) else MIN_CORRELATION_SCORE
        )
    return scores
