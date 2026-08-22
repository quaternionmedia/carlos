import asyncio
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from src import catalogue, midi, patch_format
from src.main import midi_info, midi_parse, midi_route

NODE = shutil.which("node")


class EncodeIsTheInverseOfParseTests(unittest.TestCase):
    """`parse(encode(m)) == m`, asserted over the space rather than a table.

    A table of expected bytes tests that somebody typed the table correctly. The
    property is what a device depends on, and it holds or it does not.

    This exists because a malformed message is not a wrong note. MIDI marks a
    status byte with the eighth bit, so a data byte of 200 is read as the start
    of a new message and the device then starves for data - one bad value
    desynchronises the stream rather than sounding wrong, which is why a device
    reports "malformed" and never says which byte.
    """

    def round_trip(self, message: dict):
        bytes_out = midi.encode(dict(message))
        for byte in bytes_out:
            self.assertTrue(0 <= byte <= 255, f"{byte} is not a byte")
        return midi.parse(bytes_out).model_dump(exclude_none=True)

    def test_every_channel_and_note_survives_the_trip(self):
        for channel in (1, 8, 16):
            for note in (0, 60, 127):
                for velocity in (1, 64, 127):
                    message = {"type": "note_on", "channel": channel,
                               "note": note, "value": velocity}
                    with self.subTest(f"ch{channel} n{note} v{velocity}"):
                        self.assertEqual(self.round_trip(message), message)

    def test_a_note_off_stays_a_note_off(self):
        # Sent as a real note-off rather than note-on-with-velocity-zero. Both
        # are legal; the explicit one is never mistaken for a note that failed.
        message = {"type": "note_off", "channel": 3, "note": 60, "value": 0}
        self.assertEqual(self.round_trip(message), message)

    def test_control_change_survives(self):
        for controller in (0, 74, 127):
            message = {"type": "cc", "channel": 1,
                       "controller": controller, "value": 64}
            with self.subTest(controller):
                self.assertEqual(self.round_trip(message), message)

    def test_pitch_bend_survives_its_fourteen_bits(self):
        # The one that splits across two bytes, LSB first - the likeliest
        # encoder to get backwards, and a backwards one still produces valid
        # bytes, so only the round trip catches it.
        for value in (0, 1, 8192, 16382, 16383):
            message = {"type": "pitchbend", "channel": 1, "value": value}
            with self.subTest(value):
                self.assertEqual(self.round_trip(message), message)

    def test_transport_messages_are_a_single_byte(self):
        for kind in ("clock", "start", "stop", "continue"):
            with self.subTest(kind):
                self.assertEqual(len(midi.encode({"type": kind})), 1)
                self.assertEqual(midi.parse(midi.encode({"type": kind})).type, kind)

    def test_channel_aftertouch_and_poly_are_told_apart(self):
        # The same word for two wire messages: polyphonic when it names a note,
        # channel-wide when it does not.
        poly = {"type": "aftertouch", "channel": 2, "note": 60, "value": 90}
        self.assertEqual(self.round_trip(poly), poly)
        whole = {"type": "aftertouch", "channel": 2, "value": 90}
        self.assertEqual(self.round_trip(whole), whole)
        self.assertEqual(len(midi.encode(poly)), 3)
        self.assertEqual(len(midi.encode(whole)), 2)


