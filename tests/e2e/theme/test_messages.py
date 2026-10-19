"""Final review fixes 3 and 4 (fantasymate rebrand/appearance): scene messages.

- The player character's name and message border use the ``you`` role;
  other characters keep their accent.
- Character lines have no text shadow without a scene backdrop (it used to
  be an unconditional black shadow, smudgy under light presets).

Restores ``appearance.theme`` to the default in a ``finally`` block, like
tests/e2e/theme/test_apply.py.
"""

from e2e.seed import open_scene, seed_world
from e2e.theme.test_apply import (
    GRUVBOX_DARK_BG_ALT,
    GRUVBOX_LIGHT_BG_ALT,
    _set_active_theme,
)

# gruvbox-light: blue (#076678, the `you` role) and magenta (#8f3f71, the
# accent "Marta" hashes to — see checks' character_key_hash_is_pinned).
GRUVBOX_LIGHT_YOU = "rgb(7, 102, 120)"
GRUVBOX_LIGHT_MAGENTA = "rgb(143, 63, 113)"


def _wait_for_background(page, rgb: str) -> None:
    page.wait_for_function(
        f"""
        () => getComputedStyle(document.querySelector('.v-application'))
            .backgroundColor === '{rgb}'
        """,
        timeout=15_000,
    )


def _name_chip(page, name: str):
    return page.locator(".character-name-chip", has_text=name).first


def test_player_lines_use_you_and_have_no_shadow(app, page):
    world = seed_world(
        app.root,
        project="theme-messages",
        messages=[
            {"character": "Ilsa", "text": "We cross at dawn."},
            {"character": "Marta", "text": "Not before the toll is paid."},
        ],
        characters=[
            {"name": "Ilsa", "is_player": True},
            {"name": "Marta"},
        ],
    )
    open_scene(page, world.scene_path)
    try:
        _set_active_theme(page, "gruvbox-light")
        _wait_for_background(page, GRUVBOX_LIGHT_BG_ALT)

        ilsa = _name_chip(page, "Ilsa")
        marta = _name_chip(page, "Marta")
        ilsa.wait_for(state="visible", timeout=30_000)
        marta.wait_for(state="visible", timeout=30_000)

        # Both names hash to magenta; only the player switches to `you`.
        page.wait_for_function(
            f"""
            () => {{
                const chip = [...document.querySelectorAll('.character-name-chip')]
                    .find((el) => el.textContent.trim() === 'Ilsa');
                return chip && getComputedStyle(chip).color === '{GRUVBOX_LIGHT_YOU}';
            }}
            """,
            timeout=15_000,
        )
        assert marta.evaluate("(el) => getComputedStyle(el).color") == (
            GRUVBOX_LIGHT_MAGENTA
        )
        ilsa_border = ilsa.evaluate(
            "(el) => getComputedStyle(el.closest('.message')).borderLeftColor"
        )
        assert ilsa_border == GRUVBOX_LIGHT_YOU

        # No backdrop: character lines carry no text shadow.
        shadows = page.evaluate(
            "() => [...document.querySelectorAll('.character-message')]"
            ".map((el) => getComputedStyle(el).textShadow)"
        )
        assert shadows and all(s == "none" for s in shadows), shadows
    finally:
        _set_active_theme(page, "gruvbox-dark")
        _wait_for_background(page, GRUVBOX_DARK_BG_ALT)
