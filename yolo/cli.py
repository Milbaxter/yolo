"""YOLO (Your Ongoing Life Ontology): all your AI threads, one living personal wiki.

  yolo init                 create the vault (a private local git repo)
  yolo ingest [--since 7d]  normalize + redact new threads into vault/threads/
  yolo update [--agent X]   have a headless agent fold the new threads into vault/wiki/
  yolo weekly               ingest + update + commit (what the schedule runs)
  yolo schedule install     weekly launchd job (macOS)
  yolo stats                what's in the vault
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import sources
from .model import Thread
from .redact import redact

DEFAULT_VAULT = Path(os.environ.get("YOLO_VAULT", Path.home() / "PersonalContext"))
REPO = Path(__file__).resolve().parent.parent
USER_CAP, ASSISTANT_CAP = 6000, 1500  # chars kept per message; assistants ramble
LABEL = "dev.yolo.weekly"


# ---------- helpers

def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_since(s: str, state: dict) -> datetime:
    if s == "all":
        return datetime(2000, 1, 1, tzinfo=timezone.utc)
    if s == "last":
        last = state.get("last_ingest")
        return datetime.fromisoformat(last) - timedelta(hours=1) if last else now() - timedelta(days=7)
    if m := re.fullmatch(r"(\d+)([dw])", s):
        n = int(m[1]) * (7 if m[2] == "w" else 1)
        return now() - timedelta(days=n)
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def load_state(vault: Path) -> dict:
    f = vault / ".yolo" / "state.json"
    return json.loads(f.read_text()) if f.exists() else {}


def save_state(vault: Path, state: dict) -> None:
    f = vault / ".yolo" / "state.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(state, indent=2))


def git(vault: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(vault), *args], capture_output=True, text=True)


def template(name: str) -> str:
    return (Path(__file__).parent / "templates" / name).read_text()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "untitled"


def notify(msg: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "YOLO"'], check=False)


# ---------- init

def cmd_init(a) -> None:
    v = a.vault
    for d in ("wiki", "threads", "inbox/chatgpt", "inbox/claude", ".yolo"):
        (v / d).mkdir(parents=True, exist_ok=True)
    for name, dest in (("AGENTS.md", "AGENTS.md"), ("index.md", "wiki/index.md"), ("me.md", "wiki/me.md")):
        if not (v / dest).exists():
            (v / dest).write_text(template(name))
    if not (v / "CLAUDE.md").exists():
        (v / "CLAUDE.md").write_text("@AGENTS.md\n")
    if not (v / ".gitignore").exists():
        (v / ".gitignore").write_text("inbox/\n.yolo/runs/\n")
    if not (v / ".git").exists():
        git(v, "init", "-q")
        git(v, "add", "-A")
        git(v, "commit", "-qm", "yolo: init vault")
    print(f"vault ready at {v}\nnext: yolo ingest --since all   (backfill everything once)")


# ---------- ingest

def render(t: Thread) -> tuple[str, int]:
    hits = 0
    out = [
        "---",
        f"source: {t.source}",
        f"id: {t.id}",
        f"title: {json.dumps(t.title.strip().splitlines()[0] if t.title.strip() else '')}",
        f"started: {t.started.isoformat(timespec='minutes')}",
        f"updated: {t.updated.isoformat(timespec='minutes')}",
        *( [f"cwd: {t.cwd}"] if t.cwd else [] ),
        f"messages: {len(t.messages)}",
        "---",
        "",
    ]
    for m in t.messages:
        cap = USER_CAP if m.role == "user" else ASSISTANT_CAP
        text, n = redact(m.text)
        hits += n
        if len(text) > cap:
            text = text[:cap] + f"\n[… {len(text) - cap} chars trimmed]"
        out += [f"## {m.role}", "", text, ""]
    return "\n".join(out), hits


def thread_path(vault: Path, t: Thread) -> Path:
    s = t.started
    return vault / "threads" / f"{s:%Y}" / f"{s:%m}" / t.source / f"{s:%Y-%m-%d}-{slug(t.title)}-{t.id[-8:]}.md"


def excluded(t: Thread, vault: Path) -> bool:
    """Skip YOLO's own runs (and work on YOLO itself) so it never digests itself."""
    if not t.cwd:
        return False
    cwd = Path(t.cwd).resolve()
    return any(cwd == p or p in cwd.parents for p in (vault.resolve(), REPO))