class BothEncodersAgreeTests(unittest.TestCase):
    """The browser and the seam send the same bytes, or they are two apps.

    `static/midi.js` says it mirrors `src/midi.py`. For parsing, a disagreement
    shows up as a mapping that behaves differently depending where the message
    arrived - annoying and visible. For *sending* it is worse: the two would put
    different bytes on the wire for the same instruction, and the one that is
    wrong is discovered by a device refusing it.

    So this runs both over the same messages and compares the arrays, in the
    same spirit as `FrontendContractTests` for the patch format.
    """

    MESSAGES = [
        {"type": "note_on", "channel": 1, "note": 60, "value": 100},
        {"type": "note_on", "channel": 16, "note": 0, "value": 1},
        {"type": "note_on", "channel": 10, "note": 36, "value": 127},
        {"type": "note_off", "channel": 3, "note": 60, "value": 0},
        {"type": "cc", "channel": 1, "controller": 74, "value": 64},
        {"type": "cc", "channel": 16, "controller": 0, "value": 127},
        {"type": "program", "channel": 5, "value": 12},
        {"type": "aftertouch", "channel": 2, "note": 60, "value": 90},
        {"type": "aftertouch", "channel": 2, "value": 90},
        {"type": "pitchbend", "channel": 1, "value": 0},
        {"type": "pitchbend", "channel": 1, "value": 8192},
        {"type": "pitchbend", "channel": 1, "value": 16383},
        {"type": "clock"},
        {"type": "start"},
        {"type": "stop"},
        {"type": "continue"},
    ]

    @unittest.skipUnless(NODE, "node is not installed")
    def test_the_browser_encodes_what_the_seam_encodes(self):
        script = (
            "const fs=require('fs');"
            "const src=fs.readFileSync('static/midi.js','utf8');"
            "const make=new Function(src+';return midiEncode;');"
            "const midiEncode=make();"
            "const out=JSON.parse(process.argv[1]).map(m=>{"
            "  try { return midiEncode(m); } catch (e) { return {error: e.message}; }"
            "});"
            "process.stdout.write(JSON.stringify(out));"
        )
        result = subprocess.run(
            [NODE, "-e", script, json.dumps(self.MESSAGES)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        from_browser = json.loads(result.stdout)

        self.assertEqual(len(from_browser), len(self.MESSAGES))
        for message, browser in zip(self.MESSAGES, from_browser):
            with self.subTest(message["type"] + str(message.get("value", ""))):
                self.assertNotIsInstance(
                    browser, dict, f"the browser refused {message}: {browser}")
                self.assertEqual(
                    browser, midi.encode(dict(message)),
                    f"the two encoders disagree about {message}",
                )

    @unittest.skipUnless(NODE, "node is not installed")
    def test_both_refuse_the_same_malformed_messages(self):
        bad = [
            {"type": "note_on", "channel": 1, "note": 200, "value": 1},
            {"type": "note_on", "channel": 0, "note": 60, "value": 1},
            {"type": "note_on", "channel": 17, "note": 60, "value": 1},
            {"type": "note_on", "note": 60, "value": 1},
            {"type": "pitchbend", "channel": 1, "value": 20000},
            {"type": "nonsense", "channel": 1},
        ]
        script = (
            "const fs=require('fs');"
            "const src=fs.readFileSync('static/midi.js','utf8');"
            "const midiEncode=new Function(src+';return midiEncode;')();"
            "const out=JSON.parse(process.argv[1]).map(m=>{"
            "  try { midiEncode(m); return 'accepted'; } catch (e) { return 'refused'; }"
            "});"
            "process.stdout.write(JSON.stringify(out));"
        )
        result = subprocess.run(
            [NODE, "-e", script, json.dumps(bad)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        for message, browser in zip(bad, json.loads(result.stdout)):
            with self.subTest(str(message)):
                self.assertEqual(browser, "refused",
                                 f"the browser accepted {message}")
                with self.assertRaises(midi.MidiError):
                    midi.encode(dict(message))


class NothingMalformedLeavesTests(unittest.TestCase):
    """What `encode` refuses, and that it says which value was wrong."""

    def refusal(self, message: dict) -> str:
        with self.assertRaises(midi.MidiError) as caught:
            midi.encode(message)
        return str(caught.exception)

    def test_a_data_byte_above_127_is_refused_with_the_reason(self):
        for field, message in (
            ("note", {"type": "note_on", "channel": 1, "note": 200, "value": 64}),
            ("velocity", {"type": "note_on", "channel": 1, "note": 60, "value": 200}),
            ("controller", {"type": "cc", "channel": 1, "controller": 200, "value": 1}),
        ):
            with self.subTest(field):
                said = self.refusal(message)
                self.assertRegex(said, r"127|less than or equal")

    def test_a_channel_outside_one_to_sixteen_is_refused(self):
        for channel in (0, 17, -1):
            with self.subTest(channel):
                self.refusal({"type": "note_on", "channel": channel,
                              "note": 60, "value": 64})

    def test_a_message_with_no_channel_is_refused(self):
        self.assertIn("channel", self.refusal({"type": "note_on", "note": 60}))

    def test_a_pitch_bend_past_fourteen_bits_is_refused(self):
        self.assertIn("16383", self.refusal(
            {"type": "pitchbend", "channel": 1, "value": 20000}))

    def test_the_refusal_does_not_name_the_library(self):
        said = self.refusal({"type": "note_on", "channel": 1, "note": 200, "value": 1})
        for leak in ("pydantic", "errors.pydantic.dev", "MidiMessage", "input_value"):
            with self.subTest(leak):
                self.assertNotIn(leak, said)

    def test_a_sound_message_is_not_refused(self):
        # The other half. A guard that refuses everything is not a guard.
        self.assertEqual(
            midi.encode({"type": "note_on", "channel": 10, "note": 36, "value": 100}),
            [0x99, 36, 100],
        )


class ParseTests(unittest.TestCase):
    """Real MIDI arrives as status and data bytes. A build that only accepts a
    friendly JSON shape has anticipated a description of a signal, not a
    signal."""

    def test_note_on(self):
        message = midi.parse([0x99, 36, 100])  # channel 10, kick, velocity 100

        self.assertEqual(message.type, "note_on")
        self.assertEqual(message.channel, 10)  # wire is 0-based, humans are not
        self.assertEqual(message.note, 36)
        self.assertAlmostEqual(message.intensity, 100 / 127, places=4)

    def test_note_on_with_velocity_zero_is_a_note_off(self):
        # Devices really send this. Reading it as a note-on leaves the display
        # lit with nothing playing.
        self.assertEqual(midi.parse([0x90, 60, 0]).type, "note_off")
        self.assertEqual(midi.parse([0x90, 60, 0]).intensity, 0.0)

    def test_note_off_proper(self):
        self.assertEqual(midi.parse([0x80, 60, 64]).type, "note_off")

    def test_control_change(self):
        message = midi.parse([0xB0, 74, 127])

        self.assertEqual(message.type, "cc")
        self.assertEqual(message.controller, 74)
        self.assertEqual(message.intensity, 1.0)

    def test_pitchbend_is_fourteen_bit_lsb_first(self):
        centre = midi.parse([0xE0, 0x00, 0x40])
        self.assertEqual(centre.value, 8192)
        self.assertEqual(midi.parse([0xE0, 0x7F, 0x7F]).value, 16383)

    def test_program_change_has_one_data_byte(self):
        self.assertEqual(midi.parse([0xC3, 5]).type, "program")
        self.assertEqual(midi.parse([0xC3, 5]).channel, 4)

    def test_transport(self):
        for status, kind in ((0xF8, "clock"), (0xFA, "start"),
                             (0xFB, "continue"), (0xFC, "stop")):
            with self.subTest(kind):
                self.assertEqual(midi.parse([status]).type, kind)

    def test_a_stop_is_zero_intensity(self):
        self.assertEqual(midi.parse([0xFC]).intensity, 0.0)

    def test_a_data_byte_is_not_a_message(self):
        with self.assertRaises(midi.MidiError) as caught:
            midi.parse([0x40, 0x00])
        self.assertIn("data byte", str(caught.exception))

    def test_truncated_message_is_refused(self):
        with self.assertRaises(midi.MidiError):
            midi.parse([0x90, 60])

    def test_no_bytes_is_refused(self):
        with self.assertRaises(midi.MidiError):
            midi.parse([])


class BindingTests(unittest.TestCase):
    def binding(self, **source):
        return midi.MidiBinding(id="b1", source=midi.MidiSource(**source), module="m1")

    def test_a_channel_binding_takes_everything_on_that_channel(self):
        b = self.binding(type="channel", channel=10)

        self.assertTrue(midi.matches(b.source, midi.parse([0x99, 36, 100])))
        self.assertTrue(midi.matches(b.source, midi.parse([0xB9, 74, 10])))
        self.assertFalse(midi.matches(b.source, midi.parse([0x90, 36, 100])))

    def test_a_note_binding_selects_one_note(self):
        b = self.binding(type="note", note=36)

        self.assertTrue(midi.matches(b.source, midi.parse([0x90, 36, 100])))
        self.assertFalse(midi.matches(b.source, midi.parse([0x90, 38, 100])))

    def test_omitting_the_channel_is_a_wildcard(self):
        # A rig where a machine moves to another channel should not need its
        # bindings rewritten.
        b = self.binding(type="note", note=36)
        for channel in range(16):
            with self.subTest(channel):
                self.assertTrue(
                    midi.matches(b.source, midi.parse([0x90 | channel, 36, 100]))
                )

    def test_a_cc_binding_ignores_notes(self):
        b = self.binding(type="cc", controller=74)
        self.assertFalse(midi.matches(b.source, midi.parse([0x90, 74, 100])))
        self.assertTrue(midi.matches(b.source, midi.parse([0xB0, 74, 100])))

    def test_transport_matches_all_four(self):
        b = self.binding(type="transport")
        for status in (0xF8, 0xFA, 0xFB, 0xFC):
            with self.subTest(hex(status)):
                self.assertTrue(midi.matches(b.source, midi.parse([status])))

    def test_a_note_source_cannot_select_a_controller(self):
        with self.assertRaises(Exception):
            midi.MidiSource(type="note", controller=74)

    def test_out_of_range_channel_is_refused(self):
        for channel in (0, 17):
            with self.subTest(channel):
                with self.assertRaises(Exception):
                    midi.MidiSource(type="channel", channel=channel)


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.bindings = [
            midi.MidiBinding(
                id="kick", module="dfam",
                source=midi.MidiSource(type="note", channel=10, note=36),
            ),
            midi.MidiBinding(
                id="everything-on-10", module="desk",
                source=midi.MidiSource(type="channel", channel=10),
            ),
            midi.MidiBinding(
                id="clock", module="hapax",
                source=midi.MidiSource(type="transport"),
            ),
        ]

    def test_all_matching_bindings_fire(self):
        # One message genuinely can concern two devices; picking a single
        # winner would hide that.
        activity = midi.route(self.bindings, midi.parse([0x99, 36, 100]))

        self.assertEqual({a.module for a in activity}, {"dfam", "desk"})

    def test_a_non_matching_message_lights_nothing(self):
        self.assertEqual(midi.route(self.bindings, midi.parse([0x90, 60, 100])), [])

    def test_clock_reaches_only_the_transport_binding(self):
        activity = midi.route(self.bindings, midi.parse([0xF8]))
        self.assertEqual([a.module for a in activity], ["hapax"])

    def test_activity_carries_the_intensity(self):
        activity = midi.route(self.bindings, midi.parse([0x99, 36, 64]))
        self.assertAlmostEqual(activity[0].intensity, 64 / 127, places=4)

    def test_a_note_off_routes_with_zero_intensity(self):
        # It has to route, or the device it lit never gets told to stop.
        activity = midi.route(self.bindings, midi.parse([0x89, 36, 0]))
        self.assertTrue(activity)
        self.assertEqual(activity[0].intensity, 0.0)


class RadVocabularyTests(unittest.TestCase):
    def test_rad_speed_axis_controllers_are_recorded_as_reserved(self):
        # rad drives bpm, aps, div and quantize from CC 20-23. Carlos may watch
        # them; giving them a second meaning would repurpose a shared vocabulary,
        # which the seams record permits extending and forbids repurposing.
        self.assertEqual(midi.RAD_RESERVED_CC, (20, 21, 22, 23))

    def test_the_api_says_which_controllers_are_reserved(self):
        payload = asyncio.run(midi_info())
        self.assertEqual(payload["reserved_cc"]["controllers"], [20, 21, 22, 23])
        self.assertIn("rad", payload["reserved_cc"]["why"])

    def test_the_frontend_agrees_on_the_reserved_set(self):
        source = Path("static/midi.js").read_text(encoding="utf-8")
        self.assertIn("MIDI_RESERVED_CC = [20, 21, 22, 23]", source)


class MidiApiTests(unittest.TestCase):
    def test_parse_endpoint(self):
        payload = asyncio.run(midi_parse({"bytes": [0x99, 36, 100]}))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["message"]["type"], "note_on")

    def test_parse_endpoint_refuses_rubbish_with_a_reason(self):
        response = asyncio.run(midi_parse({"bytes": [0x40]}))
        self.assertEqual(response.status_code, 422)
        self.assertIn(b"data byte", response.body)

    def test_route_endpoint_takes_raw_bytes(self):
        payload = asyncio.run(midi_route({
            "bindings": [{
                "id": "b1", "module": "dfam",
                "source": {"type": "note", "channel": 10, "note": 36},
            }],
            "bytes": [0x99, 36, 100],
        }))

        self.assertTrue(payload["ok"])
        self.assertEqual([a["module"] for a in payload["activity"]], ["dfam"])

    def test_route_endpoint_refuses_a_bad_binding(self):
        response = asyncio.run(midi_route({
            "bindings": [{"id": "b1", "module": "x", "source": {"type": "nonsense"}}],
            "bytes": [0x99, 36, 100],
        }))
        self.assertEqual(response.status_code, 422)


class FormatV3Tests(unittest.TestCase):
    def v3(self, **overrides):
        document = {
            "format": "carlos.patch", "version": 3, "name": "Mapped",
            "modules": [{"id": "a", "type": "moog.dfam"}],
            "connections": [], "groups": [],
            "display": {"mode": "irl"},
            "midi": [{
                "id": "kick", "module": "a",
                "source": {"type": "note", "channel": 10, "note": 36},
            }],
        }
        document.update(overrides)
        return document

    def test_a_v3_document_carries_bindings_and_a_mode(self):
        patch = patch_format.load(self.v3())

        self.assertEqual(patch.display.mode, "irl")
        self.assertEqual(patch.midi[0].source.note, 36)

    def test_both_default_when_absent(self):
        document = self.v3()
        del document["display"]
        del document["midi"]
        patch = patch_format.load(document)

        self.assertEqual(patch.display.mode, "minimal")
        self.assertEqual(patch.midi, [])

    def test_a_binding_naming_an_absent_module_is_refused(self):
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(self.v3(midi=[{
                "id": "x", "module": "ghost",
                "source": {"type": "channel", "channel": 1},
            }]))
        self.assertIn("ghost", str(caught.exception))

    def test_duplicate_binding_ids_are_refused(self):
        source = {"type": "channel", "channel": 1}
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(self.v3(midi=[
                {"id": "same", "module": "a", "source": source},
                {"id": "same", "module": "a", "source": source},
            ]))
        self.assertIn("duplicate midi binding", str(caught.exception))

    def test_an_invented_display_mode_is_refused(self):
        with self.assertRaises(patch_format.PatchFormatError):
            patch_format.load(self.v3(display={"mode": "photoreal"}))

    def test_a_v2_document_upgrades(self):
        document = self.v3(version=2)
        del document["display"]
        del document["midi"]
        patch = patch_format.load(document)

        self.assertEqual(patch.version, 3)
        self.assertEqual(patch.display.mode, "minimal")
        self.assertEqual(patch.midi, [])

    def test_a_v1_document_upgrades_all_the_way(self):
        patch = patch_format.load({
            "format": "carlos.patch", "version": 1,
            "modules": [{"id": "a", "type": "carlos.vco"}], "connections": [],
        })

        self.assertEqual(patch.version, 3)
        self.assertEqual(patch.groups, [])
        self.assertEqual(patch.midi, [])
        self.assertEqual(patch.display.mode, "minimal")

    def test_a_v4_document_is_still_refused(self):
        with self.assertRaises(patch_format.PatchFormatError):
            patch_format.load(self.v3(version=4))


class LayoutTests(unittest.TestCase):
    def setUp(self):
        catalogue.load_all.cache_clear()
        self.devices = catalogue.load_all()

    def test_some_devices_carry_a_layout(self):
        laid_out = [d for d in self.devices.values() if d.layout]
        self.assertGreaterEqual(len(laid_out), 5)

    def test_a_device_without_a_layout_still_loads(self):
        # The catalogue accepts a device the moment someone describes it;
        # holding one back for want of a measured panel would collect fewer.
        #
        # This used to assert some shipped device had no layout, which made
        # finishing the catalogue break it - the fallback was being covered by
        # the catalogue staying incomplete. It is covered by a device built
        # here instead, so the path stays exercised and the shipped entries are
        # free to all be finished.
        bare = catalogue.Device(
            id="test.bare",
            maker="Test",
            model="Bare",
            category="eurorack",
            summary="A device nobody has measured a panel for.",
            jacks=[{"name": "out", "label": "OUT", "type": "output",
                    "signal": "audio", "connector": "1/4in"}],
            parameters=[{"name": "level", "label": "LEVEL"}],
        )
        self.assertIsNone(bare.layout)
        self.assertEqual(bare.sides(), ["front"])

    def test_the_shipped_catalogue_is_fully_laid_out(self):
        # The other direction, and the one worth having now: every entry
        # carries a box and a face, so nothing ships drawn at a proportion
        # that only ever described its front.
        for device in self.devices.values():
            with self.subTest(device.id):
                self.assertIsNotNone(device.layout, "no layout")
                self.assertIsNotNone(device.layout.box, "no box")
                self.assertIn(device.layout.face, device.sides())

    def test_every_layout_places_only_things_the_device_has(self):
        for device in self.devices.values():
            if not device.layout:
                continue
            names = {j.name for j in device.jacks}
            params = {p.name for p in device.parameters}
            with self.subTest(device.id):
                self.assertLessEqual(set(device.layout.jacks), names)
                self.assertLessEqual(set(device.layout.controls), params)

    def test_every_placement_agrees_with_the_declared_side(self):
        for device in self.devices.values():
            if not device.layout:
                continue
            for name, placement in device.layout.jacks.items():
                with self.subTest(f"{device.id}:{name}"):
                    self.assertEqual(placement.side, device.jack(name).side)

    def test_a_layout_placing_an_unknown_jack_is_refused(self):
        payload = {
            "id": "test.device", "maker": "T", "model": "D",
            "category": "eurorack", "summary": "x",
            "jacks": [{"name": "out", "label": "OUT", "type": "output", "signal": "audio", "connector": "1/4in"}],
            "layout": {"aspect": 1, "jacks": {"nope": {"x": 0.5, "y": 0.5}}},
        }
        with self.assertRaises(Exception):
            catalogue.Device.model_validate(payload)

    def test_a_layout_contradicting_a_jacks_side_is_refused(self):
        payload = {
            "id": "test.device", "maker": "T", "model": "D",
            "category": "eurorack", "summary": "x",
            "jacks": [{"name": "out", "label": "OUT", "type": "output",
                       "signal": "audio", "connector": "1/4in", "side": "back"}],
            "layout": {"aspect": 1,
                       "jacks": {"out": {"x": 0.5, "y": 0.5, "side": "front"}}},
        }
        with self.assertRaises(Exception):
            catalogue.Device.model_validate(payload)

    def test_the_catalogue_api_serves_layouts(self):
        from src.main import catalogue_index

        payload = asyncio.run(catalogue_index())

        # Every entry is laid out now, and the browser has to receive the whole
        # of it: the box it derives each face's proportion from, the face it
        # opens on, and the furniture it draws.
        for served in payload["devices"]:
            with self.subTest(served["id"]):
                layout = served["layout"]
                self.assertIsNotNone(layout)
                self.assertIn("box", layout)
                self.assertIn("face", layout)
                self.assertIn("features", layout)

        dfam = next(d for d in payload["devices"] if d["id"] == "moog.dfam")
        self.assertEqual(
            set(dfam["layout"]["box"]), {"width", "height", "depth"}
        )


class FrontendMidiAndModeTests(unittest.TestCase):
    def setUp(self):
        self.models = Path("static/models.js").read_text(encoding="utf-8")
        self.midi = Path("static/midi.js").read_text(encoding="utf-8")

    def test_the_frontend_writes_version_3(self):
        self.assertIn("const PATCH_VERSION = 3", self.models)
        self.assertIn("const PATCH_READS = [1, 2, 3]", self.models)

    def test_the_frontend_has_both_modes(self):
        self.assertIn("setMode(mode)", self.models)
        self.assertIn("renderIrlFace(side)", self.models)
        self.assertIn("'irl'", self.models)

    def test_activity_is_not_exported(self):
        # The binding is state; the flash is not. If `is-active` ever reaches
        # exportState, a screenshot has become part of the document.
        exporter = self.models.split("exportState()")[1].split("importState")[0]
        for leak in ("is-active", "activity", "intensity"):
            with self.subTest(leak):
                self.assertNotIn(leak, exporter)

    def test_the_frontend_reports_rather_than_swallows_a_missing_port(self):
        for state in ("unsupported", "refused", "no-ports"):
            with self.subTest(state):
                self.assertIn(state, self.midi)

    def test_a_synthetic_source_exists(self):
        # A feature only visible with hardware plugged in is a feature nobody
        # reviews.
        self.assertIn("simulate(", self.midi)


@unittest.skipUnless(NODE, "node is not installed")
class CrossImplementationTests(unittest.TestCase):
    """Python and the browser must agree, or a mapping means two things."""

    def js_parse(self, data):
        script = """
        const fs = require('fs');
        (0, eval)(fs.readFileSync('static/midi.js', 'utf8')
            + '\\nglobalThis.midiParse = midiParse;'
            + '\\nglobalThis.midiRoute = midiRoute;'
            + '\\nglobalThis.midiIntensity = midiIntensity;');
        const out = %s;
        console.log(JSON.stringify(out));
        """ % data
        result = subprocess.run(
            [NODE, "-e", script], capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            self.fail(result.stderr)
        return json.loads(result.stdout)

    def test_both_sides_parse_the_same_bytes_the_same_way(self):
        cases = [
            [0x99, 36, 100], [0x90, 60, 0], [0x80, 60, 64],
            [0xB0, 74, 127], [0xE0, 0x00, 0x40], [0xC3, 5], [0xF8], [0xFC],
        ]
        js = self.js_parse(
            "[%s].map(b => midiParse(b))" % ",".join(str(c) for c in cases)
        )
        for raw, from_js in zip(cases, js):
            with self.subTest(raw):
                from_py = midi.parse(raw).model_dump(exclude_none=True)
                trimmed = {k: v for k, v in from_js.items() if v is not None}
                self.assertEqual(trimmed, from_py)

    def test_both_sides_route_the_same_way(self):
        bindings = [{
            "id": "kick", "module": "dfam",
            "source": {"type": "note", "channel": 10, "note": 36},
        }, {
            "id": "any10", "module": "desk",
            "source": {"type": "channel", "channel": 10},
        }]
        js = self.js_parse(
            "midiRoute(%s, midiParse([153,36,100])).map(a => a.module)"
            % json.dumps(bindings)
        )
        py = [
            a.module for a in
            midi.route([midi.load_binding(b) for b in bindings], midi.parse([0x99, 36, 100]))
        ]
        self.assertEqual(js, py)

    def test_both_sides_agree_a_velocity_zero_note_is_off(self):
        js = self.js_parse("midiParse([144, 60, 0]).type")
        self.assertEqual(js, midi.parse([0x90, 60, 0]).type)


if __name__ == "__main__":
    unittest.main()
