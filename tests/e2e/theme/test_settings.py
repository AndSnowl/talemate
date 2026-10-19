"""Task 9 (fantasymate rebrand/appearance): the Theme settings page.

See .superpowers/sdd/2026-10-18-fantasymate-rebrand-and-appearance/task-9-brief.md.

Every test restores ``appearance.theme`` to the default
(``{active: 'gruvbox-dark', custom: []}``) in a ``finally`` block, so tests
are independent of each other and of execution order (the app under test is
session-scoped — see tests/e2e/conftest.py).
"""

from e2e.seed import send_backend

# The app's own backend socket (open, not vite's HMR socket) — duplicated
# from e2e.seed (private there) the same way tests/e2e/theme/test_apply.py
# does.
_BACKEND_SOCKET_JS = (
    "(window.__e2eSockets || []).filter("
    "(s) => s.readyState === WebSocket.OPEN && s.protocol !== 'vite-hmr'"
    ").pop()"
)

GRUVBOX_DARK_BG_ALT = "rgb(29, 32, 33)"  # #1d2021
NORD_BG_ALT = "rgb(39, 44, 54)"  # #272c36
MONOKAI_BG_ALT = "rgb(30, 31, 28)"  # #1e1f1c


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


def _wait_for_background(page, rgb: str) -> None:
    page.wait_for_function(
        f"""
        () => getComputedStyle(document.querySelector('.v-application'))
            .backgroundColor === '{rgb}'
        """,
        timeout=15_000,
    )


def _reset_theme(page) -> None:
    """Restore ``appearance.theme`` to the default, the way AppSettings.vue's
    saveConfig does (see tests/e2e/theme/test_apply.py's ``_set_active_theme``)."""
    config = _current_app_config(page)
    config["appearance"]["theme"] = {"active": "gruvbox-dark", "custom": []}
    send_backend(page, {"type": "config", "action": "save", "config": config})
    _wait_for_background(page, GRUVBOX_DARK_BG_ALT)


def _open_theme_settings(page) -> None:
    # The app bar's "Settings" button (icon mdi-cog) — distinct from the
    # "Clients / Agents" button next to it (icon mdi-application-cog).
    page.locator("button:has(i.mdi-cog)").first.click()
    page.locator(".v-list-item", has_text="Theme").first.click()
    page.get_by_text("Presets", exact=True).first.wait_for(
        state="visible", timeout=10_000
    )


def _click_preset(page, name: str) -> None:
    page.locator(".v-list-item", has_text=name).first.click()


def test_pick_preset_recolours_live(page):
    try:
        _open_theme_settings(page)
        _click_preset(page, "Nord")
        _wait_for_background(page, NORD_BG_ALT)
    finally:
        _reset_theme(page)


def test_duplicate_edit_save_persists(page):
    try:
        _open_theme_settings(page)
        page.get_by_role("button", name="Duplicate current as new").click()

        # "orange" is the default selected palette swatch.
        hex_field = page.get_by_label("Palette colour (hex)", exact=True)
        hex_field.fill("#aa5500")
        hex_field.press("Tab")

        page.locator(".app-settings-toolbar").get_by_role("button", name="Save").click()
        page.get_by_text("Unsaved changes.").wait_for(state="hidden", timeout=15_000)

        page.reload()
        config = _current_app_config(page)
        theme = config["appearance"]["theme"]
        assert theme["active"].startswith("custom-")
        custom = next(c for c in theme["custom"] if c["id"] == theme["active"])
        assert custom["palette"]["orange"] == "#aa5500"

        accent_var = page.evaluate(
            "() => getComputedStyle(document.querySelector('.v-application'))"
            ".getPropertyValue('--v-theme-accent').trim()"
        )
        assert accent_var.replace(" ", "") == "170,85,0"
    finally:
        _reset_theme(page)


def test_unsaved_theme_reverts_on_leave(page):
    try:
        _open_theme_settings(page)
        _click_preset(page, "Monokai")
        _wait_for_background(page, MONOKAI_BG_ALT)

        home_tab = page.get_by_role("tab", name="Home")
        home_tab.click()

        # Leaving settings with unsaved edits may raise the "unsaved
        # settings" guard dialog first — dismiss it with Ignore, which still
        # leaves the tab (see TalemateApp.vue's onUnsavedSettingsIgnore).
        ignore_button = page.get_by_role("button", name="Ignore")
        if ignore_button.is_visible():
            ignore_button.click()

        _wait_for_background(page, GRUVBOX_DARK_BG_ALT)
    finally:
        _reset_theme(page)


def test_import_bad_file_shows_error(page, tmp_path):
    bad_file = tmp_path / "bad.fantasymate-theme.json"
    bad_file.write_text('{"format": "x"}')

    try:
        _open_theme_settings(page)
        # "Yours" is empty — see _reset_theme's {"active": "gruvbox-dark",
        # "custom": []} baseline every test restores in its own finally.
        page.get_by_text("No themes of your own yet.").wait_for(
            state="visible", timeout=10_000
        )

        import_card = page.locator(".v-card", has_text="Import / export")
        import_card.locator('input[type="file"]').set_input_files(str(bad_file))

        page.locator(".v-alert", has_text="format").wait_for(
            state="visible", timeout=10_000
        )

        # Still empty: the failed import changed nothing.
        page.get_by_text("No themes of your own yet.").wait_for(
            state="visible", timeout=5_000
        )
    finally:
        _reset_theme(page)
