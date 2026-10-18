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

import pytest

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


def _closed_local_url() -> str:
    """A koboldcpp URL nothing listens on, so a stray probe can't go anywhere."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{sock.getsockname()[1]}"


def _ai_conftest(body: str) -> str:
    """pytester conftest text: load tests/ai/conftest.py as ``mod``, then ``body``."""
    path = _REPO_ROOT / "tests" / "ai" / "conftest.py"
    return textwrap.dedent(
        f"""
            import importlib.util
            import types
            from pathlib import Path

            import pytest

            spec = importlib.util.spec_from_file_location(
                "ai_conftest_under_test", {str(path)!r}
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            """
    ) + textwrap.dedent(body)


_PYTESTER_ARGS = ("-p", "no:cacheprovider", "-p", "no:xdist", "-p", "no:asyncio")


@pytest.mark.parametrize(
    "markexpr, probes",
    [(None, False), ("not e2e and not ai", False), ("e2e", False), ("ai", True)],
)
def test_header_probes_koboldcpp_only_when_ai_is_selected(
    pytester, monkeypatch, markexpr, probes
):
    """With TALEMATE_AI_TESTS=1 exported, only a run selecting ``-m ai`` probes.

    The probe is replaced by a recorder and the URL points at a closed local
    port: nothing here can reach a real koboldcpp.
    """
    monkeypatch.setenv("TALEMATE_AI_TESTS", "1")
    monkeypatch.setenv("TALEMATE_TEST_KOBOLDCPP_URL", _closed_local_url())
    pytester.makeconftest(
        _ai_conftest(
            """
            def _recording_probe(url, timeout=5):
                with open("probed.txt", "a") as f:
                    f.write(url + "\\n")
                return "stub-model"

            mod.koboldcpp_model = _recording_probe
            pytest_report_header = mod.pytest_report_header
            """
        )
    )
    pytester.makepyfile("def test_nothing(): pass")
    args = list(_PYTESTER_ARGS) + (["-m", markexpr] if markexpr else [])

    result = pytester.runpytest_inprocess(*args)

    probed = (pytester.path / "probed.txt").exists()
    assert probed is probes
    header = "koboldcpp model: stub-model" in result.stdout.str()
    assert header is probes


_RESULTS_CONFTEST = """
    mod.ARTIFACTS_DIR = Path.cwd() / "artifacts"
    mod.koboldcpp_model = lambda url, timeout=5: "stub-model"
    mod.talemate_app = types.SimpleNamespace(
        start=lambda root, ai: types.SimpleNamespace(root=root),
        stop=lambda root: None,
    )
    ai_app = mod.ai_app
    pytest_runtest_logreport = mod.pytest_runtest_logreport
    pytest_sessionfinish = mod.pytest_sessionfinish
    """

_RESULTS_TESTS = """
    import pytest

    def test_passes(ai_app):
        pass

    def test_fails(ai_app):
        assert False

    def test_skips(ai_app):
        pytest.skip("not this one")
    """


def test_ai_run_writes_results_with_model_name(pytester, monkeypatch):
    """An AI run records its counts and model in .test-artifacts/<ts>/results.txt.

    No network: the opt-in fixture is a no-op stand-in (TALEMATE_AI_TESTS is
    never set), the probe is stubbed and the app start is a fake.
    """
    monkeypatch.delenv("TALEMATE_AI_TESTS", raising=False)
    monkeypatch.setenv("TALEMATE_TEST_KOBOLDCPP_URL", _closed_local_url())
    pytester.makeconftest(
        _ai_conftest(
            _RESULTS_CONFTEST
            + """
    @pytest.fixture(scope="session")
    def _require_ai_tests_opt_in():
        pass
    """
        )
    )
    pytester.makepyfile(textwrap.dedent(_RESULTS_TESTS))

    result = pytester.runpytest_inprocess(*_PYTESTER_ARGS)

    result.assert_outcomes(passed=1, failed=1, skipped=1)
    [results] = (pytester.path / "artifacts").glob("*/results.txt")
    assert results.read_text() == (
        "model: stub-model\npassed: 1\nfailed: 1\nskipped: 1\n"
    )
    assert (results.parent / "model.txt").read_text() == "stub-model\n"


def test_no_results_file_when_ai_group_did_not_run(pytester, monkeypatch):
    """Without the opt-in the group skips, and nothing is written."""
    monkeypatch.delenv("TALEMATE_AI_TESTS", raising=False)
    monkeypatch.setenv("TALEMATE_TEST_KOBOLDCPP_URL", _closed_local_url())
    pytester.makeconftest(
        _ai_conftest(
            _RESULTS_CONFTEST
            + """
    _require_ai_tests_opt_in = mod._require_ai_tests_opt_in
    """
        )
    )
    pytester.makepyfile(textwrap.dedent(_RESULTS_TESTS))

    result = pytester.runpytest_inprocess(*_PYTESTER_ARGS)

    result.assert_outcomes(skipped=3)
    assert not (pytester.path / "artifacts").exists()
