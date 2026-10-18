"""Task 3 (fantasymate rebrand/appearance): the configured theme applies to the whole app.

See .superpowers/sdd/2026-10-18-fantasymate-rebrand-and-appearance/task-3-brief.md.

No scene/world seeding is needed here — the ``page`` fixture alone gives a
connected app with its app config already loaded (``dismiss_onboarding``
waits for exactly that).
"""

from e2e.seed import dismiss_onboarding, send_backend

# The app's own backend socket (open, not vite's HMR socket) — mirrors
# e2e.seed._BACKEND_SOCKET_JS (duplicated here because that one is private to
# seed.py; see tests/e2e/cultures/test_story.py for the same pattern).
_BACKEND_SOCKET_JS = (
    "(window.__e2eSockets || []).filter("
    "(s) => s.readyState === WebSocket.OPEN && s.protocol !== 'vite-hmr'"
    ").pop()"
)

GRUVBOX_DARK_BG_ALT = "rgb(29, 32, 33)"  # #1d2021
NORD_BG_ALT = "rgb(39, 44, 54)"  # #272c36


def _v_application_background(page) -> str:
    return page.evaluate(
        "() => getComputedStyle(document.querySelector('.v-application')).backgroundColor"
    )


def _current_app_config(page) -> dict:
    """Round-trip ``request_app_config`` and return the config it answers with."""
    page.wait_for_function(f"!!({_BACKEND_SOCKET_JS})")
    return page.evaluate(
        f"""
        () => new Promise((resolve) => {{
            const socket = {_BACKEND_SOCKET_JS};
            function onMessage(event) {{
                const data = JSON.parse(event.data);
                if (data.type === 'app_config') {{
                    socket.removeEventListener('message', onMessage);
                    resolve(data.data);
                }}
            }}
            socket.addEventListener('message', onMessage);
            socket.send(JSON.stringify({{type: 'request_app_config'}}));
        }})
        """
    )


def _set_active_theme(page, active_id: str) -> None:
    """Save ``appearance.theme.active`` the same way AppSettings.vue's saveConfig does.

    (``{type: 'config', action: 'save', config: <the whole app config>}`` —
    see AppSettings.vue around line 364-379.)
    """
    config = _current_app_config(page)
    config["appearance"]["theme"]["active"] = active_id
    send_backend(page, {"type": "config", "action": "save", "config": config})


def test_default_theme_is_gruvbox_dark(page):
    assert _v_application_background(page) == GRUVBOX_DARK_BG_ALT


def test_theme_from_config_applies(page):
    try:
        _set_active_theme(page, "nord")
        page.wait_for_function(
            f"""
            () => getComputedStyle(document.querySelector('.v-application'))
                .backgroundColor === '{NORD_BG_ALT}'
            """,
            timeout=15_000,
        )
        page.reload()
        dismiss_onboarding(page)
        assert _v_application_background(page) == NORD_BG_ALT
    finally:
        _set_active_theme(page, "gruvbox-dark")
        page.wait_for_function(
            f"""
            () => getComputedStyle(document.querySelector('.v-application'))
                .backgroundColor === '{GRUVBOX_DARK_BG_ALT}'
            """,
            timeout=15_000,
        )
