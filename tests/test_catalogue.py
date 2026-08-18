import asyncio
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

NODE = shutil.which("node")

from src import catalogue, patch_format
from src.main import (
    catalogue_categories,
    catalogue_device,
    catalogue_device_examples,
    catalogue_index,
)


class CatalogueLoadTests(unittest.TestCase):
    def setUp(self):
        catalogue.load_all.cache_clear()
        self.devices = catalogue.load_all()

    def test_the_shipped_catalogue_loads(self):
        # Every file under catalogue/devices/ validates, or this raises.
        self.assertGreaterEqual(len(self.devices), 9)

    def test_the_named_devices_are_present(self):
        # The set this catalogue was started from. A device disappearing is a
        # breaking change for anything addressing it by id.
        for device_id in (
            "allen-heath.qu24",
            "focusrite.scarlett-2i2",
            "squarp.hapax",
            "nord.stage-3",
            "teenage-engineering.ep-133",
            "moog.subharmonicon",
            "moog.dfam",
        ):
            with self.subTest(device_id):
                self.assertIn(device_id, self.devices)

    def test_every_device_declares_a_known_category(self):
        for device in self.devices.values():
            with self.subTest(device.id):
                self.assertIn(device.category, catalogue.CATEGORIES)

    def test_every_device_has_at_least_one_jack(self):
        for device in self.devices.values():
            with self.subTest(device.id):
                self.assertTrue(device.jacks, f"{device.id} has no jacks")

    def test_ids_are_addressable_and_match_their_filenames(self):
        directory = catalogue.CATALOGUE_ROOT / "devices"
        for device in self.devices.values():
            with self.subTest(device.id):
                self.assertTrue((directory / f"{device.id}.json").is_file())

    def test_every_device_has_something_on_the_face_it_opens_on(self):
        """The face a device opens on is never a blank rectangle.

        The browser draws only the faces that carry something, and opens each
        device on the face its entry names. Those two rules meet here: an entry
        naming a face with nothing on it would arrive showing nothing, and
        turning would step straight over the face it claims to be looked at
        from. Nothing in the loader stops that being written, so it is checked
        over every entry rather than guarded per field.

        A face carries something if a socket is on it, if the layout places
        anything there, or if the device has parameters - those are drawn on
        the face, which is what makes an unmeasured device still show up.
        """
        for device in self.devices.values():
            with self.subTest(device.id):
                face = device.layout.face if device.layout else "front"
                on_it = (
                    any(jack.side == face for jack in device.jacks)
                    or (device.layout and face in device.layout.sides_used())
                    or bool(device.parameters)
                )
                self.assertTrue(
                    on_it,
                    f"{device.id} opens on its {face} and has nothing there",
                )

    def test_the_face_a_device_opens_on_is_one_it_has(self):
        # The loader refuses `layout.face` naming a side the device has not,
        # so this holds by construction. Kept because the browser trusts it:
        # `preferredView()` returns that face without checking the device has
        # it, on the strength of this.
        for device in self.devices.values():
            with self.subTest(device.id):
                face = device.layout.face if device.layout else "front"
                self.assertIn(face, device.sides())

    def test_semi_modulars_are_front_heavy(self):
        # A patch bay lives on the front. If a semi-modular has no front jacks,
        # something has been transcribed onto the wrong side.
        for device in self.devices.values():
            if device.category != "semi-modular":
                continue
            with self.subTest(device.id):
                front = [j for j in device.jacks if j.side == "front"]
                self.assertGreater(len(front), 5)


