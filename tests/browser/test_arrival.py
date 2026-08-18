"""What a person meets when they open the address.

`walkthrough/05-in-the-browser.md` shows the happy path a reader follows. This
covers what a reader does not need to see: the redirect's shape, the page
working before any script does, and the workspace still being reachable by its
own address.
"""

from __future__ import annotations


class TestTheBarePort:
    def test_it_redirects_to_the_splash(self, blank, app):
        response = blank.goto(app.base, wait_until="networkidle")
        assert blank.url.rstrip("/").endswith("/splash")
        assert response.status == 200  # after following the redirect

    def test_the_redirect_is_temporary_not_permanent(self, blank, app):
        # A 301 is cached by the browser forever. Moving the workspace back to
        # `/` later would then reach nobody who had ever visited, and the fix
        # would be asking people to clear their history.
        chain = blank.goto(app.base, wait_until="networkidle")
        hops = []
        walk = chain.request.redirected_from
        while walk is not None:
            hops.append(walk.response().status)
            walk = walk.redirected_from
        assert hops == [307], f"expected one temporary redirect, got {hops}"

    def test_the_splash_says_what_this_is(self, blank, app):
        blank.goto(f"{app.base}/splash", wait_until="networkidle")
        assert blank.inner_text(".splash-name") == "CARLOS"
        assert "rigs" in blank.inner_text(".splash-line")

    def test_the_way_in_is_a_link_that_needs_no_script(self, blank, app):
        # A button wired by JavaScript is a door that does not open until the
        # script does. This one is an anchor with an href.
        blank.goto(f"{app.base}/splash", wait_until="networkidle")
        assert blank.get_attribute(".splash-enter", "href") == "/rack"

    def test_following_it_reaches_the_workspace(self, blank, app):
        blank.goto(f"{app.base}/splash", wait_until="networkidle")
        blank.click(".splash-enter")
        # `#rack` is in the template and exists before any script runs, so it
        # is not a signal that the app booted. The status line is.
        blank.wait_for_function(
            "() => (document.querySelector('#status')?.textContent || '')"
            ".startsWith('Carlos ready')",
            timeout=15_000,
        )
        assert blank.url.endswith("/rack")
        assert blank.locator(".module").count() == 2

    def test_its_figures_are_measured_rather_than_typed(self, app, blank):
        from src import catalogue

        blank.goto(f"{app.base}/splash", wait_until="networkidle")
        facts = blank.inner_text(".splash-facts")
        assert str(len(catalogue.load_all())) in facts
        assert "carlos.patch" in facts

    def test_nothing_throws_on_the_way_in(self, blank, app):
        blank.goto(app.base, wait_until="networkidle")
        blank.click(".splash-enter")
        blank.wait_for_function(
            "() => (document.querySelector('#status')?.textContent || '')"
            ".startsWith('Carlos ready')",
            timeout=15_000,
        )
        assert blank.errors == []


class TestTheWorkspace:
    def test_it_boots_with_the_generic_pair(self, page):
        assert page.locator(".module").count() == 2

    def test_the_facing_indicator_reports_the_rack_it_is_looking_at(self, page):
        # It read EMPTY on a rack with two devices for two sessions, because
        # nothing refreshed it when a device was added and every model-level
        # test agreed with the model.
        assert page.locator("#view-indicator").inner_text() == "ALL FRONT"

    def test_the_palette_opens_at_its_default_corner(self, page):
        palette = page.locator("#tool-palette").bounding_box()
        viewport = page.viewport_size
        assert round(viewport["width"] - (palette["x"] + palette["width"])) == 20
        assert round(palette["y"]) == 68

    def test_the_console_is_clean(self, page):
        assert page.errors == []
