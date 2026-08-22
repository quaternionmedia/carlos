"""The rack, the menu and the panels, driven the way a hand drives them.

The stub harnesses model a DOM. This is one. Everything here is a real gesture
against the real page: geometry the stubs invent, CSS the stubs do not have,
and event ordering the stubs approximate.
"""

from __future__ import annotations

import pytest

from walkthrough.support import bare_rack, open_menu, pick, until
from walkthrough.support import was_lit, watch_class


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
        assert any("Unpin ring" in text for text in labels)

    def test_a_right_click_survives_the_release_that_opened_it(self, page):
        """The platform difference that cost the first CI run.

        `contextmenu` fires on pointer *down* on Linux and on pointer *up* on
        Windows. Opened from it, a ring on Linux is still owed a release — which
        reaches it, lands in the dead zone at its centre and cancels it. A
        right-click opened a ring and shut it in the same gesture; this
        workstation never saw it, and thirty-nine tests went down on the first
        remote run.

        Driven by dispatching the events in Linux order, so the ordering is
        covered wherever this runs rather than only where it broke.
        """
        x, y = bare_rack(page)
        opened = page.evaluate(
            """([x, y]) => {
                const target = document.elementFromPoint(x, y);
                const of = (type, extra) => new PointerEvent(type, {
                    bubbles: true, cancelable: true, clientX: x, clientY: y,
                    button: 2, buttons: 2, pointerId: 1, ...extra,
                });
                target.dispatchEvent(of('pointerdown'));
                // Linux: the context menu arrives while the button is down.
                target.dispatchEvent(new MouseEvent('contextmenu', {
                    bubbles: true, cancelable: true, clientX: x, clientY: y,
                    button: 2,
                }));
                const during = document.querySelectorAll('.rad-wedge').length;
                target.dispatchEvent(of('pointerup', { buttons: 0 }));
                return {
                    during,
                    after: document.querySelectorAll('.rad-wedge').length,
                };
            }""",
            [x, y])

        assert opened["during"] == 7, "the right-click did not open a ring"
        assert opened["after"] == 7, (
            "the release that opened the ring closed it again")

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


