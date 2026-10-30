"""A cue from the performing family's hub: `POST /family/cue`, `GET /family/state`.

The rack the hub leaves is held by the server, so it is asserted here without a
browser: what each action does to the state, what is refused and that a refusal
changes nothing, and the two routes answering in their own words. That an open
tab draws it is `tests/browser/test_family.py`.
"""

import asyncio
import json
import re
import unittest
from pathlib import Path

from src import catalogue, family, main


class _Posted:
    """The half of a request `family_cue` reads: its body."""

    def __init__(self, raw: bytes):
        self.raw = raw

    async def body(self) -> bytes:
        return self.raw


def cue(number: str, action, name: str = "A cue") -> dict:
    return {"cue": {"number": number, "name": name, "fired_at": "2026-10-10T20:00:00+00:00"},
            "action": action}


# Bodies the hub might send that carlos does not understand. Each is a 422 with
# a reason, never a 500 and never a change to the rack.
NOT_UNDERSTOOD = {
    "an example that does not exist": cue("9", {"patch": "moog.dfam.enormous"}),
    "a device with no kind": cue("9", {"patch": "moog.dfam"}),
    "an example named by its title": cue("9", {"patch": "One drum voice"}),
    "a patch that is not text": cue("9", {"patch": ["moog.dfam.simple"]}),
    "a side no rack has": cue("9", {"turn": "sideways"}),
    "a side that is not text": cue("9", {"turn": {"side": "back"}}),
    "two actions at once": cue("9", {"patch": "moog.dfam.simple", "turn": "back"}),
    "another member's action": cue("9", {"clock": "start"}),
    "an empty action": cue("9", {}),
    "an action that is not an object": cue("9", "turn"),
    "no action": {"cue": {"number": "9"}},
    "no cue": {"action": {"turn": "back"}},
    "a cue that is not an object": {"cue": "9", "action": {"turn": "back"}},
    "a body that is a list": [cue("9", {"turn": "back"})],
    "a body that is null": None,
}


class TheRackTests(unittest.TestCase):
    def setUp(self):
        catalogue.load_all.cache_clear()
        self.rack = family.Rack(catalogue.opening_rack())

    def test_it_starts_with_no_cue_no_patch_and_the_opening_rigs_facing(self):
        self.assertEqual(self.rack.snapshot(), {
            "member": "carlos", "cue": None,
            "state": {"patch": None,
                      "facing": family.document_facing(catalogue.opening_rack()),
                      "revision": 0, "held": None}})

    def test_a_patch_names_an_example_by_its_device_and_kind(self):
        status, answer = self.rack.receive(
            cue("3", {"patch": "novation.launchpad-x.complex"}, "Second tune"))

        self.assertEqual(status, 200)
        self.assertEqual(answer, {"ok": True, "state": {
            "patch": "novation.launchpad-x.complex", "facing": "top", "revision": 1,
            "held": None}})
        self.assertEqual(self.rack.snapshot()["cue"]["number"], "3")

    def test_loading_a_patch_faces_the_rack_the_way_its_document_does(self):
        for name, document in family.examples().items():
            with self.subTest(name):
                self.rack.receive(cue("1", {"patch": name}))
                self.assertEqual(self.rack.facing, family.document_facing(document))

    def test_a_turn_faces_the_rack_and_keeps_the_patch(self):
        self.rack.receive(cue("3", {"patch": "moog.dfam.complex"}))
        status, answer = self.rack.receive(cue("4", {"turn": "back"}))

        self.assertEqual(status, 200)
        self.assertEqual(answer["state"],
                         {"patch": "moog.dfam.complex", "facing": "back", "revision": 2,
                          "held": None})

    def test_every_side_is_a_turn_it_takes(self):
        for side in family.SIDES:
            with self.subTest(side):
                self.assertEqual(self.rack.receive(cue("1", {"turn": side}))[0], 200)
                self.assertEqual(self.rack.facing, side)

    def test_every_cue_it_takes_is_a_new_revision_even_one_that_changes_nothing(self):
        # A tab tells cues apart by revision, so the same cue twice is two.
        self.rack.receive(cue("1", {"turn": "front"}))
        self.rack.receive(cue("2", {"turn": "front"}))
        self.assertEqual(self.rack.revision, 2)

    def test_what_it_does_not_understand_is_422_and_changes_nothing(self):
        self.rack.receive(cue("1", {"patch": "moog.dfam.simple"}))
        before = self.rack.snapshot()

        for what, body in NOT_UNDERSTOOD.items():
            with self.subTest(what):
                status, answer = self.rack.receive(body)
                self.assertEqual(status, 422)
                self.assertIs(answer["ok"], False)
                self.assertTrue(answer["error"])
                self.assertEqual(self.rack.snapshot(), before)

    def test_every_shipped_example_is_a_patch_it_takes(self):
        # Two per device, named the way the menu loads them.
        names = set(family.examples())
        expected = {f"{device}.{kind}" for device in catalogue.load_all()
                    for kind in ("simple", "complex")}
        self.assertEqual(names, expected)


