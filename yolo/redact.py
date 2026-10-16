"""Scrub secrets before any thread text is written to the vault or sent to a model.

Patterns are a small subset of gitleaks' rules plus generic key=value and PEM
blocks. Detection always misses something: treat the vault as sensitive anyway.
"""
from __future__ import annotations

import re

_PATTERNS = [
    ("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    ("anthropic-key", r"(?<![A-Za-z0-9])sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("openai-key", r"(?<![A-Za-z0-9])sk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{20,}"),
    ("github-token", r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}"),
    ("aws-key", r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    ("google-key", r"AIza[0-9A-Za-z_\-]{35}"),
    ("slack-token", r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    ("stripe-key", r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}"),
    ("jwt", r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ("bearer", r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}"),
    ("url-credentials", r"(?<=://)[^\s/:@]+:[^\s/@]+(?=@)"),
    # key = value style; group 1 (the key) is kept, the value is replaced.
    ("assigned-secret", r"(?i)((?:password|passwd|secret|token|api[_-]?key|access[_-]?key)[\"']?\s{0,3}[:=]\s{0,3}[\"']?)[^\s\"',;]{8,}"),
]
_RX = [(name, re.compile(rx)) for name, rx in _PATTERNS]


def redact(text: str) -> tuple[str, int]:
    hits = 0
    for name, rx in _RX:
        repl = (r"\1" if rx.groups else "") + f"[REDACTED:{name}]"
        text, n = rx.subn(repl, text)
        hits += n
    return text, hits