class TestMovingADevice:
    """A handle in the corner opposite the flip.

    Turning a device and moving it are the two things you do to a whole device
    rather than to something on it, so they take the two top corners and each
    keeps its own. A grip sharing a corner with a button would be a grip that
    sometimes turned the device instead.
    """

    def layout(self, page):
        return page.evaluate(
            """() => [...document.querySelectorAll('.rack-group, .rack-loose')]
                .map(shelf => ({
                    row: shelf.dataset.groupId || 'loose',
                    devices: [...shelf.querySelectorAll(':scope .module')]
                        .map(m => m.dataset.moduleId),
                }))"""
        )

    def row(self, page, name):
        for shelf in self.layout(page):
            if shelf["row"] == name:
                return shelf["devices"]
        return []

    def drag(self, page, moving, onto, steps=10):
        grip = page.locator(f'[data-module-id="{moving}"] .module-move').bounding_box()
        target = page.locator(f'[data-module-id="{onto}"]').bounding_box()
        page.mouse.move(grip["x"] + 9, grip["y"] + 9)
        page.mouse.down()
        page.mouse.move(target["x"] + 6, target["y"] + 40, steps=steps)
        page.mouse.up()
        page.wait_for_timeout(200)

    def test_every_device_has_one(self, page):
        assert page.locator(".module-move").count() == page.locator(".module").count()

    def test_it_is_in_the_corner_opposite_the_flip(self, page):
        corners = page.evaluate(
            """() => {
                const m = document.querySelector('.module');
                const box = m.getBoundingClientRect();
                const grip = m.querySelector('.module-move').getBoundingClientRect();
                const flip = m.querySelector('.module-flip').getBoundingClientRect();
                return {
                    gripFromLeft: Math.round(grip.left - box.left),
                    flipFromRight: Math.round(box.right - flip.right),
                    gripFromTop: Math.round(grip.top - box.top),
                    flipFromTop: Math.round(flip.top - box.top),
                };
            }"""
        )
        # Mirrored: the same inset from opposite sides, at the same height.
        assert corners["gripFromLeft"] == corners["flipFromRight"]
        assert corners["gripFromTop"] == corners["flipFromTop"]

    def test_dragging_it_reorders_the_row(self, page):
        assert self.row(page, "row-control") == ["grid", "seq", "keys"]
        self.drag(page, "keys", "grid")
        assert self.row(page, "row-control") == ["keys", "grid", "seq"]

    def test_a_bar_shows_the_gap_it_will_land_in(self, page):
        # A bar between two devices rather than a highlight on one, because the
        # answer is a gap and not a neighbour.
        grip = page.locator('[data-module-id="keys"] .module-move').bounding_box()
        first = page.locator('[data-module-id="grid"]').bounding_box()
        page.mouse.move(grip["x"] + 9, grip["y"] + 9)
        page.mouse.down()
        page.mouse.move(first["x"] + 6, first["y"] + 40, steps=10)

        assert page.locator(".rack-drop").count() == 1
        page.mouse.up()
        page.wait_for_timeout(200)
        assert page.locator(".rack-drop").count() == 0

    def test_what_you_carry_is_the_device_itself(self, page):
        """Not a copy of it.

        The cable preview is drawn by the routine that draws the real cable, so
        it cannot disagree with what it previews. A device is already rendered,
        so the honest preview is *it*, lifted out of the flow and put under the
        hand. A clone would be a second copy whose screens and lit pads could
        drift from the original's inside one drag.
        """
        grip = page.locator('[data-module-id="keys"] .module-move').bounding_box()
        page.mouse.move(grip["x"] + 9, grip["y"] + 9)
        page.mouse.down()
        page.mouse.move(grip["x"] + 209, grip["y"] + 260, steps=10)

        carried = page.evaluate(
            """() => {
                const all = document.querySelectorAll('[data-module-id="keys"]');
                const style = getComputedStyle(all[0]);
                return {
                    copies: all.length,
                    position: style.position,
                    // Under the hand, so it must not be what the hand is over:
                    // the drop target is asked of the page, and a carried
                    // device would answer every time.
                    events: style.pointerEvents,
                };
            }"""
        )
        page.mouse.up()
        page.wait_for_timeout(200)

        assert carried["copies"] == 1
        assert carried["position"] == "fixed"
        assert carried["events"] == "none"

    def test_it_comes_with_the_hand(self, page):
        before = page.locator('[data-module-id="keys"]').bounding_box()
        grip = page.locator('[data-module-id="keys"] .module-move').bounding_box()
        page.mouse.move(grip["x"] + 9, grip["y"] + 9)
        page.mouse.down()
        page.mouse.move(grip["x"] + 209, grip["y"] + 260, steps=10)
        during = page.locator('[data-module-id="keys"]').bounding_box()
        page.mouse.up()
        page.wait_for_timeout(200)

        # Where the hand went, to the pixel: the pointer travelled (200, 251)
        # from where it went down, so the device did too.
        assert round(during["x"] - before["x"]) == 209 - 9
        assert round(during["y"] - before["y"]) == 260 - 9

    def test_the_gap_is_as_wide_as_the_device(self, page):
        # The room being made, not a line between two things: a hairline tells
        # you the order, and the point of carrying it is to see it fit.
        held = page.locator('[data-module-id="keys"]').bounding_box()
        grip = page.locator('[data-module-id="keys"] .module-move').bounding_box()
        first = page.locator('[data-module-id="grid"]').bounding_box()
        page.mouse.move(grip["x"] + 9, grip["y"] + 9)
        page.mouse.down()
        page.mouse.move(first["x"] + 6, first["y"] + 40, steps=10)
        gap = page.locator(".rack-drop").bounding_box()
        page.mouse.up()
        page.wait_for_timeout(200)

        assert abs(gap["width"] - held["width"]) <= 4

    def test_the_leads_follow_while_you_carry_it(self, page):
        drawn = """() => {
            const out = {};
            document.querySelectorAll('path.cable').forEach(path => {
                const name = path.dataset.cable || '';
                if (name.startsWith('keys:')) out[name] = path.getAttribute('d');
            });
            return out;
        }"""
        at_rest = page.evaluate(drawn)
        assert at_rest, "keys should have leads to follow it"

        grip = page.locator('[data-module-id="keys"] .module-move').bounding_box()
        page.mouse.move(grip["x"] + 9, grip["y"] + 9)
        page.mouse.down()
        page.mouse.move(grip["x"] + 9, grip["y"] + 340, steps=10)
        page.wait_for_timeout(150)
        carried = page.evaluate(drawn)
        page.mouse.up()
        page.wait_for_timeout(200)

        # Every one of them, because they are drawn from where the sockets
        # actually are and the sockets have moved.
        assert set(carried) == set(at_rest)
        assert all(carried[name] != at_rest[name] for name in at_rest)

    def test_holding_still_holds_the_landing_still(self, page):
        # The gap is as wide as the device, so placing it shifts the row - and a
        # row that shifts changes the answer to where the pointer is aiming. If
        # that fed back on itself the bar would flicker between two slots.
        grip = page.locator('[data-module-id="keys"] .module-move').bounding_box()
        page.mouse.move(grip["x"] + 9, grip["y"] + 9)
        page.mouse.down()
        page.mouse.move(grip["x"] + 9, grip["y"] + 340, steps=10)

        seen = []
        for nudge in range(4):
            page.mouse.move(grip["x"] + 9 + nudge % 2, grip["y"] + 340)
            page.wait_for_timeout(60)
            seen.append(page.evaluate(
                """() => {
                    const bar = document.querySelector('.rack-drop');
                    return bar ? [...bar.parentElement.children].indexOf(bar) : null;
                }"""
            ))
        page.mouse.up()
        page.wait_for_timeout(200)

        assert len(set(seen)) == 1, f"the landing hunted: {seen}"

    def test_it_is_put_back_in_the_flow(self, page):
        # A guard, not a discovery: `renderRack` moves elements rather than
        # recreating them, so anything the gesture set on the element outlives
        # the gesture unless the gesture takes it off again.
        self.drag(page, "keys", "dfam")
        left_over = page.evaluate(
            """() => {
                const m = document.querySelector('[data-module-id="keys"]');
                const style = m.style;
                return ['position', 'left', 'top', 'width', 'height', 'transform']
                    .filter(named => style.getPropertyValue(named));
            }"""
        )
        assert left_over == []
        assert page.locator('[data-module-id="keys"]').evaluate(
            "m => getComputedStyle(m).position") == "relative"

    def test_it_can_be_dragged_into_another_row(self, page):
        self.drag(page, "keys", "dfam")
        assert "keys" not in self.row(page, "row-control")
        assert "keys" in self.row(page, "row-voices")

    def test_the_cables_come_with_it(self, page):
        before = page.locator("path.cable").evaluate_all(
            "paths => new Set(paths.map(p => p.dataset.cable)).size")
        self.drag(page, "keys", "dfam")
        after = page.locator("path.cable").evaluate_all(
            "paths => new Set(paths.map(p => p.dataset.cable)).size")
        assert after == before == 17

    def test_dropping_it_nowhere_leaves_it_alone(self, page):
        # A drag that ends off the rack should leave everything where it was
        # rather than guess at what was meant.
        was = self.layout(page)
        grip = page.locator('[data-module-id="keys"] .module-move').bounding_box()
        page.mouse.move(grip["x"] + 9, grip["y"] + 9)
        page.mouse.down()
        page.mouse.move(grip["x"] + 9, 4, steps=8)   # up onto the bar
        page.mouse.up()
        page.wait_for_timeout(200)

        assert self.layout(page) == was
        assert "stayed where it was" in page.locator("#status").inner_text()

    def test_the_arrow_keys_move_it_along_the_row(self, page):
        # A grip you can only drag is a grip a keyboard cannot reach.
        page.locator('[data-module-id="grid"] .module-move').focus()
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(150)
        assert self.row(page, "row-control") == ["seq", "grid", "keys"]

    def test_and_between_rows(self, page):
        page.locator('[data-module-id="keys"] .module-move').focus()
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(150)
        assert "keys" not in self.row(page, "row-control")
        assert "keys" in self.row(page, "row-voices")

    def test_the_ends_hold(self, page):
        # A device at the front pressing left stays there rather than appearing
        # at the back of somewhere else.
        was = self.row(page, "row-control")
        page.locator('[data-module-id="grid"] .module-move').focus()
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(150)
        assert self.row(page, "row-control") == was

    def test_nothing_throws_through_any_of_it(self, page):
        self.drag(page, "keys", "dfam")
        page.locator('[data-module-id="keys"] .module-move').focus()
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(150)
        assert page.errors == []


