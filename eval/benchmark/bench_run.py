#!/usr/bin/env python3
"""bench_run.py — Pass 1 of the retrieval benchmark: keyword vs embed vs doc2query, per corpus,
split by jargon vs lay query form. Consumes configs/<name>.pairs.json + the seeded _emb/_d2q dbs.

Reports per-corpus (the anti-overfit guardrail) and a fleet line; the jargon→lay drop is the
vocab-foreign gap each arm is measured on.
"""
import json, os, re, sqlite3, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import embed  # noqa

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "..", "configs")
STOP = set("the a an of to in is are for and or it its on at as be by we you i with not this that".split())


def toks(s):
    return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP and len(t) > 1]


def cos(a, b):
    d = sum(x*y for x, y in zip(a, b)); na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return d/(na*nb) if na and nb else 0.0


def load_vecs(db):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    out = {}
    for r in con.execute("SELECT slug,vector FROM chunk WHERE vector IS NOT NULL"):
        out.setdefault(r["slug"], []).append(json.loads(r["vector"]))
    return out


def load_kw(db):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    return [(r["slug"], set(toks(r["title"])), toks(r["body"]))
            for r in con.execute("SELECT slug,title,body FROM memory")]


def rank_embed(vecs, qv, gold):
    best = {s: max(cos(qv, v) for v in vs) for s, vs in vecs.items()}
    order = [s for s, _ in sorted(best.items(), key=lambda x: -x[1])]
    return order.index(gold)+1 if gold in order else 999


def rank_kw(rows, q, gold):
    qset = set(toks(q)); best = {}
    for slug, tt, bt in rows:
        sc = 3*sum(t in qset for t in tt) + sum(min(bt.count(t), 4) for t in qset)
        if sc > best.get(slug, -1): best[slug] = sc
    order = [s for s, sc in sorted(best.items(), key=lambda x: -x[1]) if sc > 0]
    return order.index(gold)+1 if gold in order else 999


def rec(ranks, k):
    return sum(1 for r in ranks if r <= k)/len(ranks) if ranks else 0.0


def main():
    names = sys.argv[1:] or ["fastapi", "rustbook", "cosmos"]
    fleet = {a: {f: [] for f in ("jargon", "lay")} for a in ("keyword", "embed", "doc2query")}
    for name in names:
        pairs = json.load(open(os.path.join(CONF, f"{name}.pairs.json")))
        raw = load_vecs(os.path.join(CONF, f"{name}_emb.db"))
        aug = load_vecs(os.path.join(CONF, f"{name}_d2q.db"))
        kw = load_kw(os.path.join(CONF, f"{name}_emb.db"))
        res = {a: {f: [] for f in ("jargon", "lay")} for a in ("keyword", "embed", "doc2query")}
        for p in pairs:
            for form in ("jargon", "lay"):
                q = p[form]; qv = embed.embed([q])[0]
                res["keyword"][form].append(rank_kw(kw, q, p["slug"]))
                res["embed"][form].append(rank_embed(raw, qv, p["slug"]))
                res["doc2query"][form].append(rank_embed(aug, qv, p["slug"]))
        print(f"\n=== {name}  (n={len(pairs)} golds) ===")
        print(f"  {'arm':10} {'jargon @1/@3/@5':22} {'lay @1/@3/@5':22} lay-gap@3")
        for a in ("keyword", "embed", "doc2query"):
            j, l = res[a]["jargon"], res[a]["lay"]
            for f in ("jargon", "lay"):
                fleet[a][f] += res[a][f]
            js = f"{rec(j,1):.0%}/{rec(j,3):.0%}/{rec(j,5):.0%}"
            ls = f"{rec(l,1):.0%}/{rec(l,3):.0%}/{rec(l,5):.0%}"
            print(f"  {a:10} {js:22} {ls:22} {rec(j,3)-rec(l,3):+.0%}")
    print(f"\n=== FLEET (all corpora pooled) ===")
    print(f"  {'arm':10} {'jargon @1/@3/@5':22} {'lay @1/@3/@5':22} lay-gap@3")
    for a in ("keyword", "embed", "doc2query"):
        j, l = fleet[a]["jargon"], fleet[a]["lay"]
        js = f"{rec(j,1):.0%}/{rec(j,3):.0%}/{rec(j,5):.0%}"
        ls = f"{rec(l,1):.0%}/{rec(l,3):.0%}/{rec(l,5):.0%}"
        print(f"  {a:10} {js:22} {ls:22} {rec(j,3)-rec(l,3):+.0%}")


if __name__ == "__main__":
    main()
