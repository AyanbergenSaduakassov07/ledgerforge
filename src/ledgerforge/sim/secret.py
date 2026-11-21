"""Generator secret for closed evaluation (trusted side only: sim/ and evaluation/).

Without a key every random stream is derived from the public seed alone, so anyone holding the
open generator can search seeds until the episode_id matches and rebuild the private truth.
When LEDGERFORGE_SECRET is set, every seed string is replaced by HMAC-SHA256(key, seed string):
episode ids, world/fault/order streams and id salts then depend on a value the agent never sees.

With an empty key the seed strings pass through unchanged, so open episodes stay byte-identical.
env/ and agents/ must never import this module.
"""

from __future__ import annotations

import hashlib
import hmac
import os

SECRET_ENV = "LEDGERFORGE_SECRET"  # noqa: S105 - variable name, not a value


def secret_key() -> bytes:
    """Read at call time so the evaluator process picks up the key from its own environment."""
    return os.environ.get(SECRET_ENV, "").encode("utf-8")


def keyed(material: str) -> str:
    """Seed string for random.Random: unchanged without a key, HMAC-SHA256 hex with one."""
    key = secret_key()
    if not key:
        return material
    return hmac.new(key, material.encode("utf-8"), hashlib.sha256).hexdigest()
