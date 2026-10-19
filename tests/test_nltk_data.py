"""Vendored NLTK data makes sentence tokenization work with no network.

The real failure mode this guards: a machine with no ``~/nltk_data`` and no
network access still needs ``nltk.sent_tokenize`` to work in tests. NLTK
looks data up via ``nltk.data.path``, which conftest.py prepends the
vendored copy to (see ``tests/data/nltk_data``); this test proves that path
is enough on its own, independent of any download NLTK may find elsewhere.

NLTK reads the ``NLTK_DATA`` environment variable only once, at import time,
to seed ``nltk.data.path`` — so ``monkeypatch.setenv("NLTK_DATA", ...)``
after that import has no effect on lookups. This test instead replaces
``nltk.data.path`` itself for the duration of the test, so the only entry
left is the vendored copy.
"""

from pathlib import Path

import nltk

_VENDORED_NLTK_DATA = Path(__file__).resolve().parent / "data" / "nltk_data"


def test_sent_tokenize_works_offline(monkeypatch):
    # Only the vendored copy on the path, and no network: the only way this
    # can succeed is via that vendored data, independent of whatever else
    # conftest.py or the environment may have added to nltk.data.path.
    monkeypatch.setattr(nltk.data, "path", [str(_VENDORED_NLTK_DATA)])

    assert nltk.sent_tokenize("Hello there. How are you?") == [
        "Hello there.",
        "How are you?",
    ]
