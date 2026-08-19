"""The rack, the menu and the panels, driven the way a hand drives them.

The stub harnesses model a DOM. This is one. Everything here is a real gesture
against the real page: geometry the stubs invent, CSS the stubs do not have,
and event ordering the stubs approximate.
"""

from __future__ import annotations

import pytest

from walkthrough.support import bare_rack, open_menu, pick, until


def ready(page, fragment: str, timeout: int = 8_000) -> None:
    """Wait for the status line to say the thing happened."""
    until(
        page,
        "() => (document.querySelector('#status')?.textContent || '')"
        f".includes({fragment!r})",
        timeout=timeout,
    )


class TestTheMenu:
    def test_right_click_opens_a_ring_of_six_families(self, page):
        # Six rather than eight, and every one of them opens something. The
        # ring used to mix families with actions, and which was which you
        # learned by trying.
        open_menu(page, *bare_rack(page))
        assert page.locator(".rad-wedge").count() == 6

        # Each label carries a chevron because each opens a submenu. Asserted
        # on the whole set: it is the one thing all six have in common, and
        # the reason the ring is learnable.
        labels = page.locator(".rad-label").all_text_contents()
        assert [text.rstrip(" ▸") for text in labels] == [
            "Add", "Rows", "View", "Patch", "MIDI", "All Devices"]

    def test_a_family_says_it_opens_something(self, page):
        # `▸` is the mark rad-android puts on a verb that opens a ring rather
        # than committing. Every wedge here carries it, which is the visible
        # half of "all six are families".
        open_menu(page, *bare_rack(page))
        labels = page.locator(".rad-label").all_text_contents()
        assert all(text.endswith("▸") for text in labels)

    def test_the_ring_is_announced(self, page):
        # It handled its own keys from the start, so it was operable and
        # unannounced: a screen reader met eight unlabelled shapes.
        open_menu(page, *bare_rack(page))
        layer = page.locator(".rad-layer")
        assert layer.get_attribute("role") == "menu"
        assert layer.get_attribute("aria-label")

        wedges = page.locator(".rad-wedge")
        for index in range(wedges.count()):
            wedge = wedges.nth(index)
            assert wedge.get_attribute("role") == "menuitem"
            assert wedge.get_attribute("aria-label")
            assert wedge.get_attribute("aria-posinset") == str(index + 1)

    def test_escape_closes_it(self, page):
        open_menu(page, *bare_rack(page))
        page.keyboard.press("Escape")
        assert page.locator(".rad-wedge").count() == 0

    def test_a_submenu_replaces_the_ring(self, page):
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        labels = page.locator(".rad-label").all_text_contents()
        assert any("Minimal" in text for text in labels)
        assert any("Reset panel" in text for text in labels)
        # The overlay's own exit, and the way back is this same ring.
        assert any("Hide panel" in text for text in labels)

    def test_a_right_click_on_a_device_opens_that_device_s_menu(self, page):
        module = page.locator(".module").first.bounding_box()
        page.mouse.click(
            module["x"] + module["width"] / 2,
            module["y"] + 8,
            button="right",
        )
        page.wait_for_selector(".rad-wedge", timeout=5_000)
        labels = " ".join(page.locator(".rad-label").all_text_contents())
        assert "Delete" in labels


