"""Grok (grok.com / xAI) data export: Settings > Download your data.

Drop the zip (or the extracted prod-grok-backend.json) into <vault>/inbox/grok/.
xAI doesn't document the format, so this parser is lenient. Observed shape:
items of {"conversation": {...}, "responses": [{"response": {...}}]}, with
ISO dates on conversations and BSON {"$date": {"$numberLong": ms}} dates on
responses. Senders are "human"/"user" for you; anything else is Grok.
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

from ..model import Message, Thread, from_iso, from_ms

NAME = "grok"


def _when(v) -> datetime | None:
    if isinstance(v, dict):
        v = v.get("$date", v)
        if isinstance(v, dict):
            v = v.get("$numberLong")
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
        return from_ms(int(v))
    return from_iso(v) if isinstance(v, str) else None


def _items(data):
    if isinstance(data, dict):
        data = data.get("conversations") or []
    return data if isinstance(data, list) else []


def _load(inbox: Path):
    for f in sorted((inbox / "grok").glob("*")):
        if f.suffix == ".zip":
            with zipfile.ZipFile(f) as z:
                for n in z.namelist():
                    if n.endswith("prod-grok-backend.json"):
                        yield from _items(json.loads(z.read(n)))
        elif f.name.endswith(".json"):
            yield from _items(json.loads(f.read_text()))


def threads(since: datetime, inbox: Path | None = None, **_):
    if not inbox or not (inbox / "grok").exists():
        return
    for item in _load(inbox):
        c = item.get("conversation") or {}
        msgs = []
        for r in item.get("responses") or []:
            r = r.get("response", r)
            text = (r.get("message") or "").strip()
            if text:
                role = "user" if str(r.get("sender", "")).lower() in ("human", "user") else "assistant"
                msgs.append(Message(role, text, _when(r.get("create_time"))))
        stamps = [m.at for m in msgs if m.at]
        updated = _when(c.get("modify_time")) or (max(stamps) if stamps else None)
        if not msgs or not updated or updated < since:
            continue
        msgs.sort(key=lambda m: m.at or updated)
        started = _when(c.get("create_time")) or (min(stamps) if stamps else updated)
        title = c.get("title") or next((m.text[:80] for m in msgs if m.role == "user"), "")
        yield Thread(NAME, str(c.get("id") or c.get("_id") or title), title, started, updated, messages=msgs)
