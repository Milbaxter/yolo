"""Render the vault's wiki as one self-contained HTML file for reading in a browser.

Pages are embedded as JSON and rendered client-side with marked; [[slug]] links
become in-page links and [src] links point at the thread files (relative to
the vault, so it works opened from disk or served from the vault root).
Nothing is uploaded anywhere: the file lives in <vault>/.yolo/wiki.html.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _front(text: str) -> tuple[dict, str]:
    meta = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            for line in text[4:end].splitlines():
                k, _, v = line.partition(":")
                if v:
                    meta[k.strip()] = v.strip().strip('"')
            text = text[end + 4:].lstrip("\n")
    return meta, text


def build(vault: Path) -> Path:
    wiki = vault / "wiki"
    pages = {}
    for f in sorted(wiki.rglob("*.md")):
        meta, body = _front(f.read_text(errors="replace"))
        rel = f.relative_to(wiki)
        section = rel.parts[0] if len(rel.parts) > 1 else ""
        # Thread links are relative to the page; rebase them onto <vault>/.yolo/.
        body = re.sub(r"\]\((?:\.\./)+(threads/[^)]+)\)", r"](../\1)", body)
        pages[f.stem] = {"title": meta.get("title") or f.stem, "section": section, "meta": meta, "body": body}
    html = (Path(__file__).parent / "templates" / "wiki.html").read_text()
    out = vault / ".yolo" / "wiki.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html.replace("/*PAGES*/{}", json.dumps(pages).replace("</", "<\\/")))
    return out