class TestThePanelIsAnOverlaySurface:
    """The floating panel is somewhere the ring can always be reached.

    That is what rad-android's overlay is for: a window whose whole job is to
    be reachable when what is under your hand is not the thing you want to act
    on. And it can be dismissed, because a floating surface you cannot get rid
    of is one you are stuck with.
    """

    def test_the_panel_summons_the_rack_ring(self, page):
        grip = page.locator("#tool-palette-grip").bounding_box()
        page.mouse.click(grip["x"] + 40, grip["y"] + 10, button="right")
        page.wait_for_selector(".rad-wedge", timeout=5_000)
        assert page.locator(".rad-wedge").count() == 6

    def test_it_opens_at_the_touch_point_pulled_in_to_fit(self, page):
        # Summon opens the ring at the touch point, which is the whole of
        # rad-android's overlay gesture: press, drag, release, one gesture.
        #
        # The panel sits in a corner, so the ring is shifted inward to stay on
        # screen - the centre moves, the geometry never shrinks. Asserted both
        # ways round, because "near where you pressed" and "entirely visible"
        # is the pair of promises, and a ring that honoured only the first
        # would hang half off the window.
        grip = page.locator("#tool-palette-grip").bounding_box()
        x, y = grip["x"] + 40, grip["y"] + 10
        page.mouse.click(x, y, button="right")
        page.wait_for_selector(".rad-wedge", timeout=5_000)

        hub = page.locator(".rad-hub").bounding_box()
        centre = (hub["x"] + hub["width"] / 2, hub["y"] + hub["height"] / 2)
        viewport = page.viewport_size
        assert abs(centre[0] - x) < 150
        assert abs(centre[1] - y) < 150

        board = page.locator(".rad-backing").bounding_box()
        assert board["x"] >= 0
        assert board["y"] >= 0
        assert board["x"] + board["width"] <= viewport["width"]
        assert board["y"] + board["height"] <= viewport["height"]

    def test_a_field_inside_the_panel_keeps_its_own_menu(self, page):
        # Taking the right-click on a text field would cost the field its own
        # menu to give the rack a second door it already has.
        field = page.locator("#patch-name").bounding_box()
        page.mouse.click(field["x"] + 20, field["y"] + 8, button="right")
        page.wait_for_timeout(300)
        assert page.locator(".rad-wedge").count() == 0

    def test_the_panel_can_be_dismissed(self, page):
        assert page.locator("#tool-palette").is_visible()
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        pick(page, "Hide panel")
        ready(page, "Panel hidden")
        assert page.locator("#tool-palette").is_visible() is False

    def test_the_ring_brings_it_back(self, page):
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        pick(page, "Hide panel")
        ready(page, "Panel hidden")

        # The way back is the same ring, which the rack always answers to.
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        labels = page.locator(".rad-label").all_text_contents()
        assert any("Show panel" in text for text in labels)
        pick(page, "Show panel")
        ready(page, "Panel back")
        assert page.locator("#tool-palette").is_visible()

    def test_dismissing_it_keeps_where_it_was(self, page):
        # Dismissed, not deleted: it keeps its position and its state.
        grip = page.locator("#tool-palette-grip").bounding_box()
        page.mouse.move(grip["x"] + 40, grip["y"] + 10)
        page.mouse.down()
        page.mouse.move(grip["x"] + 40 - 120, grip["y"] + 10 + 90, steps=8)
        page.mouse.up()
        moved = page.locator("#tool-palette").bounding_box()

        open_menu(page, *bare_rack(page))
        pick(page, "View")
        pick(page, "Hide panel")
        ready(page, "Panel hidden")
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        pick(page, "Show panel")
        ready(page, "Panel back")

        assert page.locator("#tool-palette").bounding_box() == moved

    def test_the_ring_sits_on_a_board(self, page):
        # rad-android draws one soft, low-alpha blob behind its nodes - the
        # painter's palette the daubs are arranged on, which is where the word
        # comes from. Decoration, and it says so: no pointer events, no aria.
        open_menu(page, *bare_rack(page))
        board = page.locator(".rad-backing")
        assert board.count() == 1
        assert board.get_attribute("aria-hidden") == "true"

        paint = board.evaluate(
            """el => ({ fill: getComputedStyle(el).fill,
                        events: getComputedStyle(el).pointerEvents })"""
        )
        assert paint["fill"] == "rgba(136, 116, 196, 0.16)"
        assert paint["events"] == "none"

    def test_the_board_is_behind_the_wedges(self, page):
        # Or it would be a sheet over the thing it is meant to sit under.
        open_menu(page, *bare_rack(page))
        first = page.locator(".rad-layer g > *").first
        assert "rad-backing" in (first.get_attribute("class") or "")

    def test_nothing_throws_through_any_of_it(self, page):
        grip = page.locator("#tool-palette-grip").bounding_box()
        page.mouse.click(grip["x"] + 40, grip["y"] + 10, button="right")
        page.wait_for_selector(".rad-wedge", timeout=5_000)
        page.keyboard.press("Escape")
        assert page.errors == []


