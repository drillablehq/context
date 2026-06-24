# Benchmark results — Pass 1 (baseline arms)

Run 2026-06-24. 60 golds (20/corpus), each asked two ways (jargon + lay). Arms: keyword · embed-only ·
doc2query. `lay-gap@3` = jargon recall@3 − lay recall@3 (the everyday-words penalty; smaller is better).

## Pooled (all three corpora)

| arm | jargon @1/@3/@5 | lay @1/@3/@5 | lay-gap@3 |
|---|---|---|---|
| keyword | 37% / 60% / 72% | 5% / 10% / 18% | +50% |
| embed | 85% / 100% / 100% | 45% / 62% / 72% | +38% |
| **doc2query** | 83% / 98% / 100% | **55% / 73% / 80%** | **+25%** |

## Per corpus — lay recall@3 (embed → doc2query)

| corpus | keyword | embed | doc2query |
|---|---|---|---|
| fastapi | 0% | 50% | **65%** |
| rustbook | 15% | 55% | **60%** |
| cosmos | 15% | 80% | **95%** |

## Reading

1. **The everyday-words penalty is real and cross-project.** Embeddings answer 98–100% of jargon queries
   @3 but only 62% of lay queries — a 38-point drop that shows up on *every* corpus. It's a property of
   retrieval over technical docs, not any one project.
2. **doc2query generalizes.** It lifts lay recall@3 on all three corpora (+5 to +15), narrows the gap
   (+38 → +25, ~⅓ of the penalty closed), and barely touches jargon recall. Confirms shipping it.
3. **Keyword alone is catastrophic on lay queries** (10% @3 vs embed's 62%) — semantic retrieval is the
   dominant lever, doc2query the consistent second.
4. **Residual headroom: a 25-point gap remains.** That's the target for Pass 2 (cross-encoder rerank of
   top-k; query-conditional augmentation), to be measured against this same benchmark.

# Benchmark results — Pass 2 (levers vs the residual)

Run 2026-06-24 (`bench_pass2.py`). Two levers over the Pass-1 arms, measured on LAY queries (the residual):
**routed** (query-conditional: per query, rank with whichever index — raw or augmented — is more
confident) and **rerank** (an LLM reorders doc2query's top-20 by relevance).

| arm | jargon @3 | lay @1/@3/@5 |
|---|---|---|
| embed | 100% | 45% / 62% / 72% |
| doc2query | 98% | 60% / 75% / 78% |
| routed | 100% | 60% / 73% / 78% |
| **rerank** | 97% | **63% / 83% / 93%** |

Per-corpus lay recall@20 (the rerank ceiling): FastAPI 90%, Rust 95%, Cosmos 100%.

## Reading

1. **The residual is a RANKING problem, not a retrieval problem.** lay recall@20 is 90–100% — the right doc
   is almost always *in* doc2query's candidate set; it's just ranked below the serve band. So the fix is
   reordering, not better retrieval.
2. **Rerank closes most of it.** lay@5 78→**93%** pooled (per-corpus 65→85 / 70→95 / 100→100), approaching
   the recall@20 ceiling — the LLM reorder reliably promotes the gold into the top-5. Combined embed→rerank
   is lay@5 72→93%. Slight jargon cost (100→97). **Cost: one LLM call per query at SERVE time** (vs
   doc2query's index-time, free-at-serve) — a different, premium cost class.
3. **Routed is a marginal polish, and not free to ship.** It recovers doc2query's tiny jargon displacement
   (98→100 @3) at ≈no lay change — but productionizing it needs BOTH raw and augmented vectors stored per
   chunk (dual-vector). Not worth a 2-point jargon gain. Tried and skipped.

## The Pass-2 conclusion

The everyday-words gap is closable — by **rerank**, which is cheap to *wire* (no schema change, just
reorder the top-k) but costs a per-query LLM call to *run*. The recommended shape is **query-conditional
rerank**: fire only on low-confidence retrieval (the lay queries), skip it when embedding is already
confident (jargon, already ~100%) — paying the LLM call only on the ~third of queries that need it.
