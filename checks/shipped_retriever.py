#!/usr/bin/env python3
"""shipped_retriever.py — drive the REAL v_search() and report the slugs a user actually sees.

Why this exists: it is tempting to measure retrieval by the RANK of a gold slug in the full cosine
order. That is NOT what ships. The server's v_search() (src/server.py) applies, on top of the cosine
sort: the EMBED_FLOOR abstain gate, the EMBED_BAND top-band trim, _best_by_slug one-per-fact collapse,
the optional low-confidence LLM rerank, and the MAX_HITS cap — then abstains outright when nothing
clears the floor. So "rank in full order" over-reports what a query actually returns. An instrument must
call the path exactly as the product ships, or its worklist is confidently wrong.

This module is the single place that drives the shipped path, so every check shares ONE definition of
"what the retriever returns". It parses v_search's text output back into an ordered slug list (+ an
abstain flag), because v_search is a text-returning MCP verb by contract.

    from shipped_retriever import load_cfg, ranked_slugs
    cfg = load_cfg()                       # configs/memory.json (auto-reseeds if the DB schema is stale)
    slugs, abstained = ranked_slugs(cfg, "who is Asher?")
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import config  # noqa: E402
import server  # noqa: E402

CONF = os.path.join(HERE, "..", "configs")

# A v_search hit line is:  "(0.82) some-slug · proj § Heading  [⛓ cited] ⚠ may be stale"
# Slugs are kebab-case with no spaces, so the first whitespace-delimited token after the score is it.
_HIT = re.compile(r"^\((?:\d+\.\d+|\d+)\)\s+(\S+)")


def load_cfg(name="memory"):
    """Resolve a corpus config the same way the server does. First real query through v_search will
    auto-(re)seed to the current chunk schema if the on-disk DB is stale (server.con handles it)."""
    return config.resolve(["--config", os.path.join(CONF, f"{name}.json")])


def ranked_slugs(cfg, query, project="all"):
    """(ordered_slugs, abstained) exactly as v_search would return them to a user — post floor / band /
    rerank / cap. `abstained` is True when v_search returned an honest 'no record' (nothing cleared the
    floor) — the SEVERE findability miss. project='all' spans every project (no session scoping)."""
    out = server.v_search(cfg, query=query, project=project)
    if out.startswith("no record") or out.startswith("empty query"):
        return [], True
    slugs = []
    for line in out.splitlines():
        m = _HIT.match(line.strip())
        if m:
            slugs.append(m.group(1))
    return slugs, False


def rank_of(cfg, query, gold, project="all"):
    """1-based rank of `gold` in what v_search RETURNS, or None if it never surfaces (miss). A None here
    is the honest answer 'the shipped retriever does not return this record for this query'."""
    slugs, _ = ranked_slugs(cfg, query, project=project)
    return slugs.index(gold) + 1 if gold in slugs else None


if __name__ == "__main__":  # self-test: prove the helper drives the real path against a live corpus
    cfg = load_cfg()
    probes = [("Who is Asher?", "asher-son-demand-driver"),
              ("What is Hannah's Law?", "hannahs-law"),
              ("Should I ever run `gh pr create` to open a PR?", "github-app-publish-model"),
              ("zxqwv nonsense gibberish that matches nothing", None)]
    print(f"driving v_search against {cfg['_db']}")
    for q, gold in probes:
        slugs, ab = ranked_slugs(cfg, q)
        r = (slugs.index(gold) + 1) if (gold and gold in slugs) else None
        tag = "ABSTAIN" if ab else (f"gold@{r}" if r else f"gold MISSING (gold={gold})" if gold else "n/a")
        print(f"  [{tag:16}] returned {len(slugs)}: {slugs[:5]}  ← {q!r}")
