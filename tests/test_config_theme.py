"""
Unit tests for the `appearance.theme` config field.

Covers:
- `Config().appearance.theme` defaults to the gruvbox-dark theme with no
  custom themes.
- Setting an active custom theme and a `CustomTheme` entry round-trips
  through `save_config` / `_load_config` (yaml persistence).
- A legacy `appearance` dict that only sets `scene` still validates and
  gets the default theme.
"""

import pytest

import talemate.config.state as config_state
from talemate.config.schema import Appearance, Config, CustomTheme


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_config(monkeypatch, tmp_path):
    """Replace `CONFIG` with a fresh, fully-populated Config and redirect
    CONFIG_FILE to a tmp_path. Restores CONFIG on teardown so the
    session-level autouse fixture from conftest still has its expected
    state for the next test.

    Mirrors the isolation pattern in `tests/test_config_state.py`.
    """
    import talemate.instance as instance_module
    import talemate.emit.async_signals as async_signals

    original_config = config_state.CONFIG
    cfg = Config()
    cfg.dirty = False
    config_state.CONFIG = cfg

    fake_path = tmp_path / "config.yaml"
    monkeypatch.setattr(config_state, "CONFIG_FILE", fake_path)

    original_agents = dict(instance_module.AGENTS)
    instance_module.AGENTS.clear()

    changed_signal = async_signals.get("config.changed")
    changed_follow_signal = async_signals.get("config.changed.follow")
    original_receivers = list(changed_signal.receivers)
    original_follow_receivers = list(changed_follow_signal.receivers)
    changed_signal.receivers.clear()
    changed_follow_signal.receivers.clear()

    yield cfg

    config_state.CONFIG = original_config
    instance_module.AGENTS.clear()
    instance_module.AGENTS.update(original_agents)
    changed_signal.receivers[:] = original_receivers
    changed_follow_signal.receivers[:] = original_follow_receivers


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_default_theme_is_gruvbox_dark():
    config = Config()
    assert config.appearance.theme.active == "gruvbox-dark"
    assert config.appearance.theme.custom == []


def test_theme_round_trips_through_yaml(isolated_config):
    isolated_config.appearance.theme.active = "custom-1"
    isolated_config.appearance.theme.custom.append(
        CustomTheme(
            id="custom-1",
            name="My Custom Theme",
            palette={"orange": "#aa5500"},
        )
    )

    config_state.save_config()
    reloaded = config_state._load_config()

    assert reloaded.appearance.theme.active == "custom-1"
    assert len(reloaded.appearance.theme.custom) == 1
    custom = reloaded.appearance.theme.custom[0]
    assert custom.id == "custom-1"
    assert custom.name == "My Custom Theme"
    assert custom.base == "gruvbox-dark"
    assert custom.dark is True
    assert custom.palette == {"orange": "#aa5500"}
    assert custom.roles == {}


def test_config_without_theme_loads():
    appearance = Appearance.model_validate({"scene": {}})
    assert appearance.theme.active == "gruvbox-dark"
    assert appearance.theme.custom == []
