"""Drive a running local Talemate backend over its websocket, without a browser.

For AI tests and evaluation scripts: load a scene, create characters,
trigger narration, and read the results, the same way the frontend does. Start the backend with
``scripts/dev/talemate_app.py`` and pass its ``AppInfo.backend_ws_url``::

    with BackendSession(info.backend_ws_url) as session:
        session.wait_client_ready()
        session.load_scene(world.scene_path)
        session.persist_character("the ferryman", "A gruff old man.")
        print(session.last_output("creator"))

The backend accepts one frontend connection at a time, so don't open the
app in a browser while a session is connected (the second connection is
told so and closed; this driver raises ``BackendError`` for it).

Every wait reads real messages (never a fixed sleep) and has a timeout. A
``TimeoutError`` names the last message types seen and the model's last
output. Backend failures raise ``BackendError`` (a ``RuntimeError``):

- ``{"type": "error"}`` (an exception in a websocket route);
- a ``generation_error`` (the client failed and the backend asks what to
  do): the driver answers ``cancel`` so the backend doesn't hang, then
  raises;
- the per-call failure replies (``scene.load_failure``, an
  ``operation_done`` carrying an ``error``).

Every received message is kept in ``messages``, in order; ``prompts()`` and
``last_output()`` read from it. ``mark()`` returns the current position, to read
only what a later call produced.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Literal

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

__all__ = ["BackendError", "BackendSession"]

LAST_TYPES = 10
OUTPUT_EXCERPT = 600
# The backend sends a keep-alive ping every second; it says nothing useful
# about what happened, so it's left out of error reports.
_QUIET_TYPES = frozenset({"ping"})

Predicate = Callable[[dict], bool]


class BackendError(RuntimeError):
    """The backend reported a failure for what the driver asked it to do."""


def _label(message: dict) -> str:
    """``type``, or ``type:action`` / ``type:id`` when the message has one."""
    kind = str(message.get("type"))
    detail = message.get("action") or (message.get("id") if kind == "system" else None)
    return f"{kind}:{detail}" if detail else kind


def _error_text(error) -> str:
    if isinstance(error, dict):
        return str(error.get("message") or error)
    return str(error)


def _operation_failed(router: str) -> Predicate:
    """An ``operation_done`` on ``router`` that carries an ``error``."""

    def check(message: dict) -> bool:
        return (
            message.get("type") == router
            and message.get("action") == "operation_done"
            and bool(message.get("error"))
        )

    return check


class BackendSession:
    """A frontend-like websocket session with a running Talemate backend."""

    def __init__(self, ws_url: str, open_timeout: float = 30):
        self.ws_url = ws_url
        self.open_timeout = open_timeout
        self.messages: list[dict] = []
        self._ws = None

    # --- connection ------------------------------------------------------

    def __enter__(self) -> "BackendSession":
        self._ws = connect(self.ws_url, max_size=None, open_timeout=self.open_timeout)
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        if self._ws is not None:
            self._ws.close()
            self._ws = None

    def send(self, payload: dict) -> None:
        self._ws.send(json.dumps(payload))

    def mark(self) -> int:
        """The current end of ``messages``, for a later ``start=``."""
        return len(self.messages)

    # --- waiting ---------------------------------------------------------

    def _context(self) -> str:
        """The last message types, and the model's last output, for reports."""
        labels = [
            _label(m) for m in self.messages if m.get("type") not in _QUIET_TYPES
        ][-LAST_TYPES:]
        text = f"last {len(labels)} message types: {', '.join(labels) or '(none)'}"
        output = self.last_output()
        if output is not None:
            prompt = self.prompts()[-1]
            if len(output) > OUTPUT_EXCERPT:
                output = output[:OUTPUT_EXCERPT] + "..."
            text += (
                f"\nlast model output ({prompt.get('agent_type')}"
                f".{prompt.get('agent_action')}): {output!r}"
            )
        return text

    def _fail(self, what: str) -> BackendError:
        return BackendError(f"{what}\n{self._context()}")

    def _check_errors(self, message: dict, error: Predicate | None) -> None:
        kind = message.get("type")
        if kind == "error":
            raise self._fail(
                f"backend error in {message.get('plugin')}: "
                f"{_error_text(message.get('error'))}"
            )
        if kind == "generation_error":
            data = message.get("data") or {}
            request_id = data.get("request_id")
            if request_id:
                # Answer like the dialog's Cancel, so the backend doesn't
                # wait forever on a choice nobody will make.
                self.send(
                    {
                        "type": "generation_error_response",
                        "request_id": request_id,
                        "action": "cancel",
                    }
                )
            raise self._fail(
                f"generation error from client {data.get('client')!r}: "
                f"{data.get('error_message') or message.get('message')}"
            )
        if kind == "system" and message.get("status") == "error":
            if "Another Talemate frontend" in str(message.get("message")):
                raise self._fail(str(message.get("message")))
        if error is not None and error(message):
            raise self._fail(
                f"{_label(message)} failed: "
                f"{_error_text(message.get('error') or message.get('message'))}"
            )

    def wait_for(
        self, predicate: Predicate, timeout: float, *, error: Predicate | None = None
    ) -> dict:
        """Read messages until ``predicate`` holds for one; return that message.

        Only messages that arrive from now on are checked. Raises
        ``TimeoutError`` after ``timeout`` seconds, ``BackendError`` on a
        backend failure (see the module docstring) or when ``error`` holds
        for a message.
        """
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"no matching message after {timeout:g}s; {self._context()}"
                )
            try:
                raw = self._ws.recv(timeout=remaining)
            except TimeoutError:
                continue
            except ConnectionClosed as exc:
                raise self._fail(f"the backend closed the connection ({exc})") from exc
            message = json.loads(raw)
            self.messages.append(message)
            self._check_errors(message, error)
            if predicate(message):
                return message

    # --- actions -----------------------------------------------------------

    def wait_client_ready(self, timeout: float = 120) -> dict:
        """Wait until an AI client reports itself idle (connected, a model loaded)."""
        return self.wait_for(
            lambda m: m.get("type") == "client_status"
            and m.get("status") == "idle"
            and bool(m.get("model_name")),
            timeout,
        )

    def load_scene(self, path: Path, timeout: float = 180) -> None:
        """Load the scene file at ``path``, as Load Scene does; wait until loaded."""
        status_errors: list[str] = []

        def failed(message: dict) -> bool:
            if message.get("type") == "status" and message.get("status") == "error":
                status_errors.append(str(message.get("message")))
            return message.get("type") == "system" and message.get("id") == (
                "scene.load_failure"
            )

        self.send({"type": "load_scene", "file_path": str(path)})
        try:
            self.wait_for(
                lambda m: m.get("type") == "system" and m.get("id") == "scene.loaded",
                timeout,
                error=failed,
            )
        except BackendError as exc:
            if status_errors:
                raise BackendError(
                    f"loading {path} failed: {'; '.join(status_errors)}\n{exc}"
                ) from None
            raise

    def persist_character(
        self, name: str, content: str = "", timeout: float = 600, **fields
    ) -> None:
        """Create a character with the director, as the Create Character dialog does.

        ``name`` is the dialog's name field (with ``determine_name`` on, the
        default, a hint the creator turns into a real name). Extra
        ``fields`` go into the payload (see ``PersistCharacterPayload``).
        """
        self.send(
            {
                "type": "director",
                "action": "persist_character",
                "name": name,
                "content": content,
                "narrate_entry": False,
                **fields,
            }
        )
        self.wait_for(
            lambda m: m.get("type") == "director"
            and m.get("action") == "character_persisted",
            timeout,
            error=_operation_failed("director"),
        )

    def narrate(
        self,
        action: Literal["narrate_environment", "progress"] = "narrate_environment",
        direction: str = "",
        timeout: float = 600,
    ) -> str:
        """Ask the narrator for ``action``; return the narration's text."""
        self.send(
            {"type": "narrator", "action": action, "narrative_direction": direction}
        )

        def failed(message: dict) -> bool:
            # A bare operation_done on the narrator router means cancelled.
            return (
                message.get("type") == "narrator"
                and message.get("action") == "operation_done"
            )

        message = self.wait_for(
            lambda m: m.get("type") == "narrator" and not m.get("action"),
            timeout,
            error=failed,
        )
        return message.get("message", "")

    # --- reading -----------------------------------------------------------

    def prompts(self, agent_type: str | None = None, start: int = 0) -> list[dict]:
        """``prompt_sent`` data (prompt, raw ``response``, agent, timing) from ``start``.

        ``agent_type`` keeps only one agent's prompts (e.g. ``"creator"``).
        """
        return [
            m.get("data") or {}
            for m in self.messages[start:]
            if m.get("type") == "prompt_sent"
            and (
                agent_type is None
                or (m.get("data") or {}).get("agent_type") == agent_type
            )
        ]

    def last_output(self, agent_type: str | None = None) -> str | None:
        """The model's raw response to the last prompt, or None if none was sent."""
        prompts = self.prompts(agent_type)
        return prompts[-1].get("response") if prompts else None
