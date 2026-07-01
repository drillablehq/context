#!/usr/bin/env python3
"""embed.py — optional embedding retriever (mirrors the gateway's `nearest.ts`).

Stdlib-only (urllib) so the no-pip-install property survives. Calls OpenAI's embeddings endpoint with
`text-embedding-3-small` — the same model the drillable gateway uses (F2dl proved recall@3 = 100%,
scale-invariant to 25×). Degrades gracefully: no key → returns None and the engine falls back to the
keyword scorer (so a small/offline corpus still works with zero config).

The model + endpoint are grounded in the gateway's working retriever, not memory — drillable's `models`
domain honestly abstains on OpenAI model specs (a declared vendor boundary), so we don't assert
dimensions; we store whatever the API returns.
"""
import json
import math
import os
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.openai.com/v1/embeddings"
MODEL = os.environ.get("DRILLABLE_EMBED_MODEL", "text-embedding-3-small")
_RETRYABLE = frozenset((429, 500, 502, 503, 504))


def _key():
    return os.environ.get("OPENAI_API_KEY")


def available():
    return _key() is not None


def _post(req, retries=6):
    """POST with a bounded retry-with-backoff on a RATE LIMIT (429) or a transient 5xx / network error —
    indexing a large corpus fires many embedding batches back-to-back and WILL hit 429 without this
    (surfaced dogfooding the sessions adapter at full scale). Honors a `Retry-After` header when present;
    else exponential backoff capped at 30s. Re-raises after the cap so a genuine outage still fails loud."""
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code not in _RETRYABLE or attempt >= retries:
                raise
            ra = e.headers.get("Retry-After") if e.headers else None
            try:
                wait = float(ra) if ra else min(2.0 ** attempt, 30.0)
            except ValueError:
                wait = min(2.0 ** attempt, 30.0)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError):
            if attempt >= retries:
                raise
            time.sleep(min(2.0 ** attempt, 30.0))


def embed(texts, batch=100):
    """List[str] -> List[vector], or None if no key. Order-preserving (sorts by response index).
    Rate-limit-resilient (see _post) so a large first index doesn't die on a 429."""
    key = _key()
    if not key:
        return None
    out = []
    for i in range(0, len(texts), batch):
        chunk = [(t[:8000] or " ") for t in texts[i:i + batch]]
        req = urllib.request.Request(
            ENDPOINT, method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            data=json.dumps({"model": MODEL, "input": chunk}).encode())
        data = _post(req)
        out.extend(d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"]))
    return out


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
