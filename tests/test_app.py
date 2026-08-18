import asyncio
from pathlib import Path
import re
import unittest

from src.main import app, healthz, patch_format_info, validate_patch
from src import patch_format


class _arrived_on:
    """The half of a request `healthz` reads: which socket it came in on.

    A stand-in rather than a real request, because the handler's whole job here
    is to describe the connection rather than to parse anything from it.
    """

    def __init__(self, server):
        self.scope = {"server": server}


class AppSmokeTests(unittest.TestCase):
    def test_healthz(self):
        # `healthz` reads the connection it arrived on, so a caller has to
        # supply one. That is the point of it: the port is observed rather
        # than read back off the settings that asked for it.
        answered = asyncio.run(healthz(_arrived_on(("127.0.0.1", 8123))))

        self.assertTrue(answered["ok"])
        self.assertEqual(answered["app"], "Carlos")
        self.assertEqual(answered["version"], "0.1.0")

    def test_healthz_names_the_instance_that_answered(self):
        # A package constant is identical across every clone and every
        # process, so two checkouts answered the same and a collector could
        # not tell which one it had reached. These are what tell them apart.
        answered = asyncio.run(healthz(_arrived_on(("127.0.0.1", 8123))))

        for named in ("instance", "pid", "started_at", "port", "host", "database"):
            with self.subTest(named):
                self.assertIsNotNone(answered.get(named))

    def test_it_reports_the_process_that_is_serving(self):
        # The one thing the operating system will not reliably say on Windows:
        # `netstat` blames the parent that bound the socket, which by then has
        # exited, while the reloader's spawned child is the one answering.
        import os

        answered = asyncio.run(healthz(_arrived_on(("127.0.0.1", 8123))))
        self.assertEqual(answered["pid"], os.getpid())

    def test_the_port_is_the_one_that_answered_not_the_one_configured(self):
        # The case worth catching is a process serving somewhere other than
        # where it was configured - a handler reading its own settings would
        # report the configured port and hide exactly that.
        from src.main import settings

        odd = settings.port + 4321
        answered = asyncio.run(healthz(_arrived_on(("127.0.0.1", odd))))

        self.assertEqual(answered["port"], odd)
        self.assertNotEqual(answered["port"], settings.port)

    def test_a_taken_port_is_reported_as_taken(self):
        # The failure this replaces: uvicorn printed the address to open, then
        # "Application startup complete", and only then one ERROR line saying
        # it never bound. Whoever already held the port answered the URL, so
        # the server looked up and was not running.
        import socket

        from src.main import port_is_free

        squatter = socket.socket()
        squatter.bind(("127.0.0.1", 0))
        squatter.listen(1)
        taken = squatter.getsockname()[1]
        try:
            self.assertFalse(port_is_free("127.0.0.1", taken))
        finally:
            squatter.close()

    def test_a_free_port_is_reported_as_free(self):
        import socket

        from src.main import port_is_free

        finder = socket.socket()
        finder.bind(("127.0.0.1", 0))
        free = finder.getsockname()[1]
        finder.close()

        self.assertTrue(port_is_free("127.0.0.1", free))

    def test_checking_the_port_does_not_keep_it(self):
        # A probe that held what it tested would make the real bind fail.
        import socket

        from src.main import port_is_free

        finder = socket.socket()
        finder.bind(("127.0.0.1", 0))
        free = finder.getsockname()[1]
        finder.close()

        self.assertTrue(port_is_free("127.0.0.1", free))
        after = socket.socket()
        try:
            after.bind(("127.0.0.1", free))
        finally:
            after.close()

    def test_the_advertised_address_is_never_the_bind_address(self):
        # `0.0.0.0` means "every interface" to a listener and nothing at all
        # to a browser: Chrome answers ERR_ADDRESS_INVALID. uvicorn prints it
        # on startup regardless, so for the life of this project the one URL
        # the server offered was one that could not be opened.
        from src.main import reachable_urls

        for host in ("0.0.0.0", "::", ""):
            urls = reachable_urls(host, 8000)
            self.assertTrue(urls, f"{host!r} advertised nothing")
            for url in urls:
                self.assertNotIn("0.0.0.0", url)
                self.assertNotIn("[::]", url)
            self.assertEqual(urls[0], "http://127.0.0.1:8000/")

    def test_a_specific_bind_is_advertised_as_itself(self):
        from src.main import reachable_urls

        self.assertEqual(
            reachable_urls("127.0.0.1", 9001), ["http://127.0.0.1:9001/"])

    def test_the_port_it_advertises_is_the_port_it_was_given(self):
        from src.main import reachable_urls

        for url in reachable_urls("0.0.0.0", 8123):
            self.assertTrue(url.endswith(":8123/"), url)

    def test_finding_the_network_address_sends_nothing_and_cannot_hang(self):
        # A UDP socket has no handshake, so connecting one only asks the
        # routing table which local address it would use. The destination is
        # TEST-NET-1, reserved and unroutable, and is never contacted — which
        # is what makes this safe to call on every startup, offline included.
        from src.main import lan_address

        found = lan_address()
        if found is not None:
            self.assertRegex(found, r"^\d+\.\d+\.\d+\.\d+$")

    def test_reload_is_off_by_default(self):
        # It does not reload here, and the reloader process it adds owns the
        # socket and hands it to a child — so killing the server that answers
        # leaves a parent to spawn another, and killing the parent leaves a
        # listening socket with nothing behind it. Measured: reload on leaves
        # two processes and an orphaned port after a stop; reload off leaves
        # neither. A default that costs that much for nothing is not a default.
        from src.main import Settings

        self.assertFalse(Settings().reload)

    def test_reload_can_still_be_asked_for(self):
        import os
        from src.main import Settings

        os.environ["CARLOS_RELOAD"] = "1"
        try:
            self.assertTrue(Settings().reload)
        finally:
            del os.environ["CARLOS_RELOAD"]

    def test_the_database_path_is_resolved(self):
        # `data/db.json` means two different files from two working
        # directories, which is the confusion this reports its way out of.
        from pathlib import Path

        answered = asyncio.run(healthz(_arrived_on(("127.0.0.1", 8123))))
        self.assertTrue(Path(answered["database"]).is_absolute())

    def test_two_answers_from_one_process_name_the_same_instance(self):
        # The id is per process. Two reads of one server are one instance;
        # anything else would make a collector see churn that is not there.
        first = asyncio.run(healthz(_arrived_on(("127.0.0.1", 8123))))
        second = asyncio.run(healthz(_arrived_on(("127.0.0.1", 8123))))

        self.assertEqual(first["instance"], second["instance"])
        self.assertEqual(first["started_at"], second["started_at"])

    def test_app_metadata_and_routes(self):
        routes = {route.path for route in app.routes}

        self.assertEqual(app.title, "Carlos")
        self.assertIn("/", routes)
        self.assertIn("/healthz", routes)
        self.assertIn("/static", routes)
        self.assertIn("/api/patch/format", routes)
        self.assertIn("/api/patch/validate", routes)

    def test_demo_is_local_first(self):
        html = Path("templates/demo.html").read_text()

        self.assertIn("Carlos - Synth Patch Workspace", html)
        # Assets go through asset() for cache-busting, so the assertion is that
        # the motion library is served from this app rather than fetched.
        self.assertIn("asset('anime-shim.js')", html)
        self.assertNotIn("cdnjs.cloudflare.com", html)
        self.assertNotIn("//cdn.", html)


