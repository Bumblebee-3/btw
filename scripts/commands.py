#!/usr/bin/env python3
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from embeddings import embed_text, load_or_build_cache, EmbeddingError
from matcher import rank_matches
from param_parser import extract_params

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
REGISTRY_PATH = SCRIPTS / "commands.json"
CACHE_PATH = SCRIPTS / "commands_cache.json"

DEFAULT_THRESHOLD = float(os.getenv("CMD_MATCH_THRESHOLD", "0.75"))
CLARIFY_THRESHOLD = float(os.getenv("CMD_CLARIFY_THRESHOLD", "0.60"))
AMBIGUITY_DELTA = float(os.getenv("CMD_AMBIGUITY_DELTA", "0.05"))


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


def _yad_choose(options):
    """Return selected label or empty if cancelled. Uses YAD list."""
    try:
        p = subprocess.run(
            [
                "yad",
                "--title",
                "Select action",
                "--list",
                "--column=Action",
                *options,
                "--width=420",
                "--height=240",
            ],
            capture_output=True,
            text=True,
        )
        if p.returncode == 0:
            out = p.stdout.strip()
            if out:
                return out.split("|", 1)[0].strip()
    except FileNotFoundError:
        return ""
    return ""


def _spoken_for(cmd_id: str, desc: str, params: dict | None, success: bool, exit_code: int) -> str:
    if not success:
        return f"Failed to {desc}."
    p = params or {}
    # Brightness
    if cmd_id == "brightness_set":
        v = p.get("value")
        if isinstance(v, int):
            return f"Setting brightness to {v} percent."
        return "Setting brightness."
    if cmd_id == "brightness_up":
        d = p.get("delta")
        if isinstance(d, int):
            return f"Increasing brightness by {d} percent."
        return "Increasing brightness."
    if cmd_id == "brightness_down":
        d = p.get("delta")
        if isinstance(d, int):
            return f"Decreasing brightness by {d} percent."
        return "Decreasing brightness."
    # Volume
    if cmd_id == "volume_set":
        v = p.get("value")
        if isinstance(v, int):
            return f"Setting volume to {v} percent."
        return "Setting volume."
    if cmd_id == "volume_up":
        d = p.get("delta")
        if isinstance(d, int):
            return f"Turning the volume up by {d} percent."
        return "Turning the volume up."
    if cmd_id == "volume_down":
        d = p.get("delta")
        if isinstance(d, int):
            return f"Turning the volume down by {d} percent."
        return "Turning the volume down."
    if cmd_id == "volume_mute":
        return "Volume muted."
    # System and network
    if cmd_id == "lock_screen" or cmd_id == "system_lock":
        return "Locking the screen."
    if cmd_id == "system_shutdown":
        return "Shutting down now."
    if cmd_id == "system_reboot":
        return "Rebooting now."
    if cmd_id == "system_suspend":
        return "Suspending now."
    if cmd_id == "wifi_on":
        return "Turning Wi‑Fi on."
    if cmd_id == "wifi_off":
        return "Turning Wi‑Fi off."
    if cmd_id == "arch_update":
        return "Updating system packages."
    return desc


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
    ranked = rank_matches(qvec, registry, cache)
    if not ranked:
        return {"type": "no_match", "score": 0.0}

    top_cmd, top_score, _matched = ranked[0]

    # Ambiguity: ask if close scores
    candidates = [ranked[0]]
    for item in ranked[1:3]:
        if abs(item[1] - top_score) <= AMBIGUITY_DELTA:
            candidates.append(item)
    if len(candidates) > 1 and top_score >= CLARIFY_THRESHOLD:
        opts = [c[0]["description"] for c in candidates]
        sel = _yad_choose(opts)
        if not sel:
            return {"type": "cancelled"}
        for c in candidates:
            if c[0]["description"] == sel:
                top_cmd, top_score, _matched = c
                break

    # Threshold rules
    if top_score < CLARIFY_THRESHOLD:
        return {"type": "no_match", "score": top_score}
    if CLARIFY_THRESHOLD <= top_score < threshold:
        ok = _yad_confirm(f"Did you mean: {top_cmd['description']}?")
        if not ok:
            return {"type": "cancelled"}

    # Dangerous confirm
    if top_cmd.get("dangerous", False):
        ok = _yad_confirm(
            f"Allow action?\n\n{top_cmd['description']}\nCommand: {top_cmd.get('shell_command_template','')}"
        )
        if not ok:
            return {
                "type": "cancelled",
                "id": top_cmd["id"],
                "description": top_cmd["description"],
                "score": top_score,
            }

    params = extract_params(top_cmd["id"], text)
    spoken = _spoken_for(top_cmd["id"], top_cmd["description"], params, True, 0)
    return {
        "type": "confirmed",
        "id": top_cmd["id"],
        "description": top_cmd["description"],
        "command": top_cmd.get("shell_command_template", ""),
        "score": top_score,
        "spoken": spoken,
        "params": params,
    }


def _format_command(template: str, params: dict) -> str:
    # Only permit integer substitutions for value/delta
    safe = {}
    for k in ("value", "delta"):
        if k in params:
            try:
                safe[k] = int(params[k])
            except Exception:
                pass
    try:
        return template.format(**safe)
    except Exception:
        return template


def exec_by_id(cmd_id: str, params: dict | None = None) -> dict:
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

    template = target.get("shell_command_template") or target.get("shell_command") or ""
    shell_cmd = _format_command(template, params or {})
    try:
        proc = subprocess.run(
            shell_cmd,
            shell=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        success = proc.returncode == 0
        spoken = _spoken_for(target["id"], target["description"], params or {}, success, proc.returncode)
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
    params_json = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--plan" and i + 1 < len(argv):
            text = argv[i + 1]
            i += 2
        elif a == "--exec-id" and i + 1 < len(argv):
            exec_id = argv[i + 1]
            i += 2
        elif a == "--params" and i + 1 < len(argv):
            params_json = argv[i + 1]
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
        params = {}
        if params_json:
            try:
                params = json.loads(params_json)
            except Exception:
                params = {}
        result = exec_by_id(exec_id, params)
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