class ShippedPatchTests(unittest.TestCase):
    """The opening rack and every worked example, checked against the devices.

    A patch document names modules, jacks and parameters by string. Nothing in
    the loader checks those against the catalogue - it cannot, because a
    document is readable without one - so a typo is not an error, it is a
    setting that quietly does nothing.

    Nine of them shipped in the first draft of the opening rack: `volume` on a
    device whose control is `main_level`, four `fader_N` on a desk whose faders
    are `chN_fader`. The rack loaded, drew, and every knob sat at its default.
    """

    def setUp(self):
        catalogue.load_all.cache_clear()
        self.devices = catalogue.load_all()

    def shipped(self):
        """Every patch document in the build, by the file it came from."""
        found = []
        opening = catalogue.opening_rack()
        if opening is not None:
            found.append(("opening.json", opening))
        for path in sorted((catalogue.CATALOGUE_ROOT / "examples").glob("*.json")):
            found.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
        return found

    def test_there_is_something_to_check(self):
        # A sweep over nothing passes loudly and proves nothing.
        self.assertGreater(len(self.shipped()), 10)

    def test_every_shipped_patch_is_a_readable_document(self):
        for name, document in self.shipped():
            with self.subTest(name):
                patch_format.load(document)

    def test_every_module_names_a_device_this_build_has(self):
        for name, document in self.shipped():
            patch = patch_format.load(document)
            for module in patch.modules:
                with self.subTest(f"{name}:{module.id}"):
                    self.assertIn(module.type, self.devices)

    def test_every_cable_end_names_a_jack_that_device_has(self):
        for name, document in self.shipped():
            patch = patch_format.load(document)
            by_id = {m.id: self.devices.get(m.type) for m in patch.modules}
            for cable in patch.connections:
                for end in (cable.source, cable.target):
                    with self.subTest(f"{name}:{end.module}.{end.jack}"):
                        device = by_id.get(end.module)
                        self.assertIsNotNone(device, f"no module {end.module!r}")
                        self.assertIsNotNone(
                            device.jack(end.jack),
                            f"{device.id} has no jack {end.jack!r}")

    def test_every_parameter_names_a_control_that_device_has(self):
        for name, document in self.shipped():
            patch = patch_format.load(document)
            for module in patch.modules:
                device = self.devices.get(module.type)
                if device is None:
                    continue
                known = {p.name for p in device.parameters}
                for parameter in module.parameters:
                    with self.subTest(f"{name}:{module.id}.{parameter}"):
                        self.assertIn(
                            parameter, known,
                            f"{device.id} has no parameter {parameter!r}")

    def test_every_binding_names_a_module_in_its_own_patch(self):
        for name, document in self.shipped():
            patch = patch_format.load(document)
            ids = {m.id for m in patch.modules}
            for binding in patch.midi:
                with self.subTest(f"{name}:{binding.id}"):
                    self.assertIn(binding.module, ids)

    def test_every_row_names_modules_in_its_own_patch(self):
        for name, document in self.shipped():
            patch = patch_format.load(document)
            ids = {m.id for m in patch.modules}
            for group in patch.groups:
                for member in group.members:
                    with self.subTest(f"{name}:{group.id}:{member}"):
                        self.assertIn(member, ids)


class TheOpeningRackTests(unittest.TestCase):
    """The rig the workspace opens on.

    It is the first and often only thing anyone sees, so what it demonstrates
    is what this project appears to be. That makes it worth asserting rather
    than leaving to whoever edits the file next.
    """

    def setUp(self):
        catalogue.load_all.cache_clear()
        self.devices = catalogue.load_all()
        document = catalogue.opening_rack()
        self.assertIsNotNone(document, "this build ships no opening rack")
        self.patch = patch_format.load(document)

    def test_it_shows_every_device_in_the_catalogue(self):
        # A device nobody can see in the opening rack is a device nobody knows
        # is there. Adding one to the catalogue means adding it to the rig.
        shown = {m.type for m in self.patch.modules}
        self.assertEqual(shown, set(self.devices))

    def test_every_device_is_patched_to_something(self):
        # A rig with an unpatched box in it reads as a rig somebody stopped
        # building half way.
        wired = set()
        for cable in self.patch.connections:
            wired.add(cable.source.module)
            wired.add(cable.target.module)
        for module in self.patch.modules:
            with self.subTest(module.id):
                self.assertIn(module.id, wired)

    def test_every_device_is_in_a_row(self):
        claimed = {m for g in self.patch.groups for m in g.members}
        for module in self.patch.modules:
            with self.subTest(module.id):
                self.assertIn(module.id, claimed)

    def test_it_is_drawn_as_laid_out(self):
        # The point of naming real devices is that they look like themselves.
        self.assertEqual(self.patch.display.mode, "irl")

    def test_the_drums_are_on_channel_ten(self):
        channels = {b.source.channel for b in self.patch.midi}
        self.assertIn(10, channels)

    def test_more_than_one_lead_carries_channels(self):
        # So the split reads as a property of a lead rather than as a thing the
        # opening rack happens to do once.
        driven = {b.module for b in self.patch.midi}
        self.assertGreater(len(driven), 1)