def valid_patch(**overrides):
    document = {
        "format": "carlos.patch",
        "version": 1,
        "name": "Test Patch",
        "modules": [
            {"id": "a", "type": "carlos.vco", "parameters": {"frequency": 64.0}},
            {"id": "b", "type": "carlos.vcf", "view": "back", "parameters": {"cutoff": 40.0}},
        ],
        "connections": [
            {
                "source": {"module": "a", "jack": "audio_out"},
                "target": {"module": "b", "jack": "audio_in"},
            }
        ],
    }
    document.update(overrides)
    return document


class PatchFormatTests(unittest.TestCase):
    def test_round_trip_of_a_valid_document(self):
        patch = patch_format.load(valid_patch())

        self.assertEqual(patch.name, "Test Patch")
        self.assertEqual(len(patch.modules), 2)
        self.assertEqual(patch.connections[0].source.jack, "audio_out")

    def test_view_is_per_module_and_defaults_to_front(self):
        patch = patch_format.load(valid_patch())

        self.assertEqual(patch.modules[0].view, "front")  # absent -> front
        self.assertEqual(patch.modules[1].view, "back")

    def test_invented_view_is_refused(self):
        document = valid_patch(
            modules=[{"id": "a", "type": "carlos.vco", "view": "sideways"}],
            connections=[],
        )
        with self.assertRaises(patch_format.PatchFormatError):
            patch_format.load(document)

    def test_a_cable_carries_no_side_of_its_own(self):
        # Side is fixed by the module definition that declares the jack, so a
        # document that tries to state it is refused rather than half-honoured.
        document = valid_patch(
            connections=[
                {
                    "side": "front",
                    "source": {"module": "a", "jack": "audio_out"},
                    "target": {"module": "b", "jack": "audio_in"},
                }
            ]
        )
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(document)
        self.assertIn("side", str(caught.exception))

    def test_front_to_back_cable_is_accepted(self):
        # Running a lead round the back is legal, and the format says nothing
        # about it either way - which is the point of not storing a side.
        document = valid_patch(
            connections=[
                {
                    "source": {"module": "a", "jack": "sub_out"},
                    "target": {"module": "b", "jack": "audio_in"},
                }
            ]
        )
        self.assertEqual(len(patch_format.load(document).connections), 1)

    def test_empty_rack_is_a_valid_patch(self):
        patch = patch_format.load(valid_patch(modules=[], connections=[]))
        self.assertEqual(patch.modules, [])

    def test_empty_helper_matches_the_format(self):
        patch = patch_format.empty("Nothing Yet")
        self.assertEqual(patch.format, patch_format.FORMAT_NAME)
        self.assertEqual(patch.version, patch_format.FORMAT_VERSION)
        self.assertEqual(patch.name, "Nothing Yet")

    def test_foreign_format_is_refused(self):
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(valid_patch(format="ableton.set"))
        self.assertIn("ableton.set", str(caught.exception))

    def test_future_version_is_refused_rather_than_half_read(self):
        # One past whatever this build writes, so the test keeps meaning the
        # same thing after a version bump instead of asserting about a version
        # that has since become readable.
        future = patch_format.FORMAT_VERSION + 1
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(valid_patch(version=future))
        self.assertIn(f"version {future}", str(caught.exception))

    def test_unknown_top_level_field_is_refused(self):
        with self.assertRaises(patch_format.PatchFormatError):
            patch_format.load(valid_patch(tempo=120))

    def test_duplicate_module_ids_are_refused(self):
        document = valid_patch(
            modules=[
                {"id": "a", "type": "carlos.vco", "parameters": {}},
                {"id": "a", "type": "carlos.vcf", "parameters": {}},
            ],
            connections=[],
        )
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(document)
        self.assertIn("duplicate module id", str(caught.exception))

    def test_connection_to_absent_module_is_refused(self):
        document = valid_patch(
            connections=[
                {
                    "source": {"module": "a", "jack": "audio_out"},
                    "target": {"module": "ghost", "jack": "audio_in"},
                }
            ]
        )
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load(document)
        self.assertIn("ghost", str(caught.exception))

    def test_self_patch_is_refused(self):
        document = valid_patch(
            connections=[
                {
                    "source": {"module": "a", "jack": "audio_out"},
                    "target": {"module": "a", "jack": "audio_out"},
                }
            ]
        )
        with self.assertRaises(patch_format.PatchFormatError):
            patch_format.load(document)

    def test_a_list_is_not_a_patch(self):
        with self.assertRaises(patch_format.PatchFormatError) as caught:
            patch_format.load([])
        self.assertIn("JSON object", str(caught.exception))


