"""A cue from the performing family's hub, and the family's contract: `/family/*`.

The rack the hub leaves is held by the server, so it is asserted here without a
browser: what each action does to the state, what is refused and that a refusal
changes nothing, what the rack says it is, the state as a stream, and the four
routes answering in their own words. That an open tab draws it is
`tests/browser/test_family.py`.

The four routes are `family/1`, which hearth publishes with the cases that test
it. `TheContractTests` replays the member's cases at the version pinned below.
"""

import asyncio
import io
import json
import os
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from src import catalogue, family, main

# The version of hearth's vector set, `conformance/vectors.json`, that this
# suite replays. The corpus's `qm interop` reads this line and compares it with
# the version hearth publishes.
PINNED = "0.0.1"

# That set's member cases by id, in the order `hearth check` asks them.
MEMBER_CASES = (
    "identity-answers",
    "identity-is-an-object",
    "identity-keeps-contract",
    "identity-names-member",
    "identity-names-family",
    "identity-names-instance",
    "identity-names-conformance",
    "state-shape",
    "cue-not-json-refused",
    "cue-unknown-action-refused",
    "refused-cue-changes-nothing",
    "events-state-at-once",
    "action-taken",
    "cue-reaches-follower",
)
# Its hub cases, which a member does not answer.
HUB_CASES = 10


class _Posted:
    """The half of a request `family_cue` reads: its body."""

    def __init__(self, raw: bytes):
        self.raw = raw

    async def body(self) -> bytes:
        return self.raw


class _Following:
    """The half of a request `family_events` reads: whether its follower has gone."""

    def __init__(self):
        self.gone = False

    async def is_disconnected(self) -> bool:
        return self.gone


async def said(stream) -> str:
    """The next thing a stream says, or a failure once it has said nothing for five seconds."""
    return await asyncio.wait_for(anext(stream), 5)


def states(stream: str) -> list[dict]:
    """The data of each `state` event in a stretch of an event stream."""
    found = []
    for event in stream.split("\n\n"):
        lines = event.split("\n")
        if "event: state" in lines:
            found.append(json.loads("".join(
                line[len("data:"):] for line in lines if line.startswith("data:"))))
    return found


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
            "held": None}, "instance": self.rack.instance})
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

    def test_it_says_what_it_is(self):
        rack = family.Rack(version="1.2.3", instance="0123456789ab")

        self.assertEqual(rack.identity(), {
            "member": "carlos", "family": "instruments", "version": "1.2.3",
            "contract": "family/1", "conformance": PINNED,
            "verbs": ["patch", "turn", "hold"], "instance": "0123456789ab",
            "pid": os.getpid()})

    def test_a_cue_taken_names_the_instance_that_took_it(self):
        rack = family.Rack(instance="0123456789ab")
        self.assertEqual(rack.receive(cue("1", {"turn": "back"}))[1]["instance"],
                         "0123456789ab")
        # A restart is another rack, and never answers as the one before it.
        self.assertNotEqual(family.Rack().instance, family.Rack().instance)

    def test_the_verbs_it_names_are_the_actions_it_takes_and_no_others(self):
        taken = {"patch": "moog.dfam.simple", "turn": "back", "hold": a_hold()}
        self.assertEqual(set(taken), set(self.rack.identity()["verbs"]))
        for verb, value in taken.items():
            with self.subTest(verb):
                self.assertEqual(self.rack.receive(cue("1", {verb: value}))[0], 200)
        self.assertEqual(self.rack.receive(cue("1", {"clock": "start"}))[0], 422)


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
    "a jack its device does not have": a_hold(states={"modules": {"devkit": {
        "level": "ok", "says": [], "jacks": {"midi": {"level": "warn", "says": []}}}}}),
    "jacks that are not by name": a_hold(states={"modules": {"devkit": {
        "level": "ok", "says": [], "jacks": ["usb"]}}}),
    "a jack's state of no level": a_hold(states={"modules": {"devkit": {
        "level": "ok", "says": [], "jacks": {"usb": {"says": []}}}}}),
    # Leads the rack could not draw, which a tab would leave out without a word.
    "a lead to a jack its device does not have": a_hold(patch={
        **a_hold()["patch"], "connections": [
            {**LEAD, "target": {"module": "host", "jack": "ethernet"}}]}),
    "a lead joining two inputs": a_hold(patch={
        **a_hold()["patch"],
        "modules": a_hold()["patch"]["modules"] + [
            {"id": "sub", "type": "moog.subharmonicon"}, {"id": "dfam", "type": "moog.dfam"}],
        "connections": [{"source": {"module": "sub", "jack": "clock_in"},
                         "target": {"module": "dfam", "jack": "adv_clock_in"}}]}),
    "a lead joining two buses of different signals": a_hold(devices=[
        BOARD, {**HOST, "jacks": [{**HOST["jacks"][0], "signal": "midi"}]}]),
    "the same lead twice": a_hold(patch={**a_hold()["patch"], "connections": [LEAD, LEAD]}),
    "the same lead twice, named the other way round": a_hold(patch={
        **a_hold()["patch"],
        "connections": [LEAD, {"source": LEAD["target"], "target": LEAD["source"]}]}),
    "one lead's state twice": a_hold(states={"connections": [
        {**LEAD, "level": "ok", "says": []}, {**LEAD, "level": "fault", "says": []}]}),
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

    def test_a_module_s_state_may_say_what_state_some_of_its_jacks_are_in(self):
        hold = a_hold()
        hold["states"]["modules"]["devkit"]["jacks"] = {
            "usb": {"level": "warn", "says": ["seen: a plug, at a guess"]}}

        status, answer = self.rack.receive(cue("1", {"hold": hold}))

        self.assertEqual(status, 200, answer)
        self.assertEqual(answer["state"]["held"]["states"]["modules"]["devkit"]["jacks"],
                         {"usb": {"level": "warn", "says": ["seen: a plug, at a guess"]}})

    def test_a_lead_named_input_first_is_held_with_its_state(self):
        # The rack draws it output first; the patch and its state name it as sent.
        backwards = {"source": {"module": "dfam", "jack": "adv_clock_in"},
                     "target": {"module": "sub", "jack": "clock_out"}}
        hold = a_hold(patch={**a_hold()["patch"],
                             "modules": [{"id": "sub", "type": "moog.subharmonicon"},
                                         {"id": "dfam", "type": "moog.dfam"}],
                             "connections": [backwards]},
                      states={"connections": [{**backwards, "level": "ok", "says": ["seen"]}]})

        status, answer = self.rack.receive(cue("1", {"hold": hold}))

        self.assertEqual(status, 200, answer)
        self.assertEqual(answer["state"]["held"]["states"]["connections"][0]["level"], "ok")

    def test_every_shipped_example_held_as_it_is_is_a_rig_it_takes(self):
        # The lead rule is the rack's own: every lead carlos ships is one it draws.
        for name, document in family.examples().items():
            with self.subTest(name):
                status, answer = self.rack.receive(
                    cue("1", {"hold": {"patch": document, "devices": [], "states": {}}}))
                self.assertEqual(status, 200, answer)

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