def cmd_ingest(a) -> list[Path]:
    v = a.vault
    state = load_state(v)
    since = parse_since(a.since, state)
    wanted = a.source or list(sources.ALL)
    touched, totals = [], {}
    for name in wanted:
        n = chars = hits = 0
        try:
            for t in sources.ALL[name].threads(since, inbox=v / "inbox"):
                if excluded(t, v) or not any(m.role == "user" for m in t.messages):
                    continue
                body, h = render(t)
                p = thread_path(v, t)
                if p.exists() and p.read_text() == body:
                    continue
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body)
                touched.append(p)
                n, chars, hits = n + 1, chars + len(body), hits + h
        except Exception as e:  # one broken source shouldn't stop the others
            print(f"  {name}: FAILED ({e})", file=sys.stderr)
            continue
        totals[name] = n
        print(f"  {name:12} {n:5} threads  ~{chars // 4:>9,} tokens  {hits} secrets redacted")
    state["last_ingest"] = now().isoformat()
    state["pending"] = sorted({*state.get("pending", []), *(str(p.relative_to(v)) for p in touched)})
    save_state(v, state)
    print(f"{len(touched)} new/updated threads since {since:%Y-%m-%d}; {len(state['pending'])} waiting for `yolo update`")
    return touched


# ---------- update

def agent_cmd(agent: str, prompt: str, vault: Path, model: str | None = None) -> list[str]:
    extra = ["--model", model] if model else []
    if agent == "codex":
        # workspace-write: may only edit inside the vault; --ephemeral: no session log to re-ingest
        return ["codex", "exec", "-C", str(vault), "--sandbox", "workspace-write",
                "--skip-git-repo-check", "--ephemeral", *extra, prompt]
    if agent == "claude":
        return ["claude", "-p", prompt, "--permission-mode", "acceptEdits",
                "--allowedTools", "Read,Write,Edit,Glob,Grep,Bash(ls *),Bash(wc *)",
                "--no-session-persistence", *extra]
    raise SystemExit(f"unknown agent {agent!r}")


def cmd_update(a) -> bool:
    v = a.vault
    state = load_state(v)
    pending = state.get("pending", [])
    if not pending:
        print("nothing pending; run `yolo ingest` first")
        return True
    batch = pending[: a.batch]
    manifest = v / ".yolo" / "batch.md"
    manifest.write_text(
        "# Threads to fold in this run\n\n"
        + "\n".join(f"- {p}  ({(v / p).stat().st_size // 4:,} tokens)" for p in batch if (v / p).exists())
        + "\n"
    )
    prompt = template("update_prompt.md").replace("{{TODAY}}", f"{now():%Y-%m-%d}").replace("{{N}}", str(len(batch)))
    if a.dry_run:
        print(" ".join(agent_cmd(a.agent, "<prompt>", v, a.model)))
        print(prompt)
        return True
    if not shutil.which(a.agent):
        raise SystemExit(f"`{a.agent}` not found on PATH")
    print(f"folding {len(batch)} threads into the wiki with {a.agent}…")
    r = subprocess.run(agent_cmd(a.agent, prompt, v, a.model), cwd=v, capture_output=True, text=True, timeout=a.timeout)
    log = v / ".yolo" / "runs" / f"{now():%Y%m%dT%H%M%S}-{a.agent}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(r.stdout + "\n--- stderr ---\n" + r.stderr)
    if r.returncode != 0:
        print(f"agent failed (exit {r.returncode}); see {log}", file=sys.stderr)
        return False
    state["pending"] = pending[len(batch):]
    state["last_update"] = now().isoformat()
    save_state(v, state)
    git(v, "add", "-A")
    git(v, "commit", "-qm", f"yolo: fold {len(batch)} threads ({a.agent}, {now():%Y-%m-%d})")
    print(f"done; review with: git -C {v} show --stat HEAD")
    return True