class PatchEndpointTests(unittest.TestCase):
    def test_format_endpoint_matches_the_module(self):
        self.assertEqual(
            asyncio.run(patch_format_info()),
            {"format": patch_format.FORMAT_NAME, "version": patch_format.FORMAT_VERSION},
        )

    def test_validate_accepts_a_good_document(self):
        result = asyncio.run(validate_patch(valid_patch()))

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["modules"], 2)
        self.assertEqual(result["connections"], 1)

    def test_validate_reports_422_with_a_reason(self):
        response = asyncio.run(validate_patch(valid_patch(version=99)))

        self.assertEqual(response.status_code, 422)
        self.assertIn(b"version 99", response.body)


class FrontendContractTests(unittest.TestCase):
    """The browser is the other implementation of the format, so the two
    declarations are checked against each other rather than trusted."""

    def setUp(self):
        self.models = Path("static/models.js").read_text()

    def test_frontend_declares_the_same_format_and_version(self):
        self.assertIn(f"const PATCH_FORMAT = '{patch_format.FORMAT_NAME}'", self.models)
        self.assertIn(f"const PATCH_VERSION = {patch_format.FORMAT_VERSION}", self.models)

    def test_devices_with_jacks_on_both_sides_exist_in_the_catalogue(self):
        # This used to grep models.js for the strings 'front' and 'back'. Once
        # the definitions moved into the catalogue those strings survived only
        # in comments and defaults, so the check passed while asserting nothing.
        # Ask the catalogue, which is now where the answer lives.
        from src import catalogue

        both = [
            d for d in catalogue.load_all().values()
            if any(j.side == "front" for j in d.jacks)
            and any(j.side == "back" for j in d.jacks)
        ]
        self.assertTrue(both, "no device has jacks on both sides")

    def test_a_letter_turns_the_rack_and_tab_is_left_alone(self):
        # Turning was on `Tab`, guarded by "unless something focusable already
        # has it". At load nothing is focused, so the first Tab turned the rack
        # and so did every one after it: seventeen focusable controls, none of
        # them reachable. Measured in a real browser, which is the only place
        # it was visible — the stub pre-focused a knob and so only ever tested
        # the half of the rule that worked.
        #
        # A string assertion cannot see that, which is why
        # `tests/browser/test_without_a_pointer.py` is where the property now
        # lives. This one holds the line the source can state: Tab is not a key
        # this file has an opinion about.
        main = Path("static/main.js").read_text()
        source = re.sub(r"//.*$", "", main, flags=re.M)

        self.assertIn("flipView", source)
        self.assertNotIn("'Tab'", source)
        self.assertNotIn('"Tab"', source)

    def test_escape_deselects(self):
        main = Path("static/main.js").read_text()

        self.assertIn("'Escape'", main)
        self.assertIn("deselect", main)

    def test_turning_is_available_per_device_and_for_all(self):
        self.assertIn("turnModule(id, step = 1)", self.models)
        self.assertIn("flipAll(step = 1)", self.models)
        # Tab routes to one or the other depending on the selection.
        self.assertIn("this.selected", self.models)

    def test_cables_carry_no_stored_side(self):
        # The exporter must not reintroduce the field the format dropped.
        exporter = self.models.split("exportState()")[1].split("importState")[0]
        self.assertNotIn("side,", exporter)


if __name__ == "__main__":
    unittest.main()
