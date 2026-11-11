"""Persistent progress log, kept on the host and never touched by `destroy`.

~/.local/share/brokenbox/progress.json:
{
  "scenarios": {
    "<id>": {"starts": 3, "resets": 1, "failed_checks": 4,
             "solves": [{"at": 1795290000.0, "seconds": 312, "within_limit": true}]}
  }
}
"""
from __future__ import annotations

import json
import os
import time

from . import config as C

PATH = C.DATA_DIR / "progress.json"
# tests/selftest.sh sets this so reference-solution runs don't count as your solves
DISABLED = os.environ.get("BROKENBOX_NO_PROGRESS") == "1"


def load() -> dict:
    try:
        data = json.loads(PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data.setdefault("scenarios", {})
    return data


def _save(data: dict) -> None:
    if DISABLED:
        return
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, PATH)


def _entry(data: dict, sid: str) -> dict:
    e = data["scenarios"].setdefault(sid, {})
    for k in ("starts", "resets", "failed_checks"):
        e.setdefault(k, 0)
    e.setdefault("solves", [])
    return e


def bump(sid: str, counter: str) -> None:
    data = load()
    _entry(data, sid)[counter] += 1
    _save(data)


def record_solve(sid: str, seconds: float, limit_minutes: int) -> None:
    data = load()
    _entry(data, sid)["solves"].append(
        {"at": time.time(), "seconds": int(seconds), "within_limit": seconds <= limit_minutes * 60})
    _save(data)


def get(sid: str) -> dict | None:
    return load()["scenarios"].get(sid)


def best_seconds(e: dict | None) -> int | None:
    if not e or not e["solves"]:
        return None
    return min(s["seconds"] for s in e["solves"])


def reset_all() -> None:
    PATH.unlink(missing_ok=True)
