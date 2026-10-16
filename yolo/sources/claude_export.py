"""Claude.ai / Claude desktop chat export (Settings > Privacy > Export data).

Drop the emailed .zip (or conversations.json) into <vault>/inbox/claude/.
The desktop app keeps chats server-side, so the export is the only way in.
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

from ..model import Message, Thread, from_iso

NAME = "claude-ai"


def _load(inbox: Path):
    for f in sorted((inbox / "claude").glob("*")):
        if f.suffix == ".zip":
            with zipfile.ZipFile(f) as z:
                for n in z.namelist():
                    if n.endswith("conversations.json"):
                        yield from json.loads(z.read(n))
        elif f.name.endswith(".json"):
            yield from json.loads(f.read_text())


def _text(m) -> str:
    if m.get("text"):
        return m["text"]
    return "\n".join(c.get("text", "") for c in m.get("content") or [] if c.get("type") == "text")


def threads(since: datetime, inbox: Path | None = None, **_):
    if not inbox or not (inbox / "claude").exists():
        return
    for c in _load(inbox):
        updated = from_iso(c.get("updated_at"))
        if not updated or updated < since:
            continue
        t = Thread(NAME, c.get("uuid", ""), c.get("name") or "", from_iso(c.get("created_at")) or updated, updated)
        for m in c.get("chat_messages") or []:
            text = _text(m).strip()
            if text:
                role = "user" if m.get("sender") == "human" else "assistant"
                t.messages.append(Message(role, text, from_iso(m.get("created_at"))))
        if t.messages:
            yield t