class CatalogueRejectionTests(unittest.TestCase):
    """The loader is a gate, so it is tested by feeding it bad files."""

    def _write(self, payload, name="test.device.json"):
        directory = Path(self.tmp.name) / "devices"
        directory.mkdir(exist_ok=True)
        path = directory / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.valid = {
            "id": "test.device",
            "maker": "Test",
            "model": "Device",
            "category": "eurorack",
            "summary": "A device used only by the tests.",
            "jacks": [
                {"name": "out", "label": "OUT", "type": "output", "signal": "audio"}
            ],
            "parameters": [{"name": "level", "label": "LEVEL"}],
        }

    def test_a_valid_file_loads(self):
        device = catalogue.load_device(self._write(self.valid))
        self.assertEqual(device.id, "test.device")
        self.assertEqual(device.jacks[0].side, "front")  # defaults

    def test_unknown_category_is_refused(self):
        self.valid["category"] = "toaster"
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.load_device(self._write(self.valid))
        self.assertIn("toaster", str(caught.exception))

    def test_unknown_signal_is_refused(self):
        self.valid["jacks"][0]["signal"] = "steam"
        with self.assertRaises(catalogue.CatalogueError):
            catalogue.load_device(self._write(self.valid))

    def test_id_must_match_filename(self):
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.load_device(self._write(self.valid, "wrong-name.json"))
        self.assertIn("should be named", str(caught.exception))

    def test_malformed_id_is_refused(self):
        self.valid["id"] = "NotAnId"
        with self.assertRaises(catalogue.CatalogueError):
            catalogue.load_device(self._write(self.valid, "NotAnId.json"))

    def test_duplicate_jack_names_are_refused(self):
        self.valid["jacks"].append(
            {"name": "out", "label": "OUT 2", "type": "output", "signal": "audio"}
        )
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.load_device(self._write(self.valid))
        self.assertIn("duplicate jack", str(caught.exception))

    def test_a_feature_running_off_the_panel_is_refused(self):
        # Legal size, illegal place: a keybed 0.4 wide centred at 0.9 reaches
        # 1.1, and draws as a device that is not the shape the entry says.
        # This is the case the field bounds cannot see, because each number is
        # in range on its own and it is the pair that is wrong.
        self.valid["layout"] = {
            "features": [
                {"kind": "keybed", "keys": 88, "x": 0.9, "y": 0.7,
                 "w": 0.4, "h": 0.4}
            ]
        }
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.load_device(self._write(self.valid))
        self.assertIn("runs off the front", str(caught.exception))

    def test_a_feature_wider_than_its_panel_is_refused(self):
        # The simpler half, caught by the field bound rather than the pair.
        self.valid["layout"] = {
            "features": [
                {"kind": "keybed", "keys": 88, "x": 0.5, "y": 0.7,
                 "w": 1.2, "h": 0.4}
            ]
        }
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.load_device(self._write(self.valid))
        self.assertIn("less than or equal to 1", str(caught.exception))

    def test_a_feature_missing_what_its_kind_needs_is_refused(self):
        for feature, missing in (
            ({"kind": "keybed", "x": 0.5, "y": 0.5, "w": 0.5, "h": 0.2}, "keys"),
            ({"kind": "pads", "x": 0.5, "y": 0.5, "w": 0.5, "h": 0.2}, "rows"),
            ({"kind": "logo", "x": 0.5, "y": 0.5, "w": 0.2, "h": 0.1}, "text"),
        ):
            with self.subTest(feature["kind"]):
                self.valid["layout"] = {"features": [feature]}
                with self.assertRaises(catalogue.CatalogueError) as caught:
                    catalogue.load_device(self._write(self.valid))
                self.assertIn(missing, str(caught.exception))

    def test_facing_a_side_the_device_has_not_is_refused(self):
        self.valid["layout"] = {"face": "left"}
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.load_device(self._write(self.valid))
        self.assertIn("faces the left", str(caught.exception))

    def test_a_feature_gives_the_device_the_side_it_sits_on(self):
        # Sockets alone was the older rule, and under it a device could carry a
        # fully drawn face that officially did not exist.
        self.valid["layout"] = {
            "face": "top",
            "features": [
                {"kind": "screen", "source": "static", "x": 0.5, "y": 0.5,
                 "w": 0.3, "h": 0.2, "side": "top", "text": "HELLO"}
            ],
        }
        device = catalogue.load_device(self._write(self.valid))
        self.assertIn("top", device.sides())
        self.assertEqual(device.layout.face, "top")

    def test_a_box_gives_the_faces_their_own_proportions(self):
        self.valid["layout"] = {"box": {"width": 400, "height": 100, "depth": 200}}
        device = catalogue.load_device(self._write(self.valid))
        self.assertAlmostEqual(device.layout.aspect_of("front"), 4.0)
        self.assertAlmostEqual(device.layout.aspect_of("top"), 2.0)
        self.assertAlmostEqual(device.layout.aspect_of("left"), 2.0)

    def test_unknown_field_is_refused(self):
        self.valid["colour"] = "black"
        with self.assertRaises(catalogue.CatalogueError):
            catalogue.load_device(self._write(self.valid))

    def test_inverted_parameter_range_is_refused(self):
        self.valid["parameters"][0].update({"min": 100, "max": 10})
        with self.assertRaises(catalogue.CatalogueError):
            catalogue.load_device(self._write(self.valid))

    def test_not_json_is_refused(self):
        directory = Path(self.tmp.name) / "devices"
        directory.mkdir(exist_ok=True)
        path = directory / "test.device.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(catalogue.CatalogueError) as caught:
            catalogue.load_device(path)
        self.assertIn("not JSON", str(caught.exception))