# A rig held from outside: a board carlos's catalogue does not have, sent with
# it, patched into a device it does, with a state on each.
BOARD = {"id": "espressif.esp32-devkitc", "maker": "Espressif", "model": "ESP32-DevKitC V4",
         "category": "board", "summary": "A devkit.",
         "jacks": [{"name": "usb", "label": "USB", "type": "output", "signal": "data",
                    "carrier": "usb", "connector": "micro-USB", "side": "right"}]}
HOST = {"id": "apothecary.host", "maker": "Apothecary", "model": "Host",
        "category": "computer", "summary": "The computer.",
        "jacks": [{"name": "usb", "label": "USB", "type": "input", "signal": "data",
                   "carrier": "usb", "connector": "USB-A", "side": "back"}]}
LEAD = {"source": {"module": "devkit", "jack": "usb"},
        "target": {"module": "host", "jack": "usb"}}


def a_hold(**changed) -> dict:
    hold = {
        "patch": {"format": "carlos.patch", "version": 3, "name": "garage",
                  "modules": [{"id": "devkit", "type": BOARD["id"], "view": "right"},
                              {"id": "host", "type": HOST["id"]}],
                  "connections": [LEAD]},
        "devices": [BOARD, HOST],
        "states": {"modules": {"devkit": {"level": "fault",
                                          "says": ["absent: expected, and not answering"]}},
                   "connections": [{**LEAD, "level": "fault",
                                    "says": ["declared: the board is not answering"]}]},
    }
    hold.update(changed)
    return hold


NOT_HELD = {
    "a hold that is not an object": "garage",
    "a patch that is not one": a_hold(patch={"format": "carlos.patch", "version": 99}),
    "a type neither in the catalogue nor sent": a_hold(devices=[HOST]),
    "a device with no id": a_hold(devices=[{**BOARD, "id": "esp32"}, HOST]),
    "a jack of no type": a_hold(devices=[
        {**BOARD, "jacks": [{**BOARD["jacks"][0], "type": "both"}]}, HOST]),
    "a level carlos does not colour": a_hold(states={"modules": {
        "devkit": {"level": "red", "says": []}}}),
    "lines that are not text": a_hold(states={"modules": {
        "devkit": {"level": "ok", "says": "present"}}}),
    "a state for a module not in the patch": a_hold(states={"modules": {
        "printer": {"level": "ok", "says": []}}}),
    "a state for a lead not in the patch": a_hold(states={"connections": [
        {"source": {"module": "host", "jack": "usb"},
         "target": {"module": "devkit", "jack": "usb"}, "level": "ok", "says": []}]}),
    "a field a hold does not have": a_hold(owner="apothecary"),
    "a control its device does not have": a_hold(states={"modules": {"devkit": {
        "level": "ok", "says": [], "controls": {"tempo": {"level": "warn", "says": []}}}}}),
    "controls that are not by name": a_hold(states={"modules": {"devkit": {
        "level": "ok", "says": [], "controls": ["tempo"]}}}),
}


class AHeldRigTests(unittest.TestCase):
    def setUp(self):
        catalogue.load_all.cache_clear()
        self.rack = family.Rack(catalogue.opening_rack())

    def test_a_held_rig_is_held_whole_and_faced_as_its_document(self):
        status, answer = self.rack.receive(cue("garage", {"hold": a_hold()}, "apothecary"))

        self.assertEqual(status, 200)
        held = answer["state"]["held"]
        self.assertEqual(held["patch"], a_hold()["patch"])
        self.assertEqual([d["id"] for d in held["devices"]], [BOARD["id"], HOST["id"]])
        self.assertEqual(held["states"]["modules"]["devkit"]["level"], "fault")
        self.assertEqual(held["states"]["connections"][0]["says"],
                         ["declared: the board is not answering"])
        self.assertEqual(answer["state"]["patch"], None)
        self.assertEqual(answer["state"]["facing"], "right")

    def test_a_module_s_state_may_say_what_state_some_of_its_controls_are_in(self):
        # A DFAM from the catalogue beside the board: a control read and one not,
        # by the parameters its catalogue entry has.
        hold = a_hold()
        hold["patch"]["modules"].append({"id": "dfam", "type": "moog.dfam",
                                         "parameters": {"tempo": 90}})
        hold["states"]["modules"]["dfam"] = {
            "level": "warn", "says": ["read: 23 of 24 controls on its front"],
            "controls": {"vcf_cutoff": {"level": "warn", "says": ["not read: no pointer to see"]}}}

        status, answer = self.rack.receive(cue("1", {"hold": hold}))

        self.assertEqual(status, 200, answer)
        dfam = answer["state"]["held"]["states"]["modules"]["dfam"]
        self.assertEqual(dfam["controls"], {"vcf_cutoff": {
            "level": "warn", "says": ["not read: no pointer to see"]}})
        # A module whose state names no control is held as it always was.
        self.assertNotIn("controls", answer["state"]["held"]["states"]["modules"]["devkit"])

    def test_its_devices_are_held_for_it_and_not_put_in_the_catalogue(self):
        self.rack.receive(cue("1", {"hold": a_hold()}))
        self.assertNotIn(BOARD["id"], catalogue.load_all())

    def test_a_turn_keeps_it_and_an_example_lets_it_go(self):
        self.rack.receive(cue("1", {"hold": a_hold()}))
        self.rack.receive(cue("2", {"turn": "back"}))
        self.assertIsNotNone(self.rack.held)
        self.rack.receive(cue("3", {"patch": "moog.dfam.simple"}))
        self.assertIsNone(self.rack.held)

    def test_a_held_device_may_use_words_the_catalogue_does_not(self):
        # A micro-USB socket on a board: neither is in carlos's vocabulary, and
        # neither is carlos's to judge in a rig it only holds.
        self.assertEqual(self.rack.receive(cue("1", {"hold": a_hold()}))[0], 200)

    def test_a_hold_carlos_cannot_draw_is_422_and_changes_nothing(self):
        self.rack.receive(cue("1", {"hold": a_hold()}))
        before = self.rack.snapshot()

        for what, hold in NOT_HELD.items():
            with self.subTest(what):
                status, answer = self.rack.receive(cue("9", {"hold": hold}))
                self.assertEqual(status, 422, answer)
                self.assertTrue(answer["error"])
                self.assertEqual(self.rack.snapshot(), before)