class TestTheLeadsFollowAScroll:
    """A row never wraps, so a rack wider than the window scrolls sideways.

    Cable endpoints are measured from laid-out elements, so scrolling moves the
    sockets without moving the layer the leads were drawn on. Measured before
    the fix, on a 1000px window: the device moved -180px and its lead moved 0,
    leaving the cable pointing at where the socket used to be.

    The listener has to be on the document and in the capture phase - a scroll
    event does not bubble, so one on `window` never hears a shelf scroll at all.
    """

    def a_scrolling_shelf(self, page):
        """A shelf that overflows, holding a device with a lead on it."""
        return page.evaluate(
            """() => {
                for (const shelf of document.querySelectorAll('.rack-shelf')) {
                    if (shelf.scrollWidth <= shelf.clientWidth + 4) continue;
                    for (const module of shelf.querySelectorAll('.module')) {
                        const id = module.dataset.moduleId;
                        const lead = [...document.querySelectorAll('path.cable')]
                            .find(p => (p.dataset.cable || '').includes(id + ':'));
                        if (lead) {
                            shelf.dataset.probe = '1';
                            module.dataset.probe = '1';
                            document.body.dataset.probeCable = lead.dataset.cable;
                            return { id, cable: lead.dataset.cable };
                        }
                    }
                }
                return null;
            }"""
        )

    def where(self, page):
        # The lead is re-found by key rather than by a flag: a redraw replaces
        # every path, so a marker set before the scroll does not survive one.
        return page.evaluate(
            """() => {
                const shelf = document.querySelector('.rack-shelf[data-probe]');
                const module = document.querySelector('.module[data-probe]');
                const key = document.body.dataset.probeCable;
                const lead = document.querySelector(
                    `path.cable[data-cable="${key}"]`);
                if (!lead) return null;
                return {
                    device: Math.round(module.getBoundingClientRect().left),
                    lead: Math.round(lead.getBoundingClientRect().left),
                };
            }"""
        )

    def test_a_lead_stays_on_its_socket_when_the_row_scrolls(self, page):
        page.set_viewport_size({"width": 1000, "height": 900})
        page.wait_for_timeout(200)

        chosen = self.a_scrolling_shelf(page)
        assert chosen, "no overflowing shelf holds a patched device at this size"

        before = self.where(page)
        page.evaluate(
            "() => { document.querySelector('.rack-shelf[data-probe]')"
            ".scrollLeft = 180; }")
        until(page, "() => document.querySelector('.rack-shelf[data-probe]')"
                    ".scrollLeft === 180")
        page.wait_for_timeout(200)   # the redraw is coalesced to a frame
        after = self.where(page)
        assert after, "the lead vanished instead of moving"

        moved_device = after["device"] - before["device"]
        moved_lead = after["lead"] - before["lead"]
        assert moved_device != 0, "the shelf did not actually scroll"
        assert abs(moved_device - moved_lead) <= 2, (
            f"the device moved {moved_device}px and its lead moved "
            f"{moved_lead}px - the cable is pointing at where the socket was"
        )


