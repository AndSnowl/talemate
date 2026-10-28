"""Seed a running isolated app's root with scenes and world data, for e2e tests.

The scene and shared-context files are built by Talemate's own classes
(``Scene.save``, ``SharedContext.write_to_file``, ``apply_import``), in a
subprocess that runs the *copy's* code (``backend_env(root)``, cwd = root),
so the files match exactly what the running app reads and writes.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_PREFIX = "SEED_RESULT "
SCENE_TITLE_TIMEOUT_MS = 60_000


# Same import-by-path as conftest._load_script, duplicated because conftest
# imports this module (importing conftest from here would be circular).
def _load_talemate_app():
    if "talemate_app" in sys.modules:
        return sys.modules["talemate_app"]
    spec = importlib.util.spec_from_file_location(
        "talemate_app", _REPO_ROOT / "scripts" / "dev" / "talemate_app.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["talemate_app"] = module
    spec.loader.exec_module(module)
    return module


@dataclasses.dataclass
class SeededWorld:
    scene_path: Path
    shared_context_path: Path


# Runs inside the copy (PYTHONPATH=<root>/src). argv[1] is a JSON spec; the
# last stdout line is RESULT_PREFIX + JSON.
_SCENE_SCRIPT = """
import asyncio, json, sys
from pathlib import Path

import talemate.instance as instance
from talemate.character import Character
from talemate.scene_message import CharacterMessage, NarratorMessage
from talemate.shared_context import SharedContext
from talemate.tale_mate import Scene
from talemate.world_state import WorldState


async def main(spec):
    scene = Scene()
    scene.name = spec["title"]
    scene.title = spec["title"]
    scene.project_name = spec["project"]
    scene.filename = spec["project"] + ".json"
    scene.intro = spec.get("intro") or ""

    player_names = {
        item["name"] for item in spec.get("characters") or [] if item.get("is_player")
    }
    for message in spec.get("messages") or []:
        speaker = message.get("character")
        if speaker:
            scene.history.append(
                CharacterMessage(
                    message=CharacterMessage.with_name_prefix(speaker, message["text"]),
                    source="player" if speaker in player_names else "ai",
                )
            )
        else:
            scene.history.append(NarratorMessage(message=message["text"]))

    ws = dict(spec.get("world_state") or {})
    ws.setdefault("anchor_message_ids", [m.id for m in scene.history])
    if spec.get("location") is not None:
        ws.setdefault("location", spec["location"])
    scene.world_state = WorldState(**ws)

    # Inline, rather than tests._director_test_helpers.add_character_to_scene:
    # that module isn't importable here (this script runs under the
    # isolated copy's own PYTHONPATH, which has no tests/ on it).
    # `Scene.add_actor` always looks up the memory agent (even when
    # `commit_to_memory=False` it only skips *using* it), and a config save
    # right after also probes every registered agent's status, so a
    # placeholder with just enough surface is registered in this bare
    # subprocess, which never starts the real agent manager.
    if any(item.get("active", True) for item in spec.get("characters") or []):
        class _PlaceholderMemoryAgent:
            async def emit_status(self):
                return None

        instance.AGENTS.setdefault("memory", _PlaceholderMemoryAgent())

    for item in spec.get("characters") or []:
        character = Character(
            name=item["name"],
            description=item.get("description", ""),
            base_attributes={},
            details={},
            color="#fff",
            shared=item.get("shared", False),
            is_player=item.get("is_player", False),
        )
        if item.get("active", True):
            actor_cls = scene.Player if character.is_player else scene.Actor
            actor = actor_cls(character, None)
            await scene.add_actor(actor, commit_to_memory=False)
            if character.name not in scene.active_characters:
                scene.active_characters.append(character.name)
        else:
            scene.character_data[character.name] = character

    result = {}
    if spec["context"]:
        shared_dir = Path(scene.shared_context_dir)
        shared_dir.mkdir(parents=True, exist_ok=True)
        shared = SharedContext(filepath=shared_dir / (spec["context"] + ".json"))
        await shared.init_from_scene(scene, write=True)
        scene.shared_context = shared
        result["shared_context_path"] = str(shared.filepath)
    await scene.save(force=True)
    result["scene_path"] = scene.full_path
    print(RESULT_PREFIX + json.dumps(result))


