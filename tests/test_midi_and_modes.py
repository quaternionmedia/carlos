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
        bare = [d for d in self.devices.values() if not d.layout]
        self.assertTrue(bare, "no device exercises the fallback path")

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
            "jacks": [{"name": "out", "label": "OUT", "type": "output", "signal": "audio"}],
            "layout": {"aspect": 1, "jacks": {"nope": {"x": 0.5, "y": 0.5}}},
        }
        with self.assertRaises(Exception):
            catalogue.Device.model_validate(payload)

    def test_a_layout_contradicting_a_jacks_side_is_refused(self):
        payload = {
            "id": "test.device", "maker": "T", "model": "D",
            "category": "eurorack", "summary": "x",
            "jacks": [{"name": "out", "label": "OUT", "type": "output",
                       "signal": "audio", "side": "back"}],
            "layout": {"aspect": 1,
                       "jacks": {"out": {"x": 0.5, "y": 0.5, "side": "front"}}},
        }
        with self.assertRaises(Exception):
            catalogue.Device.model_validate(payload)

    def test_the_catalogue_api_serves_layouts(self):
        from src.main import catalogue_index

        payload = asyncio.run(catalogue_index())
        dfam = next(d for d in payload["devices"] if d["id"] == "moog.dfam")
        hapax = next(d for d in payload["devices"] if d["id"] == "squarp.hapax")

        self.assertIsNotNone(dfam["layout"])
        self.assertIsNone(hapax["layout"])  # falls back, and says so


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
