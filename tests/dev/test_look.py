"""Unit tests for scripts/dev/look.py: argument parsing, and the screenshot
a failed step still leaves. No browser: Playwright is replaced by fakes.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_DEV = Path(__file__).resolve().parents[2] / "scripts" / "dev"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _DEV / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("browser")  # look.py imports it as a sibling module
look = _load("look")


def test_fill_takes_selector_and_text_as_two_arguments():
    selector = 'role=textbox[name="Title"]'  # the docs' style: contains "="
    args = look.parse_args(
        [
            "http://127.0.0.1:1/",
            "--click",
            "text=New",
            "--fill",
            selector,
            "a = b",
            "--wait",
            "css=.done",
            "--shot",
            "out.png",
        ]
    )
    assert args.steps == [
        ("click", "text=New"),
        ("fill", (selector, "a = b")),
        ("wait", "css=.done"),
    ]


def test_fill_with_one_argument_is_an_error(capsys):
    with pytest.raises(SystemExit):
        look.parse_args(["http://x/", "--shot", "out.png", "--fill", "#title"])
    assert "--fill" in capsys.readouterr().err


def test_timeout_width_height_defaults_and_overrides():
    args = look.parse_args(["http://x/", "--shot", "out.png"])
    assert (args.timeout, args.width, args.height) == (30.0, 1280, 900)
    args = look.parse_args(
        ["http://x/", "--shot", "o.png", "--timeout", "5", "--width", "800"]
        + ["--height", "600"]
    )
    assert (args.timeout, args.width, args.height) == (5.0, 800, 600)


class _TimeoutError(Exception):
    pass


class _FakePage:
    def __init__(self, shots):
        self.shots = shots

    def set_default_timeout(self, ms):
        pass

    def on(self, event, handler):
        if event == "console":
            handler(
                types.SimpleNamespace(type="log", text="hello", location={"url": ""})
            )

    def goto(self, url, wait_until):
        pass

    def locator(self, selector):
        def wait_for(state):
            raise _TimeoutError(f"timed out waiting for {selector}")

        return types.SimpleNamespace(
            first=types.SimpleNamespace(wait_for=wait_for, click=lambda: None)
        )

    def screenshot(self, path, full_page):
        Path(path).write_bytes(b"png")
        self.shots.append(path)


def test_failed_step_still_saves_screenshot_and_console(tmp_path, monkeypatch):
    shots = []
    closed = []
    fake_browser = types.SimpleNamespace(
        new_page=lambda viewport: _FakePage(shots), close=lambda: closed.append(1)
    )

    class _Playwright:
        def __enter__(self):
            return object()

        def __exit__(self, *exc):
            return False

    monkeypatch.setitem(
        sys.modules,
        "playwright.sync_api",
        types.SimpleNamespace(sync_playwright=_Playwright),
    )
    monkeypatch.setattr(look.browser_mod, "chromium_path", lambda: "/fake/chromium")
    monkeypatch.setattr(look.browser_mod, "ensure_driver_node", lambda: None)
    monkeypatch.setattr(look.browser_mod, "launch", lambda pw, path: fake_browser)
    shot = tmp_path / "shots" / "out.png"
    console = tmp_path / "console.txt"
    args = look.parse_args(
        [
            "http://x/",
            "--wait",
            "css=.never",
            "--shot",
            str(shot),
            "--console",
            str(console),
        ]
    )

    with pytest.raises(_TimeoutError):
        look.run(args)

    assert shots == [str(shot)] and shot.read_bytes() == b"png"
    assert console.read_text() == "[log] hello\n"
    assert closed == [1]
