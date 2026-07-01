# Changelog

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
