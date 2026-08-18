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
    def test_right_click_opens_a_ring_of_eight(self, page):
        open_menu(page, *bare_rack(page))
        assert page.locator(".rad-wedge").count() == 8

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
        pick(page, "Display")
        labels = page.locator(".rad-label").all_text_contents()
        assert any("Minimal" in text for text in labels)
        assert any("Reset palette" in text for text in labels)

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


class TestPatchingAndUnpatching:
    def test_clicking_two_sockets_makes_a_cable(self, page):
        before = page.locator("path.cable").count()
        modules = page.locator(".module")
        modules.nth(0).locator('.face.active .jack[data-type="output"]').first.click()
        modules.nth(1).locator('.face.active .jack[data-type="input"]').first.click()
        until(
            page,
            f"() => document.querySelectorAll('path.cable').length > {before}",
        )
        assert page.locator("path.cable").count() == before + 1

    def test_a_cable_can_be_pulled_out_again(self, page):
        modules = page.locator(".module")
        modules.nth(0).locator('.face.active .jack[data-type="output"]').first.click()
        modules.nth(1).locator('.face.active .jack[data-type="input"]').first.click()
        until(page, "() => document.querySelectorAll('path.cable').length === 1")

        # The menu on a device offers to pull every lead out of it. Reaching a
        # cable itself needs the geometry probe, which is covered by the model
        # harness; this is the path a hand takes.
        module = modules.nth(0).bounding_box()
        page.mouse.click(module["x"] + module["width"] / 2, module["y"] + 8,
                         button="right")
        page.wait_for_selector(".rad-wedge", timeout=5_000)
        pick(page, "Unpatch")

        until(page, "() => document.querySelectorAll('path.cable').length === 0")
        assert page.locator("path.cable").count() == 0

    def test_two_outputs_refuse_each_other(self, page):
        modules = page.locator(".module")
        modules.nth(0).locator('.face.active .jack[data-type="output"]').first.click()
        modules.nth(1).locator('.face.active .jack[data-type="output"]').first.click()
        assert "cannot" in page.locator("#status").inner_text().lower()
        assert page.locator("path.cable").count() == 0


class TestDrawnAsLaidOut:
    @pytest.fixture
    def drum_rig(self, page):
        open_menu(page, *bare_rack(page))
        pick(page, "Examples")
        pick(page, "controller")
        pick(page, "Launchpad X")
        ready(page, "Imported")
        return page

    def test_the_example_loads_a_whole_rack(self, drum_rig):
        assert drum_rig.locator(".module").count() == 4
        assert drum_rig.locator("path.cable").count() == 4

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
        pick(drum_rig, "Display")
        pick(drum_rig, "Minimal")
        until(
            drum_rig,
            "() => document.body.dataset.displayMode === 'minimal'",
        )
        assert drum_rig.locator(".module").count() == 4
        assert drum_rig.locator(".irl-pads").count() == 0

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
        pick(page, "Display")
        pick(page, "Reset palette")
        ready(page, "back to where it starts")
        assert page.locator("#tool-palette").bounding_box() == default
