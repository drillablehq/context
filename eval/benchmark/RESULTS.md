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
