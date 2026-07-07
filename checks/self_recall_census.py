#!/usr/bin/env python3
"""self_recall_census.py — can the retriever find each fact by the fact's OWN name?

Asks of EVERY queryable fact: does a free-text query for the fact's own subject (its title) surface that
fact through the shipped retriever? A fact the retriever can't find by its own name is a recall hole —
worst case (FLOOR-MISS) the corpus abstains, denying it holds what it holds. (The drillable-context
analog of the reference gateway's findability census.)

Exhaustive + auto-derived + self-labeled (gold = the fact itself): it sweeps the whole corpus with zero
authoring, complementing the curated query-set checks in eval/.

Discipline: drive the REAL v_search via shipped_retriever, not a reimplemented cosine order — else it
measures a path the product doesn't ship. Standing facts are excluded automatically (v_search filters
serving='queryable'). For the memory corpus rerank is off, so this is deterministic.

  export OPENAI_API_KEY=...                                   # semantic retrieval needs a key
  python3 src/seed.py --config configs/memory.json           # seed the corpus once
  python3 checks/self_recall_census.py [--only <slug-substr>]

SURFACE ⊥ ADJUDICATE: it flags candidates; each is a human read (a generic one-word title is legitimately
ambiguous, not a gap — a placeholder `description:` is the classic false flag). Not a gate.
"""
import argparse
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shipped_retriever import load_cfg, ranked_slugs  # noqa: E402


def _open_seeded(cfg):
    """Open the corpus DB, or exit with a clear seed instruction if it isn't built yet (this is an audit
    tool, not the server — it does not silently seed a 200-fact corpus for you)."""
    db = cfg["_db"]
    if not os.path.exists(db):
        sys.exit(f"no corpus DB at {db}\n  seed it first: python3 src/seed.py --config configs/{cfg['name']}.json")
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    if not con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory'").fetchone():
        sys.exit(f"{db} has no 'memory' table — reseed: python3 src/seed.py --config configs/{cfg['name']}.json")
    return con


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="restrict to slugs containing this substring")
    a = ap.parse_args()

    cfg = load_cfg()
    con = _open_seeded(cfg)
    facts = con.execute(
        "SELECT slug, title FROM memory WHERE serving='queryable' ORDER BY slug").fetchall()
    facts = [f for f in facts if a.only in f["slug"]]
    print(f"self-recall census · {len(facts)} queryable facts · db={os.path.basename(cfg['_db'])}\n")

    floor, rank, found1, foundk = [], [], 0, []
    for i, f in enumerate(facts):
        slug, title = f["slug"], (f["title"] or "").strip()
        if not title:
            continue
        slugs, abstained = ranked_slugs(cfg, title)     # query the fact's OWN title
        if abstained:
            floor.append((slug, title, []))
        elif slug not in slugs:
            rank.append((slug, title, slugs[:3]))       # returned others, not itself → crowded out
        elif slugs[0] == slug:
            found1 += 1
        else:
            foundk.append((slug, slugs.index(slug) + 1))
        if (i + 1) % 40 == 0:
            print(f"  …{i+1}/{len(facts)}")

    n = len(facts) or 1
    print(f"\n=== self-recall over {len(facts)} queryable facts ===")
    print(f"  found@1        {found1:>4}  ({found1/n:.0%})   — own-title query returns the fact first")
    print(f"  found@2+       {len(foundk):>4}  ({len(foundk)/n:.0%})   — returned, but not first")
    print(f"  RANK-MISS      {len(rank):>4}  ({len(rank)/n:.0%})   — returned others, NOT itself (crowded out)")
    print(f"  FLOOR-MISS     {len(floor):>4}  ({len(floor)/n:.0%})   — v_search ABSTAINED on its own title (severe)")

    if floor:
        print("\nFLOOR-MISSES (corpus abstains on the fact's own title — read each):")
        for slug, title, _ in floor:
            print(f"  ✗ {slug:42} “{title[:52]}”")
    if rank:
        print("\nRANK-MISSES (own-title query returns others, not itself — top-3 shown):")
        for slug, title, top in rank:
            print(f"  ~ {slug:42} “{title[:32]}” → {top}")
    print("\nNote: over-surfaces on generic/one-word titles (often a placeholder description) — each flag "
          "is a human read, not a gap. Not a gate.")


if __name__ == "__main__":
    main()
