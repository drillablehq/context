#!/usr/bin/env python3
"""bench_pass2.py — Pass 2 levers vs the residual lay-query gap, on the same benchmark.

Arms added over Pass 1:
  routed  — query-conditional: per query, rank with whichever index is MORE CONFIDENT
            (raw top-cosine vs augmented top-cosine). Parameter-free. Targets doc2query's
            displacement (jargon queries keep the raw index; lay queries get the augmented one).
  rerank  — take doc2query's top-K candidates, have an LLM reorder them by relevance to the query
            (cross-encoder style). Targets "gold is in the top-20 but not the top-5".
Reports lay (the residual) per corpus + pooled; recall@20 = the rerank ceiling.
"""
import json, os, re, sqlite3, sys, math, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
import embed  # noqa
HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "..", "..", "configs")
KEY = os.environ.get("OPENAI_API_KEY")


def _retry(fn, n=5):
    import time
    for i in range(n):
        try:
            return fn()
        except Exception:
            if i == n-1:
                raise
            time.sleep(1.5*(i+1))


def cos(a, b):
    d = sum(x*y for x, y in zip(a, b)); na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return d/(na*nb) if na and nb else 0.0


def load(db):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    vecs, text, title = {}, {}, {}
    for r in con.execute("SELECT slug,heading,text,vector FROM chunk WHERE vector IS NOT NULL"):
        vecs.setdefault(r["slug"], []).append(json.loads(r["vector"]))
        if r["slug"] not in text or len(r["text"]) > len(text[r["slug"]]):
            text[r["slug"]] = r["text"]
    for r in con.execute("SELECT slug,title FROM memory"):
        title[r["slug"]] = r["title"]
    return vecs, text, title


def best_by_slug(vecs, qv):
    return sorted(((max(cos(qv, v) for v in vs), s) for s, vs in vecs.items()), key=lambda x: -x[0])


def rank_of(order, gold):
    return order.index(gold)+1 if gold in order else 999


def rerank(query, cands, title, text, model="gpt-4o-mini"):
    """cands: list of slugs (top-K). LLM reorders by relevance. Returns reordered slug list."""
    listing = "\n".join(f"{i+1}. {title.get(s,s)} — {text.get(s,'')[:240]}" for i, s in enumerate(cands))
    sysmsg = ("Rank the numbered documents by how well each answers the question, best first. "
              "Reply with ONLY the numbers, comma-separated, best first (you may list all or just the top 8).")
    data = json.dumps({"model": model, "temperature": 0,
        "messages": [{"role": "system", "content": sysmsg},
                     {"role": "user", "content": f"Question: {query}\n\nDocuments:\n{listing}"}]}).encode()
    def _call():
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=data,
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"]
    try:
        out = _retry(_call)
        nums = [int(x) for x in re.findall(r"\d+", out) if 1 <= int(x) <= len(cands)]
    except Exception:
        nums = []
    seen, order = set(), []
    for n in nums:
        if n not in seen:
            seen.add(n); order.append(cands[n-1])
    for i, s in enumerate(cands):                    # append any the model dropped, in base order
        if s not in order:
            order.append(s)
    return order


def rec(rs, k):
    return sum(1 for r in rs if r <= k)/len(rs) if rs else 0.0


def main():
    names = sys.argv[1:] or ["fastapi", "rustbook", "cosmos"]
    K = 20
    pooled = {a: {f: [] for f in ("jargon", "lay")} for a in ("embed", "doc2query", "routed", "rerank")}
    for name in names:
        pairs = json.load(open(os.path.join(CONF, f"{name}.pairs.json")))
        raw, _, _ = load(os.path.join(CONF, f"{name}_emb.db"))
        aug, text, title = load(os.path.join(CONF, f"{name}_d2q.db"))
        res = {a: {f: [] for f in ("jargon", "lay")} for a in ("embed", "doc2query", "routed", "rerank")}
        qtexts = [p[f] for p in pairs for f in ("jargon", "lay")]      # batch-embed all queries once
        qvecs = _retry(lambda: embed.embed(qtexts))
        qmap = {t: v for t, v in zip(qtexts, qvecs)}
        for p in pairs:
            for form in ("jargon", "lay"):
                qv = qmap[p[form]]
                rb = best_by_slug(raw, qv); ab = best_by_slug(aug, qv)
                ro = [s for _, s in rb]; ao = [s for _, s in ab]
                res["embed"][form].append(rank_of(ro, p["slug"]))
                res["doc2query"][form].append(rank_of(ao, p["slug"]))
                res["routed"][form].append(rank_of(ro if rb[0][0] >= ab[0][0] else ao, p["slug"]))
                topk = ao[:K]
                res["rerank"][form].append(rank_of(rerank(p[form], topk, title, text), p["slug"]))
        print(f"\n=== {name} (n={len(pairs)}) — LAY recall ===")
        at20 = rec([rank_of([s for _, s in best_by_slug(aug, qmap[p['lay']])], p['slug']) for p in pairs], 20)
        print(f"  {'arm':10} @1/@3/@5    (lay @20 base={at20:.0%} = rerank ceiling)")
        for a in ("embed", "doc2query", "routed", "rerank"):
            for f in ("jargon", "lay"):
                pooled[a][f] += res[a][f]
            l = res[a]["lay"]
            print(f"  {a:10} {rec(l,1):.0%}/{rec(l,3):.0%}/{rec(l,5):.0%}")
    print(f"\n=== POOLED ===\n  {'arm':10} jargon @3   lay @1/@3/@5")
    for a in ("embed", "doc2query", "routed", "rerank"):
        j, l = pooled[a]["jargon"], pooled[a]["lay"]
        print(f"  {a:10} {rec(j,3):.0%}        {rec(l,1):.0%}/{rec(l,3):.0%}/{rec(l,5):.0%}")


if __name__ == "__main__":
    main()