class ExampleTests(unittest.TestCase):
    """Every example is a real patch document, checked against the catalogue."""

    def setUp(self):
        catalogue.load_all.cache_clear()
        self.devices = catalogue.load_all()

    def test_every_device_ships_a_simple_and_a_complex_example(self):
        for device_id in self.devices:
            with self.subTest(device_id):
                examples = catalogue.examples_for(device_id)
                self.assertIn("simple", examples, f"{device_id} has no simple example")
                self.assertIn("complex", examples, f"{device_id} has no complex example")

    def test_every_example_is_a_valid_patch(self):
        for device_id in self.devices:
            for kind, document in catalogue.examples_for(device_id).items():
                with self.subTest(f"{device_id}.{kind}"):
                    patch_format.load(document)

    def test_every_example_names_devices_this_catalogue_has(self):
        for device_id in self.devices:
            for kind, document in catalogue.examples_for(device_id).items():
                for module in document["modules"]:
                    with self.subTest(f"{device_id}.{kind}:{module['type']}"):
                        self.assertIn(module["type"], self.devices)

    def test_every_example_cable_names_real_jacks_in_the_right_direction(self):
        for device_id in self.devices:
            for kind, document in catalogue.examples_for(device_id).items():
                types = {m["id"]: self.devices[m["type"]] for m in document["modules"]}
                for index, cable in enumerate(document["connections"]):
                    for role, want in (("source", "output"), ("target", "input")):
                        end = cable[role]
                        device = types[end["module"]]
                        jack = device.jack(end["jack"])
                        with self.subTest(f"{device_id}.{kind}[{index}].{role}"):
                            self.assertIsNotNone(
                                jack, f"{device.id} has no jack {end['jack']!r}"
                            )
                            self.assertEqual(jack.type, want)

    def test_the_complex_example_is_bigger_than_the_simple_one(self):
        # Otherwise the pair is not teaching the difference it claims to.
        for device_id in self.devices:
            examples = catalogue.examples_for(device_id)
            simple, complex_ = examples["simple"], examples["complex"]
            with self.subTest(device_id):
                self.assertGreater(
                    len(complex_["modules"]) + len(complex_["connections"]),
                    len(simple["modules"]) + len(simple["connections"]),
                )

    def test_a_device_with_no_examples_is_not_an_error(self):
        self.assertEqual(catalogue.examples_for("nobody.nothing"), {})


