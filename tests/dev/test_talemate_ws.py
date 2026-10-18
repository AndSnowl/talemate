"""Unit tests for the websocket driver (scripts/dev/talemate_ws.py).

No real backend and no network: each test starts a local
``websockets.sync.server`` stub on a free 127.0.0.1 port, in a thread. The
stub answers each message it receives with scripted replies, picked by the
message's ``type``/``action``, and records what it received.
"""

import importlib.util
import json
import sys
import threading
from pathlib import Path

import pytest
from websockets.sync.server import serve

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "talemate_ws", _REPO_ROOT / "scripts" / "dev" / "talemate_ws.py"
)
talemate_ws = importlib.util.module_from_spec(_spec)
sys.modules["talemate_ws"] = talemate_ws
_spec.loader.exec_module(talemate_ws)

BackendSession = talemate_ws.BackendSession
BackendError = talemate_ws.BackendError


class Stub:
    """A scripted backend: ``replies[(type, action)]`` (or ``[type]``) -> messages."""

    def __init__(self, replies=None, on_connect=()):
        self.replies = replies or {}
        self.on_connect = list(on_connect)
        self.received: list[dict] = []

    def handler(self, websocket):
        for message in self.on_connect:
            websocket.send(json.dumps(message))
        for raw in websocket:
            data = json.loads(raw)
            self.received.append(data)
            key = (data.get("type"), data.get("action"))
            for reply in self.replies.get(key, self.replies.get(data.get("type"), [])):
                websocket.send(json.dumps(reply))


@pytest.fixture
def stub_server():
    servers = []

    def start(stub: Stub) -> str:
        server = serve(stub.handler, "127.0.0.1", 0)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.socket.getsockname()[1]
        return f"ws://127.0.0.1:{port}/ws"

    yield start
    for server in servers:
        server.shutdown()


def _prompt(agent_type, response, action="act"):
    return {
        "type": "prompt_sent",
        "data": {
            "kind": "create",
            "prompt": "...",
            "response": response,
            "agent_type": agent_type,
            "agent_action": action,
        },
    }


def test_load_scene_waits_for_loaded(stub_server, tmp_path):
    stub = Stub(
        replies={
            "load_scene": [
                {"type": "system", "id": "scene.loading", "status": "loading"},
                {"type": "ping"},
                {"type": "scene_status", "name": "x", "status": "started"},
                {"type": "system", "id": "scene.loaded", "status": "success"},
            ]
        }
    )
    url = stub_server(stub)
    scene = tmp_path / "scene.json"
    with BackendSession(url) as session:
        session.load_scene(scene, timeout=5)
        assert session.messages[-1]["id"] == "scene.loaded"
    assert stub.received == [{"type": "load_scene", "file_path": str(scene)}]


def test_load_scene_raises_on_failure(stub_server, tmp_path):
    stub = Stub(
        replies={
            "load_scene": [
                {"type": "status", "status": "error", "message": "no such file"},
                {"type": "system", "id": "scene.load_failure"},
            ]
        }
    )
    with BackendSession(stub_server(stub)) as session:
        with pytest.raises(BackendError, match="no such file"):
            session.load_scene(tmp_path / "missing.json", timeout=5)


def test_persist_character_raises_on_error(stub_server):
    stub = Stub(
        replies={
            ("director", "persist_character"): [
                {
                    "type": "director",
                    "action": "operation_done",
                    "error": {"message": "Error persisting character: boom"},
                }
            ]
        }
    )
    with BackendSession(stub_server(stub)) as session:
        with pytest.raises(RuntimeError, match="boom"):
            session.persist_character("the ferryman", "A gruff old man.", timeout=5)
    assert stub.received == [
        {
            "type": "director",
            "action": "persist_character",
            "name": "the ferryman",
            "content": "A gruff old man.",
            "narrate_entry": False,
        }
    ]


def test_persist_character_waits_for_persisted(stub_server):
    stub = Stub(
        replies={
            ("director", "persist_character"): [
                {"type": "director", "action": "operation_done", "data": {}},
                {"type": "director", "action": "character_persisted"},
            ]
        }
    )
    with BackendSession(stub_server(stub)) as session:
        session.persist_character("the fishwife", active=False, timeout=5)
        assert session.messages[-1]["action"] == "character_persisted"
    assert stub.received[0]["active"] is False


def test_narrate_returns_the_narration(stub_server):
    stub = Stub(
        replies={
            ("narrator", "progress"): [
                {"type": "status", "status": "busy", "message": "Progressing"},
                {"type": "narrator", "message": "The river rose.", "id": 3},
            ]
        }
    )
    with BackendSession(stub_server(stub)) as session:
        assert session.narrate("progress", "rain", timeout=5) == "The river rose."
    assert stub.received == [
        {"type": "narrator", "action": "progress", "narrative_direction": "rain"}
    ]


