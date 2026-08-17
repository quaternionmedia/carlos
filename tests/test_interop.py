import asyncio
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from src import catalogue, interop, patch_format
from src.main import apply_transform, list_peers, list_transforms, plan_outbound


def example(device_id: str, kind: str = "complex") -> dict:
    return catalogue.examples_for(device_id)[kind]


class TransformTests(unittest.TestCase):
    def setUp(self):
        catalogue.load_all.cache_clear()
        self.patch = patch_format.load(example("squarp.hapax"))

    def test_every_registered_transform_runs_on_a_real_example(self):
        for name in interop.TRANSFORMS:
            with self.subTest(name):
                result = interop.apply_transform(name, self.patch)
                self.assertIsInstance(result, dict)

    def test_every_transform_is_described(self):
        for entry in interop.transforms():
            with self.subTest(entry["name"]):
                self.assertTrue(entry["description"].strip())

    def test_identity_round_trips_through_the_format(self):
        result = interop.apply_transform("identity", self.patch)
        self.assertEqual(patch_format.load(result).name, self.patch.name)

    def test_summary_counts_without_topology(self):
        result = interop.apply_transform("summary", self.patch)

        self.assertEqual(result["modules"], len(self.patch.modules))
        self.assertEqual(result["connections"], len(self.patch.connections))
        self.assertNotIn("connections_detail", result)
        self.assertIn("semi-modular", result["by_category"])

    def test_patchbay_resolves_labels_from_the_catalogue(self):
        result = interop.apply_transform("patchbay", self.patch)

        self.assertEqual(len(result["cables"]), len(self.patch.connections))
        first = result["cables"][0]
        # Raw jack names are cv_out_1 / vco1_cv_in; the transform reports the
        # panel legends instead, which is what a human-facing peer wants.
        self.assertEqual(first["from"]["device"], "Squarp Instruments Hapax")
        self.assertEqual(first["from"]["jack"], "CV 1")
        self.assertEqual(first["to"]["jack"], "VCO 1 CV")
        self.assertIn("->", first["text"])

    def test_patchbay_reports_the_side_each_end_sits_on(self):
        # Any side the catalogue can produce, not just front and back: a K.O. II
        # patches on its top edge, and this assertion used to say that was wrong.
        result = interop.apply_transform("patchbay", self.patch)
        for cable in result["cables"]:
            with self.subTest(cable["text"]):
                self.assertIn(cable["from"]["side"], catalogue.SIDE_ORDER)
                self.assertIn(cable["to"]["side"], catalogue.SIDE_ORDER)

    def test_patchbay_reports_a_side_that_is_neither_front_nor_back(self):
        # The Hapax rig clocks a K.O. II, whose sync input is on its top.
        result = interop.apply_transform("patchbay", self.patch)
        sides = {c["to"]["side"] for c in result["cables"]}
        self.assertIn("top", sides)

    def test_topology_strips_every_parameter_but_keeps_the_routing(self):
        result = interop.apply_transform("topology", self.patch)

        self.assertEqual(len(result["connections"]), len(self.patch.connections))
        for module in result["modules"]:
            with self.subTest(module["id"]):
                self.assertEqual(module["parameters"], {})
        # Still a valid patch, so a peer can hand it straight back.
        patch_format.load(result)

    def test_topology_actually_had_parameters_to_strip(self):
        # Otherwise the test above passes on an input that proves nothing.
        self.assertTrue(any(m.parameters for m in self.patch.modules))

    def test_inventory_addresses_devices_by_catalogue_id(self):
        result = interop.apply_transform("inventory", self.patch)
        ids = {d["id"] for d in result["devices"]}

        self.assertIn("moog.dfam", ids)
        self.assertTrue(all(d["known"] for d in result["devices"]))

    def test_inventory_marks_a_device_this_catalogue_lacks(self):
        document = example("squarp.hapax")
        document["modules"].append(
            {"id": "mystery", "type": "roland.tr909", "parameters": {}}
        )
        result = interop.apply_transform("inventory", patch_format.load(document))
        unknown = next(d for d in result["devices"] if d["id"] == "roland.tr909")

        self.assertFalse(unknown["known"])
        self.assertIsNone(unknown["maker"])

    def test_an_unknown_transform_names_the_known_ones(self):
        with self.assertRaises(interop.InteropError) as caught:
            interop.apply_transform("interpretive-dance", self.patch)
        self.assertIn("patchbay", str(caught.exception))


class PeerTests(unittest.TestCase):
    def setUp(self):
        interop.load_peers.cache_clear()
        self.peers = interop.load_peers()

    def test_the_shipped_peers_file_loads(self):
        self.assertTrue(self.peers)

    def test_every_endpoint_states_a_side_effect(self):
        for peer in self.peers.values():
            for endpoint in peer.endpoints:
                with self.subTest(f"{peer.id}.{endpoint.name}"):
                    self.assertIn(
                        endpoint.side_effect, ("none", "persists", "creates")
                    )

    def test_every_endpoint_names_a_transform_that_exists(self):
        for peer in self.peers.values():
            for endpoint in peer.endpoints:
                with self.subTest(f"{peer.id}.{endpoint.name}"):
                    self.assertIn(endpoint.transform, interop.TRANSFORMS)

    def test_no_address_is_committed(self):
        # The monitoring-seam record: a committed policy carries no machine
        # literal. Assert against the file rather than the parsed model.
        raw = interop.PEERS_FILE.read_text(encoding="utf-8")
        for literal in ("http://", "https://", "127.0.0.1", "localhost"):
            with self.subTest(literal):
                self.assertNotIn(literal, raw)

    def test_an_unconfigured_peer_reports_unresolved_rather_than_vanishing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            interop.load_peers.cache_clear()
            status = interop.peer_status()

        self.assertTrue(status, "peers disappeared when unconfigured")
        self.assertTrue(all(p["resolved"] is False for p in status))

    def test_a_configured_peer_resolves(self):
        with mock.patch.dict(
            os.environ, {"CARLOS_PEER_STAGE_PLOT": "http://plots.invalid"}
        ):
            interop.load_peers.cache_clear()
            status = {p["id"]: p for p in interop.peer_status()}

        self.assertTrue(status["stage-plot"]["resolved"])
        self.assertFalse(status["gear-inventory"]["resolved"])


