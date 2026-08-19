"""One server and one browser for the whole browser suite.

Built on `walkthrough/support.py` rather than on `pytest-playwright`'s own
fixtures, for one reason: there is already a mechanism here that starts the
real app, registers its shutdown for the failure path, and releases the driver
on the success path. Two mechanisms driving the sync Playwright API in one
session is how the walkthrough pages broke forty-four unittest tests — the
driver holds a running event loop and anything calling `asyncio.run` afterwards
fails on it.

The server is session-scoped because starting FastAPI costs more than every
test here put together. Each test gets its own page, so nothing inherits a
previous test's rack, palette position, or local storage.
"""

from __future__ import annotations

import pytest

from walkthrough.support import LiveApp, chromium, open_rack, release


# Package-scoped, not session-scoped, and the difference is not about speed.
#
# Playwright's sync driver holds a running event loop in this thread for as
# long as it is alive, and anything calling `asyncio.run` afterwards fails with
# "cannot be called from a running event loop". A session-scoped browser is
# alive until the whole run ends, so every `asyncio.run` test collected after
# this package failed — the same defect the walkthrough pages had, arriving by
# a different door one commit later. Package scope releases it when these
# tests finish, which is while the rest of the suite is still to come.
@pytest.fixture(scope="package")
def app():
    """The real application, on a port of its own."""
    live = LiveApp().start()
    yield live
    live.stop()


@pytest.fixture(scope="package")
def browser():
    """Real Chromium, released when this package's tests are done."""
    driver = chromium()
    yield driver
    release(driver)


@pytest.fixture(autouse=True)
def _a_browser_that_remembers_nothing(browser):
    """Forget what the last test taught this browser.

    Pages are fresh; the browser context they share is not. The ring's
    arrangement and the bar's hint both live in `localStorage`, so a test that
    hides a family leaves it hidden for every test after it - and the ones that
    then find a ring without `Add` on it fail somewhere far from the cause.

    It did not show up on this workstation and did show up on the first CI run,
    which is the usual shape of a shared-state defect: order and timing decide
    whether you see it.
    """
    yield
    for context in browser.contexts:
        try:
            context.clear_cookies()
        except Exception:
            pass
        for page_ in context.pages:
            try:
                page_.evaluate("() => { localStorage.clear(); }")
            except Exception:
                # A closed page has nothing left to forget.
                pass


@pytest.fixture
def page(app, browser):
    """A fresh page on the workspace, with its console captured.

    A browser JS error never reaches the server log — the log is identical
    whether the page works perfectly or throws on every keypress — so every
    test in this suite can assert `page.errors == []` and mean it.
    """
    fresh = open_rack(app, browser)
    yield fresh
    fresh.close()


@pytest.fixture
def bench(page):
    """A known rig, built here rather than inherited from the opening rack.

    The page opens on a grid and a sampler linked over USB, which is a rig with
    a question in it and a poor fixture: both devices are played from above,
    both sockets are round the back, and neither has a front to patch. Tests
    that need two boxes with visible sockets should say so rather than depend on
    whatever ships as the opening picture - that rack is presentation, and it
    has changed twice already.
    """
    page.evaluate(
        """() => {
            system.clearRack();
            system.setMode('minimal');
            system.addModule('carlos.vco');
            system.addModule('carlos.vcf');
        }"""
    )
    return page


@pytest.fixture
def blank(app, browser):
    """A page that has navigated nowhere yet, for testing what the port does."""
    fresh = browser.new_page(viewport={"width": 1280, "height": 860})
    fresh.errors = []
    fresh.on("pageerror", lambda error: fresh.errors.append(str(error)))
    yield fresh
    fresh.close()
