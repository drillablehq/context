# checks/ — retrieval-quality audits (driven through the shipped serve path)

Standing audit tools that exercise the **real** `src/server.py:v_search` — floor / band / rerank / cap /
abstain / `serving='queryable'` filter — rather than a reimplemented cosine order. Measuring anything
short of the shipped path produces a confident, wrong worklist, so every check here routes through one
helper.

Unlike `eval/` (curated one-off experiments, gitignored scratch), these are tracked and meant to be
re-run as the corpus grows.

## Files

- **`shipped_retriever.py`** — the one place that drives `v_search` and parses its text output back into
  an ordered slug list (+ an abstain flag). Import `load_cfg` / `ranked_slugs` / `rank_of`. Run it
  directly for a quick smoke test against a live corpus.
- **`self_recall_census.py`** — sweeps every queryable fact and asks: does a query for the fact's **own
  title** surface it? Buckets each into found@1 / found@2+ / RANK-MISS (returned others, not itself) /
  **FLOOR-MISS** (abstained on its own title — the severe hole). Surfaces candidates; it is **not a gate**
  (a generic one-word title — usually a placeholder `description:` — is a legitimate false flag, so each
  hit is a human read).

## Running

```sh
export OPENAI_API_KEY=...                          # semantic retrieval needs a key
python3 src/seed.py --config configs/memory.json   # build the corpus DB once
python3 checks/self_recall_census.py               # audit; --only <slug-substr> to scope
python3 checks/shipped_retriever.py                # helper smoke test
```

A clean run is `0 FLOOR-MISS` and no genuine RANK-MISS. A FLOOR-MISS means the corpus can't retrieve a
fact by its own name — fix the fact's content/description (recall-only, never by broadening the shared
matcher), reseed, and re-run.
