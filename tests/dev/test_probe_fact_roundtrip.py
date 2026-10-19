"""Unit tests for the fact round-trip probe (scripts/dev/probe_fact_roundtrip.py).

No real network: a local stub HTTP server answers ``/api/v1/model`` and
``/v1/chat/completions``, the latter with a canned reply chosen by a
keyword found in either the system or the user message (extract / prose /
check, or a per-sample override), same pattern as
``tests/dev/test_ai_helpers.py``. ``TALEMATE_AI_TESTS`` is set only in the
tests that need ``main()`` to actually run, and always points at this stub.
"""

import importlib.util
import json
import sys
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "probe_fact_roundtrip",
    _REPO_ROOT / "scripts" / "dev" / "probe_fact_roundtrip.py",
)
probe = importlib.util.module_from_spec(_spec)
sys.modules["probe_fact_roundtrip"] = probe
_spec.loader.exec_module(probe)


def _make_handler(replies: dict[str, str], model_name: str = "stub-model"):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/v1/model":
                body = json.dumps({"result": model_name}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            system = next(
                (m["content"] for m in payload["messages"] if m["role"] == "system"),
                "",
            )
            user = next(
                (m["content"] for m in payload["messages"] if m["role"] == "user"),
                "",
            )
            # a keyword may be in the system prompt (which step) or the user
            # message (e.g. a marker specific to one sample's text), checked
            # in the replies dict's insertion order so a sample-specific
            # override can be listed ahead of the general per-step replies
            haystack = f"{system}\n{user}"
            content = next(
                (reply for keyword, reply in replies.items() if keyword in haystack),
                "",
            )
            body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # quiet: no per-request stderr noise
            pass

    return Handler


@contextmanager
def _stub_server(replies: dict[str, str], model_name: str = "stub-model"):
    server = HTTPServer(("127.0.0.1", 0), _make_handler(replies, model_name))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


_FACTS_REPLY = json.dumps(
    [
        {"category": "appearance", "text": "tall with a shaved head"},
        {"category": "personality", "text": "blunt and loyal"},
    ]
)
_CHECK_REPLY = json.dumps({"invented": ["has a limp"], "dropped": ["blunt and loyal"]})

_STANDARD_REPLIES = {
    "JSON list": _FACTS_REPLY,
    "one paragraph": "He is tall with a shaved head.",
    "invented": _CHECK_REPLY,
}


def test_main_refuses_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv("TALEMATE_AI_TESTS", raising=False)
    out_dir = tmp_path / "out"

    code = probe.main(["--out", str(out_dir)])

    assert code == 2
    assert not out_dir.exists()


def test_run_sample_against_stub():
    with _stub_server(_STANDARD_REPLIES) as url:
        sample = {
            "name": "Dorran",
            "text": "A tall, shaved-headed man, blunt and loyal.",
        }

        result = probe.run_sample(url, sample, rounds=2)

    assert len(result["rounds"]) == 3
    assert result["rounds"][0]["facts"] == json.loads(_FACTS_REPLY)
    assert result["rounds"][0]["invented"] == ["has a limp"]
    assert result["errors"] == []


def test_unparsable_facts_recorded_as_error(tmp_path, monkeypatch):
    """One sample's unparsable extraction is recorded as an error, and the
    run still completes the next sample (via ``main()`` end to end, since
    that's the only level at which "the next sample" has meaning).
    """
    # "ZZZ_BROKEN_ZZZ" only ever appears in the broken sample's own source
    # text, so it's checked (and matches) ahead of the general "JSON list"
    # extraction reply -- the fine sample's text never contains it, so its
    # extract/re-extract calls fall through to the normal facts reply.
    replies = {"ZZZ_BROKEN_ZZZ": "sorry", **_STANDARD_REPLIES}

    with _stub_server(replies) as url:
        monkeypatch.setenv("TALEMATE_AI_TESTS", "1")
        monkeypatch.setenv("TALEMATE_TEST_KOBOLDCPP_URL", url)

        samples_path = tmp_path / "samples.json"
        samples_path.write_text(
            json.dumps(
                [
                    {"name": "Broken", "text": "ZZZ_BROKEN_ZZZ description"},
                    {
                        "name": "Fine",
                        "text": "A tall, shaved-headed man, blunt and loyal.",
                    },
                ]
            )
        )
        out_dir = tmp_path / "out"

        code = probe.main(
            ["--rounds", "2", "--samples", str(samples_path), "--out", str(out_dir)]
        )

    assert code == 0
    report = json.loads((out_dir / "report.json").read_text())

    assert len(report["errors"]) == 1
    error = report["errors"][0]
    assert error["sample"] == "Broken"
    assert error["step"] == "extract"

    broken, fine = report["samples"]
    assert broken["name"] == "Broken"
    assert broken["rounds"] == []
    # the run continued past the broken sample: the next one completed in full
    assert fine["name"] == "Fine"
    assert len(fine["rounds"]) == 3
    assert fine["rounds"][0]["facts"] == json.loads(_FACTS_REPLY)


def test_run_sample_calls_on_step_after_every_step():
    """``on_step`` fires after every extract/prose/check/reextract, with the
    result built so far -- so a caller can rewrite its report after each
    one rather than losing a sample's completed rounds to a kill or a hang.
    """
    with _stub_server(_STANDARD_REPLIES) as url:
        sample = {
            "name": "Dorran",
            "text": "A tall, shaved-headed man, blunt and loyal.",
        }
        snapshots = []

        probe.run_sample(
            url,
            sample,
            rounds=2,
            on_step=lambda partial: snapshots.append(json.loads(json.dumps(partial))),
        )

    # 1 (extract) + 2 rounds * 3 (prose, check, reextract) + 1 (final
    # trailing re-extract-only round) = 8 calls
    assert len(snapshots) == 8
    assert [len(s["rounds"]) for s in snapshots] == [0, 0, 0, 1, 1, 1, 2, 3]


def test_think_block_stripped():
    with _stub_server({"JSON list": "<think>reasoning here</think>[1, 2]"}) as url:
        reply = probe.chat(url, "Extract facts as a JSON list.", "some text")

    assert "<think>" not in reply
    assert reply == "[1, 2]"
