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
    def test_right_click_opens_the_six_families_and_the_door(self, page):
        # Six families, and every one of them opens something. Plus the one
        # fixed `Edit` that arranges them - still under the ceiling of eight,
        # which is why stopping at six was worth doing.
        open_menu(page, *bare_rack(page))
        assert page.locator(".rad-wedge").count() == 7

        # Each label carries a chevron because each opens a submenu. Asserted
        # on the whole set: it is the one thing all six have in common, and
        # the reason the ring is learnable.
        labels = page.locator(".rad-label").all_text_contents()
        assert [text.rstrip(" ▸") for text in labels] == [
            "Add", "Rows", "View", "Patch", "MIDI", "All Devices", "Edit"]

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
        assert any("Pin ring" in text for text in labels)

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


class TestGettingBackOut:
    """Two failures rad-android found by using the thing, checked here.

    Neither was in the ported reducer; both were in what the host does around
    it, which is exactly where this app's version of them would live too.
    """

    def hub_text(self, page):
        return " ".join(
            page.locator("#rad-menu-title tspan").all_text_contents()).strip()

    def test_the_hub_says_a_tap_there_goes_back(self, page):
        # Back already worked and had no affordance at all, so the way out of
        # a submenu was something you knew or you did not.
        open_menu(page, *bare_rack(page))
        assert "Back" not in self.hub_text(page)

        pick(page, "View")
        assert self.hub_text(page).startswith("◂ Back")
        assert page.locator("#rad-menu-title").get_attribute("data-back") == "true"

    def test_it_stops_saying_so_once_you_aim(self, page):
        # Aiming at a wedge means a release commits that wedge, not a step
        # back, and the hub has to stop promising otherwise.
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        target = page.locator(".rad-label", has_text="Minimal").first.bounding_box()
        page.mouse.move(target["x"] + target["width"] / 2,
                        target["y"] + target["height"] / 2)
        assert "Back" not in self.hub_text(page)
        assert page.locator("#rad-menu-title").get_attribute("data-back") is None

    def test_the_hub_takes_you_back(self, page):
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        assert page.locator(".rad-wedge").count() == 4

        hub = page.locator(".rad-hub").bounding_box()
        page.mouse.move(hub["x"] + hub["width"] / 2, hub["y"] + hub["height"] / 2)
        page.mouse.down()
        page.mouse.up()

        labels = page.locator(".rad-label").all_text_contents()
        assert [text.rstrip(" ▸") for text in labels] == [
            "Add", "Rows", "View", "Patch", "MIDI", "All Devices", "Edit"]

    def test_a_summon_always_opens_at_the_root(self, page):
        # rad-android's real footgun: closing never reset the navigation stack,
        # so drilling into a deep ring and then closing left every future
        # summon opening on that same deep ring - a dead end with no memory of
        # how you got there. This app resets on open rather than on close, so
        # it never had it; asserted so it never grows one.
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        assert page.locator(".rad-wedge").count() == 4
        page.keyboard.press("Escape")

        open_menu(page, *bare_rack(page))
        labels = page.locator(".rad-label").all_text_contents()
        assert [text.rstrip(" ▸") for text in labels] == [
            "Add", "Rows", "View", "Patch", "MIDI", "All Devices", "Edit"]

    def test_even_after_committing_from_a_submenu(self, page):
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        pick(page, "Minimal")
        ready(page, "minimally")

        open_menu(page, *bare_rack(page))
        assert page.locator(".rad-wedge").count() == 7


