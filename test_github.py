#!/usr/bin/env python3
"""test_github — the GitHub PR-history adapter (src/adapters/github.py): synthetic `gh` output converts
to engine-ready markdown (frontmatter type:github-pr + originRef → provenance; ## Summary / ## Files
touched sections), OPEN PRs are excluded (liveness is not record), PR-body headings are demoted so chunk
boundaries stay ours, and convert() is incremental (an existing pr-<n>.md is skipped).
Run: python3 test_github.py
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "adapters"))
import github  # noqa: E402


def _pr(n, state="MERGED", title="fix the widget", body="A body.", files=("src/a.py",)):
    return {"number": n, "state": state, "title": title, "body": body,
            "mergedAt": "2026-06-30T12:00:00Z" if state == "MERGED" else None,
            "closedAt": "2026-06-30T12:00:00Z",
            "url": f"https://github.com/o/r/pull/{n}",
            "author": {"login": "jane"}, "baseRefName": "main", "headRefName": f"claude/x{n}",
            "files": [{"path": p} for p in files]}


class TestGithubAdapter(unittest.TestCase):
    def test_md_shape_and_frontmatter(self):
        md = github.pr_md(_pr(7), "o/r")
        self.assertIn("type: github-pr", md)
        self.assertIn("originRef: https://github.com/o/r/pull/7", md)
        self.assertIn("project: r", md)
        self.assertIn("state: merged", md)
        self.assertIn("# PR #7 · fix the widget (merged 2026-06-30)", md)
        self.assertIn("## Summary", md)
        self.assertIn("o/r#7 by jane", md)
        self.assertIn("## Files touched", md)
        self.assertIn("- src/a.py", md)

    def test_closed_without_merge_is_labelled(self):
        md = github.pr_md(_pr(8, state="CLOSED"), "o/r")
        self.assertIn("closed WITHOUT merge", md)
        self.assertIn("state: closed", md)

    def test_body_headings_demoted(self):
        md = github.pr_md(_pr(9, body="## My own heading\ntext"), "o/r")
        self.assertIn("### My own heading", md)             # demoted — chunk boundaries stay ours
        self.assertEqual(md.count("\n## "), 2)              # only Summary + Files touched at chunk level

    def test_open_prs_excluded(self):
        fetched = [_pr(1), _pr(2, state="OPEN"), _pr(3, state="CLOSED")]
        prs = github.list_prs("o/r", fetch=lambda args, timeout=60: fetched)
        self.assertEqual([p["number"] for p in prs], [1, 3])

    def test_convert_incremental(self):
        fetched = [_pr(1), _pr(2, state="OPEN"), _pr(3, state="CLOSED")]
        fetch = lambda args, timeout=60: fetched  # noqa: E731
        with tempfile.TemporaryDirectory() as out:
            r1 = github.convert(out, ["o/r"], fetch=fetch)
            self.assertEqual(r1["fresh"], 2)                 # 1 + 3; the OPEN one never lands
            self.assertTrue(os.path.exists(os.path.join(out, "r", "pr-1.md")))
            self.assertFalse(os.path.exists(os.path.join(out, "r", "pr-2.md")))
            r2 = github.convert(out, ["o/r"], fetch=fetch)
            self.assertEqual(r2["fresh"], 0)                 # incremental: nothing new → nothing rewritten
            self.assertEqual(r2["written"], 2)

    def test_error_surfaces_not_raises(self):
        def boom(args, timeout=60):
            raise RuntimeError("gh failed: auth")
        with tempfile.TemporaryDirectory() as out:
            r = github.convert(out, ["o/r"], fetch=boom)
            self.assertIn("gh failed", r["error"])


if __name__ == "__main__":
    unittest.main()
