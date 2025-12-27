import re
from typing import Dict, Optional

# Clamp helper

def clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


BIT_WORDS = ("a bit", "slightly", "little", "bit")


def _default_delta(text: str) -> int:
    lt = text.lower()
    for w in BIT_WORDS:
        if w in lt:
            return 5
    return 10


def parse_brightness(text: str, kind: str) -> Dict:
    t = text.lower()
    # set: look for explicit value
    if kind == "set":
        m = re.search(r"(\d{1,3})\s*%?", t)
        if m:
            v = clamp(int(m.group(1)), 0, 100)
            return {"value": v}
        # fallback: no value -> ask 50
        return {"value": 50}
    # up/down: try "by N" first, else default delta with bit/slightly
    m = re.search(r"by\s*(\d{1,3})\s*%?", t)
    if m:
        d = clamp(int(m.group(1)), 1, 100)
    else:
        d = clamp(_default_delta(t), 1, 100)
    return {"delta": d}


def parse_volume(text: str, kind: str) -> Dict:
    t = text.lower()
    if kind == "set":
        m = re.search(r"(\d{1,3})\s*%?", t)
        if m:
            v = clamp(int(m.group(1)), 0, 153)
            return {"value": v}
        return {"value": 50}
    m = re.search(r"by\s*(\d{1,3})\s*%?", t)
    if m:
        d = clamp(int(m.group(1)), 1, 100)
    else:
        d = clamp(_default_delta(t), 1, 100)
    return {"delta": d}


def extract_params(cmd_id: str, utterance: str) -> Dict:
    """
    Deterministic parameter extraction for brightness and volume families.
    brightness_set / brightness_up / brightness_down
    volume_set / volume_up / volume_down
    """
    if cmd_id.startswith("brightness_"):
        if cmd_id.endswith("_set"):
            return parse_brightness(utterance, "set")
        elif cmd_id.endswith("_up"):
            return parse_brightness(utterance, "up")
        elif cmd_id.endswith("_down"):
            return parse_brightness(utterance, "down")
    if cmd_id.startswith("volume_"):
        if cmd_id.endswith("_set"):
            return parse_volume(utterance, "set")
        elif cmd_id.endswith("_up"):
            return parse_volume(utterance, "up")
        elif cmd_id.endswith("_down"):
            return parse_volume(utterance, "down")
    return {}
