#!/usr/bin/env python3
"""prove_d2q.py — chunk-level prove-out of doc2query through the REAL seed path.

Measures FOREIGN-query recall@k over the `chunk` table for two seeded DBs:
  memory.db      (doc2query OFF — baseline)
  memory_d2q.db  (doc2query ON  — index-side expansion)
Best-chunk-per-slug ranking, matching the server's _best_by_slug. Gold = the slug.
"""
import json, os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import embed  # noqa

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "..", "configs")

FOREIGN = [
    ("If I finish some changes, how do they get submitted upstream — do I push the button myself?", "github-app-publish-model"),
    ("The service returns a weird error number right after a deploy — is something broken?", "gateway-get-400-is-stale"),
    ("Are we locked into one AI vendor, or can the system reach other engines too?", "cross-family-model-access"),
    ("What's the repeatable grind that keeps pushing the work forward bit by bit?", "the-ratchet"),
    ("If I attach a document in the conversation, can the person on the other end open it?", "no-file-attachments-readable"),
    ("What determines whether a capability is worth money versus free for anyone to copy?", "hannahs-law"),
    ("When can a contribution land on its own without someone signing off on it?", "auto-apply-line"),
    ("Which relative of Jared's is the origin of some of the early feature requests?", "asher-son-demand-driver"),
    ("Should I open with insider shorthand or everyday wording?", "communicate-plain-not-jargon"),
    ("There are two copies of the repo checked out — which one am I supposed to change?", "worktree-edit-path-discipline"),
    ("The endpoint hangs and never answers at all — what does that mean versus a bad reply?", "gateway-timeout-is-app-down-oom"),
    ("Stuff here goes live almost immediately after I open it — what should I plan around?", "fast-pr-merge-races-followups"),
]


def best_by_slug_rank(db, qvec, gold):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    rows = con.execute("SELECT slug,vector FROM chunk WHERE vector IS NOT NULL").fetchall()
    con.close()
    best = {}
    for r in rows:
        s = embed.cosine(qvec, json.loads(r["vector"]))
        if r["slug"] not in best or s > best[r["slug"]]:
            best[r["slug"]] = s
    order = [s for s, _ in sorted(best.items(), key=lambda x: -x[1])]
    return order.index(gold) + 1 if gold in order else 999


# CONTROL — already-working queries; the PRECISION proxy (doc2query must not drop these).
CONTROL = [
    ("Should I ever run `gh pr create` to open a PR in this project?", "github-app-publish-model"),
    ("Why would the gateway return a 400 when I fetch its URL?", "gateway-get-400-is-stale"),
    ("Can this project call OpenAI or Gemini, or only Claude?", "cross-family-model-access"),
    ("Who is Asher?", "asher-son-demand-driver"),
    ("What is Hannah's Law?", "hannahs-law"),
    ("What's 'the ratchet' here?", "the-ratchet"),
    ("Can Jared read a PDF if I send him one as a file?", "no-file-attachments-readable"),
    ("How does the auto-apply lane work and what's its scope?", "auto-apply-line"),
]


def measure(db, label, qs):
    if not os.path.exists(db):
        print(f"  {label}: MISSING db {db}"); return
    ranks = [best_by_slug_rank(db, embed.embed([q])[0], gold) for q, gold in qs]
    n = len(ranks)
    def rec(k): return sum(1 for r in ranks if r <= k) / n
    print(f"  {label:18} n={n}  recall@1 {rec(1):>4.0%}  @3 {rec(3):>4.0%}  @5 {rec(5):>4.0%}  @10 {rec(10):>4.0%}")


def main():
    base, d2q = os.path.join(CONF, "memory.db"), os.path.join(CONF, "memory_d2q.db")
    print("=== FOREIGN recall (recover) — chunk-level, real seed path ===")
    measure(base, "BASELINE (d2q off)", FOREIGN)
    measure(d2q, "DOC2QUERY (d2q on)", FOREIGN)
    print("=== CONTROL recall (precision proxy — must not drop) ===")
    measure(base, "BASELINE (d2q off)", CONTROL)
    measure(d2q, "DOC2QUERY (d2q on)", CONTROL)


if __name__ == "__main__":
    main()