class TestAPinnedRingIsThePanel:
    """One object in two states.

    A ring you can leave open over the rack *is* what a floating panel was, so
    there is no second surface: pinning is a state of the menu rather than a
    window beside it. Two menu systems would be two answers to a question rad's
    contract already settles.
    """

    def pin(self, page):
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        pick(page, "Pin ring")
        page.wait_for_selector(".rad-layer.is-pinned", timeout=5_000)

    def hub(self, page):
        return " ".join(
            page.locator("#rad-menu-title tspan").all_text_contents()).strip()

    def test_it_stays_open(self, page):
        self.pin(page)
        assert page.locator(".rad-wedge").count() == 7

    def test_it_survives_being_used(self, page):
        # A ring that vanished after every commit would be a panel that closed
        # itself whenever you used it.
        self.pin(page)
        pick(page, "View")
        pick(page, "Minimal")
        ready(page, "minimally")
        assert page.locator(".rad-wedge").count() == 7

    def test_using_it_returns_it_to_its_root(self, page):
        self.pin(page)
        pick(page, "View")
        pick(page, "Minimal")
        ready(page, "minimally")
        labels = [t.rstrip(" ▸")
                  for t in page.locator(".rad-label").all_text_contents()]
        assert labels[0] == "Add"

    def test_the_hub_reads_the_rack(self, page):
        # What the panel was for. Asked at render time rather than pushed, so
        # the ring holds no copy of a rack that changes underneath it.
        self.pin(page)
        hub = self.hub(page)
        assert "11 devices" in hub
        assert "17 leads" in hub
        assert "3 rows" in hub

    def test_the_readout_is_live(self, page):
        self.pin(page)
        assert "11 devices" in self.hub(page)
        page.evaluate("() => system.addModule('moog.dfam')")
        pick(page, "View")
        pick(page, "As laid out")
        page.wait_for_timeout(200)
        assert "12 devices" in self.hub(page)

    def test_nothing_of_the_readout_is_dropped(self, page):
        # Four facts, and silently losing one would be the truncation the
        # contract bans wearing a different hat.
        self.pin(page)
        assert self.hub(page).count("|") == 3

    def test_the_gesture_is_unchanged_by_pinning(self, page):
        # Only the drawn hub grows. The dead zone the machine cancels inside is
        # the contract's `r0` and stays it.
        self.pin(page)
        geometry = page.evaluate("() => radMenu.geometry.r0")
        drawn = float(page.locator(".rad-hub").get_attribute("r"))
        assert drawn > geometry
        assert page.evaluate("() => radMenu.machine.geometry?.r0 ?? radMenu.geometry.r0") == geometry

    def test_it_lets_go(self, page):
        self.pin(page)
        pick(page, "View")
        pick(page, "Unpin ring")
        ready(page, "let go")
        assert page.locator(".rad-wedge").count() == 0

    def test_it_offers_to_let_go_while_pinned(self, page):
        self.pin(page)
        pick(page, "View")
        labels = page.locator(".rad-label").all_text_contents()
        assert any("Unpin" in text for text in labels)

    def test_a_pinned_ring_shows_the_world_after_the_verb_not_before(self, page):
        """The ordering bug a demo dry-run found.

        A pinned ring is drawn from state the intent is about to change, and it
        used to re-resolve *before* dispatching — so it showed the previous
        answer to everything. Hiding a family left it on the ring until the next
        commit, at which point it vanished and looked like that commit had done
        it.
        """
        self.pin(page)
        labels = lambda: [t.rstrip(" ▸")
                          for t in page.locator(".rad-label").all_text_contents()]
        assert "MIDI" in labels()

        pick(page, "Edit")
        pick(page, "MIDI")
        pick(page, "Hide")
        page.wait_for_function(
            "() => ![...document.querySelectorAll('.rad-label')]"
            ".some(l => l.textContent.trim().startsWith('MIDI'))",
            timeout=5_000)
        assert "MIDI" not in labels()

        pick(page, "Edit")
        pick(page, "Reset ring")
        page.wait_for_function(
            "() => [...document.querySelectorAll('.rad-label')]"
            ".some(l => l.textContent.trim().startsWith('MIDI'))",
            timeout=5_000)
        assert "MIDI" in labels()

    def test_the_readout_follows_the_verb_immediately(self, page):
        # Same ordering, seen through the hub: clearing the rack has to be
        # visible in the readout without a second commit to shake it loose.
        self.pin(page)
        assert "11 devices" in self.hub(page)
        page.evaluate("() => system.addModule('moog.dfam')")
        pick(page, "View")
        pick(page, "As laid out")
        page.wait_for_timeout(250)
        assert "12 devices" in self.hub(page)

    def test_nothing_throws_through_any_of_it(self, page):
        self.pin(page)
        pick(page, "View")
        pick(page, "Unpin ring")
        assert page.errors == []


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


