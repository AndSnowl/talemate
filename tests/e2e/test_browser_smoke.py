"""Smoke test that the Playwright + Guix Chromium harness works at all."""


def test_browser_renders_a_data_url(page):
    page.goto("data:text/html,<h1 id=t>ok</h1>")

    assert page.locator("#t").inner_text() == "ok"
    assert len(page.screenshot()) > 0
