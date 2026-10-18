"""E2E: the shared fixtures, world seeding and failure artifacts work."""

import json
import textwrap
from pathlib import Path

# tests/ has no __init__.py, so pytest imports this package as `e2e`.
from e2e import conftest as e2e_conftest
from e2e.seed import open_scene, seed_world

pytest_plugins = ["pytester"]

APP_BAR = "header.v-app-bar"


def test_app_loads_without_console_errors(page):
    page.locator(APP_BAR).wait_for(state="visible", timeout=60_000)

    assert page.console_errors == []


def test_seeded_world_opens_with_cultures_tab(app, page):
    world = seed_world(app.root)

    scene_data = json.loads(world.scene_path.read_text())
    assert scene_data["shared_context"] == world.shared_context_path.name
    assert world.world_dir == world.shared_context_path.with_name("world.world")

    open_scene(page, world.scene_path)

    page.locator(f"{APP_BAR} .v-tab", has_text="World Editor").click()
    cultures_tab = page.locator(".v-tab", has_text="Cultures")
    cultures_tab.wait_for(state="visible", timeout=30_000)
    cultures_tab.click()

    # Wait for the tab's positive "linked world, no cultures yet" state, so
    # the absence check below isn't passing just because nothing rendered yet.
    page.get_by_text("No cultures yet.").wait_for(state="visible", timeout=30_000)
    assert page.get_by_text("Link this scene to a Shared World").count() == 0


def test_failure_artifacts_written(page, tmp_path):
    page.locator(APP_BAR).wait_for(state="visible", timeout=60_000)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "backend.log").write_text(
        "\n".join(f"line {i}" for i in range(500)) + "\n"
    )

    out = e2e_conftest.save_failure_artifacts(
        page,
        log_dir,
        "test_x[param/1]",
        base=tmp_path / "artifacts",
        stamp="20261017-120000",
    )

    assert out == tmp_path / "artifacts" / "20261017-120000" / "test_x_param_1_"
    assert (out / "screenshot.png").stat().st_size > 0
    tail = (out / "backend.log.tail").read_text().splitlines()
    assert tail[-1] == "line 499"
    assert len(tail) == e2e_conftest.LOG_TAIL_LINES


def test_failure_hook_saves_artifacts_for_failing_test(pytester, tmp_path):
    """The makereport hook calls the saver for a failed test that has a page."""
    artifacts = tmp_path / "artifacts"
    conftest_path = Path(e2e_conftest.__file__)
    pytester.makeconftest(
        textwrap.dedent(
            f"""
            import importlib.util
            from pathlib import Path

            import pytest

            spec = importlib.util.spec_from_file_location(
                "e2e_conftest_under_test", {str(conftest_path)!r}
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.ARTIFACTS_DIR = Path({str(artifacts)!r})
            pytest_runtest_makereport = mod.pytest_runtest_makereport


            class FakePage:
                def screenshot(self, path, full_page):
                    Path(path).write_bytes(b"png")


            @pytest.fixture
            def page():
                return FakePage()
            """
        )
    )
    pytester.makepyfile(
        """
        def test_boom(page):
            assert False

        def test_fine(page):
            pass
        """
    )

    result = pytester.runpytest_inprocess(
        "-p", "no:cacheprovider", "-p", "no:xdist", "-p", "no:asyncio"
    )

    result.assert_outcomes(passed=1, failed=1)
    shots = list(artifacts.glob("*/*/screenshot.png"))
    assert [p.parent.name for p in shots] == ["test_boom"]
