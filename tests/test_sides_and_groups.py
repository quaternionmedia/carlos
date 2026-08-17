import unittest
from pathlib import Path

from src import catalogue, patch_format


def v2(**overrides):
    document = {
        "format": "carlos.patch",
        "version": 2,
        "name": "Grouped",
        "modules": [
            {"id": "a", "type": "carlos.vco", "view": "front", "parameters": {}},
            {"id": "b", "type": "carlos.vcf", "view": "back", "parameters": {}},
            {"id": "c", "type": "teenage-engineering.ep-133", "view": "top",
             "parameters": {}},
        ],
        "connections": [],
        "groups": [
            {"id": "row-1", "kind": "row", "label": "Synths", "members": ["a", "b"]}
        ],
    }
    document.update(overrides)
    return document


class SideTests(unittest.TestCase):
    def setUp(self):
        catalogue.load_all.cache_clear()
        self.devices = catalogue.load_all()

    def test_a_device_declares_only_the_sides_it_uses(self):
        ko2 = self.devices["teenage-engineering.ep-133"]
        # Everything is on its top edge, so it has a face and a top, no back.
        self.assertEqual(ko2.sides(), ["front", "top"])

    def test_front_is_always_present_even_with_nothing_socketed_there(self):
        # A Stage 3 wires entirely from the back and still has a face you play,
        # which is where the knobs are drawn.
        nord = self.devices["nord.stage-3"]
        self.assertEqual([j.side for j in nord.jacks].count("front"), 0)
        self.assertIn("front", nord.sides())

    def test_sides_come_back_in_cycling_order(self):
        for device in self.devices.values():
            with self.subTest(device.id):
                order = [s for s in catalogue.SIDE_ORDER if s in device.sides()]
                self.assertEqual(device.sides(), order)

    def test_no_device_claims_a_side_with_nothing_on_it(self):
        for device in self.devices.values():
            used = {j.side for j in device.jacks} | {"front"}
            with self.subTest(device.id):
                self.assertEqual(set(device.sides()), used)

    def test_the_format_accepts_every_side_the_catalogue_can_produce(self):
        for device in self.devices.values():
            for side in device.sides():
                with self.subTest(f"{device.id}:{side}"):
                    document = v2(
                        modules=[{"id": "x", "type": device.id, "view": side}],
                        groups=[],
                    )
                    self.assertEqual(
                        patch_format.load(document).modules[0].view, side
                    )

    def test_an_invented_side_is_still_refused(self):
        with self.assertRaises(patch_format.PatchFormatError):
            patch_format.load(v2(modules=[{"id": "a", "type": "carlos.vco",
                                           "view": "inside"}], groups=[]))

    def test_side_order_agrees_between_catalogue_and_format(self):
        self.assertEqual(catalogue.SIDE_ORDER, patch_format.SIDE_ORDER)


class GroupTests(unittest.TestCase):
    def test_a_patch_can_carry_rows(self):
        patch = patch_format.load(v2())

        self.assertEqual(len(patch.groups), 1)
        self.assertEqual(patch.groups[0].kind, "row")
        self.assertEqual(patch.groups[0].members, ["a", "b"])

    def test_groups_default_to_empty(self):
        document = v2()
        del document["groups"]
        self.assertEqual(patch_format.load(document).groups, [])

    def test_a_module_in_no_group_is_allowed(self):
        # Module "c" is loose. Loose is a state, not an error.
        patch = patch_format.load(v2())
        claimed = {m for g in patch.groups for m in g.members}
        self.assertNotIn("c", claimed)

    def test_a_group_naming_an_absent_module_is_refused(self):
        document = v2(groups=[{"id": "row-1", "members": ["ghost"]}])
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(document)
        self.assertIn("ghost", str(caught.exception))

    def test_a_module_in_two_groups_is_refused(self):
        document = v2(groups=[
            {"id": "row-1", "members": ["a"]},
            {"id": "row-2", "members": ["a"]},
        ])
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(document)
        self.assertIn("two groups", str(caught.exception))

    def test_duplicate_group_ids_are_refused(self):
        document = v2(groups=[
            {"id": "row-1", "members": ["a"]},
            {"id": "row-1", "members": ["b"]},
        ])
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(document)
        self.assertIn("duplicate group id", str(caught.exception))

    def test_an_unknown_group_kind_is_refused(self):
        # Rows are the only kind today; a second one is a deliberate addition.
        document = v2(groups=[{"id": "g", "kind": "constellation", "members": []}])
        with self.assertRaises(patch_format.PatchFormatError):
            patch_format.load(document)

    def test_an_empty_group_is_allowed(self):
        patch = patch_format.load(v2(groups=[{"id": "row-1", "members": []}]))
        self.assertEqual(patch.groups[0].members, [])