class TestHighContrast:
    """Colour comes out of every signal; the signal stays.

    rad-android's rule, and the reason its high-contrast mode is a correctness
    contract rather than a theme: idle and highlighted become black and white,
    the text inverts to match, and the decoration goes entirely because it
    carries nothing anyone has to read.

    Resolved from `prefers-contrast` — the browser already knows, and asking a
    second time in an app toggle would be a second answer to the same question.
    """

    @pytest.fixture
    def hard(self, page):
        page.emulate_media(contrast="more")
        yield page
        page.emulate_media(contrast="no-preference")

    def paint(self, page, selector):
        return page.locator(selector).first.evaluate(
            """el => ({ fill: getComputedStyle(el).fill,
                        stroke: getComputedStyle(el).stroke,
                        filter: getComputedStyle(el).filter })"""
        )

    def test_the_wedges_lose_their_colour(self, hard):
        open_menu(hard, *bare_rack(hard))
        wedge = self.paint(hard, ".rad-wedge")
        assert wedge["fill"] == "rgb(0, 0, 0)"
        assert wedge["stroke"] == "rgb(255, 255, 255)"

    def test_but_not_the_signal(self, hard):
        # Idle and highlighted still differ - that is the whole contract.
        open_menu(hard, *bare_rack(hard))
        idle = self.paint(hard, ".rad-wedge")
        picked = hard.locator(".rad-label", has_text="View").first.bounding_box()
        hard.mouse.move(picked["x"] + picked["width"] / 2,
                        picked["y"] + picked["height"] / 2)
        hot = self.paint(hard, ".rad-wedge.is-highlighted")
        assert hot["fill"] == "rgb(255, 255, 255)"
        assert hot["fill"] != idle["fill"]

    def test_the_shadow_goes(self, hard):
        # Depth for a colour swap that no longer happens, and a grey blur under
        # a white shape is the one thing this mode cannot afford.
        open_menu(hard, *bare_rack(hard))
        target = hard.locator(".rad-label", has_text="View").first.bounding_box()
        hard.mouse.move(target["x"] + target["width"] / 2,
                        target["y"] + target["height"] / 2)
        assert self.paint(hard, ".rad-wedge.is-highlighted")["filter"] == "none"

    def test_the_decoration_goes(self, hard):
        open_menu(hard, *bare_rack(hard))
        board = hard.locator(".rad-backing").evaluate(
            "el => getComputedStyle(el).fill")
        assert board == "rgba(0, 0, 0, 0)"

    def test_destructive_is_still_marked_without_colour(self, hard):
        # The dashes were half the signal and are now all of it.
        open_menu(hard, *bare_rack(hard))
        pick(hard, "All Devices")
        marked = hard.locator(".rad-wedge.is-destructive")
        assert marked.count() == 1
        dashes = marked.evaluate("el => getComputedStyle(el).strokeDasharray")
        assert dashes not in ("none", "")

    def test_the_ring_still_works(self, hard):
        # A mode that changes what things look like must not change what they
        # do. This is the same gesture, driven the same way.
        open_menu(hard, *bare_rack(hard))
        pick(hard, "View")
        labels = hard.locator(".rad-label").all_text_contents()
        assert any("Minimal" in text for text in labels)

    def test_ordinary_contrast_keeps_the_family_colours(self, page):
        # The other side of it: nothing above leaks into the normal mode.
        open_menu(page, *bare_rack(page))
        assert page.locator(".rad-wedge").first.evaluate(
            "el => getComputedStyle(el).fill") == "rgb(75, 59, 117)"


