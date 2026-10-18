"""Unit tests for the koboldcpp helpers (scripts/dev/ai_helpers.py).

No real network: `test_koboldcpp_model_parses_result` talks to a local
stub HTTP server, `test_koboldcpp_model_none_when_unreachable` to a closed
local port, and `test_ai_tests_skip_without_opt_in` runs a throwaway AI
test (via pytester) against the opt-in fixture itself -- never the real
koboldcpp target, and never with TALEMATE_AI_TESTS=1.
"""

import importlib.util
import json
import socket
import sys
import textwrap
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "ai_helpers", _REPO_ROOT / "scripts" / "dev" / "ai_helpers.py"
)
ai_helpers = importlib.util.module_from_spec(_spec)
sys.modules["ai_helpers"] = ai_helpers
_spec.loader.exec_module(ai_helpers)

pytest_plugins = ["pytester"]


class _StubModelHandler(BaseHTTPRequestHandler):
    result = "koboldcpp/stub-model"

    def do_GET(self):
        if self.path != "/api/v1/model":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"result": self.result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # quiet: no per-request stderr noise
        pass


def test_koboldcpp_model_parses_result():
    server = HTTPServer(("127.0.0.1", 0), _StubModelHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        assert ai_helpers.koboldcpp_model(url) == "koboldcpp/stub-model"
    finally:
        server.shutdown()
        thread.join()


def test_koboldcpp_model_none_when_unreachable():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
    # The socket above is now closed; nothing listens on closed_port, so the
    # connection is refused immediately (no hang on the 5s default timeout).
    began = time.monotonic()
    assert ai_helpers.koboldcpp_model(f"http://127.0.0.1:{closed_port}") is None
    assert time.monotonic() - began < 4


def test_koboldcpp_url_defaults_and_honors_override(monkeypatch):
    monkeypatch.delenv("TALEMATE_TEST_KOBOLDCPP_URL", raising=False)
    assert ai_helpers.koboldcpp_url() == ai_helpers.DEFAULT_KOBOLDCPP_URL

    monkeypatch.setenv("TALEMATE_TEST_KOBOLDCPP_URL", "http://127.0.0.1:9999")
    assert ai_helpers.koboldcpp_url() == "http://127.0.0.1:9999"


def test_ai_tests_skip_without_opt_in(pytester, monkeypatch):
    """Without TALEMATE_AI_TESTS=1, a test under the real opt-in fixture skips.

    Exercises the actual `_require_ai_tests_opt_in` fixture from
    tests/ai/conftest.py (loaded here by path, so this doesn't duplicate its
    logic) in a throwaway pytester test that makes no network call of its
    own -- it never reaches `ai_app`, which is the only thing here that
    would probe koboldcpp.
    """
    monkeypatch.delenv("TALEMATE_AI_TESTS", raising=False)
    ai_conftest_path = _REPO_ROOT / "tests" / "ai" / "conftest.py"

    pytester.makeconftest(
        textwrap.dedent(
            f"""
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "ai_conftest_under_test", {str(ai_conftest_path)!r}
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _require_ai_tests_opt_in = mod._require_ai_tests_opt_in
            """
        )
    )
    pytester.makepyfile(
        """
        def test_never_runs(_require_ai_tests_opt_in):
            assert False, "should have been skipped before this ran"
        """
    )

    result = pytester.runpytest_inprocess(
        "-rs", "-p", "no:cacheprovider", "-p", "no:xdist", "-p", "no:asyncio"
    )

    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*TALEMATE_AI_TESTS=1*"])
