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
from datetime import date
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
    world_dir: Path


# Runs inside the copy (PYTHONPATH=<root>/src). argv[1] is a JSON spec; the
# last stdout line is RESULT_PREFIX + JSON.
_SCENE_SCRIPT = """
import asyncio, json, sys
from pathlib import Path

from talemate.cultures.store import world_dir_for
from talemate.shared_context import SharedContext
from talemate.tale_mate import Scene


async def main(spec):
    scene = Scene()
    scene.name = spec["title"]
    scene.title = spec["title"]
    scene.project_name = spec["project"]
    scene.filename = spec["project"] + ".json"
    result = {}
    if spec["context"]:
        shared_dir = Path(scene.shared_context_dir)
        shared_dir.mkdir(parents=True, exist_ok=True)
        shared = SharedContext(filepath=shared_dir / (spec["context"] + ".json"))
        await shared.init_from_scene(scene, write=True)
        scene.shared_context = shared
        result["shared_context_path"] = str(shared.filepath)
        result["world_dir"] = str(world_dir_for(shared.filepath))
    await scene.save(force=True)
    result["scene_path"] = scene.full_path
    print(RESULT_PREFIX + json.dumps(result))


asyncio.run(main(json.loads(sys.argv[1])))
"""

_CULTURE_SCRIPT = """
import json, sys
from pathlib import Path

from talemate.cultures.exchange import apply_import
from talemate.cultures.store import WorldStore

spec = json.loads(sys.argv[1])
culture = apply_import(
    WorldStore(Path(spec["world_dir"])),
    Path(spec["culture_file"]).read_text(encoding="utf-8"),
    spec["today"],
)
print(RESULT_PREFIX + json.dumps({"id": culture.id}))
"""


def _run_in_copy(root: Path, script: str, spec: dict) -> dict:
    """Run ``script`` with the copy's code in ``root``; return its result JSON."""
    root = Path(root)
    env = _load_talemate_app().backend_env(root)
    proc = subprocess.run(
        [sys.executable, "-c", f"RESULT_PREFIX = {RESULT_PREFIX!r}\n{script}"]
        + [json.dumps(spec)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith(RESULT_PREFIX)]
    if proc.returncode != 0 or not lines:
        raise RuntimeError(
            f"seeding in {root} failed (exit {proc.returncode}):\n"
            f"--- stdout:\n{proc.stdout}\n--- stderr:\n{proc.stderr}"
        )
    return json.loads(lines[-1][len(RESULT_PREFIX) :])


def _root_from_world(world_dir: Path) -> Path:
    # <root>/scenes/<project>/shared-context/<name>.world
    return world_dir.parents[3]


def seed_world(
    root: Path, project: str = "e2e-world", context: str = "world"
) -> SeededWorld:
    """Create a minimal scene in ``<root>/scenes/<project>/`` linked to a Shared World."""
    result = _run_in_copy(
        root, _SCENE_SCRIPT, {"project": project, "title": project, "context": context}
    )
    return SeededWorld(
        scene_path=Path(result["scene_path"]),
        shared_context_path=Path(result["shared_context_path"]),
        world_dir=Path(result["world_dir"]),
    )


def seed_scene_without_world(root: Path, project: str = "e2e-plain") -> Path:
    """Create a minimal scene in ``<root>/scenes/<project>/`` with no shared context."""
    result = _run_in_copy(
        root, _SCENE_SCRIPT, {"project": project, "title": project, "context": None}
    )
    return Path(result["scene_path"])


def place_culture(world: SeededWorld, culture_file: Path) -> None:
    """Import ``culture_file`` into the world's folder, as World Editor's import does."""
    _run_in_copy(
        _root_from_world(world.world_dir),
        _CULTURE_SCRIPT,
        {
            "world_dir": str(world.world_dir),
            "culture_file": str(Path(culture_file).resolve()),
            "today": date.today().isoformat(),
        },
    )


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
    """Close the first-run "Welcome to Talemate" wizard, if it opens.

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