def test_narrate_raises_on_error_envelope(stub_server):
    stub = Stub(
        replies={
            ("narrator", "narrate_environment"): [
                {
                    "type": "narrator",
                    "action": "operation_done",
                    "error": {"message": "client down"},
                }
            ]
        }
    )
    with BackendSession(stub_server(stub)) as session:
        with pytest.raises(BackendError, match="client down"):
            session.narrate(timeout=5)


def test_generation_error_is_cancelled_and_raised(stub_server):
    stub = Stub(
        replies={
            ("narrator", "narrate_environment"): [
                _prompt("narrator", "half a sentence"),
                {
                    "type": "generation_error",
                    "message": "502 Bad Gateway",
                    "data": {"request_id": "r1", "error_message": "502 Bad Gateway"},
                },
            ],
            "generation_error_response": [{"type": "ack"}],
        }
    )
    with BackendSession(stub_server(stub)) as session:
        with pytest.raises(BackendError, match="502 Bad Gateway") as excinfo:
            session.narrate(timeout=5)
        # the last model output is part of the report
        assert "half a sentence" in str(excinfo.value)
        session.wait_for(lambda m: m["type"] == "ack", timeout=5)
    assert stub.received[1] == {
        "type": "generation_error_response",
        "request_id": "r1",
        "action": "cancel",
    }


def test_request_snapshot_returns_processed_data(stub_server):
    processed = {"place": "Veldhaer", "new_places": [], "new_names": []}
    stub = Stub(
        replies={
            ("world_state_agent", "request_update"): [
                {"type": "world_state_agent", "action": "operation_done", "data": {}},
                {"type": "cultures", "action": "world", "data": {"available": True}},
                {"type": "cultures", "action": "snapshot_processed", "data": processed},
            ]
        }
    )
    with BackendSession(stub_server(stub)) as session:
        assert session.request_snapshot(timeout=5) == processed
        assert session.events("snapshot_processed") == [processed]
        assert session.events("snapshot_processed", start=len(session.messages)) == []
    assert stub.received == [{"type": "world_state_agent", "action": "request_update"}]


def test_get_world_returns_world_data(stub_server):
    world = {"available": True, "cultures": [], "glossary": []}
    stub = Stub(
        replies={
            ("cultures", "get_world"): [
                {"type": "cultures", "action": "world", "data": world}
            ]
        }
    )
    with BackendSession(stub_server(stub)) as session:
        assert session.get_world(timeout=5) == world


def test_wait_for_timeout_names_last_types(stub_server):
    stub = Stub(
        on_connect=[
            {"type": "client_status", "status": "idle"},
            {"type": "ping"},
            {"type": "cultures", "action": "context_injected", "data": {}},
            {"type": "status", "status": "idle"},
        ]
    )
    with BackendSession(stub_server(stub)) as session:
        session.wait_for(lambda m: m["type"] == "status", timeout=5)
        with pytest.raises(TimeoutError) as excinfo:
            session.wait_for(lambda m: False, timeout=0.3)
    text = str(excinfo.value)
    assert "client_status" in text
    assert "cultures:context_injected" in text
    assert "status" in text


def test_type_error_message_raises(stub_server):
    stub = Stub(
        replies={
            ("cultures", "get_world"): [
                {"type": "error", "plugin": "cultures", "error": "kaput"}
            ]
        }
    )
    with BackendSession(stub_server(stub)) as session:
        with pytest.raises(BackendError, match="kaput"):
            session.get_world(timeout=5)


def test_prompts_filter_by_agent(stub_server):
    stub = Stub(
        on_connect=[
            _prompt("narrator", "It rains."),
            _prompt("culture", "Kethra", action="pick_name"),
            {"type": "ping"},
            _prompt("culture", "Veldhaer: town", action="places"),
            {"type": "status", "status": "idle", "message": "done"},
        ]
    )
    with BackendSession(stub_server(stub)) as session:
        session.wait_for(lambda m: m["type"] == "status", timeout=5)
        culture = session.prompts("culture")
        assert [p["response"] for p in culture] == ["Kethra", "Veldhaer: town"]
        assert len(session.prompts()) == 3
        # `start` is an index into `messages`
        assert [p["response"] for p in session.prompts("culture", start=2)] == [
            "Veldhaer: town"
        ]
        assert session.last_output() == "Veldhaer: town"
