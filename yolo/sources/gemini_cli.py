"""Gemini CLI: ~/.gemini/tmp/<project>/chats/session-*.json

Only the chats/ glob is read. ~/.gemini also holds oauth_creds.json and
google_accounts.json, which must never be ingested.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..model import Message, Thread, from_iso

NAME = "gemini-cli"
ROOT = Path.home() / ".gemini" / "tmp"


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def threads(since: datetime, **_):
    for f in ROOT.glob("*/chats/session-*.json"):
        if datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) < since:
            continue
        try:
            d = json.loads(f.read_text(errors="replace"))
        except json.JSONDecodeError:
            continue
        updated = from_iso(d.get("lastUpdated")) or datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        if updated < since:
            continue
        t = Thread(NAME, d.get("sessionId") or f.stem, "", from_iso(d.get("startTime")) or updated, updated)
        for m in d.get("messages") or []:
            role = {"user": "user", "gemini": "assistant", "model": "assistant"}.get(m.get("type"))
            text = _text(m.get("content")).strip()
            if role and text:
                t.messages.append(Message(role, text, from_iso(m.get("timestamp"))))
        if t.messages:
            t.title = t.messages[0].text[:80]
            yield t
