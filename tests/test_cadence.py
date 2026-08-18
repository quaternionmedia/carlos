"""What another application may expect from this seam, held to.

A cadence document is only worth reading if it is true, and the ways it stops
being true are all quiet: an endpoint gets added and nobody declares it, an
endpoint is removed and its entry lingers, or something declared `none` grows a
write. None of those break a test that merely parses the document.

The record behind this is
`governance/qm/records/DRAFT-monitoring-seam-and-instance-identity.md`, which
exists because `qmcp`'s detail endpoint expired the request it was asked about.
Reading the queue wrote to it, so a dashboard that polled detail URLs destroyed
the decisions it was displaying, and the document it produced said everything
was fine. `side_effect` is a reviewed fact here for that reason, and the test
below calls every `none` endpoint twice rather than believing the declaration.
"""

import asyncio
import json
import re
import unittest
from datetime import datetime
from pathlib import Path

from src import cadence, catalogue, interop, main, patch_format


class _ArrivedOn:
    """The half of a request `healthz` reads: which socket it came in on."""

    def __init__(self, server):
        self.scope = {"server": server}


# Routes that are deliberately not part of the seam, each with the reason.
#
# An allowlist rather than a prefix rule. The prefix rule this replaces only
# looked at `/api` and `/healthz`, so a route added anywhere else was neither
# declared nor caught - a guard with a hole in exactly the place a reader would
# assume it was covered. Adding a route now forces a decision: declare its
# cadence, or say here why it has none.
NOT_A_SEAM = {
    ("GET", "/"): "a redirect to the splash; the bare port is not an endpoint",
    ("GET", "/splash"): "the page the bare port lands on, for a person not a peer",
    ("GET", "/rack"): "the workspace itself, an HTML page rather than a seam",
    ("GET", "/docs"): "FastAPI's own interactive documentation",
    ("GET", "/docs/oauth2-redirect"): "FastAPI's own OAuth redirect helper",
    ("GET", "/redoc"): "FastAPI's own alternative documentation",
    ("GET", "/openapi.json"): "the generated API description; a peer reads it once",
    ("GET", "/api/cadence"): "the declaration itself, which cannot describe itself",
}


def routes() -> dict[tuple[str, str], object]:
    """Every route this build serves, keyed by (method, path)."""
    found = {}
    for route in main.app.routes:
        path = getattr(route, "path", "")
        if not path:
            continue
        for method in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}:
            found[(method, path)] = route
    return found


class DeclarationCoversTheSeamTests(unittest.TestCase):
    """The document and the application, checked against each other.

    Both directions. A cadence document that quietly stopped covering half the
    API would be worse than none, because a caller would read it and believe it.
    """

    def setUp(self):
        self.declared = {(e.method, e.path) for e in cadence.CADENCE}
        self.served = {k for k in routes() if k not in NOT_A_SEAM}

    def test_every_exclusion_names_a_route_that_exists(self):
        # An exclusion for a route that has gone is a licence nobody revoked.
        served = set(routes())
        for excluded in NOT_A_SEAM:
            with self.subTest(excluded):
                self.assertIn(excluded, served)

    def test_every_exclusion_gives_a_reason(self):
        for excluded, reason in NOT_A_SEAM.items():
            with self.subTest(excluded):
                self.assertGreater(len(reason), 20)

    def test_every_endpoint_this_build_serves_is_declared(self):
        missing = self.served - self.declared
        self.assertEqual(
            missing, set(),
            "these endpoints exist and say nothing about what calling them costs",
        )

    def test_nothing_is_declared_that_this_build_does_not_serve(self):
        ghosts = self.declared - self.served
        self.assertEqual(
            ghosts, set(),
            "these are declared and are not there - a caller would loop on a 404",
        )

    def test_every_entry_says_why(self):
        # A budget with no reason is a number somebody typed. The reason is
        # what a reviewer checks and what a caller weighs.
        for entry in cadence.CADENCE:
            with self.subTest(entry.path):
                self.assertGreater(len(entry.why), 20)

    def test_an_interval_is_never_shorter_than_the_budget(self):
        # Asking faster than the answer changes costs both sides and buys
        # nothing. Where there is a budget, the interval has to respect it.
        for entry in cadence.CADENCE:
            if entry.staleness_budget_seconds in (None, 0):
                continue
            with self.subTest(entry.path):
                self.assertIsNotNone(entry.min_interval_seconds)
                self.assertLessEqual(
                    entry.min_interval_seconds, entry.staleness_budget_seconds
                )

    def test_liveness_is_never_quotable(self):
        # A cached liveness answer is the thing liveness exists to avoid.
        health = cadence.for_path("/healthz")
        self.assertEqual(health.staleness_budget_seconds, 0)


