# Web imports and recurring refreshes

YOLO's CLI reads local histories and files in `inbox/`. It does not log in to
Gemini, request exports, read email, or control a browser. A browser-capable
agent can collect those sources separately, then compile the evidence using
the same vault conventions. Keep the public tool separate from the private
vault, archives, browser URLs, email download links, and review ledger.

## What was tested on 2026-10-16

A user-authorized import combined three kinds of evidence:

- **Gemini web:** the first 25 chats in the unfiltered recent-chat sidebar
  were opened in signed-in Brave. Each received a selective review note with
  its source URL and review order. These were not full transcript exports.
  Original timestamps were not visible and stayed unknown.
- **Grok conversations:** an official account export was requested through
  Settings → Data Controls → Export. The account download arrived by email
  and the ZIP was saved in the private `inbox/grok/`. Its backend JSON held
  1,810 conversations; 132 conversations / 498 messages in the requested
  calendar month were normalized with the existing Grok adapter. Older
  conversations remained in the ignored archive. Normal message excerpt caps
  applied (6,000 user characters and 1,500 assistant characters).
- **Primary Grok Bot:** that Bot's messages were absent from this export.
  Ten selective notes were made from reachable browser history. Exact
  message dates were not exposed; voice-call summaries and images did not
  provide complete transcripts. A strict full-month Bot export was therefore
  not claimed. Future exports may differ: check their actual contents.

The wiki was reconciled against existing pages, with source links and a dated
log. User choices were separated from assistant proposals, unverified action
claims, namesakes, and speculation. Secrets and sensitive third-party details
were omitted. Raw archives stayed ignored; private source and wiki changes
were committed only in the local vault. No personal content belongs in this
public repository.

## Browser-review evidence

Use a new file per review, for example
`threads/2026/10/gemini-web/reviewed-2026-10-16-example-id.md`:

```yaml
---
source: gemini-web
id: example-id
title: "Example conversation"
source_url: "https://gemini.google.com/app/example-id"
reviewed: 2026-10-16
started: null
updated: null
capture_kind: selective-browser-review-notes
review_order: 1
---
```

Below it, record coverage, relevant user statements, attributed assistant
ideas, and uncertainties. A review date is not a conversation date. Reopen
known recent chats too: an existing conversation can receive new messages.
Do not assume stopping at one known title covers all changes. If the UI hides
dates or history, describe the gap instead of guessing.

Keep per-source progress in a private ledger such as
`.yolo/runs/source-review-state.json`: successful review time, conversation
IDs/URLs, content fingerprints or last visible message anchors, export request
and receipt times, imported file paths, date range, and coverage limitations.
Never store export bearer links or credentials there. Do not advance a source's
successful coverage marker when access or capture fails.

## Every-five-days workflow

Use one scheduler for the whole workflow. A browser-capable app automation
can return to the same chat every five days and follow this procedure:

1. Read the vault's `AGENTS.md`, prior coverage ledger and pending queue.
   Check for an existing run; do not overlap writers.
2. Review changed Gemini chats and the user's primary Grok Bot in signed-in
   Brave. Use only the supported browser UI tools. Save fresh selective notes
   and their coverage limits. A login or unavailable UI is a source gap.
3. Request/retrieve a fresh official Grok export, reconciling any pending
   request before requesting another. Read only the relevant official export
   email when needed. Save the archive in `inbox/grok/`; never expose its
   download link. Ingest any newly available ChatGPT/Claude exports too.
   Requesting a new ChatGPT/Claude export requires account access; a stale or
   missing export must be reported, not treated as current coverage.
4. Run `yolo ingest --since last`. It checks Claude Code, Codex, Cursor,
   Gemini CLI and supported inbox exports. Per-source checkpoints retain
   progress independently; failures remain in `.yolo/state.json`. A quiet
   source retains its latest observed conversation timestamp, so a delayed
   export is not skipped just because another source ran meanwhile. The
   legacy global timestamp is retained as the migration baseline: earlier
   history still needs an explicit `--since` backfill.
5. Compile the new browser notes and **all** pending adapter batches. Either
   the automation edits the wiki itself and removes only successfully compiled
   entries from `pending`, or it uses `yolo update --agent claude` repeatedly.
   Do not let both compile the same evidence concurrently. Preserve failed
   batches. Rebuild `yolo view --no-open`, append the coverage log, and commit
   only the run's private files locally. Do not stage unrelated human changes.
6. Record completed source coverage and unresolved export requests. Stay
   quiet when nothing meaningful changes; notify on material updates,
   failures, or required login/action. A partial run must identify its gaps.

The combined CLI-only operation is `yolo refresh --agent claude` (or `codex`):
ingest, drain pending batches, commit, and rebuild the viewer. It returns a
failure status if a source fails, even if healthy sources were compiled.
`yolo weekly` remains a compatibility alias. `refresh --dry-run` previews the
next pending batch without ingesting or committing. Use `ingest` plus manual
compilation when preserving unrelated uncommitted vault edits: the headless
update command currently commits all vault changes with `git add -A`.

YOLO's built-in `yolo schedule install` is still a **weekly, local-data-only**
macOS launchd alternative. Uninstall it when an app automation owns the full
workflow (`yolo schedule uninstall`), so it cannot race the browser run. A shell
cron expression using day-of-month `*/5` is not a consistent five-day interval
across month boundaries. Configure an actual every-five-days recurrence in
the chosen scheduler. Browser collection depends on the Mac, tools, and
signed-in sessions being available; it is not a server-side sync service.
