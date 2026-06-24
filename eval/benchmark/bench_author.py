#!/usr/bin/env python3
"""bench_author.py — construct (jargon-query, lay-query, gold) pairs for the retrieval benchmark,
with bias controls so we don't grade ourselves.

Per corpus:
  1. pick ~N golds (distinct files) spread across the corpus,
  2. GENERATE a jargon query + a lay query for each (model A), the lay query forbidden the gold's
     distinctive tokens,
  3. LEXICAL-LEAK gate — reject a lay query that still contains a forbidden token (deterministic),
  4. INDEPENDENT VERIFY (model B, stronger/other) — given the query + the gold title among K random
     distractor titles, does B pick the gold? Keep only pairs B can place. This breaks the
     self-grading loop: a kept pair is one an independent reader can map back to the gold.

Output: configs/<name>.pairs.json = [{slug,title,jargon,lay}]. Cached/append-safe.
"""
import json, os, re, sqlite3, sys, urllib.request, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "..", "configs")
KEY = os.environ.get("OPENAI_API_KEY")
STOP = set("the a an of to in is are for and or it its on at as be by we you i with not this that these "
           "those how what why when who do does your my use using used can will into over per via".split())


def chat(model, system, user, temp=0.3):
    data = json.dumps({"model": model, "temperature": temp,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=data,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))["choices"][0]["message"]["content"].strip()


def distinctive(text, title):
    """tokens that are 'the gold's own vocabulary' — forbidden in a lay query. Identifier-ish / rare /
    title words: длинн len>3, appears, and looks technical (has digit/_/CamelCase or is in the title)."""
    titlow = title.lower()
    toks = set()
    for t in re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", text):
        tl = t.lower()
        if tl in STOP:
            continue
        if (t != tl and t != t.upper()) or any(c.isdigit() or c == "_" for c in t) or tl in titlow:
            toks.add(tl)
    for t in re.findall(r"[a-z0-9]{4,}", titlow):
        if t not in STOP:
            toks.add(t)
    return toks


GEN_SYS = ("You are given a documentation page from a software project. Produce TWO questions a real user "
           "might ask that THIS page is the best answer to, as strict JSON {\"jargon\":\"...\",\"lay\":\"...\"}. "
           "jargon: may use the page's own technical terms. lay: phrased in plain everyday words a newcomer "
           "would use, and it MUST NOT contain any of these forbidden terms: %s. Both must be answerable "
           "specifically by this page, not generic.")
VERIFY_SYS = ("Given a user question and a numbered list of documentation page titles, reply with ONLY the "
              "single number of the page that best answers it. If none clearly fits, reply 0.")


def golds_for(db, n):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    rows = con.execute("SELECT slug, title, body FROM memory").fetchall()
    rows = [r for r in rows if len(r["body"]) > 400]          # skip stubs
    rows.sort(key=lambda r: r["slug"])
    step = max(1, len(rows) // n)
    return rows[::step][:n], {r["slug"]: r["title"] for r in rows}


def author(name, n_target=20, pool=120, distract=5, gen_model="gpt-4o-mini", verify_model="gpt-4o"):
    db = os.path.join(CONF, f"{name}_emb.db")
    golds, titles = golds_for(db, pool)
    all_titles = list(titles.values())
    out_path = os.path.join(CONF, f"{name}.pairs.json")
    pairs = json.load(open(out_path)) if os.path.exists(out_path) else []
    have = {p["slug"] for p in pairs}
    import random
    for g in golds:
        if len(pairs) >= n_target or g["slug"] in have:
            continue
        forbid = distinctive(g["body"], g["title"])
        try:
            raw = chat(gen_model, GEN_SYS % (", ".join(sorted(forbid))[:1500]), g["body"][:6000])
            q = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
        except Exception:
            continue
        lay = q.get("lay", "").strip()
        if not lay or any(re.search(rf"\b{re.escape(t)}\b", lay.lower()) for t in forbid):
            continue                                          # lexical-leak gate
        # independent verify: can model B place the lay query on the gold among distractors?
        others = [t for s, t in titles.items() if s != g["slug"]]
        random.shuffle(others); cand = others[:distract] + [g["title"]]; random.shuffle(cand)
        listing = "\n".join(f"{i+1}. {t}" for i, t in enumerate(cand))
        try:
            pick = chat(verify_model, VERIFY_SYS, f"Question: {lay}\n\nPages:\n{listing}", temp=0)
            idx = int(re.search(r"\d+", pick).group())
        except Exception:
            continue
        if not (1 <= idx <= len(cand)) or cand[idx-1] != g["title"]:
            continue                                          # verifier couldn't place it → drop
        pairs.append({"slug": g["slug"], "title": g["title"], "jargon": q.get("jargon","").strip(), "lay": lay})
        json.dump(pairs, open(out_path, "w"), indent=1)
        print(f"  [{name}] {len(pairs):2}/{n_target}  {g['slug'][:40]}")
    return pairs


if __name__ == "__main__":
    for name in (sys.argv[1:] or ["fastapi", "rustbook", "cosmos"]):
        print(f"=== authoring {name} ===")
        p = author(name)
        print(f"  → {len(p)} verified pairs for {name}")
