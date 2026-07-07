#!/usr/bin/env python3
"""test_config — config.resolve honors the doc2query/rerank flags + env in BOTH resolution paths.

Regression guard for the bug where --no-doc2query / DRILLABLE_DOC2QUERY silently no-op'd under --config
(the flag was read only in the --facts-dir branch), contradicting config.py's own docstring — which
corrupted any A/B that toggled doc2query via the flag against a config-file corpus. doc2query is an
opt-OUT (flag/env/JSON-false turns it off, never on); rerank is an opt-IN (flag/env/JSON-true turns it
on). Pure/network-free. Run: python3 test_config.py
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
import config  # noqa: E402


class TestConfigFlags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="ctx-cfg-")
        cls.facts = os.path.join(cls.dir, "facts")
        os.makedirs(cls.facts)

    def _cfg_file(self, **extra):
        p = os.path.join(self.dir, f"c-{len(extra)}-{'_'.join(extra) or 'base'}.json")
        with open(p, "w") as fh:
            json.dump({"name": "t", "facts_dir": "facts", "embed": True, **extra}, fh)
        return ["--config", p]

    def resolve(self, argv, env=None):
        with mock.patch.dict(os.environ, env or {}, clear=False):
            c = config.resolve(argv)
        return c["doc2query"], c["rerank"]

    # ── the --config path (where the bug lived) ──────────────────────────────────────────────────
    def test_config_default_d2q_on(self):
        self.assertEqual(self.resolve(self._cfg_file()), (True, False))

    def test_config_flag_turns_d2q_off(self):                       # THE FIX
        self.assertEqual(self.resolve(self._cfg_file() + ["--no-doc2query"]), (False, False))

    def test_config_env_turns_d2q_off(self):                        # THE FIX
        self.assertEqual(self.resolve(self._cfg_file(), {"DRILLABLE_DOC2QUERY": "false"}), (False, False))

    def test_config_json_false_keeps_d2q_off(self):                 # pre-existing path, must still hold
        self.assertEqual(self.resolve(self._cfg_file(doc2query=False)), (False, False))

    def test_config_no_embed_forces_d2q_off(self):                  # d2q gated on embed
        self.assertEqual(self.resolve(self._cfg_file(embed=False)), (False, False))

    def test_config_flag_turns_rerank_on(self):                     # THE FIX (opt-in mirror)
        self.assertEqual(self.resolve(self._cfg_file() + ["--rerank"]), (True, True))

    def test_config_env_turns_rerank_on(self):
        self.assertEqual(self.resolve(self._cfg_file(), {"DRILLABLE_RERANK": "true"}), (True, True))

    # ── the --facts-dir path (must be UNCHANGED by the fix) ───────────────────────────────────────
    def test_params_embed_d2q_on(self):
        self.assertEqual(self.resolve(["--facts-dir", self.facts, "--embed"]), (True, False))

    def test_params_flag_turns_d2q_off(self):
        self.assertEqual(self.resolve(["--facts-dir", self.facts, "--embed", "--no-doc2query"]), (False, False))


if __name__ == "__main__":
    unittest.main()