asyncio.run(main(json.loads(sys.argv[1])))
"""

_WORKER_SRC = r"""
import contextlib, io, json, sys, traceback
for line in sys.stdin:
    req = json.loads(line)
    buf = io.StringIO()
    ok = True
    try:
        sys.argv = ["-c", req["spec"]]
        # A fresh process started message ids at 1; keep that per seed.
        if "talemate.scene_message" in sys.modules:
            sys.modules["talemate.scene_message"].reset_message_id()
        with contextlib.redirect_stdout(buf):
            exec(compile(req["script"], "<seed>", "exec"), {"__name__": "__seed__", "RESULT_PREFIX": req["prefix"]})
    except BaseException:
        ok = False
        buf.write(traceback.format_exc())
    sys.__stdout__.write(json.dumps({"ok": ok, "out": buf.getvalue()}) + "\n")
    sys.__stdout__.flush()
"""

_WORKERS: dict = {}


def _worker(root: Path):
    key = str(Path(root).resolve())
    proc = _WORKERS.get(key)
    if proc is None or proc.poll() is not None:
        env = _load_talemate_app().backend_env(Path(root))
        proc = subprocess.Popen(
            [sys.executable, "-c", _WORKER_SRC],
            cwd=root,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        _WORKERS[key] = proc
    return proc


def _run_in_copy(root: Path, script: str, spec: dict) -> dict:
    """Run ``script`` with the copy's code in ``root``; return its result JSON."""
    root = Path(root)
    proc = _worker(root)
    proc.stdin.write(
        json.dumps(
            {"script": script, "spec": json.dumps(spec), "prefix": RESULT_PREFIX}
        )
        + "\n"
    )
    proc.stdin.flush()
    reply = json.loads(proc.stdout.readline())
    lines = [ln for ln in reply["out"].splitlines() if ln.startswith(RESULT_PREFIX)]
    if not reply["ok"] or not lines:
        raise RuntimeError(f"seeding in {root} failed:\n{reply['out']}")
    return json.loads(lines[-1][len(RESULT_PREFIX) :])


def seed_world(
    root: Path,
    project: str = "e2e-world",
    context: str = "world",
    *,
    intro: str = "",
    location: str | None = None,
    messages: list[dict] = (),
    characters: list[dict] = (),
    world_state: dict | None = None,
) -> SeededWorld:
    """Create a minimal scene in ``<root>/scenes/<project>/`` linked to a Shared World.

    ``messages`` items are ``{"text": str, "character": str|None}``, appended
    to the scene's history as a ``CharacterMessage`` (``"Name: text"``) when
    ``character`` is given, else as a ``NarratorMessage``. ``characters``
    items are ``{"name", "description"="", "active": bool=True,
    "shared": bool=False, "is_player": bool=False}``: active ones
    are added via a real ``Actor`` (``Player`` when ``is_player``,
    ``commit_to_memory=False``), inactive ones go only into
    ``scene.character_data``.

    ``world_state`` is passed straight to ``WorldState(**world_state)`` (so
    it can carry ``characters``, ``places``, etc.), with
    ``anchor_message_ids`` defaulted to every seeded message's id when the
    dict doesn't already set it.
    """
    result = _run_in_copy(
        root,
        _SCENE_SCRIPT,
        {
            "project": project,
            "title": project,
            "context": context,
            "intro": intro,
            "location": location,
            "messages": list(messages),
            "characters": list(characters),
            "world_state": world_state,
        },
    )
    return SeededWorld(
        scene_path=Path(result["scene_path"]),
        shared_context_path=Path(result["shared_context_path"]),
    )