class TestEverySocketSaysWhatItIs:
    """Labels on the laid-out panels, not only the abstract ones.

    `minimal` has labelled sockets since the beginning. `irl` drew them as bare
    circles, which made a back panel a picture of *a* back panel rather than a
    drawing of this one — and the whole reason that mode exists is being able to
    tell one socket from another without hovering each in turn.
    """

    def faces(self, page):
        """Every device, on every side it draws, in `irl`."""
        return page.evaluate(
            """() => {
                const was = system.mode;
                const out = [];
                system.clearRack();
                system.setMode('irl');
                for (const id of Object.keys(ModuleFactory.definitions)) {
                    const m = system.addModule(id);
                    for (const side of m.drawnSides()) {
                        m.setView(side);
                        const face = m.element.querySelector('.face.active');
                        const jacks = [...face.querySelectorAll('.jack')];
                        const labels = [...face.querySelectorAll(
                            '.irl-jack-label')];
                        const boxes = labels.map(l => {
                            const b = l.getBoundingClientRect();
                            return [b.left, b.top, b.width, b.height];
                        });
                        let clashes = 0;
                        for (let i = 0; i < boxes.length; i++) {
                            for (let j = i + 1; j < boxes.length; j++) {
                                const [ax, ay, aw, ah] = boxes[i];
                                const [cx, cy, cw, ch] = boxes[j];
                                if (ax < cx + cw && cx < ax + aw
                                    && ay < cy + ch && cy < ay + ah) clashes++;
                            }
                        }
                        out.push({
                            id, side,
                            jacks: jacks.length,
                            labels: labels.length,
                            blank: labels.filter(
                                l => !l.textContent.trim()).length,
                            clashes,
                        });
                    }
                    system.removeModule(m.id);
                }
                system.setMode(was);
                return out;
            }"""
        )

    def test_every_socket_on_every_drawn_face_is_labelled(self, page):
        faces = self.faces(page)
        assert faces, "no faces were examined, so this proves nothing"
        for face in faces:
            with_id = f"{face['id']} {face['side']}"
            assert face["labels"] == face["jacks"], (
                f"{with_id}: {face['jacks']} sockets, {face['labels']} labels")

    def test_no_label_is_empty(self, page):
        for face in self.faces(page):
            assert face["blank"] == 0, f"{face['id']} {face['side']}"

    def test_no_two_labels_overlap(self, page):
        # A dense back panel puts sockets closer together than their names are
        # wide: seventeen on a Qu-24, sixteen on a Hapax. Neighbours along a row
        # alternate between two lines, because an overlapping label is not a
        # label, it is a smear — and worse than the bare circle it replaced.
        crowded = [f for f in self.faces(page) if f["clashes"]]
        assert crowded == [], f"labels overlap on {crowded}"

    def test_the_stage_3_back_says_what_each_socket_is(self, page):
        # The panel this was asked about.
        said = page.evaluate(
            """() => {
                system.clearRack();
                system.setMode('irl');
                const m = system.addModule('nord.stage-3');
                m.setView('back');
                const out = [...m.element.querySelectorAll(
                    '.face.active .irl-jack-label')].map(l => l.textContent);
                system.clearRack();
                return out;
            }"""
        )
        assert len(said) == 11
        for named in ("MIDI IN", "MIDI OUT", "OUT L", "OUT R"):
            assert any(named in text for text in said), f"{named} is not named"


