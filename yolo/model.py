"""Common thread shape every source adapter produces."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Message:
    role: str  # "user" or "assistant"
    text: str
    at: datetime | None = None


@dataclass
class Thread:
    source: str  # e.g. "claude-code", "codex", "cursor"
    id: str
    title: str
    started: datetime
    updated: datetime
    cwd: str | None = None
    messages: list[Message] = field(default_factory=list)


def from_ms(ms: float | int | None) -> datetime | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def from_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
