#!/usr/bin/env python3
import json
import os
import sys
import datetime
import urllib.request
import urllib.error

USAGE_PATH = os.path.expanduser("~/.cache/assistant/gemini_usage.json")
PRIMARY_MODEL = "gemini-2.5-flash"
OVERFLOW_MODEL = "gemini-3.0-flash"
MAX_DAILY = 40
SYSTEM_PROMPT = (
    "Answer concisely using up-to-date information in full sentences suitable for text-to-speech. "
    "Avoid compact 'key: value' lists and heavy colon formatting. "
    "Spell out units and symbols: use 'degrees Fahrenheit' or 'degrees Celsius' instead of '°F'/'°C', "
    "and 'percent' instead of '%'. Do not use emojis or special symbols; prefer plain words. "
    "If unsure, say so clearly."
)


def load_usage():
    try:
        with open(USAGE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {"date": "", "count": 0}
    # reset if date changed
    today = datetime.date.today().isoformat()
    if data.get("date") != today:
        data["date"] = today
        data["count"] = 0
    return data


def save_usage(data):
    os.makedirs(os.path.dirname(USAGE_PATH), exist_ok=True)
    with open(USAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def call_gemini(text: str, api_key: str, model: str) -> tuple[bool, str]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {
            "role": "system",
            "parts": [{"text": SYSTEM_PROMPT}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": text}],
            }
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            j = json.loads(body)
            candidates = j.get("candidates", [])
            if not candidates:
                return False, ""
            parts = candidates[0].get("content", {}).get("parts", [])
            out = []
            for p in parts:
                t = p.get("text")
                if t:
                    out.append(t)
            return True, "\n".join(out).strip()
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            if "rate" in err_body.lower():
                return False, "RATE_LIMIT"
        except Exception:
            pass
        return False, ""
    except Exception:
        return False, ""


def main(argv):
    text = None
    force3 = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--text" and i + 1 < len(argv):
            text = argv[i + 1]
            i += 2
        elif a == "--force-3":
            force3 = True
            i += 1
        else:
            i += 1
    if not text:
        print("", end="")
        return 1

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("Sorry, I couldn't fetch live information right now.")
        return 0

    usage = load_usage()
    if usage.get("count", 0) >= MAX_DAILY:
        print("Live data limit reached for today.")
        return 0

    model = OVERFLOW_MODEL if force3 else PRIMARY_MODEL

    usage["count"] = int(usage.get("count", 0)) + 1
    save_usage(usage)

    ok, result = call_gemini(text, api_key, model)
    if not ok and result == "RATE_LIMIT" and not force3:
        usage = load_usage()
        if usage.get("count", 0) >= MAX_DAILY:
            print("Live data limit reached for today.")
            return 0
        usage["count"] = int(usage.get("count", 0)) + 1
        save_usage(usage)
        ok, result = call_gemini(text, api_key, OVERFLOW_MODEL)

    if not ok or not result.strip():
        print("Sorry, I couldn't fetch live information right now.")
        return 0

    print(result.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