class CatalogueApiTests(unittest.TestCase):
    def setUp(self):
        catalogue.load_all.cache_clear()

    def test_index_carries_devices_and_categories(self):
        payload = asyncio.run(catalogue_index())

        self.assertIn("devices", payload)
        self.assertIn("categories", payload)
        self.assertEqual(len(payload["devices"]), len(catalogue.load_all()))

    def test_index_devices_carry_what_the_frontend_needs(self):
        payload = asyncio.run(catalogue_index())
        device = next(d for d in payload["devices"] if d["id"] == "moog.dfam")

        for key in ("id", "maker", "model", "category", "jacks", "parameters"):
            self.assertIn(key, device)
        self.assertTrue(all("side" in j for j in device["jacks"]))

    def test_categories_endpoint_counts_devices(self):
        payload = asyncio.run(catalogue_categories())
        counts = {c["id"]: c["devices"] for c in payload["categories"]}

        self.assertEqual(counts["semi-modular"], 2)  # DFAM and Subharmonicon
        self.assertEqual(sum(counts.values()), len(catalogue.load_all()))

    def test_a_device_is_addressable_by_id(self):
        payload = asyncio.run(catalogue_device("squarp.hapax"))
        self.assertEqual(payload["maker"], "Squarp Instruments")

    def test_an_unknown_device_is_404_and_says_what_is_known(self):
        response = asyncio.run(catalogue_device("roland.tr909"))
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"roland.tr909", response.body)
        self.assertIn(b"moog.dfam", response.body)  # the `known` list

    def test_examples_endpoint_returns_both_kinds(self):
        payload = asyncio.run(catalogue_device_examples("moog.dfam"))
        self.assertEqual(set(payload["examples"]), {"simple", "complex"})

    def test_examples_for_an_unknown_device_is_404(self):
        response = asyncio.run(catalogue_device_examples("roland.tr909"))
        self.assertEqual(response.status_code, 404)


class FrontendCatalogueContractTests(unittest.TestCase):
    """The browser builds its palette from the catalogue, so it must not also
    carry a private copy of the definitions."""

    def setUp(self):
        self.models = Path("static/models.js").read_text(encoding="utf-8")

    def test_definitions_start_empty_and_are_loaded(self):
        self.assertIn("static definitions = {}", self.models)
        self.assertIn("static load(payload)", self.models)

    def test_no_hard_coded_device_survives_in_the_frontend(self):
        # The old shape was `oscillator: { name: 'VCO', ... }`. If a device
        # definition reappears here, the catalogue has stopped being the source.
        self.assertNotIn("static definitions = {\n", self.models)
        for gone in ("['cv_in', 'input'", "['audio_out', 'output'"):
            self.assertNotIn(gone, self.models)

    def test_the_frontend_fetches_the_catalogue(self):
        main = Path("static/main.js").read_text(encoding="utf-8")
        self.assertIn("/api/catalogue", main)
        self.assertIn("ModuleFactory.load", main)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(NODE, "node is not installed")
