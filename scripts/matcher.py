import math
from typing import List


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def best_match(query_vec: List[float], registry: list, cache: dict):
    """Return (command, score) highest cosine match."""
    best = None
    best_score = -1.0
    for cmd in registry:
        cid = cmd["id"]
        emb = cache.get(cid, {}).get("embedding")
        if not emb:
            continue
        score = cosine_similarity(query_vec, emb)
        if score > best_score:
            best = cmd
            best_score = score
    return best, best_score