def seed_scene_without_world(
    root: Path,
    project: str = "e2e-plain",
    *,
    messages: list[dict] = (),
    world_state: dict | None = None,
) -> Path:
    """Create a minimal scene in ``<root>/scenes/<project>/`` with no shared context."""
    result = _run_in_copy(
        root,
        _SCENE_SCRIPT,
        {
            "project": project,
            "title": project,
            "context": None,
            "messages": list(messages),
            "world_state": world_state,
        },
    )
    return Path(result["scene_path"])


# Runs inside the copy: a fantasymate world (`talemate.world`) in the copy's
# WORLDS_DIR, the folder the running app's `worlds` router lists.
_FM_WORLD_SCRIPT = """
import json, re, sys

from talemate.path import WORLDS_DIR
from talemate.world.dates import WorldDate
from talemate.world.store import Source, World


def _year(value):
    return WorldDate.of(value) if value is not None else None


def _dumped(value):
    return WorldDate.of(value).model_dump(mode="json") if value is not None else None


def _refs(text, ids):
    # "[[@Name|shown]]" links an earlier thing by name, keeping "shown"
    return re.sub(
        r"\\[\\[@([^|\\]]+)\\|([^\\]]+)\\]\\]",
        lambda m: "[[thing:" + ids[m.group(1)] + "|" + m.group(2) + "]]",
        text,
    )


spec = json.loads(sys.argv[1])
world = World.create(spec["name"], root=WORLDS_DIR)
try:
    world.set_present(WorldDate.of(spec["present_year"]))
    ids = {}
    # a fact's text as written in the spec -> its fact id
    fact_ids = {}
    with world.revision(Source.manual(note="e2e seed")) as rev:
        for thing in spec["things"]:
            fields = {"name": thing["name"], **(thing.get("fields") or {})}
            if thing.get("born") is not None:
                fields["born"] = WorldDate.of(thing["born"])
            if thing.get("stub") is not None:
                fields["stub"] = {"ignored": thing["stub"] == "ignored"}
            # a link names an earlier thing (or a list of them)
            for field, names in (thing.get("links") or {}).items():
                fields[field] = (
                    [ids[name] for name in names]
                    if isinstance(names, list)
                    else ids[names]
                )
            # the entries it's filed in: earlier things, by name
            if thing.get("filings"):
                fields["filings"] = [
                    {
                        "target": ids[filing["target"]],
                        "role": filing.get("role"),
                        "since": _dumped(filing.get("since")),
                        "until": _dumped(filing.get("until")),
                        "within": ids[filing["within"]]
                        if filing.get("within")
                        else None,
                        "exceptions": [],
                        "show_under": filing.get("show_under"),
                    }
                    for filing in thing["filings"]
                ]
            thing_id = rev.create_thing(thing["kind"], fields)
            ids[thing["name"]] = thing_id
            for fact in thing.get("facts") or []:
                fact_ids[fact["text"]] = rev.add_fact(
                    thing_id,
                    fact["category"],
                    _refs(fact["text"], ids),
                    valid_from=_year(fact.get("since")),
                    valid_until=_year(fact.get("until")),
                    # an exception's tie names its entry, an earlier thing
                    origin=(
                        {**fact["origin"], "tie": ids[fact["origin"]["tie"]]}
                        if "tie" in (fact.get("origin") or {})
                        else fact.get("origin")
                    ),
                )
    for scene in spec["scenes"]:
        world.scenes().create(
            scene["name"],
            WorldDate.of(scene["start"]),
            premise=scene.get("premise", ""),
            player_thing_id=ids.get(scene.get("player")),
        )
    result = {"id": world.id, "path": str(world.path), "things": ids, "facts": fact_ids}
finally:
    world.close()
print(RESULT_PREFIX + json.dumps(result))
"""