class TheStreamTests(unittest.IsolatedAsyncioTestCase):
    """The state as a stream: at once, then at every cue taken, until the follower goes."""

    def setUp(self):
        catalogue.load_all.cache_clear()
        self.rack = family.Rack(catalogue.opening_rack())
        self.follower = _Following()

    def follow(self, **timing):
        return family.frames(self.rack, self.follower.is_disconnected, **timing)

    async def test_the_first_event_is_the_state_at_once(self):
        self.rack.receive(cue("1", {"turn": "back"}))
        stream = self.follow()

        first = await said(stream)

        self.assertTrue(first.startswith("event: state\ndata: "))
        self.assertTrue(first.endswith("\n\n"))
        self.assertEqual(states(first), [self.rack.snapshot()])
        await stream.aclose()

    async def test_a_cue_taken_is_an_event_carrying_it(self):
        stream = self.follow()
        await said(stream)

        self.rack.receive(cue("5", {"patch": "moog.dfam.simple"}, "Second tune"))
        after = states(await said(stream))

        self.assertEqual(after, [self.rack.snapshot()])
        self.assertEqual(after[0]["cue"]["number"], "5")
        await stream.aclose()

    async def test_a_follower_that_falls_behind_is_sent_the_newest_state_and_no_backlog(self):
        stream = self.follow(heartbeat=0.02, look=0.01)
        await said(stream)

        for number, side in (("1", "back"), ("2", "top"), ("3", "left")):
            self.rack.receive(cue(number, {"turn": side}))
        after = states(await said(stream))

        self.assertEqual([each["cue"]["number"] for each in after], ["3"])
        # And nothing waits behind it: the stream is quiet until the next cue.
        self.assertEqual(await said(stream), ": still here\n\n")
        await stream.aclose()

    async def test_a_refused_cue_is_no_event(self):
        stream = self.follow(heartbeat=0.02, look=0.01)
        await said(stream)

        self.assertEqual(self.rack.receive(cue("9", {"turn": "sideways"}))[0], 422)

        self.assertEqual(await said(stream), ": still here\n\n")
        await stream.aclose()

    async def test_a_quiet_stream_is_kept_open_by_a_comment(self):
        stream = self.follow(heartbeat=0.02, look=0.01)
        await said(stream)

        quiet = await said(stream)

        # A line beginning with a colon is a comment, which no follower reads as an event.
        self.assertEqual(quiet, ": still here\n\n")
        self.assertEqual(states(quiet), [])
        await stream.aclose()

    async def test_a_follower_that_has_gone_ends_its_stream_and_is_let_go(self):
        stream = self.follow(look=0.01)
        await said(stream)
        self.assertEqual(len(self.rack.followers), 1)

        self.follower.gone = True

        with self.assertRaises(StopAsyncIteration):
            await said(stream)
        self.assertEqual(self.rack.followers, [])
        # And a cue is taken as ever, with nobody to tell.
        self.assertEqual(self.rack.receive(cue("1", {"turn": "back"}))[0], 200)

    async def test_a_stream_the_server_closes_is_let_go_too(self):
        stream = self.follow()
        await said(stream)

        await stream.aclose()

        self.assertEqual(self.rack.followers, [])

    async def test_each_follower_is_told(self):
        one, other = self.follow(), self.follow()
        await said(one)
        await said(other)

        self.rack.receive(cue("2", {"turn": "top"}))

        for stream in (one, other):
            told = states(await said(stream))
            self.assertEqual(told[0]["cue"]["number"], "2")
            await stream.aclose()


