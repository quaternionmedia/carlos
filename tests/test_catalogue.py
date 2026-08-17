import asyncio
import json
import tempfile
import unittest
from pathlib import Path

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
