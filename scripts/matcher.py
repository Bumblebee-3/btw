import math
from typing import List, Tuple, Dict, Any


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def rank_matches(query_vec: List[float], registry: list, cache: dict) -> List[Tuple[Dict[str, Any], float, str]]:
    """
    Return sorted list of (command, score, matched_text) using example embeddings.
    """
    results: List[Tuple[Dict[str, Any], float, str]] = []
    for cmd in registry:
        cid = cmd["id"]
        exs = cache.get(cid, {}).get("examples", [])
        best_for_cmd = -1.0
        best_text = ""
        for e in exs:
            emb = e.get("embedding")
            if not emb:
                continue
            s = cosine_similarity(query_vec, emb)
            if s > best_for_cmd:
                best_for_cmd = s
                best_text = e.get("text", "")
        if best_for_cmd >= 0.0:
            results.append((cmd, best_for_cmd, best_text))
    results.sort(key=lambda x: x[1], reverse=True)
    return results