class TheRoutesTests(unittest.TestCase):
    """The four routes, called the way the application defines them."""

    def setUp(self):
        self.kept = main.rack_from_the_hub
        main.rack_from_the_hub = family.Rack(catalogue.opening_rack())

    def tearDown(self):
        main.rack_from_the_hub = self.kept

    def post(self, raw: bytes):
        response = asyncio.run(main.family_cue(_Posted(raw)))
        return response.status_code, json.loads(response.body)

    def get(self, route):
        response = asyncio.run(route())
        return response, json.loads(response.body)

    def test_a_cue_is_answered_200_with_the_state_and_the_state_route_agrees(self):
        status, answer = self.post(json.dumps(cue("7", {"turn": "back"})).encode())

        self.assertEqual((status, answer["ok"]), (200, True))
        response, state = self.get(main.family_state)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(state["member"], "carlos")
        self.assertEqual(state["cue"]["number"], "7")
        self.assertEqual(state["state"], answer["state"])

    def test_a_cue_taken_names_the_instance_the_identity_names(self):
        status, answer = self.post(json.dumps(cue("7", {"turn": "back"})).encode())
        response, identity = self.get(main.family_identity)

        self.assertEqual((status, response.status_code), (200, 200))
        self.assertEqual(identity, main.rack_from_the_hub.identity())
        self.assertEqual(answer["instance"], identity["instance"])

    def test_the_served_rack_names_the_instance_and_version_healthz_does(self):
        # One id for a hub crediting a delivery and a collector attributing a
        # measurement: two would be two instances to whoever reads both.
        self.assertEqual(self.kept.instance, main.INSTANCE)
        self.assertEqual(self.kept.version, main.settings.version)

    def test_the_events_route_streams_the_state_at_once(self):
        async def opened():
            response = await main.family_events(_Following())
            first = await anext(response.body_iterator)
            await response.body_iterator.aclose()
            return response, first

        response, first = asyncio.run(opened())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.media_type, "text/event-stream")
        self.assertEqual(states(first), [main.rack_from_the_hub.snapshot()])
        self.assertEqual(main.rack_from_the_hub.followers, [])

    def test_the_routes_that_only_read_answer_any_origin(self):
        # A follower is often a page served from somewhere else.
        answered = {
            "state": self.get(main.family_state)[0],
            "identity": self.get(main.family_identity)[0],
            "events": asyncio.run(main.family_events(_Following())),
        }
        for route, response in answered.items():
            with self.subTest(route):
                self.assertEqual(response.headers["access-control-allow-origin"], "*")
        self.assertNotIn("access-control-allow-origin",
                         asyncio.run(main.family_cue(_Posted(b"{}"))).headers)

    def test_a_follower_still_attached_does_not_hold_a_stop_open(self):
        # uvicorn waits for every open response before it stops, and a stream
        # has no end of its own, so the server is started with the wait bounded.
        with mock.patch("uvicorn.run") as run, \
                mock.patch.object(main, "port_is_free", return_value=True), \
                redirect_stdout(io.StringIO()):
            main.main()

        self.assertEqual(run.call_args.kwargs["timeout_graceful_shutdown"], main.STOP_WAITS)
        self.assertGreater(main.STOP_WAITS, 0)
        self.assertLessEqual(main.STOP_WAITS, 5)

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

    def test_all_four_routes_are_on_the_served_port(self):
        served = {(method, route.path) for route in main.app.routes
                  for method in getattr(route, "methods", ())}
        self.assertIn(("POST", "/family/cue"), served)
        for path in ("/family/state", "/family/identity", "/family/events"):
            with self.subTest(path):
                self.assertIn(("GET", path), served)
        # A stream has no end for a HEAD to stand in for.
        self.assertNotIn(("HEAD", "/family/events"), served)