class DocumentFacingTests(unittest.TestCase):
    def test_the_commonest_side_wins(self):
        modules = [{"view": "back"}, {"view": "top"}, {"view": "back"}]
        self.assertEqual(family.document_facing({"modules": modules}), "back")

    def test_a_tie_goes_to_the_side_seen_first(self):
        modules = [{"view": "top"}, {"view": "back"}]
        self.assertEqual(family.document_facing({"modules": modules}), "top")

    def test_a_module_with_no_view_faces_front(self):
        self.assertEqual(family.document_facing({"modules": [{}, {"view": "back"}, {}]}),
                         "front")

    def test_nothing_faces_front(self):
        self.assertEqual(family.document_facing(None), "front")
        self.assertEqual(family.document_facing({"modules": []}), "front")


class TheRoutesTests(unittest.TestCase):
    """The two routes, called the way the application defines them."""

    def setUp(self):
        self.kept = main.rack_from_the_hub
        main.rack_from_the_hub = family.Rack(catalogue.opening_rack())

    def tearDown(self):
        main.rack_from_the_hub = self.kept

    def post(self, raw: bytes):
        response = asyncio.run(main.family_cue(_Posted(raw)))
        return response.status_code, json.loads(response.body)

    def test_a_cue_is_answered_200_with_the_state_and_the_state_route_agrees(self):
        status, answer = self.post(json.dumps(cue("7", {"turn": "back"})).encode())

        self.assertEqual((status, answer["ok"]), (200, True))
        state = asyncio.run(main.family_state())
        self.assertEqual(state["member"], "carlos")
        self.assertEqual(state["cue"]["number"], "7")
        self.assertEqual(state["state"], answer["state"])

    def test_an_action_it_does_not_understand_is_422_in_its_own_words(self):
        for what, body in NOT_UNDERSTOOD.items():
            with self.subTest(what):
                status, answer = self.post(json.dumps(body).encode())
                self.assertEqual(status, 422)
                self.assertEqual(set(answer), {"ok", "error"})
                self.assertIs(answer["ok"], False)

    def test_a_body_that_is_not_json_is_422_not_500(self):
        for raw in (b"turn: back", b"", b"\xff\xfe{"):
            with self.subTest(raw):
                self.assertEqual(self.post(raw),
                                 (422, {"ok": False, "error": "the body is not JSON"}))

    def test_both_routes_are_on_the_served_port(self):
        served = {(method, route.path) for route in main.app.routes
                  for method in getattr(route, "methods", ())}
        self.assertIn(("POST", "/family/cue"), served)
        self.assertIn(("GET", "/family/state"), served)


class TheTabAndTheServerAgreeTests(unittest.TestCase):
    """The tab draws what this module holds, so the two read the same words."""

    def setUp(self):
        self.models = Path("static/models.js").read_text(encoding="utf-8")
        self.follower = Path("static/family.js").read_text(encoding="utf-8")

    def test_the_sides_are_the_same_sides_in_the_same_order(self):
        declared = re.search(r"const SIDE_ORDER = \[([^\]]*)\]", self.models)
        self.assertIsNotNone(declared, "static/models.js no longer declares SIDE_ORDER")
        self.assertEqual(tuple(re.findall(r"'([a-z]+)'", declared.group(1))), family.SIDES)

    def test_the_tab_asks_the_route_the_server_answers(self):
        self.assertIn("fetch('/family/state'", self.follower)

    def test_the_page_loads_the_follower_after_the_rack(self):
        page = Path("templates/demo.html").read_text(encoding="utf-8")
        self.assertLess(page.index("asset('main.js')"), page.index("asset('family.js')"))