@dataclasses.dataclass
class SeededFmWorld:
    id: str
    path: Path
    # thing name -> thing id
    things: dict[str, str]
    # a fact's text, as the spec wrote it -> its fact id
    facts: dict[str, str] = dataclasses.field(default_factory=dict)


def seed_fm_world(
    root: Path,
    name: str,
    *,
    present_year: int = 1000,
    things: list[dict] = (),
    scenes: list[dict] = (),
) -> SeededFmWorld:
    """Create a fantasymate world (`talemate.world.World`) in the app's worlds folder.

    ``things`` items are ``{"kind", "name", "born": year|None, "fields":
    {field: value}|None, "links": {field: name | [names]}|None, "stub":
    "live"|"ignored"|None, "filings": [{"target": name, "role", "since":
    year|None, "until": year|None, "within": name|None}]|None, "facts":
    [{"category", "text", "since": year|None, "until": year|None,
    "origin": dict|None}]}``, written in one revision, in order. An
    origin's ``"tie"`` (an exception's) names the entry it's filed under,
    written as its id.
    A link names things listed before it (e.g. a race's ``{"species":
    "Owl-folk"}``) and is written as their ids; so does a reference in a
    fact's text, written ``[[@Name|shown text]]``. ``stub`` makes the thing
    a stub (ignored or not). ``scenes`` items are ``{"name", "start": year,
    "premise"="", "player": thing name|None}``, created in the world's
    scene store (with no messages).
    """
    result = _run_in_copy(
        root,
        _FM_WORLD_SCRIPT,
        {
            "name": name,
            "present_year": present_year,
            "things": list(things),
            "scenes": list(scenes),
        },
    )
    return SeededFmWorld(
        id=result["id"],
        path=Path(result["path"]),
        things=result["things"],
        facts=result.get("facts", {}),
    )


# The app's `worlds` router answers `preview_thing` from this file (in the
# app root) instead of asking a model; the `app` fixture points the
# backend's TALEMATE_TEST_FIXED_PREVIEW at it.
FIXED_PREVIEW_FILE = "e2e-fixed-preview.json"


def set_fixed_preview(root: Path, preview: dict) -> None:
    """Make the app's next `preview_thing` replies ``preview``: ``{"name",
    "facts": [{"category", "text", "since"?}], "prose": {section: text},
    "fields"?}`` (the request's kind, prompt and fields fill the rest)."""
    (Path(root) / FIXED_PREVIEW_FILE).write_text(json.dumps(preview))


# The app's `worlds` router answers "+ Add facts…"/"+ Add event…"
# (`add_facts`, `add_event`), a group's "✎ Synopsis" (`group_synopsis`) and
# a group's "+ Add" (`group_add`) from these files (in the app root), read
# through the real parsers as the model's reply; the `app` fixture points
# the backend's TALEMATE_TEST_FIXED_FACTS, TALEMATE_TEST_FIXED_GROUP_SYNOPSIS
# and TALEMATE_TEST_FIXED_GROUP_ADD at them.
FIXED_FACTS_FILE = "e2e-fixed-facts.json"
FIXED_GROUP_SYNOPSIS_FILE = "e2e-fixed-group-synopsis.json"
FIXED_GROUP_ADD_FILE = "e2e-fixed-group-add.json"
# language naming (definitions and picks, languages 3a)
FIXED_LANGUAGE_FILE = "e2e-fixed-language.json"


def set_fixed_reply(root: Path, file_name: str, reply: dict) -> None:
    """Make the app's next replies of that kind ``reply``, the model's
    reply: ``{"facts": [{"category", "text"}]}`` for facts and events,
    ``{"synopsis": text}`` for a synopsis, ``{"entries": [{"name", "kind",
    "tag", "line"}]}`` for a group's "+ Add"."""
    (Path(root) / file_name).write_text(json.dumps(reply))


