"""ChatGPT data export (Settings > Data controls > Export).

Drop the emailed .zip (or the extracted conversations.json) into
<vault>/inbox/chatgpt/. Conversations are a tree under `mapping`; we follow
`current_node` back to the root to get the branch the user actually kept.
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

from ..model import Message, Thread, from_ms

NAME = "chatgpt"


def _load(inbox: Path):
    for f in sorted((inbox / "chatgpt").glob("*")):
        if f.suffix == ".zip":
            with zipfile.ZipFile(f) as z:
                for n in z.namelist():
                    if n.endswith("conversations.json"):
                        yield from json.loads(z.read(n))
        elif f.name.endswith(".json"):
            yield from json.loads(f.read_text())


def threads(since: datetime, inbox: Path | None = None, **_):
    if not inbox or not (inbox / "chatgpt").exists():
        return
    for c in _load(inbox):
        updated = from_ms((c.get("update_time") or c.get("create_time") or 0) * 1000)
        if not updated or updated < since:
            continue
        mapping, node, chain = c.get("mapping") or {}, c.get("current_node"), []
        while node and node in mapping:
            chain.append(mapping[node])
            node = mapping[node].get("parent")
        t = Thread(NAME, c.get("conversation_id") or c.get("id", ""), c.get("title") or "",
                   from_ms((c.get("create_time") or 0) * 1000) or updated, updated)
        for n in reversed(chain):
            m = n.get("message") or {}
            role = (m.get("author") or {}).get("role")
            parts = (m.get("content") or {}).get("parts") or []
            text = "\n".join(p for p in parts if isinstance(p, str)).strip()
            if role in ("user", "assistant") and text:
                t.messages.append(Message(role, text, from_ms((m.get("create_time") or 0) * 1000)))
        if t.messages:
            yield t