class NoneMeansNoneTests(unittest.TestCase):
    """An endpoint declared `none` is called twice and the world is measured.

    This is the assertion the record is really about. The declaration is a
    claim; calling it and looking at the disk is evidence.
    """

    def setUp(self):
        catalogue.load_all.cache_clear()
        self.patch = patch_format.load(catalogue.examples_for("carlos.vco")["simple"])

    def world(self) -> dict:
        """Everything a read is not allowed to move."""
        data = Path("data")
        return {
            "db": sorted(
                (p.name, p.stat().st_size, p.stat().st_mtime_ns)
                for p in data.glob("*") if p.is_file()
            ),
            "catalogue": sorted(
                (p.name, p.stat().st_mtime_ns)
                for p in Path("catalogue").rglob("*.json")
            ),
        }

    def call(self, method: str, path: str):
        """Call one endpoint the way the application defines it."""
        device = "carlos.vco"
        document = self.patch.model_dump()
        by_path = {
            # `healthz` describes the connection it arrived on, so it needs
            # one. A stand-in carrying just the socket is enough.
            ("GET", "/healthz"):
                lambda: main.healthz(_ArrivedOn(("127.0.0.1", 8123))),
            ("GET", "/api/catalogue"): lambda: main.catalogue_index(),
            ("GET", "/api/catalogue/categories"): lambda: main.catalogue_categories(),
            ("GET", "/api/catalogue/devices/{device_id}"):
                lambda: main.catalogue_device(device),
            ("GET", "/api/catalogue/devices/{device_id}/examples"):
                lambda: main.catalogue_device_examples(device),
            ("GET", "/api/opening"): lambda: main.opening_rack(),
            ("GET", "/api/patch/format"): lambda: main.patch_format_info(),
            ("POST", "/api/patch/validate"): lambda: main.validate_patch(document),
            ("GET", "/api/transforms"): lambda: main.list_transforms(),
            ("POST", "/api/transforms/{name}"):
                lambda: main.apply_transform("summary", document),
            ("GET", "/api/peers"): lambda: main.list_peers(),
            ("POST", "/api/peers/{peer_id}/{endpoint_name}/plan"):
                lambda: main.plan_outbound("gear-inventory", "check", document),
            ("GET", "/api/midi"): lambda: main.midi_info(),
            ("POST", "/api/midi/parse"): lambda: main.midi_parse({"bytes": [144, 60, 100]}),
            ("POST", "/api/midi/route"):
                lambda: main.midi_route({"bytes": [144, 60, 100], "bindings": []}),
        }
        make = by_path.get((method, path))
        if make is None:
            self.fail(f"this test does not know how to call {method} {path}")
        result = make()
        return asyncio.run(result) if asyncio.iscoroutine(result) else result

    def test_nothing_declared_none_moves_anything(self):
        reads = [e for e in cadence.CADENCE if e.side_effect == "none"]
        self.assertTrue(reads, "no endpoint claims to be a read")

        for entry in reads:
            with self.subTest(f"{entry.method} {entry.path}"):
                before = self.world()
                self.call(entry.method, entry.path)
                self.call(entry.method, entry.path)
                self.assertEqual(
                    self.world(), before,
                    f"{entry.path} says side_effect none and moved something",
                )

    def test_the_test_would_notice_a_write(self):
        # A guard nobody has tried to route around is a green check standing
        # where a reader believes something is enforced. This writes on purpose
        # and the same measurement catches it.
        before = self.world()
        marker = Path("data") / "cadence-probe.json"
        marker.write_text("{}", encoding="utf-8")
        try:
            self.assertNotEqual(self.world(), before)
        finally:
            marker.unlink()
        self.assertEqual(self.world(), before)