class TestTheRingLooksLikeRad:
    """The ring follows the family rather than this app.

    rad-android is the most fully branded surface in the family, and a menu
    that looks like its host instead of like rad is a menu somebody has to
    learn twice. Its palette is red-free neon — violet wedges, a turquoise
    hub, lime for the zone that commits — and its wedges get depth from a gap
    and a shadow rather than from a flat colour swap.
    """

    def hub_text(self, page):
        return " ".join(
            page.locator("#rad-menu-title tspan").all_text_contents()).strip()

    def aim(self, page, label):
        """Point at a wedge without committing it.

        Not `hover()`: the ring's layer is `pointer-events: none` on purpose,
        so the rack underneath swallows the hover and the wedge never learns it
        was pointed at. The menu resolves a *position* into a wedge — it
        listens on the document and knows nothing about the element under the
        cursor — so this moves the real pointer and stops there.
        """
        target = page.locator(".rad-label", has_text=label).first
        target.wait_for(state="visible", timeout=5_000)
        box = target.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2,
                        box["y"] + box["height"] / 2)

    def test_the_hub_names_what_you_are_pointing_at(self, page):
        # The rule that lets a wedge be short: the hub is the one place a full
        # name is ever spelled out, so a wedge only has to be recognised.
        open_menu(page, *bare_rack(page))
        assert self.hub_text(page) == "Rack"

        self.aim(page, "Patch")
        assert self.hub_text(page) == "Patch"

    def test_the_hub_says_so_when_it_is_naming_a_choice(self, page):
        open_menu(page, *bare_rack(page))
        title = page.locator("#rad-menu-title")
        assert title.get_attribute("data-highlighted") is None

        self.aim(page, "Rows")
        assert title.get_attribute("data-highlighted") == "true"

    def test_a_long_name_wraps_rather_than_being_cut(self, page):
        # Ellipsis is banned by the contract, so truncating was never the fix.
        # A name too wide for the hub breaks at a word instead.
        open_menu(page, *bare_rack(page))
        self.aim(page, "All Devices")
        lines = page.locator("#rad-menu-title tspan").all_text_contents()
        assert lines == ["All", "Devices"]
        assert "…" not in "".join(lines)
        assert "..." not in "".join(lines)

    def test_no_wedge_label_is_ever_truncated(self, page):
        open_menu(page, *bare_rack(page))
        for text in page.locator(".rad-label").all_text_contents():
            assert "…" not in text
            assert "..." not in text

    def test_the_wedges_wear_the_family_violet(self, page):
        open_menu(page, *bare_rack(page))
        fill = page.locator(".rad-wedge").first.evaluate(
            "el => getComputedStyle(el).fill")
        # #4b3b75
        assert fill == "rgb(75, 59, 117)"

    def test_the_one_you_are_pointing_at_lifts(self, page):
        # A gap and a shadow rather than a flat colour swap alone, which is
        # rad-android's answer to a ring that otherwise reads as painted on.
        open_menu(page, *bare_rack(page))
        self.aim(page, "View")
        wedge = page.locator(".rad-wedge.is-highlighted")
        style = wedge.evaluate(
            """el => ({
                fill: getComputedStyle(el).fill,
                filter: getComputedStyle(el).filter,
                stroke: getComputedStyle(el).strokeWidth,
            })"""
        )
        assert style["fill"] == "rgb(184, 79, 255)"   # #b84fff
        assert "drop-shadow" in style["filter"]
        assert float(style["stroke"].removesuffix("px")) >= 2

    def test_the_hub_is_the_family_turquoise(self, page):
        open_menu(page, *bare_rack(page))
        hub = page.locator(".rad-hub").evaluate(
            """el => ({ fill: getComputedStyle(el).fill,
                        stroke: getComputedStyle(el).stroke })"""
        )
        assert hub["fill"] == "rgb(36, 27, 54)"      # #241b36
        assert hub["stroke"] == "rgb(45, 226, 230)"  # #2de2e6

    def test_nothing_on_the_ring_is_red(self, page):
        # The family palette is red-free so that red never has to mean two
        # things. Destructive is marked by the lime the push zone uses.
        open_menu(page, *bare_rack(page))
        pick(page, "All Devices")
        reds = page.locator(".rad-wedge").evaluate_all(
            """wedges => wedges.map(w => {
                const style = getComputedStyle(w);
                return [style.fill, style.stroke];
            }).flat().filter(colour => {
                const m = colour.match(/rgb\\((\\d+), (\\d+), (\\d+)\\)/);
                if (!m) return false;
                const [r, g, b] = m.slice(1).map(Number);
                return r > 150 && g < 110 && b < 110;
            })"""
        )
        assert reds == []

    def test_the_destructive_one_is_marked_without_red(self, page):
        open_menu(page, *bare_rack(page))
        pick(page, "All Devices")
        marked = page.locator(".rad-wedge.is-destructive")
        assert marked.count() == 1
        stroke = marked.evaluate("el => getComputedStyle(el).stroke")
        assert stroke == "rgb(212, 255, 79)"   # #d4ff4f, the push-zone lime


