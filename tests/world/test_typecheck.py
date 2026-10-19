"""Strict mypy over talemate.world, run as a regular test so the suite
enforces it. The rest of talemate stays untyped; see the `[tool.mypy]`
section in pyproject.toml.
"""

from pathlib import Path

from mypy import api as mypy_api

REPO_ROOT = Path(__file__).resolve().parents[2]

# Persistent, not a fresh tmp dir: this is the only test that runs mypy, so
# there's no other writer to race under xdist, and a warm cache keeps this
# test fast. Gitignored (see .gitignore).
CACHE_DIR = REPO_ROOT / ".mypy_cache" / "world-typecheck"


def test_world_package_typechecks():
    config_file = REPO_ROOT / "pyproject.toml"

    stdout, stderr, status = mypy_api.run(
        [
            "--config-file",
            str(config_file),
            "--cache-dir",
            str(CACHE_DIR),
            "-p",
            "talemate.world",
        ]
    )

    assert status == 0, f"mypy found errors:\n{stdout}\n{stderr}"
