# Source adapters — drill non-markdown corpora through the same engine

The engine indexes a folder of `*.md` (`seed.py`). An **adapter** converts some other corpus INTO that
markdown, so it rides the same retrieval stack (embed → `##`-section chunks → cosine floor/band → the MCP
verbs) with no engine change. Point a `configs/<name>.json` at the adapter's output and seed as usual.

## `sessions.py` — drill your own agent's session history

Converts Claude Code session transcripts (`~/.claude/projects/**/*.jsonl`) into markdown: one
`<sessionId>.md` per session, chunked by **turn** (one `## Turn N` section per user→assistant exchange — the
retrieval unit), with frontmatter `type: session` + `originSessionId:` so the engine grounds each as
**provenance** (a dated origin — the honest label; it's a record of what was said, cited to its transcript,
never "verified"). Thinking blocks are kept (capped) — they're the "what did the agent struggle with"
signal; tool *results* are dropped (retrieval noise), tool *uses* noted by name.

**Setup is one command, zero config** — good defaults, nothing to pick:

```
drillable-context sessions          # fresh user path: convert ~/.claude/projects → ~/.drillable/sessions,
                                     # seed, and print the one line that wires the MCP. That's it.
```

It writes a managed config (`~/.drillable/sessions.json`: adapter=sessions, embed on, doc2query off for a fast
first index), converts INCREMENTALLY (re-runs touch only new sessions), auto-detects `OPENAI_API_KEY` (semantic;
else keyword), and prints the `claude mcp add drillable-sessions …` line. Then drill:
`"what did I do about X" / "what did agents struggle with" / "when did I last touch Y"` — grounded to the turn.

**Updated user path: nothing.** Once the MCP is wired, the running server picks up new sessions on its own — a
throttled, incremental auto-convert on query keeps the index current (`_auto_convert`). Re-run the command only
to force a full `--rebuild`.

First index is memory-light (peak ~430 MB over 600 sessions) but network-bound: it embeds every turn, so on
a **rate-limited key** the first run can take a few minutes — `embed._post` retries 429s with backoff so it
*completes* rather than dying; `--days N` indexes only recent history for a fast start (the rest fill in
automatically as you use them). Overrides (rarely needed): `--projects-dir`, `--days`, `DRILLABLE_HOME`
(managed dir), `DRILLABLE_SESSIONS_SOURCE`.

*(Low-level: the converter `src/adapters/sessions.py` and `configs/config.example.json` still work standalone
if you want a bespoke corpus.)*

**Dogfooded (first cut, 20 recent sessions → 360 turn-chunks):** "preserve session logs across three
accounts" → the exact turn that asked it (cosine 0.60, #1); "contested 100 km in miles fork" → the turn that
built it (0.48); "braid slate bank wrong path" → the right prior session (#1). Session history is usefully
retrievable.

### Agent-agnostic

Only `sessions.py` is Claude Code specific (the `.jsonl` format). The engine, the chunk shape, and the
`provenance` label are agent-neutral, so another agent (Cursor / Aider / Codex / Cline …) is a NEW adapter
emitting the same `.md` — a parser, not a rewrite.

### Project scope (shipped)

The store is indexed machine-wide, but a query is **scoped to one project by default** so a user-level
install never contaminates one project's drills with another's. `search` takes `project=`:
- `project="myrepo"` → only that project's facts (`— scoped to project "myrepo"`).
- `project="all"` → every project, each hit **labelled** by project (`slug · project`) — cross-project is
  never silent.
- default → the config's `default_project`, else the cwd-derived project. An implicit default that matches
  nothing falls through to **all** (never a silent total-miss); an *explicit* project that matches nothing
  abstains honestly.

The `project` column comes from each fact's frontmatter (seed.py, schema v2); non-session corpora (no
`project`) are unaffected — the filter only engages when the corpus carries projects.

## `github.py` — drill a repo's pull-request history

Converts a repo's **merged/closed** PRs (via the `gh` CLI — auth is gh's, not ours) into markdown: one
`pr-<n>.md` per PR, chunked by section (`## Summary` — the PR body with its own headings demoted so chunk
boundaries stay ours — and `## Files touched`), with frontmatter `type: github-pr` + `originRef: <PR url>`
so the engine grounds each as **provenance** (a dated record of what shipped, cited to its PR). So "when
did we ship X", "was Y ever tried", "what did #698 change" become drillable instead of hand-rolled `gh`
archaeology.

**Setup is one command:**

```
drillable-context github                      # index the cwd's repo (or --repo owner/name, repeatable)
```

It writes a managed config (`~/.drillable/github.json`), converts incrementally (a closed PR is a settled
record — existing `pr-<n>.md` are skipped), seeds, and prints the `claude mcp add drillable-github …`
line. Once wired, newly-closed PRs are picked up automatically (the same throttled on-query convert as
sessions). `--limit N` caps PRs per repo (default 200, newest first); `--rebuild` re-converts everything.

**History only, by design.** An OPEN PR is *liveness*, and a snapshot of liveness is stale by
construction — indexing it would serve "X is open" minutes-to-hours after it merged. Ask liveness live
(`gh pr list --state open`); drill history here. The two halves of "what's in flight" stay honest:
the sessions adapter sees STARTS (turns), this one records SHIPS (merges) — and what's open *right now*
is a live query, never an index.

### Not yet (follow-ups)

- Incremental re-convert (only new sessions); a `bin/` entry; per-agent adapters beyond Claude Code.
- A live open-PR lane (query-time, `asof`-stamped) if drilling liveness through the same grammar proves
  worth it; issues/discussions as further GitHub record types.
