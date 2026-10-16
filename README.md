# YOLO — Your Ongoing Life Ontology

**You only live once. Your context shouldn't die with every new chat window.**

YOLO turns every thread you've had with every AI into one living personal
wiki that's on your machine, kept up to date on a schedule, and owned by you.

> This repo is the **tool and the idea**, never anyone's data. Your wiki lives
> in a separate private folder on your computer (default `~/PersonalContext`)
> and is never pushed anywhere unless you choose to.

---

## The idea

The next big platform fight is over **who owns your personal context**.

Today, what you're working on is spread across Claude, ChatGPT, Codex, Cursor,
Gemini, Grok, and whatever launches next month. Each one sees a slice. Each
vendor builds its own "memory" and hopes it becomes the one that knows you,
so that switching models means starting from zero.

YOLO takes the opposite position:

- **Your context is yours.** It sits on your disk as plain Markdown files,
  not inside any vendor's memory feature.
- **It's one picture, not ten slices.** All threads from all tools are merged,
  so you can see what you're *actually* working on: projects, decisions,
  people, open loops.
- **It's alive.** A scheduled agent updates it regularly, so it keeps up as
  your goals and projects change instead of freezing into a stale profile.
- **It's portable.** Any model can read it: paste `now.md` into a chat, point
  an agent at the folder, or open it in Obsidian. Switching models costs nothing.