class TestPatchingAndUnpatching:
    def test_clicking_two_sockets_makes_a_cable(self, bench):
        before = bench.locator("path.cable").count()
        modules = bench.locator(".module")
        modules.nth(0).locator('.face.active .jack[data-type="output"]').first.click()
        modules.nth(1).locator('.face.active .jack[data-type="input"]').first.click()
        until(
            bench,
            f"() => document.querySelectorAll('path.cable').length > {before}",
        )
        assert bench.locator("path.cable").count() == before + 1

    def test_a_cable_can_be_pulled_out_again(self, bench):
        modules = bench.locator(".module")
        modules.nth(0).locator('.face.active .jack[data-type="output"]').first.click()
        modules.nth(1).locator('.face.active .jack[data-type="input"]').first.click()
        until(bench, "() => document.querySelectorAll('path.cable').length === 1")

        # The menu on a device offers to pull every lead out of it. Reaching a
        # cable itself needs the geometry probe, which is covered by the model
        # harness; this is the path a hand takes.
        module = modules.nth(0).bounding_box()
        bench.mouse.click(module["x"] + module["width"] / 2, module["y"] + 8,
                         button="right")
        bench.wait_for_selector(".rad-wedge", timeout=5_000)
        pick(bench, "Unpatch")

        until(bench, "() => document.querySelectorAll('path.cable').length === 0")
        assert bench.locator("path.cable").count() == 0

    def test_two_outputs_refuse_each_other(self, bench):
        modules = bench.locator(".module")
        modules.nth(0).locator('.face.active .jack[data-type="output"]').first.click()
        modules.nth(1).locator('.face.active .jack[data-type="output"]').first.click()
        assert "cannot" in bench.locator("#status").inner_text().lower()
        assert bench.locator("path.cable").count() == 0


class TestDrawnAsLaidOut:
    @pytest.fixture
    def drum_rig(self, page):
        open_menu(page, *bare_rack(page))
        # Under Patch: examples are whole-rig operations, and the rack ring
        # is six families rather than a mix of families and actions.
        pick(page, "Patch")
        pick(page, "Examples")
        pick(page, "controller")
        pick(page, "Launchpad X")
        ready(page, "Imported")
        return page

    def test_the_example_loads_a_whole_rack(self, drum_rig):
        assert drum_rig.locator(".module").count() == 4
        # Leads, not pieces: a lead with one end round the back is drawn in two
        # halves on two layers, and counting paths counts halves.
        leads = drum_rig.locator("path.cable").evaluate_all(
            "paths => new Set(paths.map(p => p.dataset.cable)).size")
        assert leads == 4

    def test_it_arrives_drawn_as_laid_out(self, drum_rig):
        assert drum_rig.locator("body").get_attribute("data-display-mode") == "irl"

    def test_a_grid_controller_draws_its_grid(self, drum_rig):
        grid = drum_rig.locator('[data-module-id="grid"]')
        assert grid.locator(".irl-pads .irl-cell").count() == 64

    def test_a_pad_press_lights_the_device_bound_to_it(self, drum_rig):
        pad = drum_rig.locator('[data-module-id="grid"] .irl-pads button.irl-cell').first
        assert pad.get_attribute("title") == "note 36 ch 10"

        pad.click()
        ready(drum_rig, "note 36")
        assert "is-active" in drum_rig.locator('[data-module-id="kick"]').get_attribute("class")
        # And the voice bound to a different note stays dark.
        assert "is-active" not in drum_rig.locator('[data-module-id="clap"]').get_attribute("class")

    def test_the_light_goes_out_on_its_own(self, drum_rig):
        drum_rig.locator('[data-module-id="grid"] .irl-pads button.irl-cell').first.click()
        until(
            drum_rig,
            "() => !document.querySelector('[data-module-id=\"kick\"]')"
            ".classList.contains('is-active')",
        )

    def test_a_screen_shows_what_its_entry_says_it_reads(self, drum_rig):
        screen = drum_rig.locator('[data-module-id="grid"] .face.active .irl-screen')
        assert screen.get_attribute("data-source") == "last-event"

        drum_rig.locator('[data-module-id="grid"] .irl-pads button.irl-cell').first.click()
        ready(drum_rig, "note 36")
        assert screen.locator(".irl-screen-text").inner_text() == "NOTE 36 CH 10"

    def test_switching_to_minimal_keeps_the_devices(self, drum_rig):
        open_menu(drum_rig, *bare_rack(drum_rig))
        pick(drum_rig, "View")
        pick(drum_rig, "Minimal")
        until(
            drum_rig,
            "() => document.body.dataset.displayMode === 'minimal'",
        )
        assert drum_rig.locator(".module").count() == 4
        assert drum_rig.locator(".irl-pads").count() == 0

    def test_nothing_throws_through_any_of_it(self, drum_rig):
        assert drum_rig.errors == []


