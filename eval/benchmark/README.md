# Retrieval benchmark — does context find the right doc, when asked in plain words?

A cross-project measure of drillable-context's retrieval quality. The point it makes: embedding
retrieval answers technical (**jargon**) questions almost perfectly, but loses a lot of ground when the
*same* question is asked in everyday (**lay**) words — and that everyday-words penalty is a property of
every technical-doc corpus, not any one project. The benchmark quantifies it across three real, public
codebases and measures what closes it.

## Corpora (public, SHA-pinned — see `manifest.json`)

| name | represents | repo @ sha | license |
|---|---|---|---|
| fastapi | prose docs | `tiangolo/fastapi` `docs/en/docs` | MIT |
| rustbook | dense technical | `rust-lang/book` `src` | MIT/Apache-2.0 |
| cosmos | ADRs / decisions | `cosmos/cosmos-sdk` `docs/architecture` | Apache-2.0 |

## How the (query, gold) pairs are built — bias controls

`bench_author.py`, per corpus:
1. pick golds (distinct docs) spread across the corpus;
2. **generate** a *jargon* query and a *lay* query the doc uniquely answers (the lay query is forbidden the
   doc's distinctive tokens);
3. **lexical-leak gate** — drop a lay query that still contains a forbidden token (deterministic);
4. **independent verify** — a *different* model must place the lay query back on the gold among random
   distractors, or the pair is dropped. This breaks the self-grading loop.

Output: `pairs/<name>.json` (the committed, canonical pairs).

> Honest scope: queries are model-generated and verified by a same-family model — a strong proxy, not real
> user logs, and not yet cross-family-independent (Gemini). 20 golds/corpus. Treat as directional.

## Reproduce

```sh
# 1. vendor the corpora at the pinned SHAs (see manifest.json) into a working dir
# 2. seed each corpus twice with drillable-context: embed-only and embed+doc2query
#    (configs name them <name>_emb / <name>_d2q)
# 3. author pairs (or use the committed pairs/ — copy to configs/<name>.pairs.json)
python3 bench_author.py            # needs OPENAI_API_KEY
# 4. run the arms
python3 bench_run.py               # keyword vs embed vs doc2query, jargon vs lay
```

## What it's for

- a **standing regression gate** — a retrieval change must not drop lay recall across corpora;
- the **anti-overfit guardrail** — results are reported per-corpus, so a lever that only helps one project
  (e.g. ours) doesn't pass;
- **launch proof** — measured recall on real public codebases.

See `RESULTS.md` for the latest run.