It's a personal take on Karpathy's
[LLM wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
instead of searching raw chats every time you ask something (RAG), compile the
knowledge once into linked pages and keep them up to date.

## How it runs

```
   every AI tool you use                       your computer, nothing leaves*
 ┌─────────────────────────┐
 │ Claude Code   Codex     │   1. INGEST    ┌──────────────────────────────┐
 │ Cursor        Gemini CLI│ ─────────────▶ │ threads/   normalized,        │
 │ ChatGPT/Claude.ai/Grok  │   + REDACT     │            secret-scrubbed    │
 └─────────────────────────┘                │            Markdown archive   │
                                            └──────────────┬───────────────┘
                                                           │ 2. UPDATE
                                       headless agent you already use
                                       (codex exec / claude -p / local model)
                                                           ▼
                                            ┌──────────────────────────────┐
                                            │ wiki/  now · me · projects/  │
                                            │        people/ · topics/ ·   │
                                            │        decisions · log       │
                                            └──────────────┬───────────────┘
                                                           │ 3. COMMIT
                                                    local git: review the
                                                    weekly diff, revert anything
```

<sub>\*Except the text you choose to send to your agent's model provider in step 2. Use a local model if you want zero egress.</sub>

Each refresh runs the following steps. The built-in macOS schedule runs on Sunday
evening; a browser-capable app automation can instead own a five-day workflow
([setup and source coverage](docs/web-imports.md)).

1. **Ingest.** Read new conversations since the last run from each tool's local
   logs, plus any ChatGPT, Claude.ai or Grok export zips you dropped in `inbox/`. Keep only what you and
   the AI said (no tool output or system prompts), cut very long replies,
   and **redact secrets** (API keys, tokens, private keys, passwords).
2. **Update.** Hand the new threads to a sandboxed headless agent with a fixed
   prompt ([`update_prompt.md`](yolo/templates/update_prompt.md)). The agent
   edits only the wiki, following the vault's conventions
   ([`AGENTS.md`](yolo/templates/AGENTS.md)):
   - edit existing pages instead of duplicating them; keep `now.md` short and current
   - **link every claim to the thread it came from**
   - keep what you *said* apart from what the agent *inferred*
   - keep history ("was X until September, now Y") instead of overwriting it
   - never touch text you wrote yourself inside `<!-- human -->` blocks
3. **Commit.** Each run is one git commit in the vault, so you can review
   exactly what changed about "you" this week and roll back anything wrong.

## What you end up with

```
~/PersonalContext/            ← private, local, never in this repo
  wiki/
    index.md                  map of every page
    now.md                    what you're working on + open loops, this week
    me.md                     who you are, how you like to work
    projects/<name>.md        goals, status, decisions, links to source threads
    people/<name>.md
    topics/<name>.md
    decisions.md              dated decisions and why
    log.md                    what each weekly run changed
  threads/YYYY/MM/<tool>/     the evidence (redacted conversations)
  inbox/                      drop ChatGPT / Claude.ai / Grok export zips here
  AGENTS.md                   conventions for any agent reading the vault
```

## Quick start

```bash
pip install git+https://github.com/Milbaxter/yolo
yolo init                     # creates ~/PersonalContext (a private local git repo)
yolo ingest --since all --queue-since 30d   # archive everything, fold the last month into the wiki
yolo refresh --agent claude   # or --agent codex [--model …]; drains all pending batches
yolo schedule install         # optional weekly local-data job; choose one scheduler
```

Read it in a browser with `yolo view`: one local HTML file with a sidebar, search and clickable `[[links]]`. It is rebuilt after every update.

Other commands: `yolo stats`, `yolo refresh --dry-run`, `yolo schedule uninstall`.
`yolo weekly` remains an alias for `yolo refresh`. Source failures preserve their
checkpoints and cause `ingest` / `refresh` to exit non-zero; healthy sources continue.
Change the vault location with `--vault PATH` or `YOLO_VAULT`.

> Heads-up: the Ultralytics object-detection package also installs a `yolo`
> command. If you have it, use `python -m yolo …`.

## Supported sources

| Source | How YOLO gets it | Notes |
|---|---|---|
| Claude Code (CLI + desktop) | `~/.claude/projects/*/*.jsonl` | Claude Code deletes logs after 30 days by default. Raise `cleanupPeriodDays`; your vault keeps its own copies either way. |
| Codex (CLI + desktop) | `~/.codex/sessions/**/rollout-*.jsonl[.zst]` | Handles zstd-compressed sessions. |
| Cursor | `state.vscdb` (SQLite), read-only | Schema changes between Cursor versions. |
| Gemini CLI | `~/.gemini/tmp/*/chats/` | Credential files next to it are never read. |
| ChatGPT | export zip → `inbox/chatgpt/` | Settings → Data controls → Export. |
| Claude.ai / desktop chat | export zip → `inbox/claude/` | Settings → Privacy → Export data. |
| Grok | export zip → `inbox/grok/` | grok.com → Settings → Download your data (`prod-grok-backend.json`). Format is undocumented, so the parser is lenient. |
| Gemini web | browser review by an agent | Selective notes with source URLs and explicit date/coverage limits; no built-in web adapter. |
| Grok Bot | browser review by an agent | The tested account export omitted primary Bot history. Exact dates and complete voice transcripts may be unavailable. |
| Perplexity, aider, Continue | planned | PRs welcome; an adapter is roughly 50 lines. |

Web chat apps need fresh exports or an authorized browser review. A scheduled
CLI run cannot collect server-side history by itself. See the
[Gemini/Grok import walkthrough and five-day workflow](docs/web-imports.md) for
the tested process, evidence format, automation procedure and known gaps.
Keep raw exports, source URLs and personal context in the private vault.

## Safety and privacy

- **The vault and the tool are separate.** This repo never contains personal data.
- **Allowlisted paths only.** YOLO reads specific chat-log locations, never a whole home folder.
- **Redaction before anything leaves the tool**, with a heuristic regex set.
  It will miss things, so treat the vault as sensitive.
- **The agent is sandboxed to the vault** (`codex --sandbox workspace-write`,
  `claude --permission-mode acceptEdits` with an allowlist of file tools) and
  runs without saving its own session, so YOLO never ingests itself.
- **Zero-egress option:** run the update step on a local model (e.g. `codex --oss` with Ollama).

## Development

Run the regression checks with `python3 -m unittest discover -s tests -v`.

## Roadmap

- MCP server so any model can query and append to your vault live
- More adapters (Gemini Takeout, Perplexity, aider, Continue, Open WebUI)
- Optional typed entity graph (`entities.jsonl`) for tools that want structure
- Linux (systemd) and Windows scheduling

## Prior art

[ideal-personal-context](https://github.com/Milbaxter/ideal-personal-context)
(the idea YOLO grew out of), Karpathy's LLM wiki, basic-memory,
mem0 / OpenMemory, Letta. Those tools either search past chats or store facts
during a chat. YOLO adds a scheduled pass over **all** your AI tools that
compiles one readable picture you can carry to any model.

## License

MIT
