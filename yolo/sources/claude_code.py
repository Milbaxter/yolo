"""Claude Code CLI / desktop Code tab: ~/.claude/projects/<project>/<session>.jsonl"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..model import Message, Thread, from_iso

NAME = "claude-code"
ROOT = Path.home() / ".claude" / "projects"


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
    return ""


def threads(since: datetime, **_):
    for f in ROOT.glob("*/*.jsonl"):  # top level only: skips subagent sidechains
        if datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) < since:
            continue
        t = Thread(NAME, f.stem, "", since, since)
        stamps = []
        for line in f.open(errors="replace"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = d.get("type")
            if kind in ("custom-title", "summary") and not t.title:
                t.title = d.get("customTitle") or d.get("summary") or ""
            if kind not in ("user", "assistant") or d.get("isMeta") or d.get("isSidechain"):
                continue
            t.cwd = t.cwd or d.get("cwd")
            text = _text((d.get("message") or {}).get("content")).strip()
            if not text or text.startswith(("<command-", "<local-command", "<system-reminder")):
                continue
            at = from_iso(d.get("timestamp"))
            if at:
                stamps.append(at)
            t.messages.append(Message(kind, text, at))
        if t.messages and stamps:
            t.started, t.updated = min(stamps), max(stamps)
            if t.updated >= since:
                t.title = t.title or t.messages[0].text[:80]
                yield t