class QuotableAnswersCanBeAgedTests(unittest.TestCase):
    """A live read that cannot be stamped cannot be budgeted or quoted.

    The record's own words, and its reason: a view that looks live and is an
    hour old is worse than one that admits its age, because the first stops
    people checking.
    """

    def test_the_declaration_is_stamped(self):
        stamped = asyncio.run(main.cadence_policy())
        self.assertIn("generated_at", stamped)
        parsed = datetime.fromisoformat(stamped["generated_at"])
        self.assertIsNotNone(parsed.tzinfo, "a stamp with no zone is two answers")

    def test_the_stamp_is_utc_and_second_resolution(self):
        self.assertRegex(
            cadence.stamp(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$"
        )


class CommittedPolicyCarriesNoMachineLiteralTests(unittest.TestCase):
    """No port, no filesystem path, no `127.0.0.1`, no instance roster.

    Clause 3 of the record, word for word. A committed address publishes one
    workstation's Tuesday as a fact about the org.
    """

    def setUp(self):
        self.raw = Path("catalogue/peers.json").read_text(encoding="utf-8")

    def test_no_addresses_are_committed(self):
        for pattern, what in (
            (r"\b\d{1,3}(\.\d{1,3}){3}\b", "an IP address"),
            (r"localhost", "a hostname"),
            (r"https?://", "a URL"),
            (r":\d{2,5}\b", "a port"),
            (r"[A-Za-z]:\\\\", "a Windows path"),
        ):
            with self.subTest(what):
                self.assertNotRegex(self.raw, pattern)

    def test_every_peer_names_an_environment_variable_instead(self):
        for peer in interop.load_peers().values():
            with self.subTest(peer.id):
                self.assertTrue(peer.base_url_env)

    def test_the_per_call_timeout_is_committed_policy(self):
        declared = json.loads(self.raw)
        self.assertIn("timeout_seconds", declared)
        self.assertGreater(declared["timeout_seconds"], 0)
        # And it is bounded: a timeout long enough to be no timeout is a
        # decision nobody made.
        self.assertLessEqual(declared["timeout_seconds"], 60)
        self.assertEqual(interop.peer_timeout(), declared["timeout_seconds"])


class OutboundDeclarationTests(unittest.TestCase):
    def test_every_peer_endpoint_declares_what_it_does(self):
        allowed = {"none", "persists", "creates"}
        for peer in interop.load_peers().values():
            for endpoint in peer.endpoints:
                with self.subTest(f"{peer.id}:{endpoint.name}"):
                    self.assertIn(endpoint.side_effect, allowed)

    def test_a_plan_reports_the_timeout_it_would_use(self):
        # A plan that omitted it would be a plan of a different call.
        document = catalogue.examples_for("carlos.vco")["simple"]
        planned = interop.plan(
            "gear-inventory", "check", patch_format.load(document)
        )
        self.assertEqual(planned["timeout_seconds"], interop.peer_timeout())
        self.assertFalse(planned["sent"])

    def test_the_inbound_and_outbound_vocabularies_are_the_same_words(self):
        # A peer reading both should not have to learn two words for one idea.
        inbound = set(cadence.SideEffect.__args__)
        outbound = set(interop.SideEffect.__args__)
        self.assertEqual(inbound, outbound)