def cmd_weekly(a) -> None:
    try:
        a.since = "last"
        a.source = None
        cmd_ingest(a)
        git(a.vault, "add", "-A")
        git(a.vault, "commit", "-qm", f"yolo: ingest {now():%Y-%m-%d}")
        while load_state(a.vault).get("pending"):
            if not cmd_update(a):
                notify("weekly update failed — check `yolo` logs (agent login expired?)")
                sys.exit(1)
        notify("personal wiki updated")
    except Exception as e:
        notify(f"weekly run crashed: {e}")
        raise


# ---------- schedule (macOS launchd)

def cmd_schedule(a) -> None:
    plist = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
    if a.action == "uninstall":
        subprocess.run(["launchctl", "unload", str(plist)], check=False)
        plist.unlink(missing_ok=True)
        print("removed")
        return
    cmd = shutil.which("yolo") or f"{sys.executable} -m yolo"
    body = (template("launchd.plist")
            .replace("{{LABEL}}", LABEL)
            .replace("{{ARGS}}", "".join(f"<string>{x}</string>" for x in [*cmd.split(), "--vault", str(a.vault), "weekly", "--agent", a.agent, *(["--model", a.model] if a.model else [])]))
            .replace("{{WEEKDAY}}", str(a.weekday)).replace("{{HOUR}}", str(a.hour))
            .replace("{{PATH}}", os.environ.get("PATH", ""))
            .replace("{{LOG}}", str(a.vault / ".yolo" / "launchd.log")))
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(body)
    subprocess.run(["launchctl", "unload", str(plist)], check=False, capture_output=True)
    subprocess.run(["launchctl", "load", str(plist)], check=True)
    print(f"installed {plist}: every weekday={a.weekday} at {a.hour}:00 (runs on wake if the Mac slept)")


def cmd_stats(a) -> None:
    v = a.vault
    by = {}
    for p in (v / "threads").rglob("*.md"):
        by.setdefault(p.parent.name, [0, 0])
        by[p.parent.name][0] += 1
        by[p.parent.name][1] += p.stat().st_size
    for s, (n, b) in sorted(by.items()):
        print(f"  {s:12} {n:5} threads  ~{b // 4:>10,} tokens")
    print(f"  wiki pages: {len(list((v / 'wiki').rglob('*.md')))}   pending: {len(load_state(v).get('pending', []))}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="yolo", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    p = sub.add_parser("ingest")
    p.add_argument("--since", default="last", help="7d, 2w, all, last, or YYYY-MM-DD")
    p.add_argument("--source", action="append", choices=list(sources.ALL))
    for name in ("update", "weekly"):
        p = sub.add_parser(name)
        p.add_argument("--agent", default="codex", choices=["codex", "claude"])
        p.add_argument("--batch", type=int, default=40, help="threads per agent run")
        p.add_argument("--timeout", type=int, default=3600)
        p.add_argument("--model", help="override the agent's default model")
        p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("schedule")
    p.add_argument("action", choices=["install", "uninstall"])
    p.add_argument("--agent", default="codex", choices=["codex", "claude"])
    p.add_argument("--weekday", type=int, default=0, help="0=Sunday")
    p.add_argument("--hour", type=int, default=20)
    p.add_argument("--model")
    sub.add_parser("stats")
    a = ap.parse_args(argv)
    a.vault = a.vault.expanduser().resolve()
    if a.vault == REPO or REPO in a.vault.parents:
        raise SystemExit(f"refusing to use a vault inside the YOLO repo ({REPO}); personal data must live elsewhere")
    {"init": cmd_init, "ingest": cmd_ingest, "update": cmd_update, "weekly": cmd_weekly,
     "schedule": cmd_schedule, "stats": cmd_stats}[a.cmd](a)


if __name__ == "__main__":
    main()
