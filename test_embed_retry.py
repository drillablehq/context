#!/usr/bin/env python3
"""test_embed_retry — embed._post retries a 429/5xx (a large first index fires many batches and WILL hit
the rate limit) with backoff, honors Retry-After, and still fails loud after the cap / on a non-retryable
status. Network-free: urllib.request.urlopen + time.sleep are mocked. Run: python3 test_embed_retry.py
"""
import io
import os
import sys
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import embed  # noqa: E402


class _Hdr:
    def __init__(self, ra=None):
        self._ra = ra

    def get(self, k, d=None):
        return self._ra if k.lower() == "retry-after" else d


def _ok(payload=b'{"data":[]}'):
    class R:
        def __enter__(self):
            return io.BytesIO(payload)

        def __exit__(self, *a):
            return False
    return R()


class TestEmbedRetry(unittest.TestCase):
    def setUp(self):
        self._urlopen, self._sleep = urllib.request.urlopen, embed.time.sleep
        self.slept = []
        embed.time.sleep = lambda s: self.slept.append(s)

    def tearDown(self):
        urllib.request.urlopen, embed.time.sleep = self._urlopen, self._sleep

    def _seq(self, items):
        it = iter(items)

        def fake(req, timeout=60):
            v = next(it)
            if isinstance(v, Exception):
                raise v
            return v
        urllib.request.urlopen = fake

    def test_429_then_success_recovers(self):
        self._seq([urllib.error.HTTPError("u", 429, "rate", _Hdr(), None),
                   urllib.error.HTTPError("u", 429, "rate", _Hdr(), None),
                   _ok()])
        self.assertEqual(embed._post("req"), {"data": []})
        self.assertEqual(len(self.slept), 2)                 # backed off twice, then succeeded

    def test_retry_after_header_honored(self):
        self._seq([urllib.error.HTTPError("u", 429, "rate", _Hdr("7"), None), _ok()])
        embed._post("req")
        self.assertEqual(self.slept, [7.0])                  # slept exactly the Retry-After

    def test_persistent_429_fails_loud_after_cap(self):
        self._seq([urllib.error.HTTPError("u", 429, "rate", _Hdr(), None)] * 20)
        with self.assertRaises(urllib.error.HTTPError):
            embed._post("req", retries=3)
        self.assertEqual(len(self.slept), 3)                 # exactly `retries` backoffs, then raise

    def test_non_retryable_status_raises_immediately(self):
        self._seq([urllib.error.HTTPError("u", 400, "bad", _Hdr(), None), _ok()])
        with self.assertRaises(urllib.error.HTTPError):
            embed._post("req")
        self.assertEqual(self.slept, [])                     # a 400 is not retried


if __name__ == "__main__":
    unittest.main()
