#!/usr/bin/env python3
"""github adapter — convert a repo's CLOSED pull-request history into the markdown the engine indexes.

The drillable-context engine ingests a folder of `*.md` (seed.py). This parser produces that folder FROM
GitHub PR history via the `gh` CLI (auth is gh's problem, not ours): one `pr-<n>.md` per MERGED/CLOSED
PR, chunked by `##` section (Summary / Files touched — the retrieval units), with frontmatter
`type: github-pr` + `originRef: <PR url>` so the engine grounds each as PROVENANCE (a dated record of
what shipped, cited to its PR — the same honest label the sessions adapter earns).

HISTORY ONLY, by design: a merged/closed PR is a durable record and indexes honestly; OPEN-PR state is
liveness and a snapshot of it is stale by construction — that's a LIVE query (`gh pr list --state open`),
deliberately NOT this adapter's job. The gap this closes: "what's in flight" was split across substrates —
the sessions adapter sees STARTS (turns), GitHub holds SHIPS — and only the first was drillable.

  python3 src/adapters/github.py --out ~/.drillable/github \
      [--repo owner/name ...] [--limit 200] [--rebuild]
"""
import argparse
import json
import os
import re
import subprocess
import sys

_WS = re.compile(r"\s+")
_FIELDS = "number,title,body,state,mergedAt,closedAt,url,author,files,baseRefName,headRefName"
MAX_BODY = 4000       # a PR body beyond this is a changelog, not a summary — keep the head
MAX_FILES = 50        # the files list is a pointer, not a diff


def _gh_json(args, timeout=60):
    """Run `gh <args>` and parse its JSON stdout. Raises on a missing/unauthenticated gh with the
    actionable message (this adapter has no credential story of its own — gh IS the credential)."""
    try:
        r = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError("`gh` not found — the github adapter reads PR history through the GitHub CLI; "
                           "install it (https://cli.github.com) and `gh auth login`.")
    if r.returncode != 0:
        raise RuntimeError(f"gh failed: {(r.stderr or r.stdout).strip()[:300]}")
    return json.loads(r.stdout or "[]")


def default_repo():
    """The cwd's repo (`owner/name`), or None when not in a repo gh recognizes."""
    try:
        d = _gh_json(["repo", "view", "--json", "nameWithOwner"], timeout=15)
        return d.get("nameWithOwner") or None
    except Exception:
        return None


def list_prs(repo, limit=200, fetch=_gh_json):
    """The repo's merged/closed PRs, newest first. `--state all` then drop OPEN — gh's `closed` state
    already includes merged, so `all`-minus-open is the one call that gets both with the state field
    intact. `fetch` is injectable for tests."""
    prs = fetch(["pr", "list", "--repo", repo, "--state", "all",
                 "--limit", str(limit), "--json", _FIELDS])
    return [p for p in prs if (p.get("state") or "").upper() != "OPEN"]


def pr_md(pr, repo):
    """The `.md` for one closed PR, or None if it's malformed (no number)."""
    n = pr.get("number")
    if not n:
        return None
    state = (pr.get("state") or "").lower()
    when = ((pr.get("mergedAt") or pr.get("closedAt") or ""))[:10] or "unknown"
    title = _WS.sub(" ", pr.get("title") or "").strip()
    author = ((pr.get("author") or {}).get("login") or "?")
    url = pr.get("url") or f"https://github.com/{repo}/pull/{n}"
    verb = "merged" if state == "merged" else "closed WITHOUT merge"
    lines = ["---", "type: github-pr", f"originRef: {url}", f"project: {repo.split('/', 1)[-1]}",
             f"date: {when}", f"state: {state}", "---", "",
             f"# PR #{n} · {title} ({verb} {when})", ""]

    body = (pr.get("body") or "").strip()
    lines.append("## Summary")
    lines.append(f"{repo}#{n} by {author} — `{pr.get('headRefName', '?')}` → "
                 f"`{pr.get('baseRefName', '?')}` · {verb} {when} · {url}")
    if body:
        lines.append("")
        # PR-body headings would out-rank this file's own chunk headings — demote them a level so the
        # chunk boundaries stay OURS (Summary / Files touched), not the PR author's.
        body = re.sub(r"^(#{1,5})(?=\s)", r"#\1", body[:MAX_BODY], flags=re.M)
        lines.append(body)
        if len(pr.get("body") or "") > MAX_BODY:
            lines.append("\n_(body truncated — the head of a long PR description.)_")
    lines.append("")

    files = [f.get("path") for f in (pr.get("files") or []) if isinstance(f, dict) and f.get("path")]
    if files:
        lines.append("## Files touched")
        lines += [f"- {p}" for p in files[:MAX_FILES]]
        if len(files) > MAX_FILES:
            lines.append(f"- … and {len(files) - MAX_FILES} more")
        lines.append("")
    return "\n".join(lines)


def convert(out, repos=None, limit=200, rebuild=False, fetch=_gh_json):
    """Convert PR history → per-repo `pr-<n>.md` under `out`. INCREMENTAL by default: a closed PR is a
    settled record, so an existing `pr-<n>.md` is skipped (a re-run — and the server's throttled refresh —
    only writes PRs that closed since). Returns {written, skipped, fresh} like the sessions adapter."""
    out = os.path.expanduser(out)
    repos = [r for r in (repos or []) if r] or ([default_repo()] if default_repo() else [])
    if not repos:
        return {"written": 0, "skipped": 0, "fresh": 0,
                "error": "no repo — pass --repo owner/name (or run inside a repo gh recognizes)"}
    written = skipped = fresh = total = 0
    for repo in repos:
        proj = repo.split("/", 1)[-1]
        try:
            prs = list_prs(repo, limit=limit, fetch=fetch)
        except RuntimeError as e:
            return {"written": written, "skipped": skipped, "fresh": fresh, "error": str(e)}
        total += len(prs)
        for pr in prs:
            dpath = os.path.join(out, proj, f"pr-{pr.get('number')}.md")
            if not rebuild and os.path.exists(dpath):
                written += 1
                continue
            md = pr_md(pr, repo)
            if not md:
                skipped += 1
                continue
            os.makedirs(os.path.dirname(dpath), exist_ok=True)
            with open(dpath, "w", encoding="utf-8") as fh:
                fh.write(md + "\n")
            written += 1
            fresh += 1
    return {"written": written, "skipped": skipped, "fresh": fresh, "total": total}


def main():
    ap = argparse.ArgumentParser(description="convert GitHub PR history → drillable-context markdown")
    ap.add_argument("--out", default="~/.drillable/github", help="output facts_dir (default ~/.drillable/github)")
    ap.add_argument("--repo", action="append", help="owner/name (repeatable; default: the cwd's repo)")
    ap.add_argument("--limit", type=int, default=200, help="max PRs per repo, newest first (default 200)")
    ap.add_argument("--rebuild", action="store_true", help="re-convert every PR (ignore the incremental skip)")
    a = ap.parse_args()
    r = convert(a.out, a.repo, a.limit, a.rebuild)
    if r.get("error"):
        sys.exit(r["error"])
    print(f"github → {os.path.expanduser(a.out)}: {r['fresh']} new · {r['written']} present "
          f"· {r['skipped']} malformed (of {r['total']} closed PRs)")


if __name__ == "__main__":
    main()