class FaceGeometryAcrossTheSeamTests(unittest.TestCase):
    """One box, six faces, computed on both sides of the seam.

    `Layout.aspect_of` here and `aspectOf` in `static/models.js` are two
    implementations of the same rule, in the same position as
    `patch_format.py` and `models.js` are for the interchange format. This
    checks the answers rather than the source text: a string assertion over
    JavaScript catches a rename and misses an inverted ratio, which is the
    error that would actually be made.
    """

    def _js_aspects(self) -> dict:
        script = r"""
        const fs = require('fs');
        (0, eval)(fs.readFileSync('static/models.js', 'utf8')
            + '\nglobalThis.aspectOf = aspectOf;'
            + '\nglobalThis.SIDE_ORDER = SIDE_ORDER;'
            + '\nglobalThis.sidesUsedByLayout = sidesUsedByLayout;');
        const out = {};
        const dir = 'catalogue/devices';
        for (const file of fs.readdirSync(dir)) {
            if (!file.endsWith('.json')) continue;
            const device = JSON.parse(fs.readFileSync(dir + '/' + file, 'utf8'));
            if (!device.layout) continue;
            out[device.id] = {};
            for (const side of SIDE_ORDER) {
                out[device.id][side] = aspectOf(device.layout, side);
            }
        }
        console.log(JSON.stringify(out));
        """
        result = subprocess.run(
            [NODE, "-e", script], capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            self.fail(f"the browser implementation failed:\n{result.stderr}")
        return json.loads(result.stdout)

    def test_both_implementations_agree_on_every_face(self):
        js = self._js_aspects()
        devices = catalogue.load_all()
        laid_out = {i: d for i, d in devices.items() if d.layout}
        self.assertTrue(laid_out, "no device carries a layout to compare")
        self.assertEqual(set(js), set(laid_out), "the two saw different devices")

        for device_id, device in laid_out.items():
            for side in catalogue.SIDE_ORDER:
                with self.subTest(device=device_id, side=side):
                    self.assertAlmostEqual(
                        device.layout.aspect_of(side), js[device_id][side], places=9
                    )

    def test_a_box_gives_each_pair_of_faces_its_own_proportion(self):
        # The point of declaring a box rather than one aspect. A device whose
        # top is drawn at its front's proportion is drawn as a different shape.
        box = catalogue.Box(width=1284, height=120, depth=334)
        self.assertAlmostEqual(box.aspect("front"), 1284 / 120)
        self.assertAlmostEqual(box.aspect("back"), 1284 / 120)
        self.assertAlmostEqual(box.aspect("top"), 1284 / 334)
        self.assertAlmostEqual(box.aspect("bottom"), 1284 / 334)
        self.assertAlmostEqual(box.aspect("left"), 334 / 120)
        self.assertAlmostEqual(box.aspect("right"), 334 / 120)
        self.assertNotAlmostEqual(box.aspect("front"), box.aspect("top"))

    def test_a_device_without_a_box_still_answers(self):
        # Most of the catalogue predates the box and carries a single aspect.
        # It has to keep drawing, at that aspect, on every side.
        layout = catalogue.Layout(aspect=2.3)
        for side in catalogue.SIDE_ORDER:
            self.assertAlmostEqual(layout.aspect_of(side), 2.3)


@unittest.skipUnless(NODE, "node is not installed")
class BothSidesRefuseTheSameDocumentTests(unittest.TestCase):
    """`src/patch_format.py` and `static/models.js` are two implementations of
    one contract, and the interesting half of a contract is what it refuses.

    The existing frontend contract tests are string assertions over the JS
    source: they catch a renamed constant and miss a rule one side never
    implemented. This runs the documents. It found the browser accepting a
    duplicate module id that the server refuses - which loaded a rack quietly
    missing a device and reported success.
    """

    BAD = {
        "duplicate module id": {
            "modules": [
                {"id": "a", "type": "carlos.vco", "view": "front", "parameters": {}},
                {"id": "a", "type": "carlos.vcf", "view": "front", "parameters": {}},
            ],
        },
        "connection naming an absent module": {
            "modules": [
                {"id": "a", "type": "carlos.vco", "view": "front", "parameters": {}},
            ],
            "connections": [
                {"source": {"module": "a", "jack": "audio_out"},
                 "target": {"module": "ghost", "jack": "audio_in"}},
            ],
        },
        "duplicate group id": {
            "modules": [
                {"id": "a", "type": "carlos.vco", "view": "front", "parameters": {}},
            ],
            "groups": [
                {"id": "row-1", "kind": "row", "label": "One", "members": []},
                {"id": "row-1", "kind": "row", "label": "Two", "members": []},
            ],
        },
        "group naming an absent module": {
            "modules": [
                {"id": "a", "type": "carlos.vco", "view": "front", "parameters": {}},
            ],
            "groups": [
                {"id": "row-1", "kind": "row", "label": "One", "members": ["ghost"]},
            ],
        },
        "a version this build cannot read": {"version": 99, "modules": []},
        "a foreign format": {"format": "ableton.set", "modules": []},
    }

    def document(self, overrides):
        base = {
            "format": "carlos.patch", "version": 3, "name": "A bad patch",
            "modules": [], "connections": [], "groups": [],
        }
        base.update(overrides)
        return base

    def test_the_server_refuses_every_one(self):
        for name, overrides in self.BAD.items():
            with self.subTest(name):
                with self.assertRaises(Exception):
                    patch_format.load(self.document(overrides))

    def test_the_browser_refuses_every_one(self):
        cases = {n: self.document(o) for n, o in self.BAD.items()}
        result = subprocess.run(
            [NODE, "tests/refusal_probe.js", json.dumps(cases)],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        outcome = json.loads(result.stdout)

        for name in self.BAD:
            with self.subTest(name):
                self.assertEqual(
                    outcome[name], "refused",
                    f"the server refuses {name!r} and the browser does not",
                )

    def test_the_catalogue_is_the_one_thing_only_the_browser_checks(self):
        # A recorded asymmetry rather than a defect. `patch_format` validates
        # the format, and whether a device exists is a catalogue question - a
        # peer may legitimately hand over a document naming gear this build has
        # never heard of, and the format layer has no business refusing it. The
        # browser has the catalogue in hand and does refuse, because it would
        # otherwise draw a rack with a hole in it.
        naming_a_stranger = self.document({
            "modules": [{"id": "a", "type": "acme.theremin", "view": "front",
                         "parameters": {}}],
        })
        patch_format.load(naming_a_stranger)  # the format is satisfied

        result = subprocess.run(
            [NODE, "tests/refusal_probe.js",
             json.dumps({"unknown device": naming_a_stranger})],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["unknown device"], "refused")
