"""Unit tests for the world probes (scripts/dev/probe_world_create.py,
scripts/dev/probe_scene_setup.py).

No real network: a local stub HTTP server answers ``/api/v1/model`` and
``/v1/chat/completions``, the latter with a canned reply chosen by a
keyword found in either the system or the user message, same pattern as
``tests/dev/test_probe_fact_roundtrip.py``. ``TALEMATE_AI_TESTS`` is set
only in the tests that need ``main()`` to actually run, and always points
at this stub.
"""

import importlib.util
import json
import sys
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, _REPO_ROOT / "scripts" / "dev" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


create_probe = _load("probe_world_create")
setup_probe = _load("probe_scene_setup")


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


# --- probe_world_create.py ---------------------------------------------------

_CREATE_FACTS_REPLY = json.dumps(
    [
        {"category": "background", "text": "has ferried travelers for thirty years"},
        {"category": "personality", "text": "owes the Wardens a debt he won't discuss"},
    ]
)
_CREATE_PROSE_REPLY = "A grizzled ferryman who owes the Wardens more than he'll say."
_CREATE_INTENT_REPLY = json.dumps(
    {
        "kept_intent": [
            {"phrase": "grizzled ferryman", "kept": True},
            {"phrase": "owes the Wardens more than money", "kept": True},
        ],
        "invented": ["has ferried travelers for thirty years"],
    }
)

_CREATE_REPLIES = {
    "You create a new": _CREATE_FACTS_REPLY,
    "You write a short passage of prose": _CREATE_PROSE_REPLY,
    "kept_intent": _CREATE_INTENT_REPLY,
}


def test_create_probe_refuses_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv("TALEMATE_AI_TESTS", raising=False)
    out_dir = tmp_path / "out"

    code = create_probe.main(["--out", str(out_dir)])

    assert code == 2
    assert not out_dir.exists()


def test_create_probe_against_stub(tmp_path, monkeypatch):
    with _stub_server(_CREATE_REPLIES) as url:
        monkeypatch.setenv("TALEMATE_AI_TESTS", "1")
        monkeypatch.setenv("TALEMATE_TEST_KOBOLDCPP_URL", url)

        prompts_path = tmp_path / "prompts.json"
        prompts_path.write_text(
            json.dumps(
                {
                    "create_prompts": [
                        {
                            "kind": "character",
                            "prompt": "a grizzled ferryman who owes the Wardens more than money",
                        }
                    ]
                }
            )
        )
        out_dir = tmp_path / "out"

        code = create_probe.main(
            ["--prompts", str(prompts_path), "--out", str(out_dir)]
        )

    assert code == 0
    report = json.loads((out_dir / "report.json").read_text())
    assert report["errors"] == []

    (prompt_result,) = report["prompts"]
    assert prompt_result["kind"] == "character"
    assert prompt_result["facts"] == json.loads(_CREATE_FACTS_REPLY)
    assert prompt_result["prose"] == _CREATE_PROSE_REPLY
    assert prompt_result["invented"] == 1
    assert (
        prompt_result["kept_intent"] == json.loads(_CREATE_INTENT_REPLY)["kept_intent"]
    )

    report_md = (out_dir / "report.md").read_text()
    assert "grizzled ferryman" in report_md


def test_run_prompt_errors_on_unparsable_create_reply():
    with _stub_server({"You create a new": "sorry, I can't help with that"}) as url:
        result = create_probe.run_prompt(
            url, {"kind": "character", "prompt": "a grizzled ferryman"}
        )

    assert result["facts"] is None
    assert len(result["errors"]) == 1
    assert result["errors"][0]["step"] == "create"


# --- probe_scene_setup.py -----------------------------------------------------

_TINY_WORLD = {
    "characters": [
        {"name": "Senna Dreck", "summary": "a riverside smuggler."},
        {"name": "Corlas Wick", "summary": "a retired Warden captain."},
    ],
    "places": [{"name": "Mire's Landing", "summary": "a half-flooded lock-town."}],
    "lore": [{"name": "The Warden's Tithe", "summary": "a debt law."}],
}

_SETUP_WORLD_USE_REPLY = json.dumps(
    {
        "player": "a river trader new to the lock-town",
        "characters": [
            {"name": "Senna Dreck", "world": True},
            {"name": "a nosy toll clerk", "world": False},
        ],
        "place": {"name": "Mire's Landing", "world": True},
        "goal": "get the crate past the dawn patrol",
        "intro": "The locks groan open as the fog lifts over Mire's Landing.",
    }
)

_SETUP_REPLIES = {"player": _SETUP_WORLD_USE_REPLY}


def test_setup_probe_against_stub(tmp_path, monkeypatch):
    with _stub_server(_SETUP_REPLIES) as url:
        monkeypatch.setenv("TALEMATE_AI_TESTS", "1")
        monkeypatch.setenv("TALEMATE_TEST_KOBOLDCPP_URL", url)

        prompts_path = tmp_path / "prompts.json"
        prompts_path.write_text(
            json.dumps(
                {
                    "scene_prompts": [
                        "Senna Dreck needs to smuggle a crate through Mire's Landing."
                    ],
                    "tiny_world": _TINY_WORLD,
                }
            )
        )
        out_dir = tmp_path / "out"

        code = setup_probe.main(["--prompts", str(prompts_path), "--out", str(out_dir)])

    assert code == 0
    report = json.loads((out_dir / "report.json").read_text())
    assert report["errors"] == []

    (prompt_result,) = report["prompts"]
    scene = prompt_result["scene"]
    assert scene["player"] == "a river trader new to the lock-town"
    assert scene["goal"] == "get the crate past the dawn patrol"
    assert scene["intro"]

    report_md = (out_dir / "report.md").read_text()
    assert "Mire's Landing" in report_md


def test_setup_probe_records_world_use():
    with _stub_server(_SETUP_REPLIES) as url:
        result = setup_probe.run_prompt(
            url,
            "Senna Dreck needs to smuggle a crate through Mire's Landing.",
            _TINY_WORLD,
        )

    assert result["errors"] == []
    assert "Senna Dreck" in result["world_used"]
    assert "Mire's Landing" in result["world_used"]
    assert "a nosy toll clerk" in result["invented"]


def test_setup_probe_refuses_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv("TALEMATE_AI_TESTS", raising=False)
    out_dir = tmp_path / "out"

    code = setup_probe.main(["--out", str(out_dir)])

    assert code == 2
    assert not out_dir.exists()