class TheContractTests(unittest.IsolatedAsyncioTestCase):
    """`family/1`'s member side, replayed against the routes as the application defines them.

    `hearth check URL` asks these cases of a running member over HTTP. This
    suite has no network, so it asks the same cases of the same route functions,
    in the same order, and each case is named as it passes. What it cannot see
    is the wire: a server that buffered the stream would pass here and fail
    `hearth check`.
    """

    def setUp(self):
        catalogue.load_all.cache_clear()
        self.kept = main.rack_from_the_hub
        main.rack_from_the_hub = family.Rack(catalogue.opening_rack())

    def tearDown(self):
        main.rack_from_the_hub = self.kept

    async def asked(self, route) -> tuple[int, object]:
        response = await route
        return response.status_code, json.loads(response.body)

    def refused(self, status: int, answer: object) -> None:
        self.assertEqual(status, 422)
        self.assertIsInstance(answer, dict)
        self.assertIs(answer["ok"], False)
        self.assertIsInstance(answer["error"], str)

    async def test_every_member_case_of_the_pinned_set_passes(self):
        passed = []
        served = {(method, route.path) for route in main.app.routes
                  for method in getattr(route, "methods", ())}

        self.assertIn(("GET", "/family/identity"), served)
        status, identity = await self.asked(main.family_identity())
        passed.append("identity-answers")
        self.assertEqual(status, 200)
        self.assertIsInstance(identity, dict)
        passed.append("identity-is-an-object")
        self.assertEqual(identity["contract"], "family/1")
        passed.append("identity-keeps-contract")
        for key in ("member", "family", "instance", "conformance"):
            self.assertIsInstance(identity[key], str)
            self.assertTrue(identity[key])
            passed.append(f"identity-names-{key}")
        name = identity["member"]

        status, before = await self.asked(main.family_state())
        self.assertEqual(status, 200)
        self.assertEqual(before["member"], name)
        self.assertIn("cue", before)
        self.assertIsInstance(before["state"], dict)
        passed.append("state-shape")

        self.refused(*await self.asked(main.family_cue(_Posted(b"{not json"))))
        passed.append("cue-not-json-refused")

        probe = {"cue": {"number": "hearth", "name": "conformance", "fired_at": None},
                 "action": {"hearth-conformance-unknown-verb": True}}
        self.refused(*await self.asked(main.family_cue(_Posted(json.dumps(probe).encode()))))
        passed.append("cue-unknown-action-refused")

        _, after = await self.asked(main.family_state())
        self.assertEqual(after["cue"], before["cue"])
        passed.append("refused-cue-changes-nothing")

        opened = await main.family_events(_Following())
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.media_type, "text/event-stream")
        stream = opened.body_iterator
        first = states(await asyncio.wait_for(anext(stream), 5))
        self.assertEqual(first[0]["member"], name)
        passed.append("events-state-at-once")

        # One real action, sent once the stream is open: a rig held from outside.
        sent = cue("hearth-1", {"hold": a_hold()}, "conformance")
        status, answer = await self.asked(main.family_cue(_Posted(json.dumps(sent).encode())))
        self.assertIn(status, (200, 202))
        self.assertIs(answer["ok"], True)
        passed.append("action-taken")

        told = states(await asyncio.wait_for(anext(stream), 5))
        self.assertEqual(told[0]["cue"]["number"], "hearth-1")
        passed.append("cue-reaches-follower")
        await stream.aclose()

        self.assertEqual(passed, list(MEMBER_CASES))
        # The line the corpus's interop registry reads from a run of this file.
        print(f"\nfamily/1 conformance: {len(passed)} applicable, all passing; "
              f"{HUB_CASES} not applicable")

    def test_the_identity_names_the_version_this_suite_replays(self):
        self.assertEqual(family.CONFORMANCE, PINNED)


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
