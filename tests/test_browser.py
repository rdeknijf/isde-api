"""Run against a local server with ISDE_BROWSER_URL=http://127.0.0.1:8010."""

import os
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not os.environ.get("ISDE_BROWSER_URL"), reason="Local browser check is opt-in"
)
def test_browser_workflows():
    from playwright.sync_api import expect, sync_playwright

    origin = os.environ["ISDE_BROWSER_URL"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
        page = context.new_page()
        page.set_viewport_size({"width": 1280, "height": 1000})
        errors = []
        failures = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("requestfailed", lambda request: failures.append(request.url))
        page.goto(origin)
        page.locator("#categories article").first.wait_for()
        assert page.locator("#categories article").count() == 5
        assert (
            sum(
                int(s.replace(",", ""))
                for s in page.locator(".count").all_text_contents()
            )
            > 0
        )
        Path("data/screenshots").mkdir(parents=True, exist_ok=True)
        page.screenshot(path="data/screenshots/desktop.png", full_page=True)
        for button in page.locator(".copy").all():
            button.click()
            expect(button).to_have_text("Copied")
            assert (
                page.evaluate("navigator.clipboard.readText()")
                == button.locator("..").locator("code").inner_text()
            )
            assert origin in page.evaluate("navigator.clipboard.readText()")
        page.get_by_label("Meldcode", exact=True).fill("KA01290")
        page.get_by_role("button", name="Search", exact=True).click()
        page.locator("#lookup-output pre").wait_for()
        assert '"KA01290"' in page.locator("#lookup-output").inner_text()
        page.get_by_label("Meldcode", exact=True).fill("KA99999")
        page.get_by_role("button", name="Search", exact=True).click()
        page.locator("#lookup-output .error").wait_for()
        assert "current data" in page.locator("#lookup-output").inner_text()
        page.set_viewport_size({"width": 390, "height": 844})
        page.reload()
        page.locator("#categories article").first.wait_for()
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        page.screenshot(path="data/screenshots/mobile.png", full_page=True)
        page.route(
            "**/v1/categories",
            lambda route: route.fulfill(status=503, json={"detail": "Unavailable"}),
        )
        page.reload()
        page.locator("#categories .error").wait_for()
        assert "unavailable" in page.locator("#categories").inner_text()
        assert not errors
        assert not failures
        browser.close()
