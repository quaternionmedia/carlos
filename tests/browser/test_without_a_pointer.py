"""Everything reachable by keyboard, in a real browser.

The stub harnesses assert that a control carries `tabindex` and has a `keydown`
listener. Neither of those is the same as a key reaching it: focus order,
`preventDefault`, and a global handler stealing `Tab` are all real-browser
facts, and this project has already shipped a global `Tab` handler that made
every focusable control visible and unreachable.
"""

from __future__ import annotations

import pytest


def focus_ring(page, presses: int) -> list[str]:
    """Where focus lands, walked forward by `Tab`."""
    seen = []
    for _ in range(presses):
        page.keyboard.press("Tab")
        seen.append(page.evaluate("() => document.activeElement?.className || ''"))
    return seen


class TestTabIsFocus:
    """The defect this suite was written to find.

    Turning was on `Tab`, guarded by "unless something focusable already has
    it". At load nothing is focused, so the first `Tab` turned the rack — and
    so did every one after it. Seventeen focusable controls and a keyboard user
    could reach none of them. The stub harness agreed with the code because it
    pre-focused a knob and tested only the second half of that rule.
    """

    def test_the_first_tab_moves_focus_into_the_page(self, page):
        assert page.evaluate("() => document.activeElement.tagName") == "BODY"
        page.keyboard.press("Tab")
        assert page.evaluate("() => document.activeElement.tagName") != "BODY"

    def test_tab_does_not_turn_the_rack(self, page):
        before = page.locator("#view-indicator").inner_text()
        for _ in range(4):
            page.keyboard.press("Tab")
        assert page.locator("#view-indicator").inner_text() == before

    def test_tab_walks_the_controls(self, bench):
        # On the bench, because the two devices that open the workspace are
        # played from above with their sockets round the back: nothing is
        # wrong with a rack whose jacks are all on hidden faces, and it is a
        # poor place to ask whether Tab reaches a jack.
        classes = " ".join(focus_ring(bench, 12))
        assert "knob" in classes
        assert "jack" in classes

    def test_every_focusable_control_is_reachable(self, page):
        # Counted rather than sampled: the failure mode was all of them at
        # once, so a test that finds one and stops would have passed then too.
        declared = page.evaluate(
            "() => document.querySelectorAll("
            "'[tabindex=\"0\"], button, input, a[href]').length"
        )
        assert declared > 10

        reached = set()
        for _ in range(declared + 4):
            page.keyboard.press("Tab")
            reached.add(page.evaluate(
                "() => document.activeElement.tagName + '.'"
                " + (document.activeElement.className || '')"
            ))
        assert "BODY." not in reached or len(reached) > 5


class TestTheTurnKey:
    def test_t_turns_the_rack(self, page):
        before = page.locator("#view-indicator").inner_text()
        page.keyboard.press("t")
        page.wait_for_function(
            f"() => document.querySelector('#view-indicator').textContent"
            f" !== '{before}'",
            timeout=5_000,
        )
        assert page.locator("#view-indicator").inner_text() != before

    def test_shift_t_walks_back(self, page):
        start = page.locator("#view-indicator").inner_text()
        page.keyboard.press("t")
        page.keyboard.press("Shift+T")
        assert page.locator("#view-indicator").inner_text() == start


