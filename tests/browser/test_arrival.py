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
        # test agreed with the model. Both opening devices are played from
        # above, so the rack it is looking at is all tops.
        assert page.locator("#view-indicator").inner_text() == "ALL TOP"

    def test_it_opens_on_a_grid_and_a_sampler(self, page):
        # The opening rack is a rig rather than a demonstration of the drawing
        # code: two devices people own, one lead, four channels down it. It
        # used to be a VCO beside a VCF with nothing running between them.
        names = " ".join(page.locator(".module .module-title").all_text_contents())
        assert "Launchpad" in names
        assert "EP-133" in names or "K.O" in names

    def test_they_arrive_linked(self, page):
        assert page.locator("path.cable").count() >= 1

    def test_the_lead_is_split_into_the_channels_it_carries(self, page):
        # Three melodic groups and a kit, so the lead is drawn as four strands.
        # Derived from the bindings rather than stored on the cable: nothing has
        # to be kept in step when a group is rebound.
        channels = page.locator("path.cable[data-channel]").evaluate_all(
            "paths => paths.map(p => Number(p.dataset.channel))")
        assert sorted(channels) == [1, 2, 3, 10]

    def test_every_strand_says_what_it_carries(self, page):
        titles = page.locator("path.cable[data-channel] title").all_text_contents()
        assert len(titles) == 4
        assert all("channel" in t for t in titles)
        assert any("Group A" in t for t in titles)

    def test_the_drums_are_on_ten_and_say_so(self, page):
        drums = page.locator("path.cable.is-drums")
        assert drums.count() == 1
        assert drums.get_attribute("data-channel") == "10"
        assert "(drums)" in drums.locator("title").text_content()

    def test_the_drums_are_the_one_you_find_first(self, page):
        # Off the gradient and thicker than the rest: channel 10 is not a point
        # on a scale, it is the strand people are looking for.
        widths = page.locator("path.cable[data-channel]").evaluate_all(
            """paths => paths.map(p => ({
                channel: Number(p.dataset.channel),
                width: parseFloat(getComputedStyle(p).strokeWidth),
                stroke: getComputedStyle(p).stroke,
            }))"""
        )
        drums = [w for w in widths if w["channel"] == 10]
        rest = [w for w in widths if w["channel"] != 10]
        assert len(drums) == 1
        assert all(drums[0]["width"] > other["width"] for other in rest)
        assert all(drums[0]["stroke"] != other["stroke"] for other in rest)

    def test_the_other_strands_walk_a_gradient(self, page):
        # Every strand a different colour, so "which channel is that" is
        # answerable before anything is hovered.
        strokes = page.locator("path.cable[data-channel]").evaluate_all(
            "paths => paths.map(p => getComputedStyle(p).stroke)")
        assert len(set(strokes)) == len(strokes)

    def test_the_gradient_is_a_position_not_a_colour(self, page):
        # The strand carries where it sits on the scale; the scale itself lives
        # in the stylesheet with the rest of the palette.
        mixes = page.locator("path.cable[data-channel]").evaluate_all(
            "paths => paths.map(p => p.style.getPropertyValue('--lane-mix'))")
        assert sorted(float(m) for m in mixes) == [0.0, 1 / 3, 2 / 3, 1.0]

    def test_no_cable_paints_a_colour_of_its_own(self, page):
        # A stroke written into the SVG attribute is a colour outside the
        # palette and outside any theme that follows it.
        painted = page.locator("path.cable").evaluate_all(
            "paths => paths.filter(p => p.hasAttribute('stroke')).length")
        assert painted == 0

    def test_the_lead_is_marked_as_split(self, page):
        assert page.locator("path.cable.is-split").count() == 4

    def test_it_says_a_host_sits_in_the_middle(self, page):
        # Two USB device ports do not reach each other on a real desk. The
        # cable says so rather than implying a grid can drive a sampler alone.
        # `text_content`, not `inner_text`: an SVG <title> is not an
        # HTMLElement and has no rendered text to read.
        title = page.locator("path.cable title").first.text_content()
        assert "through a host" in title

    def test_the_lead_runs_behind_the_gear(self, page):
        # Both USB sockets are round the back, so the whole run is out of sight
        # and it belongs under the devices. It used to be drawn over the panel
        # it was meant to be behind: the dashes said "part of this is hidden"
        # and the picture showed it in front of everything.
        behind = page.locator("#patch-cables-behind path.cable").count()
        front = page.locator("#patch-cables path.cable").count()
        assert behind == 4
        assert front == 0

    def test_the_gear_is_stacked_between_the_two_cable_layers(self, page):
        z = page.evaluate(
            """() => ({
                behind: getComputedStyle(
                    document.querySelector('#patch-cables-behind')).zIndex,
                device: getComputedStyle(
                    document.querySelector('.module')).zIndex,
                front: getComputedStyle(
                    document.querySelector('#patch-cables')).zIndex,
            })"""
        )
        assert int(z["behind"]) < int(z["device"]) < int(z["front"])

    def test_a_lead_behind_the_gear_is_still_in_front_of_the_rack(self, page):
        """The one that matters: the lead is visible.

        Every other check here passed while the cables were invisible. They were
        on the right layer, at the right z-index, with the right classes — and
        painted behind the rack's own opaque floor, because a negative z-index
        paints above its *stacking context's* background and `.rack-container`
        never created one.

        `elementsFromPoint` returns what is under a point in paint order,
        front to back, so it can answer "is this lead in front of the floor it
        runs across" rather than "is it where I filed it". Hit testing ignores
        `pointer-events: none`, so the layers are opened for the duration and
        put back.
        """
        order = page.evaluate(
            """() => {
                const path = document.querySelector(
                    '#patch-cables-behind path.cable');
                const rack = document.querySelector('#rack');
                // The layer *and* the path: `.cable` carries its own
                // `pointer-events: none`, so opening only the layer leaves the
                // stroke untestable and the probe reports it as absent.
                const layers = [...document.querySelectorAll('svg')];
                const saved = layers.map(l => l.style.pointerEvents);
                layers.forEach(l => { l.style.pointerEvents = 'auto'; });
                const savedPath = path.style.pointerEvents;
                path.style.pointerEvents = 'stroke';

                // A point actually on the curve, not in its bounding box: a
                // sagging cable leaves most of that box empty.
                const at = path.getPointAtLength(path.getTotalLength() / 2);
                const ctm = path.getScreenCTM();
                const x = at.x * ctm.a + at.y * ctm.c + ctm.e;
                const y = at.x * ctm.b + at.y * ctm.d + ctm.f;

                const stack = document.elementsFromPoint(x, y);
                layers.forEach((l, i) => { l.style.pointerEvents = saved[i]; });
                path.style.pointerEvents = savedPath;

                return {
                    cable: stack.indexOf(path),
                    rack: stack.indexOf(rack),
                };
            }"""
        )
        assert order["cable"] >= 0, "the lead is not painted anywhere on screen"
        assert order["rack"] >= 0
        # Lower index is nearer the front.
        assert order["cable"] < order["rack"], (
            "the lead paints behind the rack floor, so nobody can see it")

    def test_the_mark_where_it_disappears_stays_on_top(self, page):
        # The cable goes under the device; the mark saying where it went under
        # does not, or it would be a mark you cannot see.
        assert page.locator("#patch-cables .cable-anchor").count() > 0
        assert page.locator("#patch-cables-behind .cable-anchor").count() == 0

    def test_a_lead_you_can_see_runs_over_the_gear(self, bench):
        # The other half of the rule, on two devices patched face to face.
        modules = bench.locator(".module")
        modules.nth(0).locator('.face.active .jack[data-type="output"]').first.click()
        modules.nth(1).locator('.face.active .jack[data-type="input"]').first.click()
        bench.wait_for_function(
            "() => document.querySelectorAll('path.cable').length === 1",
            timeout=5_000)

        assert bench.locator("#patch-cables path.cable").count() == 1
        assert bench.locator("#patch-cables-behind path.cable").count() == 0

    def test_turning_one_end_away_leaves_the_lead_half_in_half_out(self, bench):
        # One lead in two pieces, because its two ends are in different places
        # in the room: the half leaving the socket you can see is in the open,
        # and the half arriving behind the turned device is under it. Which
        # layer each half is on is read off the geometry every redraw, not
        # decided once when the cable was made.
        modules = bench.locator(".module")
        modules.nth(0).locator('.face.active .jack[data-type="output"]').first.click()
        modules.nth(1).locator('.face.active .jack[data-type="input"]').first.click()
        bench.wait_for_function(
            "() => document.querySelectorAll('path.cable').length === 1",
            timeout=5_000)
        assert bench.locator("#patch-cables path.cable").count() == 1

        modules.nth(1).click()
        bench.keyboard.press("t")
        bench.wait_for_function(
            "() => document.querySelectorAll("
            "'#patch-cables-behind path.cable').length === 1",
            timeout=5_000)

        # Still one lead, now drawn in two pieces - one per layer.
        assert bench.locator("#patch-cables path.cable").count() == 1
        assert bench.locator("#patch-cables-behind path.cable").count() == 1
        leads = bench.locator("path.cable").evaluate_all(
            "paths => new Set(paths.map(p => p.dataset.cable)).size")
        assert leads == 1

    def test_only_the_hidden_half_is_dashed(self, bench):
        # The dashes say "part of this run is behind something". Dashing the
        # half you can see says something untrue about it.
        modules = bench.locator(".module")
        modules.nth(0).locator('.face.active .jack[data-type="output"]').first.click()
        modules.nth(1).locator('.face.active .jack[data-type="input"]').first.click()
        bench.wait_for_function(
            "() => document.querySelectorAll('path.cable').length === 1",
            timeout=5_000)
        modules.nth(1).click()
        bench.keyboard.press("t")
        bench.wait_for_function(
            "() => document.querySelectorAll("
            "'#patch-cables-behind path.cable').length === 1",
            timeout=5_000)

        assert bench.locator("#patch-cables-behind path.cable.is-occluded").count() == 1
        assert bench.locator("#patch-cables path.cable.is-occluded").count() == 0

    def test_the_two_halves_meet(self, bench):
        # Or the lead has a gap in it where it crosses from one layer to the
        # other, which would read as two cables rather than one.
        modules = bench.locator(".module")
        modules.nth(0).locator('.face.active .jack[data-type="output"]').first.click()
        modules.nth(1).locator('.face.active .jack[data-type="input"]').first.click()
        bench.wait_for_function(
            "() => document.querySelectorAll('path.cable').length === 1",
            timeout=5_000)
        modules.nth(1).click()
        bench.keyboard.press("t")
        bench.wait_for_function(
            "() => document.querySelectorAll("
            "'#patch-cables-behind path.cable').length === 1",
            timeout=5_000)

        shared = bench.evaluate(
            """() => {
                const ends = (p) => {
                    const g = p.getTotalLength();
                    const a = p.getPointAtLength(0);
                    const b = p.getPointAtLength(g);
                    return [[a.x, a.y], [b.x, b.y]].map(
                        pt => pt.map(n => Math.round(n)).join(','));
                };
                const front = ends(document.querySelector('#patch-cables path.cable'));
                const back = ends(
                    document.querySelector('#patch-cables-behind path.cable'));
                return front.filter(p => back.includes(p)).length;
            }"""
        )
        assert shared == 1

    def test_the_palette_opens_at_its_default_corner(self, page):
        palette = page.locator("#tool-palette").bounding_box()
        viewport = page.viewport_size
        assert round(viewport["width"] - (palette["x"] + palette["width"])) == 20
        assert round(palette["y"]) == 68

    def test_the_console_is_clean(self, page):
        assert page.errors == []