class TestTheFourThingsYouCanPointAt:
    """Device, cable, row, canvas — each resolves to its own menu.

    A row used to fall through to the rack menu, so the only way to act on one
    was the small x in its header: one click target, one action, and no way to
    turn a row or empty it.
    """

    @pytest.fixture
    def rowed(self, bench):
        """Two devices, both in a row of their own."""
        bench.evaluate(
            """() => {
                const row = system.createRow();
                [...system.modules.keys()].forEach(
                    id => system.assignToGroup(id, row.id));
                return row.id;
            }"""
        )
        return bench

    def right_click(self, page, locator, dx=40, dy=8):
        box = locator.bounding_box()
        page.mouse.click(box["x"] + dx, box["y"] + dy, button="right")
        page.wait_for_selector(".rad-wedge", timeout=5_000)
        return page.locator(".rad-label").all_text_contents()

    def test_a_row_opens_the_row_menu(self, rowed):
        labels = self.right_click(rowed, rowed.locator(".rack-group-header"))
        assert any("Delete Row" in text for text in labels)
        assert any("Empty Row" in text for text in labels)
        assert any("Turn Row" in text for text in labels)

    def test_the_menu_names_the_row_and_counts_it(self, rowed):
        self.right_click(rowed, rowed.locator(".rack-group-header"))
        # `text_content`: the ring's title is an SVG text node, not an
        # HTMLElement, so there is no rendered text to read.
        title = rowed.locator(".rad-title").text_content()
        assert "Row" in title
        assert "(2)" in title

    def test_a_device_inside_a_row_still_opens_its_own_menu(self, rowed):
        # The device wins over the row it sits in, because that is what you are
        # pointing at. Ordering, not a special case.
        labels = self.right_click(rowed, rowed.locator(".module").first)
        assert any("Delete" == text for text in labels)
        assert not any("Delete Row" in text for text in labels)

    def test_turning_a_row_turns_what_is_in_it(self, rowed):
        before = rowed.locator(".module .face.active").evaluate_all(
            "faces => faces.map(f => f.dataset.side)")
        self.right_click(rowed, rowed.locator(".rack-group-header"))
        pick(rowed, "Turn Row")
        ready(rowed, "Turned")
        after = rowed.locator(".module .face.active").evaluate_all(
            "faces => faces.map(f => f.dataset.side)")
        assert after != before

    def test_emptying_a_row_keeps_the_devices(self, rowed):
        self.right_click(rowed, rowed.locator(".rack-group-header"))
        pick(rowed, "Empty Row")
        ready(rowed, "loose in the rack")
        assert rowed.locator(".module").count() == 2
        assert rowed.locator(".rack-group").count() == 1

    def test_deleting_a_row_keeps_the_devices(self, rowed):
        # A grouping is a way of looking at a rack, not a container the gear
        # lives inside, so losing it can never cost you gear.
        self.right_click(rowed, rowed.locator(".rack-group-header"))
        pick(rowed, "Delete Row")
        ready(rowed, "devices are loose")
        assert rowed.locator(".rack-group").count() == 0
        assert rowed.locator(".module").count() == 2

    def test_the_rack_itself_still_answers(self, bench):
        open_menu(bench, *bare_rack(bench))
        labels = bench.locator(".rad-label").all_text_contents()
        assert any(text.startswith("Add") for text in labels)

    def test_nothing_throws_through_any_of_it(self, rowed):
        self.right_click(rowed, rowed.locator(".rack-group-header"))
        rowed.keyboard.press("Escape")
        assert rowed.errors == []


