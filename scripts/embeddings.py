import json
import os
import urllib.request
import urllib.error

GEMINI_EMBED_MODEL = "models/text-embedding-004"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/{GEMINI_EMBED_MODEL}:embedContent"


class EmbeddingError(Exception):
    pass


def _api_key() -> str:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise EmbeddingError("Missing GEMINI_API_KEY/GOOGLE_API_KEY in environment")
    return key


def embed_text(text: str) -> list:
    key = _api_key()
    body = {
        "model": GEMINI_EMBED_MODEL,
        "content": {"parts": [{"text": text}]},
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{GEMINI_URL}?key={key}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if "embedding" in payload and "values" in payload["embedding"]:
                return payload["embedding"]["values"]
            if "embeddings" in payload and payload["embeddings"]:
                return payload["embeddings"][0]["values"]
            raise EmbeddingError("Unexpected embedding response shape")
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        raise EmbeddingError(f"Gemini API error: {e.code} {detail}")
    except urllib.error.URLError as e:
        raise EmbeddingError(f"Network error: {e}")


def load_or_build_cache(commands: list, cache_path: str) -> dict:
    """Return dict[id] -> {description, embedding}. Recompute missing/mismatched."""
    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    changed = False
    for cmd in commands:
        cid = cmd["id"]
        desc = cmd["description"].strip()
        entry = cache.get(cid)
        if not entry or entry.get("description") != desc or not entry.get("embedding"):
            vec = embed_text(desc)
            cache[cid] = {"description": desc, "embedding": vec}
            changed = True
    if changed:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    return cache
