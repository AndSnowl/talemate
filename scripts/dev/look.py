"""Quick look at a running app: open a URL, do a few steps, save a screenshot.

Usage (from the talemate repo root, inside the Guix dev shell)::

    guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/look.py \\
        URL [--click SELECTOR]... [--fill SELECTOR=TEXT]... [--wait SELECTOR] \\
        --shot OUT.png [--console OUT.txt]

``--click``, ``--fill`` and ``--wait`` run in the order given, after the page
has loaded. Each waits up to ``--timeout`` seconds for its element.
``--wait`` waits until SELECTOR is visible. Selectors are Playwright selectors
(CSS, ``text=...``, ``role=button[name="..."]``, ...). The screenshot is full
page. ``--console`` writes every console message, one per line, as
``[type] text (url:line)``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import browser as browser_mod


class _Step(argparse.Action):
    """Append (kind, value) to the shared ordered ``steps`` list."""

    def __call__(self, parser, namespace, value, option_string=None):
        kind = option_string.lstrip("-")
        if kind == "fill" and "=" not in value:
            parser.error(f"--fill needs SELECTOR=TEXT, got {value!r}")
        namespace.steps.append((kind, value))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.set_defaults(steps=[])
    for flag in ("--click", "--fill", "--wait"):
        parser.add_argument(flag, action=_Step, metavar="SELECTOR", default=None)
    parser.add_argument("--shot", required=True, type=Path, metavar="OUT.png")
    parser.add_argument("--console", type=Path, metavar="OUT.txt")
    parser.add_argument("--timeout", type=float, default=30.0, help="per step, s")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=900)
    return parser.parse_args(argv)


def _format_console(msg) -> str:
    loc = msg.location or {}
    where = f" ({loc.get('url')}:{loc.get('lineNumber')})" if loc.get("url") else ""
    return f"[{msg.type}] {msg.text}{where}"


def run(args: argparse.Namespace) -> None:
    chromium = browser_mod.chromium_path()
    if not chromium:
        raise SystemExit("error: no Chromium — run inside `guix shell -m manifest.scm`")
    browser_mod.ensure_driver_node()
    from playwright.sync_api import sync_playwright

    timeout_ms = args.timeout * 1000
    console: list[str] = []
    with sync_playwright() as pw:
        b = browser_mod.launch(pw, chromium)
        try:
            page = b.new_page(viewport={"width": args.width, "height": args.height})
            page.set_default_timeout(timeout_ms)
            page.on("console", lambda msg: console.append(_format_console(msg)))
            page.on("pageerror", lambda exc: console.append(f"[pageerror] {exc}"))
            page.goto(args.url, wait_until="load")
            for kind, value in args.steps:
                if kind == "click":
                    page.locator(value).first.click()
                elif kind == "fill":
                    selector, text = value.split("=", 1)
                    page.locator(selector).first.fill(text)
                else:
                    page.locator(value).first.wait_for(state="visible")
            args.shot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(args.shot), full_page=True)
        finally:
            if args.console:
                args.console.parent.mkdir(parents=True, exist_ok=True)
                args.console.write_text("".join(line + "\n" for line in console))
            b.close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run(args)
    print(f"screenshot: {args.shot}")
    if args.console:
        print(f"console:    {args.console}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