class PlanTests(unittest.TestCase):
    def setUp(self):
        catalogue.load_all.cache_clear()
        interop.load_peers.cache_clear()
        self.patch = patch_format.load(example("allen-heath.qu24"))

    def test_a_plan_is_never_sent(self):
        plan = interop.plan("stage-plot", "render", self.patch)
        self.assertFalse(plan["sent"])

    def test_a_plan_applies_the_endpoint_transform(self):
        plan = interop.plan("stage-plot", "render", self.patch)

        self.assertEqual(plan["transform"], "patchbay")
        self.assertIn("cables", plan["body"])
        self.assertEqual(len(plan["body"]["cables"]), len(self.patch.connections))

    def test_a_plan_carries_the_side_effect(self):
        self.assertEqual(
            interop.plan("gear-inventory", "check", self.patch)["side_effect"], "none"
        )
        self.assertEqual(
            interop.plan("gear-inventory", "reconcile", self.patch)["side_effect"],
            "persists",
        )

    def test_an_unconfigured_peer_plans_with_no_url_and_says_what_to_set(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            interop.load_peers.cache_clear()
            plan = interop.plan("stage-plot", "render", self.patch)

        self.assertIsNone(plan["url"])
        self.assertFalse(plan["resolved"])
        self.assertIn("CARLOS_PEER_STAGE_PLOT", plan["unresolved_hint"])

    def test_a_configured_peer_plans_a_full_url(self):
        with mock.patch.dict(
            os.environ, {"CARLOS_PEER_STAGE_PLOT": "http://plots.invalid/"}
        ):
            interop.load_peers.cache_clear()
            plan = interop.plan("stage-plot", "render", self.patch)

        self.assertEqual(plan["url"], "http://plots.invalid/plots")
        self.assertTrue(plan["resolved"])

    def test_an_unknown_peer_names_the_known_ones(self):
        with self.assertRaises(interop.InteropError) as caught:
            interop.plan("nobody", "render", self.patch)
        self.assertIn("stage-plot", str(caught.exception))

    def test_an_unknown_endpoint_names_the_known_ones(self):
        with self.assertRaises(interop.InteropError) as caught:
            interop.plan("stage-plot", "teleport", self.patch)
        self.assertIn("render", str(caught.exception))


class InteropApiTests(unittest.TestCase):
    def setUp(self):
        catalogue.load_all.cache_clear()
        interop.load_peers.cache_clear()
        self.document = example("moog.subharmonicon")

    def test_transforms_are_listed(self):
        payload = asyncio.run(list_transforms())
        names = {t["name"] for t in payload["transforms"]}
        self.assertIn("patchbay", names)

    def test_applying_a_transform_over_the_api(self):
        payload = asyncio.run(apply_transform("summary", self.document))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["transform"], "summary")
        self.assertEqual(payload["result"]["modules"], len(self.document["modules"]))

    def test_a_bad_patch_is_422_not_500(self):
        response = asyncio.run(apply_transform("summary", {"format": "nope"}))
        self.assertEqual(response.status_code, 422)

    def test_an_unknown_transform_is_404(self):
        response = asyncio.run(apply_transform("nonsense", self.document))
        self.assertEqual(response.status_code, 404)

    def test_peers_are_listed_over_the_api(self):
        payload = asyncio.run(list_peers())
        self.assertTrue(payload["peers"])

    def test_planning_over_the_api(self):
        plan = asyncio.run(plan_outbound("stage-plot", "render", self.document))
        self.assertFalse(plan["sent"])

    def test_planning_an_unknown_peer_is_404(self):
        response = asyncio.run(plan_outbound("nobody", "render", self.document))
        self.assertEqual(response.status_code, 404)


class NoLiveOutboundTests(unittest.TestCase):
    """This build must not be able to reach the network on its own."""

    def test_no_http_client_is_imported_anywhere_in_src(self):
        for path in Path("src").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for banned in ("import httpx", "import requests", "urllib.request"):
                with self.subTest(f"{path.name}:{banned}"):
                    self.assertNotIn(banned, source)

    def test_the_plan_says_plainly_that_it_did_not_send(self):
        catalogue.load_all.cache_clear()
        interop.load_peers.cache_clear()
        patch = patch_format.load(example("moog.dfam"))
        plan = interop.plan("patch-archive", "publish", patch)

        self.assertFalse(plan["sent"])
        self.assertIn("does not make them", plan["reason"])


if __name__ == "__main__":
    unittest.main()