class TestPullingALeadOut:
    """Press a socket and drag, and the lead follows the hand.

    Beside click-to-click rather than instead of it: two clicks is the gesture a
    keyboard can make, and a drag is the one a hand reaches for first.

    The preview is drawn by the same routine as the cable it becomes — same
    curve, same sag, same layer, same dashes for a run that goes out of sight.
    A preview built by a second drawing routine is one that can disagree with
    the thing it previews, and the disagreement is invisible until it matters.
    """

    def sockets(self, bench):
        out = bench.locator(".module").nth(0).locator(
            '.face.active .jack[data-type="output"]').first
        inp = bench.locator(".module").nth(1).locator(
            '.face.active .jack[data-type="input"]').first
        other = bench.locator(".module").nth(1).locator(
            '.face.active .jack[data-type="output"]').first
        return out, inp, other

    def centre(self, locator):
        box = locator.bounding_box()
        return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    def leads(self, bench):
        return bench.locator("path.cable:not(.is-preview)").evaluate_all(
            "paths => new Set(paths.map(p => p.dataset.cable)).size")

    def preview(self, bench):
        return bench.locator("path.cable.is-preview")

    def test_a_small_movement_is_still_a_click(self, bench):
        # Below the slop it is a hand not quite still. Taking that as a drag
        # would make every click on a socket a lead pulled half out and dropped.
        out, _, _ = self.sockets(bench)
        x, y = self.centre(out)
        bench.mouse.move(x, y)
        bench.mouse.down()
        bench.mouse.move(x + 3, y + 2)
        assert self.preview(bench).count() == 0
        bench.mouse.up()

    def test_dragging_shows_the_lead_in_the_hand(self, bench):
        out, _, _ = self.sockets(bench)
        x, y = self.centre(out)
        bench.mouse.move(x, y)
        bench.mouse.down()
        bench.mouse.move(x + 140, y + 70, steps=6)

        preview = self.preview(bench)
        assert preview.count() == 1
        assert "is-open" in preview.first.get_attribute("class")
        assert "audio lead from" in bench.locator("#status").inner_text()
        bench.mouse.up()

    def test_it_says_which_kind_of_lead(self, bench):
        # The point of previewing: which cable this is, before it exists.
        out, _, _ = self.sockets(bench)
        x, y = self.centre(out)
        bench.mouse.move(x, y)
        bench.mouse.down()
        bench.mouse.move(x + 120, y + 60, steps=6)
        assert self.preview(bench).first.get_attribute("data-signal") == "audio"
        bench.mouse.up()

    def test_over_a_socket_that_will_take_it(self, bench):
        out, inp, _ = self.sockets(bench)
        x, y = self.centre(out)
        tx, ty = self.centre(inp)
        bench.mouse.move(x, y)
        bench.mouse.down()
        bench.mouse.move(tx, ty, steps=8)

        assert "is-legal" in self.preview(bench).first.get_attribute("class")
        assert "Release to patch" in bench.locator("#status").inner_text()
        bench.mouse.up()

    def test_over_one_that_will_not(self, bench):
        out, _, other = self.sockets(bench)
        x, y = self.centre(out)
        tx, ty = self.centre(other)
        bench.mouse.move(x, y)
        bench.mouse.down()
        bench.mouse.move(tx, ty, steps=8)

        assert "is-refused" in self.preview(bench).first.get_attribute("class")
        assert "cannot be patched" in bench.locator("#status").inner_text()
        bench.mouse.up()
        assert self.leads(bench) == 0

    def test_releasing_on_a_legal_socket_patches_it(self, bench):
        out, inp, _ = self.sockets(bench)
        assert self.leads(bench) == 0

        x, y = self.centre(out)
        tx, ty = self.centre(inp)
        bench.mouse.move(x, y)
        bench.mouse.down()
        bench.mouse.move(tx, ty, steps=8)
        bench.mouse.up()

        bench.wait_for_function(
            "() => document.querySelectorAll("
            "'path.cable:not(.is-preview)').length > 0", timeout=5_000)
        assert self.leads(bench) == 1
        assert "Patched" in bench.locator("#status").inner_text()

    def test_the_preview_goes_when_the_hand_does(self, bench):
        out, inp, _ = self.sockets(bench)
        x, y = self.centre(out)
        tx, ty = self.centre(inp)
        bench.mouse.move(x, y)
        bench.mouse.down()
        bench.mouse.move(tx, ty, steps=8)
        bench.mouse.up()
        bench.wait_for_timeout(200)
        assert self.preview(bench).count() == 0

    def test_dropping_it_on_nothing_leaves_nothing_behind(self, bench):
        out, _, _ = self.sockets(bench)
        x, y = self.centre(out)
        bench.mouse.move(x, y)
        bench.mouse.down()
        bench.mouse.move(x + 40, y + 260, steps=8)
        bench.mouse.up()
        bench.wait_for_timeout(200)

        assert self.preview(bench).count() == 0
        assert self.leads(bench) == 0
        # And the socket is not left armed, which would make the next click
        # somewhere else patch something nobody asked for.
        assert bench.locator(".jack.arming").count() == 0
        assert "dropped" in bench.locator("#status").inner_text().lower()

    def test_click_to_click_still_works(self, bench):
        # The gesture a keyboard can make, and the one this was added beside
        # rather than instead of. Arming on the press broke it once: the click
        # that followed found its own socket armed and cancelled it.
        out, inp, _ = self.sockets(bench)
        out.click()
        assert bench.locator(".jack.arming").count() == 1
        inp.click()
        bench.wait_for_function(
            "() => document.querySelectorAll("
            "'path.cable:not(.is-preview)').length > 0", timeout=5_000)
        assert self.leads(bench) == 1

    def test_nothing_throws_through_any_of_it(self, bench):
        out, inp, _ = self.sockets(bench)
        x, y = self.centre(out)
        tx, ty = self.centre(inp)
        bench.mouse.move(x, y)
        bench.mouse.down()
        bench.mouse.move(tx, ty, steps=6)
        bench.mouse.up()
        assert bench.errors == []