class VersionUpgradeTests(unittest.TestCase):
    """Version 1 documents still load. That is a defined upgrade, not a
    hopeful read: the step knows exactly what changed."""

    def v1(self):
        return {
            "format": "carlos.patch",
            "version": 1,
            "name": "Made By An Older Build",
            "modules": [
                {"id": "a", "type": "carlos.vco", "view": "back",
                 "parameters": {"frequency": 90.0}}
            ],
            "connections": [],
        }

    def test_a_version_1_document_still_loads(self):
        patch = patch_format.load(self.v1())
        self.assertEqual(patch.name, "Made By An Older Build")

    def test_the_upgrade_gives_it_the_field_it_lacked(self):
        self.assertEqual(patch_format.load(self.v1()).groups, [])

    def test_the_upgrade_changes_nothing_else(self):
        patch = patch_format.load(self.v1())
        self.assertEqual(patch.modules[0].view, "back")
        self.assertEqual(patch.modules[0].parameters["frequency"], 90.0)

    def test_the_upgrade_stamps_the_current_version(self):
        self.assertEqual(
            patch_format.load(self.v1()).version, patch_format.FORMAT_VERSION)

    def test_upgrade_does_not_mutate_its_input(self):
        original = self.v1()
        patch_format.load(original)
        self.assertEqual(original["version"], 1)
        self.assertNotIn("groups", original)

    def test_a_future_version_is_still_refused(self):
        future = patch_format.FORMAT_VERSION + 1
        document = self.v1()
        document["version"] = future
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(document)
        self.assertIn(f"version {future}", str(caught.exception))

    def test_the_refusal_says_what_is_readable(self):
        document = self.v1()
        document["version"] = 99
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(document)
        readable = ", ".join(str(v) for v in patch_format.SUPPORTED_VERSIONS)
        self.assertIn(readable, str(caught.exception))


class ShippedExampleTests(unittest.TestCase):
    def setUp(self):
        catalogue.load_all.cache_clear()
        self.devices = catalogue.load_all()

    def test_every_example_is_at_the_current_version(self):
        for device_id in self.devices:
            for kind, document in catalogue.examples_for(device_id).items():
                with self.subTest(f"{device_id}.{kind}"):
                    self.assertEqual(document["version"], patch_format.FORMAT_VERSION)

    def test_every_example_module_faces_a_side_its_device_has(self):
        for device_id in self.devices:
            for kind, document in catalogue.examples_for(device_id).items():
                for module in document["modules"]:
                    device = self.devices[module["type"]]
                    with self.subTest(f"{device_id}.{kind}:{module['id']}"):
                        self.assertIn(module.get("view", "front"), device.sides())

    def test_the_complex_examples_demonstrate_grouping(self):
        grouped = [
            device_id for device_id in self.devices
            if catalogue.examples_for(device_id).get("complex", {}).get("groups")
        ]
        self.assertTrue(grouped, "no complex example shows a row")

    def test_at_least_one_example_shows_a_side_that_is_not_front_or_back(self):
        seen = set()
        for device_id in self.devices:
            for document in catalogue.examples_for(device_id).values():
                seen.update(m.get("view", "front") for m in document["modules"])
        self.assertTrue(seen - {"front", "back"}, f"only saw {seen}")


class FrontendSideAndGroupContractTests(unittest.TestCase):
    def setUp(self):
        self.models = Path("static/models.js").read_text(encoding="utf-8")

    def test_the_frontend_writes_the_current_version_and_reads_the_old_ones(self):
        # Asserted against the Python side rather than a literal, so the pair
        # stays checked after the next bump instead of pinning a stale number.
        self.assertIn(
            f"const PATCH_VERSION = {patch_format.FORMAT_VERSION}", self.models)
        readable = ", ".join(str(v) for v in patch_format.SUPPORTED_VERSIONS)
        self.assertIn(f"const PATCH_READS = [{readable}]", self.models)

    def test_the_frontend_agrees_with_the_python_side_order(self):
        for side in patch_format.SIDE_ORDER:
            with self.subTest(side):
                self.assertIn(f"'{side}'", self.models)

    def test_the_frontend_cycles_rather_than_toggles(self):
        self.assertIn("cycle(step = 1)", self.models)
        self.assertNotIn("this.view === 'front' ? 'back' : 'front'", self.models)

    def test_the_frontend_carries_groups(self):
        for symbol in ("createRow", "assignToGroup", "removeFromGroup", "renderRack"):
            with self.subTest(symbol):
                self.assertIn(symbol, self.models)


if __name__ == "__main__":
    unittest.main()
