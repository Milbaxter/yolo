"""OpenAI Codex CLI / desktop: ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl[.zst]

Newer Codex versions zstd-compress finished rollouts. Python 3.14 has zstd in
the stdlib; older Pythons fall back to the `zstd` CLI.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..model import Message, Thread, from_iso

NAME = "codex"
ROOT = Path.home() / ".codex" / "sessions"
# Injected context blocks, not things the user typed.
_TAG_ONLY = re.compile(r"^<([\w-]+)>.*</\1>$", re.S)
_INJECTED = ("<environment_context>", "<app-context>", "<user_instructions>", "<permissions", "# AGENTS.md")


def _lines(f: Path):
    if f.suffix != ".zst":
        return f.open(errors="replace")
    try:
        from compression import zstd  # Python 3.14+

        raw = zstd.decompress(f.read_bytes())
    except ImportError:
        if not shutil.which("zstd"):
            return iter(())
        raw = subprocess.run(["zstd", "-dc", str(f)], capture_output=True, check=False).stdout
    return io.StringIO(raw.decode(errors="replace"))


def threads(since: datetime, **_):
    # Codex desktop writes extra rollouts (sub-agents, forks) that reuse the
    # parent's session id. Keep the longest one per id: that's the main thread.
    best: dict[str, Thread] = {}
    for t in _all(since):
        if t.id not in best or len(t.messages) > len(best[t.id].messages):
            best[t.id] = t
    yield from best.values()


def _all(since: datetime):
    for f in (f for f in ROOT.glob("*/*/*/rollout-*.jsonl*") if f.suffix in (".jsonl", ".zst")):
        if datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) < since:
            continue
        t = Thread(NAME, f.name.split(".")[0].removeprefix("rollout-"), "", since, since)
        stamps = []
        for line in _lines(f):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = d.get("payload") or {}
            if d.get("type") == "session_meta":
                t.cwd = p.get("cwd")
                t.id = p.get("id") or t.id
                continue
            if d.get("type") != "response_item" or p.get("type") != "message":
                continue
            role = p.get("role")
            if role not in ("user", "assistant"):
                continue
            text = "\n".join(
                c.get("text", "") for c in p.get("content") or [] if c.get("type") in ("input_text", "output_text")
            ).strip()
            if not text or text.startswith(_INJECTED) or _TAG_ONLY.match(text):
                continue
            at = from_iso(d.get("timestamp"))
            if at:
                stamps.append(at)
            t.messages.append(Message(role, text, at))
        if t.messages and stamps and max(stamps) >= since:
            t.started, t.updated = min(stamps), max(stamps)
            t.title = next((m.text[:80] for m in t.messages if m.role == "user"), "")
            yield t
