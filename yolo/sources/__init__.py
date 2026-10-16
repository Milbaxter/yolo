"""Source adapters. Each exposes `NAME` and `threads(since) -> Iterator[Thread]`.

Adapters read only from known, allowlisted paths and never touch credential
files that live next to chat logs (e.g. ~/.gemini/oauth_creds.json).
"""
from . import chatgpt_export, claude_code, claude_export, codex, cursor, gemini_cli, grok_export

ALL = {
    m.NAME: m
    for m in (claude_code, codex, cursor, gemini_cli, chatgpt_export, claude_export, grok_export)
}
