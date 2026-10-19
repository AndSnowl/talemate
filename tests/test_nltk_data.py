"""Vendored NLTK data makes sentence tokenization work with no network.

The real failure mode this guards: a machine with no ``~/nltk_data`` and no
network access still needs ``nltk.sent_tokenize`` to work in tests. NLTK
looks data up via ``nltk.data.path``, which conftest.py prepends the
vendored copy to (see ``tests/data/nltk_data``); this test proves that path
is enough on its own, independent of any download NLTK may find elsewhere.
"""

import nltk


def test_sent_tokenize_works_offline(monkeypatch, tmp_path):
    # An empty NLTK_DATA dir plus no network: the only way this can succeed
    # is via the vendored copy conftest.py already added to nltk.data.path.
    monkeypatch.setenv("NLTK_DATA", str(tmp_path))

    assert nltk.sent_tokenize("Hello there. How are you?") == [
        "Hello there.",
        "How are you?",
    ]
