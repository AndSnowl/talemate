"""Helpers for talking to a koboldcpp instance, shared by dev scripts and tests.

Used by ``tests/ai/conftest.py`` (to find the opt-in AI test group's target
and skip cleanly when it's unreachable, and to print its model name in the
pytest header) and tested directly, with no network, in
``tests/dev/test_ai_helpers.py`` (a local stub server and a closed port).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_KOBOLDCPP_URL = "http://192.168.0.5:5001"


def koboldcpp_url() -> str:
    """The koboldcpp base URL for AI tests: ``TALEMATE_TEST_KOBOLDCPP_URL``, or the default."""
    return os.environ.get("TALEMATE_TEST_KOBOLDCPP_URL", DEFAULT_KOBOLDCPP_URL)


def koboldcpp_model(url: str, timeout: float = 5) -> str | None:
    """Return the loaded model's name from ``GET <url>/api/v1/model``, or None.

    None covers every way the probe can fail to produce a model name:
    unreachable (refused, timed out), not koboldcpp (bad/non-JSON body), or
    reachable but reporting no model loaded.
    """
    try:
        with urllib.request.urlopen(f"{url}/api/v1/model", timeout=timeout) as response:
            data = json.loads(response.read())
    except (OSError, urllib.error.URLError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data.get("result")
