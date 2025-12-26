#!/usr/bin/env python3
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from embeddings import embed_text, load_or_build_cache, EmbeddingError
from matcher import best_match

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
REGISTRY_PATH = SCRIPTS / "commands.json"
CACHE_PATH = SCRIPTS / "commands_cache.json"

DEFAULT_THRESHOLD = float(os.getenv("CMD_MATCH_THRESHOLD", "0.75"))


def _yad_confirm(text: str) -> bool:
    try:
        # Return code 0 for OK
        r = subprocess.run(
            [
                "yad",
                "--title",
                "Confirm",
                "--button",
                "gtk-cancel:1",
                "--button",
                "gtk-ok:0",
                "--text",
                text,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return r.returncode == 0
    except FileNotFoundError:
        return False


def _yad_info(text: str, timeout: int = 1) -> None:
    try:
        subprocess.Popen(
            [
                "yad",
                "--title",
                "Bumblebee",
                "--text",
                text,
                "--no-buttons",
                "--timeout",
                str(timeout),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def _speak_text_for(cmd_id: str, desc: str, success: bool, exit_code: int) -> str:
    if not success:
        return f"Failed to {desc}."
    mapping = {
        "brightness_up": "Increasing brightness.",
        "brightness_down": "Decreasing brightness.",
        "brightness_half": "Setting brightness to fifty percent.",
        "volume_up": "Turning the volume up.",
        "volume_down": "Turning the volume down.",
        "volume_mute": "Volume muted.",
        "system_shutdown": "Shutting down now.",
        "system_reboot": "Rebooting now.",
        "system_suspend": "Suspending now.",
        "system_lock": "Locking the session.",
        "wifi_on": "Turning Wi‑Fi on.",
        "wifi_off": "Turning Wi‑Fi off.",
        "arch_update": "Updating packages.",
    }
    return mapping.get(cmd_id, desc)


def plan_from_text(text: str, threshold: float = DEFAULT_THRESHOLD) -> dict:
    if not REGISTRY_PATH.exists():
        return {"type": "error", "message": f"Registry not found: {REGISTRY_PATH}"}
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = json.load(f)

    try:
        cache = load_or_build_cache(registry, str(CACHE_PATH))
        qvec = embed_text(text)
    except EmbeddingError as e:
        return {"type": "error", "message": str(e)}

    cmd, score = best_match(qvec, registry, cache)
    if not cmd or score < threshold:
        return {"type": "no_match", "score": score}

    if cmd.get("dangerous", False):
        ok = _yad_confirm(
            f"Allow action?\n\n{cmd['description']}\nCommand: {cmd['shell_command']}"
        )
        if not ok:
            return {
                "type": "cancelled",
                "id": cmd["id"],
                "description": cmd["description"],
                "score": score,
            }

    spoken = _speak_text_for(cmd["id"], cmd["description"], True, 0)
    return {
        "type": "confirmed",
        "id": cmd["id"],
        "description": cmd["description"],
        "command": cmd["shell_command"],
        "score": score,
        "spoken": spoken,
    }


def exec_by_id(cmd_id: str) -> dict:
    if not REGISTRY_PATH.exists():
        return {"type": "error", "message": f"Registry not found: {REGISTRY_PATH}"}
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = json.load(f)
    target = None
    for c in registry:
        if c.get("id") == cmd_id:
            target = c
            break
    if not target:
        return {"type": "error", "message": f"Unknown command id: {cmd_id}"}

    shell_cmd = target["shell_command"]
    try:
        _yad_info(f"Executing: {target['description']}")
        proc = subprocess.run(
            shell_cmd,
            shell=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        success = proc.returncode == 0
        spoken = _speak_text_for(target["id"], target["description"], success, proc.returncode)
        return {
            "type": "executed",
            "id": target["id"],
            "description": target["description"],
            "command": shell_cmd,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "spoken": spoken,
        }
    except Exception as e:
        return {
            "type": "error",
            "message": f"Execution error: {e}",
            "id": target["id"],
            "description": target["description"],
            "command": shell_cmd,
        }


def main(argv):

    text = None
    thr = DEFAULT_THRESHOLD
    exec_id = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--plan" and i + 1 < len(argv):
            text = argv[i + 1]
            i += 2
        elif a == "--exec-id" and i + 1 < len(argv):
            exec_id = argv[i + 1]
            i += 2
        elif a == "--threshold" and i + 1 < len(argv):
            try:
                thr = float(argv[i + 1])
            except Exception:
                pass
            i += 2
        else:
            i += 1

    if exec_id:
        result = exec_by_id(exec_id)
        print(json.dumps(result))
        return 0 if result.get("type") != "error" else 1

    if text is None:
        print(json.dumps({"type": "error", "message": "Missing --plan text or --exec-id"}))
        return 1

    result = plan_from_text(text, thr)
    print(json.dumps(result))
    return 0 if result.get("type") != "error" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
