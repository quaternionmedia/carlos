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

    def test_semi_modulars_are_front_heavy(self):
        # A patch bay lives on the front. If a semi-modular has no front jacks,
        # something has been transcribed onto the wrong side.
        for device in self.devices.values():
            if device.category != "semi-modular":
                continue
            with self.subTest(device.id):
                front = [j for j in device.jacks if j.side == "front"]
                self.assertGreater(len(front), 5)


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
