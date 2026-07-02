# Changelog

## 0.6.0

**Developer preview.** Drill a repo's **GitHub PR history** — the second source adapter — closing half
of the in-flight blindness gap (the sessions adapter sees session STARTS; this records what SHIPPED).
Preview means: it works and is tested, but demand for it is unproven — we shipped it to dogfood the
concept and find out. Interfaces (command flags, chunk shape, frontmatter) may change with what we learn.

- **`github.py` adapter** — `drillable-context github` converts a repo's merged/closed PRs (via the `gh`
  CLI) into the engine's markdown: one file per PR, chunked as `## Summary` / `## Files touched`,
  grounded as dated **provenance** (`originRef:` → the PR url). "When did we ship X", "was Y ever
  tried", "what did #698 change" become drillable. One-command setup, incremental (a closed PR is a
  settled record), and newly-closed PRs are picked up automatically on query — the same managed path as
  sessions. `--repo owner/name` (repeatable) indexes any repos; default is the cwd's.
- **History only, by design** — open-PR state is liveness; a snapshot of it is stale by construction, so
  the adapter refuses to index it. Ask liveness live (`gh pr list --state open`); drill record here.
- **Engine** — `originRef:` frontmatter now earns the provenance label alongside `originSessionId:`
  (one line in seed.py); the on-query auto-convert generalizes to any adapter-backed corpus.

## 0.5.0

Session history, now **painless** — one command to set up, zero to keep current — and robust at full scale.

- **One-command setup** — `drillable-context sessions` converts `~/.claude/projects`, seeds, and prints the `claude mcp add` line. Zero config: it writes a managed `~/.drillable/sessions.json` with good defaults (semantic if `OPENAI_API_KEY` is present, else keyword; doc2query off for a fast first index), picks the paths for you, and converts incrementally.
- **Stays current on its own** — once wired, the running server picks up new sessions automatically (a throttled, incremental convert on query); re-run the command only to force a rebuild. `--days N` bounds the first index for a fast start on a rate-limited key.
- **Robust at scale** — the embedding path now retries a rate limit (429) or transient 5xx with backoff (honoring `Retry-After`), so a large first index *completes* instead of dying partway. Verified over 600 sessions (peak ~430 MB).

## 0.4.0

Drill your own agent's session history — the first **source adapter** — plus project-scoped retrieval so a machine-wide install never crosses projects.

- **`sessions.py` adapter** — converts Claude Code session transcripts (`~/.claude/projects/**/*.jsonl`) into the engine's markdown: one file per session, chunked by turn, grounded as dated **provenance** (a cited record of what was said, never "verified"). So "how did we handle X", "what did the agent struggle with", "when did I last touch Y" become retrievable, grounded to the exact turn. Adapters convert any non-markdown corpus into the same retrieval stack with no engine change — session history is just the first.
- **Project-scoped retrieval** — `search` takes `project=`: a query is scoped to one project by default (a user-level install never contaminates one project's drills with another's), `project="all"` searches every project with each hit labelled, and an explicit no-match abstains honestly. Non-session corpora (no `project` frontmatter) are unaffected. Schema v2, self-heals on the next query.
- **Maintenance** — CI now publishes via npm trusted publishing (OIDC), so there is no token to expire or rotate; `repository`/`bugs` metadata points at the renamed `drillablehq/context`.

## 0.3.0

The broad view — `enumerate`, the "what does this corpus hold" verb. Search finds a needle; enumerate shows the haystack: the complete set by category, with an honest completeness bit.

- **`<name>_enumerate`** — lists the whole corpus sliced by a facet (`collection` = the source folder, or `grounding` / `type` / `serving`), each value with an exact count, the set marked `[complete set]`. Pass `kind=` to list one category's members (e.g. `enumerate(by="collection", kind="decisions")`) — capped for render, with the exact count preserved. Retrieval-grade: it lists and cites, it never computes an answer — the honest boundary a doc corpus has (no oracle behind a note to recompute against).
- Rounds out the answer shapes the reference gateway already serves — identify · find · enumerate · verify — now over your own facts.

## 0.2.0

Everyday-language retrieval — finding the right doc even when you ask in plain words, not the docs' own jargon. Measured across three public codebases (FastAPI docs, the Rust Book, Cosmos SDK ADRs); see `eval/benchmark/`.

- **doc2query, bundled with semantic retrieval.** When embeddings are on, an LLM predicts the everyday-worded questions each note answers and adds them to the search *index only* (never to what's shown), so plain-language queries still find the right note. Lifts everyday-question recall@3 ~13 points with no precision cost; one-time index cost on your own key, cached. Opt out with `--no-doc2query` / `"doc2query": false`.
- **Query-conditional rerank (opt-in).** When a search is low-confidence — typically a plain-worded question — an LLM reorders the top candidates by relevance; confident searches skip it (no extra call). Closes most of the remaining gap: everyday-question recall@5 ~78%→93%. Off by default; enable with `--rerank` / `"rerank": true` / the plugin toggle. Tunable via `DRILLABLE_RERANK_FLOOR` (default 0.60).
- **Cross-project retrieval benchmark** (`eval/benchmark/`) — SHA-pinned public corpora, bias-controlled jargon-vs-lay pairs, per-corpus reporting. A standing regression gate and reproducible proof.
- npm package and plugin manifest versions realigned to 0.2.0.

## 0.1.x

Initial public releases: local MCP over a folder of markdown; cited / provenance / judgment grounding; section-level chunk retrieval with abstention; as-of dating + schema self-heal; live retriever-mode surfacing.
