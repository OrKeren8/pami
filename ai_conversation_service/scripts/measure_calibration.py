"""Measure the cosine distribution of real context-node summaries.

Cosine similarity is not uniformly distributed and the distribution is specific to
the embedding model, so the (floor, ceiling) pair in services/similarity.py must be
measured rather than guessed. Re-run this whenever the embedding model changes.

Usage:
    py -m uv run python scripts/measure_calibration.py
    py -m uv run python scripts/measure_calibration.py --pairs 15
"""

import argparse
import asyncio
import statistics

from pymongo import AsyncMongoClient

from ai_conversation_service.core.config import settings
from ai_conversation_service.services.embedder import LocalOnnxEmbedder
from ai_conversation_service.services.similarity import cosine


async def main(show_pairs: int) -> None:
    client = AsyncMongoClient(settings.mongodb_url)
    collection = client[settings.database_name]["context_tree"]

    nodes = await collection.find(
        {}, {"header": 1, "summary": 1, "project_id": 1}
    ).to_list(length=None)
    labelled = [
        (
            str(node["_id"]),
            node.get("header") or (node.get("summary") or "")[:40],
            node.get("summary") or node.get("header") or "",
        )
        for node in nodes
        if (node.get("summary") or node.get("header"))
    ]
    print(f"nodes with text: {len(labelled)}")
    if len(labelled) < 2:
        print("not enough nodes to measure")
        return

    embedder = LocalOnnxEmbedder(settings.embedding_model, settings.embedding_cache_dir)
    vectors = await embedder.embed([text for _, _, text in labelled])
    print(f"model: {embedder.model_id}")

    pairs = []
    for i in range(len(labelled)):
        for j in range(i + 1, len(labelled)):
            pairs.append(
                (cosine(vectors[i], vectors[j]), labelled[i][1], labelled[j][1])
            )
    pairs.sort(reverse=True)

    scores = [score for score, _, _ in pairs]
    quantiles = statistics.quantiles(scores, n=100)
    print(f"\npairs: {len(pairs)}")
    print(f"min      {min(scores):.3f}")
    print(f"p05      {quantiles[4]:.3f}")
    print(f"p25      {quantiles[24]:.3f}")
    print(f"median   {statistics.median(scores):.3f}")
    print(f"p75      {quantiles[74]:.3f}")
    print(f"p95      {quantiles[94]:.3f}")
    print(f"max      {max(scores):.3f}")
    print(f"mean     {statistics.mean(scores):.3f}")

    print(f"\nmost similar {show_pairs}:")
    for score, left, right in pairs[:show_pairs]:
        print(f"  {score:.3f}  {left[:34]:<34} <-> {right[:34]}")

    print(f"\nleast similar {show_pairs}:")
    for score, left, right in pairs[-show_pairs:]:
        print(f"  {score:.3f}  {left[:34]:<34} <-> {right[:34]}")

    await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=10)
    asyncio.run(main(parser.parse_args().pairs))
