"""
Utility helpers for deterministic cache/dedup keys.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def build_pattern_fingerprint(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