class TestTheBar:
    """A pinned ring rests as a title, and blooms when you hold it.

    The panel is gone and this is what replaced it: one surface in two states.
    At rest it is a strip across the navy above the rack — a title saying what
    the rack is — and it covers nothing, because that strip is background
    nothing was ever drawn in. Hold it and the ring itself appears.

    It rests rather than staying open for a plain reason: a ring left over the
    rack is a ring in the way of the rack, and the readout was the only part of
    it worth having up all the time.
    """

    def bar(self, page):
        return page.locator(".rad-bar")

    def readout(self, page):
        return page.locator("#rad-bar-text").text_content()

    def hold(self, page, x=420):
        """Hold the bar until the ring blooms."""
        box = self.bar(page).bounding_box()
        page.mouse.move(x, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.wait_for_selector(".rad-wedge", timeout=5_000)

    def test_it_arrives_resting(self, page):
        assert page.locator(".rad-layer.is-resting").count() == 1
        assert page.locator(".rad-wedge").count() == 0

    def test_it_spans_the_top(self, page):
        # Half a pixel out on each side: the rect carries a 1px stroke and a
        # bounding box includes it.
        box = self.bar(page).bounding_box()
        assert box["x"] <= 0
        assert box["y"] <= 0
        assert box["width"] >= page.viewport_size["width"] - 1

    def test_it_takes_the_navy_and_not_the_rack(self, page):
        # The strip above the rack is background nothing is drawn in, so a
        # title can have it without taking anything from the gear.
        box = self.bar(page).bounding_box()
        rack = page.evaluate(
            "() => document.querySelector('#rack').getBoundingClientRect().top")
        assert rack >= box["y"] + box["height"]

    def test_it_says_what_the_rack_is(self, page):
        said = self.readout(page)
        assert "11 devices" in said
        assert "17 leads" in said
        assert "3 rows" in said


    def test_it_says_both_things_with_a_rule_between(self, page):
        # The figures do not stop being true when the app answers something,
        # and the answer does not stop mattering when you look away - so
        # neither replaces the other. One drawn rule separates them.
        assert page.locator("#rad-bar-said").count() == 0
        assert page.locator(".rad-bar-rule").count() == 0

        page.evaluate("() => { system.addModule('moog.dfam'); }")
        page.wait_for_selector("#rad-bar-said", timeout=5_000)

        assert "12 devices" in self.readout(page)
        assert "DFAM" in page.locator("#rad-bar-said").text_content()
        assert page.locator(".rad-bar-rule").count() == 1

    def test_the_facts_are_separated_by_dots_not_more_rules(self, page):
        # Four drawn rules in one strip is a strip nobody reads.
        # Build, devices, leads, rows, facing: five facts, four dots.
        assert page.locator("#rad-bar-text .rad-bar-dot").count() == 4
        assert page.locator(".rad-bar-rule").count() == 0

    def test_the_hint_retires_once_it_has_been_used(self, page):
        # Worth a strip of the bar exactly until somebody has held it once.
        assert page.locator("#rad-bar-hint").count() == 1
        self.hold(page)
        page.mouse.up()
        page.wait_for_function(
            "() => !document.querySelector('#rad-bar-hint')", timeout=5_000)
        assert page.locator("#rad-bar-hint").count() == 0

    def test_and_stays_retired(self, page):
        self.hold(page)
        page.mouse.up()
        page.wait_for_function(
            "() => !document.querySelector('#rad-bar-hint')", timeout=5_000)
        page.reload(wait_until="networkidle")
        page.wait_for_selector(".rad-bar", timeout=8_000)
        assert page.locator("#rad-bar-hint").count() == 0

    def test_holding_it_blooms_the_ring(self, page):
        self.hold(page)
        assert page.locator(".rad-wedge").count() == 7
        page.mouse.up()

    def test_letting_go_returns_it_to_the_bar(self, page):
        self.hold(page)
        page.mouse.up()
        page.wait_for_function(
            "() => document.querySelectorAll('.rad-wedge').length === 0",
            timeout=5_000)
        assert page.locator(".rad-layer.is-resting").count() == 1

    def test_using_it_returns_it_to_the_bar(self, page):
        # The ring is what you asked for by holding, and it has now done the
        # thing you asked for.
        self.hold(page)
        page.mouse.up()
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        pick(page, "Minimal")
        ready(page, "minimally")
        page.wait_for_function(
            "() => document.querySelectorAll('.rad-wedge').length === 0",
            timeout=5_000)
        assert page.locator(".rad-layer.is-resting").count() == 1
        assert "minimally" in page.locator("#rad-bar-said").text_content()

    def test_a_press_on_the_rack_is_the_rack_s(self, bench):
        # The bar is not a modal. Everything under it still works, which it did
        # not when a pinned ring stayed open: it owned the keyboard and
        # swallowed every click for as long as it was up.
        #
        # On the bench, because the opening rack's first device is a grid whose
        # face is sixty-four pads - a press there is a note, correctly, and says
        # nothing about whether the bar is in the way.
        assert bench.locator(".rad-bar").count() == 1
        bench.locator(".module").first.click()
        assert bench.locator(".module.selected").count() == 1

    def test_the_keyboard_still_belongs_to_the_rack(self, page):
        facing = page.locator("#view-indicator").inner_text()
        page.keyboard.press("t")
        page.wait_for_function(
            f"() => document.querySelector('#view-indicator').textContent"
            f" !== {facing!r}",
            timeout=5_000)
        assert page.locator("#view-indicator").inner_text() != facing

    def move(self, page, dx, dy, steps=10):
        """Double-tap the bar and drag it."""
        start = self.bar(page).bounding_box()
        x = start["x"] + 60
        y = start["y"] + start["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.up()
        page.mouse.down()
        page.mouse.move(x + dx, y + dy, steps=steps)
        page.mouse.up()
        page.wait_for_timeout(150)
        return start

    def test_double_tap_and_drag_moves_it(self, page):
        # rad-android's own reposition gesture, chosen so the press that works
        # the ring keeps its exact shape and never has to know this exists.
        start = self.move(page, 0, 180)
        assert round(self.bar(page).bounding_box()["y"] - start["y"]) == 180

    def test_docked_it_spans_the_window(self, page):
        assert page.locator(".rad-layer.is-docked").count() == 1
        box = self.bar(page).bounding_box()
        assert box["width"] >= page.viewport_size["width"] - 1

    def test_moved_it_becomes_a_panel_the_size_of_what_it_says(self, page):
        # A full-width strip in the middle of a rack claims every press at that
        # height - knobs and sockets included, because a bar is hit-tested by
        # geometry rather than by what is under the pointer. Docked that costs
        # nothing. Moved, it was a wall.
        self.move(page, 220, 400)
        box = self.bar(page).bounding_box()
        assert page.locator(".rad-layer.is-floating").count() == 1
        assert box["width"] < page.viewport_size["width"] / 2
        assert box["x"] > 0

    def test_it_stops_claiming_the_whole_row_it_sits_in(self, page):
        # The bug this fixes, asked the way the bar itself asks it. A press is
        # the bar's when it lands inside the bar - and while it spanned the
        # window, that was every press at that height, knobs and sockets
        # included.
        self.move(page, 300, 400)
        box = self.bar(page).bounding_box()
        middle = box["y"] + box["height"] / 2

        claims = page.evaluate(
            "([x, y]) => radMenu.aimedAtBar(x, y)", [box["x"] + 40, middle])
        assert claims, "it does not claim a press on itself"

        for beside in (20, box["x"] - 40, box["x"] + box["width"] + 40):
            assert not page.evaluate(
                "([x, y]) => radMenu.aimedAtBar(x, y)", [beside, middle]), (
                f"still claims x={beside} at its own height")

    def test_the_rack_answers_beside_a_floated_bar(self, page):
        # And the other half of it: something on the rack at that height is
        # still something you can point at.
        self.move(page, 300, 400)
        box = self.bar(page).bounding_box()
        middle = box["y"] + box["height"] / 2

        found = page.evaluate(
            """(y) => {
                for (let x = 20; x < window.innerWidth; x += 20) {
                    const el = document.elementFromPoint(x, y);
                    if (el && el.closest('.module')) return true;
                }
                return false;
            }""", middle)
        assert found, "nothing on the rack is reachable at the bar's height"

    def test_moving_it_gives_the_strip_back(self, page):
        assert page.evaluate(
            "() => getComputedStyle(document.body).paddingTop") == "46px"
        self.move(page, 200, 400)
        assert page.evaluate(
            "() => getComputedStyle(document.body).paddingTop") != "46px"

    def test_dragging_it_to_the_top_docks_it_again(self, page):
        # The gesture that moves it is the gesture that puts it back, so there
        # is nothing to find in a menu.
        self.move(page, 200, 400)
        assert page.locator(".rad-layer.is-floating").count() == 1

        box = self.bar(page).bounding_box()
        x = box["x"] + 60
        y = box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.up()
        page.mouse.down()
        page.mouse.move(x, 6, steps=8)
        page.mouse.up()
        page.wait_for_timeout(150)

        assert page.locator(".rad-layer.is-docked").count() == 1
        assert self.bar(page).bounding_box()["width"] >= (
            page.viewport_size["width"] - 1)
        assert page.evaluate(
            "() => getComputedStyle(document.body).paddingTop") == "46px"

    def test_one_tap_does_not_move_it(self, page):
        start = self.bar(page).bounding_box()
        x, y = 500, start["y"] + start["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x, y + 120, steps=6)
        page.mouse.up()
        assert self.bar(page).bounding_box()["y"] == start["y"]

    def test_it_can_be_let_go_of(self, page):
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        pick(page, "Unpin ring")
        ready(page, "let go")
        assert page.locator(".rad-bar").count() == 0
        assert page.evaluate(
            "() => document.body.getAttribute('data-ring')") is None

    def test_letting_it_go_gives_the_rack_its_strip_back(self, page):
        reserved = page.evaluate(
            "() => getComputedStyle(document.body).paddingTop")
        open_menu(page, *bare_rack(page))
        pick(page, "View")
        pick(page, "Unpin ring")
        ready(page, "let go")
        assert page.evaluate(
            "() => getComputedStyle(document.body).paddingTop") != reserved

    def test_nothing_throws_through_any_of_it(self, page):
        self.hold(page)
        page.mouse.up()
        page.keyboard.press("Escape")
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

        # Watched, not sampled. The class is taken away 220ms after it lands,
        # so reading the attribute afterwards measures how busy the machine is.
        watch_class(drum_rig, '[data-module-id="kick"]', "is-active")
        watch_class(drum_rig, '[data-module-id="clap"]', "is-active")

        pad.click()
        ready(drum_rig, "note 36")
        assert was_lit(drum_rig, '[data-module-id="kick"]', "is-active")
        # And the voice bound to a different note stays dark. This one is safe
        # to read directly - it asserts an absence, and an absence does not
        # decay - but it is watched too, so the pair is read the same way.
        assert not drum_rig.evaluate(
            "() => Boolean((window.__lit || {})"
            "['[data-module-id=\"clap\"] .is-active'])")

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