class TestOnlyTheFacesThatHaveSomething:
    """A device shows the sides it draws, and opens on the one you look at.

    Four devices in the catalogue have a front with nothing on it - the blank
    lip under a stage piano's keys, under a Launchpad's pads. Turning one used
    to walk you through that lip on the way to its sockets: a press that showed
    a blank rectangle and then had to be pressed again.
    """

    @pytest.fixture
    def drum_rig(self, page):
        open_menu(page, *bare_rack(page))
        # Under Patch: examples are whole-rig operations, and the rack ring
        # is six families rather than a mix of families and actions.
        pick(page, "Patch")
        pick(page, "Examples")
        pick(page, "controller")
        pick(page, "Launchpad X")
        ready(page, "Imported")
        return page

    def test_a_device_played_from_above_draws_no_front(self, drum_rig):
        grid = drum_rig.locator('[data-module-id="grid"]')
        sides = grid.locator(".face").evaluate_all(
            "faces => faces.map(f => f.dataset.side)")
        assert "front" not in sides
        assert set(sides) == {"back", "top"}

    def test_and_opens_on_its_top(self, drum_rig):
        grid = drum_rig.locator('[data-module-id="grid"]')
        assert grid.locator(".face.active").get_attribute("data-side") == "top"

    def test_turning_it_never_lands_on_a_blank_face(self, drum_rig):
        # Every side it stops on, all the way round twice. The bug was not that
        # the lip was reachable, it was that it was unavoidable.
        grid = drum_rig.locator('[data-module-id="grid"]')
        grid.click()
        seen = []
        for _ in range(4):
            drum_rig.keyboard.press("t")
            seen.append(
                grid.locator(".face.active").get_attribute("data-side"))
        assert "front" not in seen
        assert set(seen) == {"back", "top"}

    def test_every_device_shows_exactly_one_face(self, drum_rig):
        counts = drum_rig.locator(".module").evaluate_all(
            "modules => modules.map("
            "m => m.querySelectorAll('.face.active').length)")
        assert counts and set(counts) == {1}

    def test_a_face_that_is_drawn_is_never_empty(self, drum_rig):
        # The rule stated the other way round, over every face in the rack:
        # anything drawn carries something. A face whose only child is its
        # title is the blank rectangle this removed.
        empty = drum_rig.locator(".module").evaluate_all(
            """modules => modules.flatMap(m =>
                [...m.querySelectorAll('.face')]
                    .filter(f => f.children.length <= 1)
                    .map(f => m.dataset.moduleId + ':' + f.dataset.side))"""
        )
        assert empty == []

    def test_a_device_with_a_front_still_opens_on_it(self, bench):
        # The other half: nothing here refaces a device that has a front.
        first = bench.locator(".module").first
        assert first.locator(".face.active").get_attribute("data-side") == "front"

    def test_nothing_throws_through_any_of_it(self, drum_rig):
        assert drum_rig.errors == []


class TestThePalette:
    def test_dragging_it_moves_it_by_what_the_hand_moved(self, page):
        before = page.locator("#tool-palette").bounding_box()
        grip = page.locator("#tool-palette-grip").bounding_box()

        page.mouse.move(grip["x"] + 40, grip["y"] + 10)
        page.mouse.down()
        page.mouse.move(grip["x"] + 40 - 200, grip["y"] + 10 + 160, steps=10)
        page.mouse.up()

        after = page.locator("#tool-palette").bounding_box()
        assert round(before["x"] - after["x"]) == 200
        assert round(after["y"] - before["y"]) == 160

    def test_it_cannot_be_dragged_off_the_screen(self, page):
        grip = page.locator("#tool-palette-grip").bounding_box()
        page.mouse.move(grip["x"] + 40, grip["y"] + 10)
        page.mouse.down()
        page.mouse.move(-4000, -4000, steps=10)
        page.mouse.up()

        after = page.locator("#tool-palette").bounding_box()
        viewport = page.viewport_size
        assert after["x"] + after["width"] > 0
        assert after["y"] >= 0
        assert after["x"] < viewport["width"]

    def test_the_menu_puts_it_back(self, page):
        default = page.locator("#tool-palette").bounding_box()
        grip = page.locator("#tool-palette-grip").bounding_box()

        page.mouse.move(grip["x"] + 40, grip["y"] + 10)
        page.mouse.down()
        page.mouse.move(grip["x"] - 160, grip["y"] + 120, steps=8)
        page.mouse.up()
        assert page.locator("#tool-palette").bounding_box() != default

        open_menu(page, *bare_rack(page))
        pick(page, "View")
        pick(page, "Reset panel")
        ready(page, "back to where it starts")
        assert page.locator("#tool-palette").bounding_box() == default
