"""Cursor agent/composer chats, from the global state.vscdb SQLite store.

Conversations live in table cursorDiskKV as `composerData:<id>` (header with
bubble order + timestamps) and `bubbleId:<composerId>:<bubbleId>` (messages).
The DB is live and in WAL mode, so it is opened read-only and immutable.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from ..model import Message, Thread, from_ms

NAME = "cursor"
if sys.platform == "darwin":
    DB = Path.home() / "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
elif sys.platform.startswith("win"):
    DB = Path.home() / "AppData/Roaming/Cursor/User/globalStorage/state.vscdb"
else:
    DB = Path.home() / ".config/Cursor/User/globalStorage/state.vscdb"


def threads(since: datetime, **_):
    if not DB.exists():
        return
    con = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True)
    try:
        rows = con.execute("select key, value from cursorDiskKV where key like 'composerData:%'").fetchall()
        for key, raw in rows:
            try:
                c = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            updated = from_ms(c.get("lastUpdatedAt") or c.get("createdAt"))
            headers = c.get("fullConversationHeadersOnly") or []
            if not updated or updated < since or not headers:
                continue
            cid = c.get("composerId") or key.split(":", 1)[1]
            t = Thread(NAME, cid, c.get("name") or "", from_ms(c.get("createdAt")) or updated, updated)
            for h in headers:
                r = con.execute("select value from cursorDiskKV where key = ?", (f"bubbleId:{cid}:{h['bubbleId']}",)).fetchone()
                if not r:
                    continue
                try:
                    b = json.loads(r[0])
                except (TypeError, json.JSONDecodeError):
                    continue
                text = (b.get("text") or "").strip()
                if text:
                    t.messages.append(Message("user" if b.get("type") == 1 else "assistant", text))
            if t.messages:
                t.title = t.title or t.messages[0].text[:80]
                yield t
    finally:
        con.close()
