#!/usr/bin/env python3
"""Tests for the `enumerate` verb — the 'what does this corpus hold' shape.

Exercises every branch against an in-memory fixture (axes · kind filter · completeness bit · abstains),
then a smoke against whatever real seeded DB is checked in — so we know it runs on the live schema, not
just synthetic rows. No embeddings needed: enumerate is pure SQL over the memory table.

  python3 test_enumerate.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import server  # noqa: E402


def _fixture():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE memory (slug TEXT PRIMARY KEY, type TEXT NOT NULL, serving TEXT NOT NULL, "
              "title TEXT NOT NULL, body TEXT NOT NULL, source_file TEXT NOT NULL, grounding TEXT NOT NULL)")
    rows = [
        ("hannahs-law", "", "queryable", "Hannah's Law — price is floor-height", "b", "findings/hannahs-law.md", "cited"),
        ("the-auto-apply-line", "", "queryable", "The auto-apply line", "b", "findings/the-auto-apply-line.md", "cited"),
        ("corpus-value", "", "queryable", "Corpus value model", "b", "findings/corpus-value.md", "judgment"),
        ("ship-one-plugin", "decision", "queryable", "Ship one plugin", "b", "decisions/ship-one-plugin.md", "cited"),
        ("chunk-by-section", "decision", "queryable", "Chunk by section", "b", "decisions/chunk-by-section.md", "cited"),
        ("we-use-tabs", "preference", "standing", "We use tabs", "b", "conventions/tabs.md", "judgment"),
    ]
    c.executemany("INSERT INTO memory(slug,type,serving,title,body,source_file,grounding) VALUES (?,?,?,?,?,?,?)", rows)
    return c


def run():
    fx = _fixture()
    server.con = lambda cfg: fx
    cfg = {"name": "context"}
    fails = []

    def check(label, cond, got=""):
        print(("ok    " if cond else "FAIL  ") + label + ("" if cond else f"\n      → {got!r}"))
        if not cond:
            fails.append(label)

    # directory by collection (default) — exact counts over the whole set, marked complete
    out = server.v_enumerate(cfg)
    check("collection directory: findings · 3", "findings · 3" in out, out)
    check("collection directory: decisions · 2", "decisions · 2" in out, out)
    check("collection directory: conventions · 1", "conventions · 1" in out, out)
    check("directory carries the completeness bit", "[complete set]" in out, out)
    check("directory offers a drill", 'enumerate(by="collection"' in out, out)

    # by grounding — the axis the mock showed (cited vs judgment)
    out = server.v_enumerate(cfg, by="grounding")
    check("grounding: cited · 4", "cited · 4" in out, out)
    check("grounding: judgment · 2", "judgment · 2" in out, out)

    # by serving — standing vs queryable is a real axis (enumerate spans the whole corpus)
    out = server.v_enumerate(cfg, by="serving")
    check("serving: queryable · 5", "queryable · 5" in out, out)
    check("serving: standing · 1", "standing · 1" in out, out)

    # kind filter — a category's members, exact count, complete
    out = server.v_enumerate(cfg, by="collection", kind="decisions")
    check("decisions: 2 facts [complete]", 'decisions": 2 facts  [complete]' in out, out)
    check("decisions lists a member", "ship-one-plugin" in out, out)
    check("decisions excludes a finding", "hannahs-law" not in out, out)
    check("member carries its grounding mark", "⛓ cited" in out, out)

    # capped render → the count stays exact but completeness flips honest
    server.ENUM_CAP = 1
    out = server.v_enumerate(cfg, by="collection", kind="findings")
    check("cap surfaces 'showing 1 of 3'", "showing 1 of 3" in out, out)
    check("cap marks 'not complete'", "not complete" in out, out)
    server.ENUM_CAP = 60

    # unknown axis → rejected with the valid list
    out = server.v_enumerate(cfg, by="bogus")
    check("unknown axis rejected", "unknown axis" in out and "collection" in out, out)

    # unknown category → honest abstain with what IS available (never a fabricated set)
    out = server.v_enumerate(cfg, by="collection", kind="nope")
    check("unknown kind abstains", 'no facts with collection="nope"' in out, out)
    check("abstain names available categories", "findings" in out, out)

    return fails


if __name__ == "__main__":
    fails = run()

    here = os.path.dirname(os.path.abspath(__file__))
    for db in ("configs/memory.db", "configs/docs.db", "configs/check.db"):
        p = os.path.join(here, db)
        if os.path.exists(p):
            rc = sqlite3.connect(p)
            rc.row_factory = sqlite3.Row
            try:
                server.con = lambda cfg: rc
                out = server.v_enumerate({"name": os.path.basename(db)[:-3]}, by="grounding")
                print(f"\n[real-db smoke — {db}, live schema]\n" + out)
            except Exception as e:  # noqa: BLE001
                print(f"real-db smoke {db} FAILED: {e}")
                fails.append(f"smoke:{db}")
            break

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}"))
    sys.exit(1 if fails else 0)
