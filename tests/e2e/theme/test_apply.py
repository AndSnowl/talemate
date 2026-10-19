"""Task 3 (fantasymate rebrand/appearance): the configured theme applies to the whole app.

See .superpowers/sdd/2026-10-18-fantasymate-rebrand-and-appearance/task-3-brief.md.

No scene/world seeding is needed here — the ``page`` fixture alone gives a
connected app with its app config already loaded (``dismiss_onboarding``
waits for exactly that).
"""

from e2e.seed import dismiss_onboarding, send_backend

# The app's own backend socket (open, not vite's HMR socket) — the same
# lookup as e2e.seed._BACKEND_SOCKET_JS (duplicated here because that one is
# private to seed.py; see tests/e2e/cultures/test_story.py for another copy).
# Unlike those two, this is a bare JS *expression*, not a `() => ...` arrow
# function — it's always inlined directly (``{_BACKEND_SOCKET_JS}``), never
# called with a trailing `()`.
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


GRUVBOX_LIGHT_BG_ALT = "rgb(242, 229, 188)"  # #f2e5bc


def _root_css_var(page, name: str) -> str:
    return page.evaluate(
        f"() => getComputedStyle(document.documentElement).getPropertyValue('{name}').trim()"
    )


def _rgb_triplet(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.replace(" ", "").split(","))


def _luminance(rgb: tuple[int, ...]) -> float:
    def channel(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_vuetify_defaults_follow_light_theme(page):
    """Final fix 1: a theme swap keeps Vuetify's own keys (error, info,
    surface-bright, ...) and re-derives its variables (border-color, ...)."""
    try:
        _set_active_theme(page, "gruvbox-light")
        page.wait_for_function(
            f"""
            () => getComputedStyle(document.querySelector('.v-application'))
                .backgroundColor === '{GRUVBOX_LIGHT_BG_ALT}'
            """,
            timeout=15_000,
        )
        # gruvbox-light's red (#9d0006), via the danger role.
        assert _rgb_triplet(_root_css_var(page, "--v-theme-error")) == (157, 0, 6)
        for key in (
            "--v-theme-info",
            "--v-theme-surface-bright",
            "--v-theme-surface-light",
        ):
            assert _root_css_var(page, key), f"{key} is not set"
        # Dividers/borders: dark on light (gruvbox-light fg #3c3836), not
        # Vuetify's dark-theme white.
        border = _rgb_triplet(_root_css_var(page, "--v-border-color"))
        assert border == (60, 56, 54)
        assert _luminance(border) < 0.2
        # Inline code is a light chip with dark text under a light theme.
        assert _luminance(_rgb_triplet(_root_css_var(page, "--v-theme-code"))) > 0.5
    finally:
        _set_active_theme(page, "gruvbox-dark")
        page.wait_for_function(
            f"""
            () => getComputedStyle(document.querySelector('.v-application'))
                .backgroundColor === '{GRUVBOX_DARK_BG_ALT}'
            """,
            timeout=15_000,
        )