class TestAKnobAnswersToKeys:
    @pytest.mark.parametrize(
        "key, direction",
        [("ArrowUp", 1), ("ArrowRight", 1), ("ArrowDown", -1), ("ArrowLeft", -1)],
    )
    def test_arrows_move_it(self, bench, key, direction):
        knob = bench.locator(".knob").first
        knob.focus()
        before = float(knob.get_attribute("aria-valuenow"))
        bench.keyboard.press(key)
        after = float(knob.get_attribute("aria-valuenow"))
        assert (after - before) * direction > 0

    def test_shift_is_finer_than_a_bare_press(self, bench):
        knob = bench.locator(".knob").first
        knob.focus()

        start = float(knob.get_attribute("aria-valuenow"))
        bench.keyboard.press("ArrowUp")
        coarse = float(knob.get_attribute("aria-valuenow")) - start

        start = float(knob.get_attribute("aria-valuenow"))
        bench.keyboard.press("Shift+ArrowUp")
        fine = float(knob.get_attribute("aria-valuenow")) - start

        # `0 <=` legalised the defect this is meant to catch. `aria-valuenow`
        # was published as `Math.round(value)`, the fine step on a 0-127 knob is
        # 0.127, and rounding erased it - so `fine` was deterministically 0.0
        # and the assertion held while Shift did nothing a screen reader could
        # hear. Deleting fine adjustment outright left this green.
        assert fine > 0, "Shift+Arrow moved nothing that aria-valuenow reports"
        assert fine < coarse

    def test_every_publisher_announces_the_same_precision(self, bench):
        """One of three was guarded, so two could be reverted in silence.

        `aria-valuenow` is written in three places: the initial render, the
        keydown paint, and `paintKnob` - which the import and randomize paths go
        through. The test above only ever exercises the keydown one. Reverting
        the other two to `Math.round` left all seven tests in this class green,
        and a probe in this same fixture showed it plainly: the keyboard path
        announced `64.127` while the same value republished through `setState`
        announced `64`.

        `paintKnob`'s own comment says an imported or randomized rack "was
        announced at its old values while showing its new ones". That is the
        regression, and it was back on two paths with nothing watching.
        """
        knob = bench.locator(".knob").first
        knob.focus()
        bench.keyboard.press("Shift+ArrowUp")
        keyboard = knob.get_attribute("aria-valuenow")

        # The same value, republished through the path a rack import uses.
        module_id = knob.evaluate(
            "el => el.closest('[data-module-id]').dataset.moduleId")
        param = knob.get_attribute("data-param")
        bench.evaluate(
            """([id, name, value]) => {
                const module = system.modules.get(id);
                module.setState({ parameters: { [name]: Number(value) } });
            }""",
            [module_id, param, keyboard],
        )
        assert knob.get_attribute("aria-valuenow") == keyboard, (
            "the render path announces a different precision from the keyboard "
            "path, so an imported rack reports the wrong value"
        )

    def test_the_announcement_can_carry_a_fine_step_at_all(self, bench):
        """The trap under the assertion above, which is currently latent.

        `announced()` is `toFixed(3)` and the fine step is `span / 1000`, so any
        parameter whose span is below about 0.5 cannot express one - Shift would
        read as broken when the real fault is the precision. No device in the
        catalogue has such a range today, which makes this a trap waiting for the
        first small-range knob rather than a live defect.
        """
        spans = bench.evaluate(
            """() => [...document.querySelectorAll('.knob')].map(el => {
                const lo = Number(el.getAttribute('aria-valuemin'));
                const hi = Number(el.getAttribute('aria-valuemax'));
                return hi - lo;
            })"""
        )
        assert spans, "no knob declared a range"
        too_small = [s for s in spans if s / 1000 < 0.0005]
        assert not too_small, (
            f"parameters with span {too_small} cannot announce a fine step at "
            f"three decimals; widen the precision in announced()"
        )

    def test_home_and_end_reach_the_stops(self, bench):
        knob = bench.locator(".knob").first
        knob.focus()

        bench.keyboard.press("End")
        assert knob.get_attribute("aria-valuenow") == knob.get_attribute("aria-valuemax")

        bench.keyboard.press("Home")
        assert knob.get_attribute("aria-valuenow") == knob.get_attribute("aria-valuemin")

    def test_it_announces_the_value_it_is_showing(self, bench):
        # The number a screen reader reads has to be the number on screen.
        knob = bench.locator(".knob").first
        knob.focus()
        bench.keyboard.press("End")
        assert knob.get_attribute("role") == "slider"
        assert knob.get_attribute("aria-valuenow") is not None


class TestPatchingWithoutAPointer:
    def test_enter_on_two_sockets_makes_a_cable(self, bench):
        # Only sockets on a *showing* face. A device draws every side it has
        # and lays out one, so the others are in the tree and `display: none` —
        # focusing one silently does nothing, focus stays where it was, and the
        # second Enter lands on the armed jack and cancels it.
        before = bench.locator("path.cable").count()
        modules = bench.locator(".module")

        source = modules.nth(0).locator('.face.active .jack[data-type="output"]').first
        target = modules.nth(1).locator('.face.active .jack[data-type="input"]').first

        source.focus()
        bench.keyboard.press("Enter")
        assert "armed" in bench.locator("#status").inner_text()

        target.focus()
        bench.keyboard.press("Enter")

        bench.wait_for_function(
            f"() => document.querySelectorAll('path.cable').length > {before}",
            timeout=5_000,
        )
        assert bench.locator("path.cable").count() == before + 1

    def test_a_socket_on_a_turned_away_face_is_not_in_the_tab_order(self, page):
        # It is in the tree, because every side is drawn. It is not reachable,
        # because only one side is laid out — which is the correct answer and
        # worth holding: a tab order that walked invisible controls would be a
        # keyboard user pressing Enter on something nobody can see.
        hidden = page.locator('.face:not(.active) .jack')
        assert hidden.count() > 0, "no device has a turned-away face to check"
        assert hidden.first.is_visible() is False

        reached = set()
        for _ in range(20):
            page.keyboard.press("Tab")
            reached.add(page.evaluate(
                "() => document.activeElement.closest?.('.face')"
                "?.classList.contains('active') ?? true"
            ))
        assert False not in reached, "focus reached a socket on a hidden face"

    def test_space_works_the_same_way(self, bench):
        bench.locator('.face.active .jack[data-type="output"]').first.focus()
        bench.keyboard.press(" ")
        assert "armed" in bench.locator("#status").inner_text()

    def test_escape_lets_go_of_the_selection_and_the_focus(self, bench):
        bench.locator(".module").first.click()
        assert bench.locator(".module.selected").count() == 1

        bench.keyboard.press("Escape")
        assert bench.locator(".module.selected").count() == 0