# The app's `worlds` router answers `plan_scene` and `continue_scene` from
# this file (in the app root) instead of asking a model; the `app` fixture
# points the backend's TALEMATE_TEST_FIXED_SETUP at it.
FIXED_SETUP_FILE = "e2e-fixed-setup.json"


def set_fixed_setup(root: Path, reply: dict) -> None:
    """Make the app's next scene setups come from ``reply``, a scene-setup
    model reply: ``{"player", "characters": [name | {"name", "facts"}],
    "place": name | {"name", "facts"}, "goal", "intro", "extras"?}``. Its
    names are resolved against the world as a model's would be."""
    (Path(root) / FIXED_SETUP_FILE).write_text(json.dumps(reply))


# Installed by the ``page`` fixture (context.add_init_script) before the app's
# code runs: records every WebSocket the page opens, so ``open_scene`` can
# send on the app's own backend connection (the scene is per connection).
SOCKET_HOOK_JS = """
(() => {
    const Native = window.WebSocket;
    const sockets = [];
    window.__e2eSockets = sockets;
    window.WebSocket = class extends Native {
        constructor(...args) {
            super(...args);
            sockets.push(this);
        }
    };
})();
"""

# The app's backend socket: open, and not vite's HMR socket.
_BACKEND_SOCKET_JS = """
() => (window.__e2eSockets || []).filter(
    (s) => s.readyState === WebSocket.OPEN && s.protocol !== "vite-hmr"
).pop()
"""


def dismiss_onboarding(page, timeout_ms: float = 60_000) -> None:
    """Close the first-run "Welcome to fantasymate" wizard, if it opens.

    The app opens it when its config has no AI client (a run started
    without ``--ai``), and remembers a dismissal only per page. With a
    client configured it never opens. The app bar alone can't tell those
    apart (it shows before the config arrives), so wait for whichever comes
    first: the wizard's Skip button, or a configured client listed in the
    Clients drawer (``data-testid="ai-client"``), which means the config has
    a client and the wizard won't open.
    """
    skip = page.get_by_role("button", name="Skip setup for now")
    client = page.get_by_test_id("ai-client")
    skip.or_(client).first.wait_for(state="visible", timeout=timeout_ms)
    if skip.is_visible():
        skip.click()
        skip.wait_for(state="hidden", timeout=10_000)


def open_scene(page, scene_path: Path) -> None:
    """Load ``scene_path`` in the UI the way Load Scene does, wait for its title.

    Sends ``{"type": "load_scene", "file_path": ...}`` on the app's websocket
    (what ``SceneLanding.vue`` sends) and waits until the scene's title shows
    as the app bar's scene tab. Needs a page from the ``page`` fixture, which
    installs ``SOCKET_HOOK_JS``.
    """
    scene_path = Path(scene_path)
    data = json.loads(scene_path.read_text())
    title = data.get("title") or data.get("name")
    if page.evaluate("() => window.__e2eSockets === undefined"):
        raise RuntimeError("open_scene needs a page with seed.SOCKET_HOOK_JS installed")
    page.wait_for_function(f"!!({_BACKEND_SOCKET_JS})()", timeout=60_000)
    page.evaluate(
        f"(path) => ({_BACKEND_SOCKET_JS})().send("
        "JSON.stringify({type: 'load_scene', file_path: path}))",
        str(scene_path),
    )
    page.locator("header.v-app-bar .v-tab", has_text=title).wait_for(
        state="visible", timeout=SCENE_TITLE_TIMEOUT_MS
    )


def send_backend(page, payload: dict) -> None:
    """Send ``payload`` on the page's backend socket, the way the app itself does.

    Needs a page with a scene already open (``open_scene``), on the same
    backend connection the app's own UI sends on.
    """
    page.wait_for_function(f"!!({_BACKEND_SOCKET_JS})()", timeout=60_000)
    page.evaluate(
        f"(data) => ({_BACKEND_SOCKET_JS})().send(JSON.stringify(data))",
        payload,
    )
