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
                      "revision": 0}})

    def test_a_patch_names_an_example_by_its_device_and_kind(self):
        status, answer = self.rack.receive(
            cue("3", {"patch": "novation.launchpad-x.complex"}, "Second tune"))

        self.assertEqual(status, 200)
        self.assertEqual(answer, {"ok": True, "state": {
            "patch": "novation.launchpad-x.complex", "facing": "top", "revision": 1}})
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
                         {"patch": "moog.dfam.complex", "facing": "back", "revision": 2})

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
