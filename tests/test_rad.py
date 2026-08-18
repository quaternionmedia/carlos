"""Carlos as a RAD consumer.

`quaternionmedia/rad` governs a contract, not an implementation: "share a
contract, let each platform implement it natively". So there is nothing of rad's
to import, and conformance is the only thing that makes the claim real. These
tests run rad's own vectors against this implementation and enforce the clause
rad's reference implementation cannot enforce on itself.
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

VECTORS = Path("vendor/rad/vectors.json")
PROVENANCE = Path("vendor/rad/PROVENANCE.json")
CORE = Path("static/rad-core.js")
NODE = shutil.which("node")


class VendoredVectorTests(unittest.TestCase):
    def test_the_vectors_are_vendored(self):
        self.assertTrue(VECTORS.is_file(), "rad's vectors are not vendored")

    def test_provenance_records_where_they_came_from(self):
        provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))

        self.assertEqual(provenance["source"], "https://github.com/quaternionmedia/rad")
        self.assertRegex(provenance["upstream_commit"], r"^[0-9a-f]{40}$")
        self.assertTrue(provenance["why"], "no reason recorded for vendoring")

    def test_the_pinned_version_matches_the_vendored_file(self):
        # A provenance file claiming one version while the vectors are another
        # is worse than no provenance at all.
        provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
        vectors = json.loads(VECTORS.read_text(encoding="utf-8"))

        self.assertEqual(provenance["vectors_version"], vectors["version"])

    def test_the_core_declares_the_version_it_was_written_against(self):
        source = CORE.read_text(encoding="utf-8")
        vectors = json.loads(VECTORS.read_text(encoding="utf-8"))

        self.assertIn(f"RAD_VECTORS_VERSION = '{vectors['version']}'", source)

    def test_the_geometry_constants_match_the_vectors(self):
        # The vectors carry the geometry they were generated against. If the
        # core disagrees, every trace case is being replayed against different
        # radii than the ones that produced the expectations.
        source = CORE.read_text(encoding="utf-8")
        geometry = json.loads(VECTORS.read_text(encoding="utf-8"))["geometry"]

        for key, value in geometry.items():
            # JSON booleans are Python bools but JavaScript literals, so the
            # expected text is the JS spelling rather than str(value).
            literal = json.dumps(value)
            with self.subTest(key):
                pattern = rf"{key}:\s*{re.escape(literal)}\b"
                self.assertRegex(source, pattern, f"core does not carry {key}={literal}")


class PlatformFreeCoreTests(unittest.TestCase):
    """rad's conformance clause: state machine and geometry live in a core with
    no platform imports, enforced by a lint rather than by a comment banner.

    rad's own `DRAFT-rad-core-extraction` record exists because its reference
    implementation cannot pass this - the core is delimited by a comment inside
    a 1,500-line file full of `document`. There is no reason for a consumer to
    inherit that, so the lint runs here.
    """

    BANNED = ("document", "window", "navigator", "HTMLElement", "localStorage")

    def source_without_comments(self):
        source = CORE.read_text(encoding="utf-8")
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        source = re.sub(r"^\s*//.*$", "", source, flags=re.M)
        return source

    def test_the_core_has_no_platform_references(self):
        source = self.source_without_comments()
        for banned in self.BANNED:
            with self.subTest(banned):
                self.assertNotRegex(
                    source, rf"\b{banned}\b",
                    f"rad-core.js references {banned}; the core must be platform-free",
                )

    def test_the_lint_would_catch_a_violation(self):
        # A lint nobody has seen fail is a lint nobody knows works.
        polluted = self.source_without_comments() + "\nconst x = document.body;\n"
        self.assertRegex(polluted, r"\bdocument\b")

    def test_the_dom_layer_is_a_separate_file(self):
        # The split is the point: rendering lives somewhere the lint does not
        # run, so the boundary is a file boundary rather than a line range.
        self.assertTrue(Path("static/rad-menu.js").is_file())
        self.assertIn("document", Path("static/rad-menu.js").read_text(encoding="utf-8"))


@unittest.skipUnless(NODE, "node is not installed")
class ConformanceTests(unittest.TestCase):
    """Replays rad's vectors against this core, in Node, with no browser."""

    def run_conformance(self):
        script = """
        const rad = require('./static/rad-core.js');
        const vectors = require('./vendor/rad/vectors.json');
        console.log(JSON.stringify(rad.radConformance(vectors)));
        """
        result = subprocess.run(
            [NODE, "-e", script],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            self.fail(f"conformance runner failed:\n{result.stderr}")
        return json.loads(result.stdout)

    def setUp(self):
        self.report = self.run_conformance()

    def test_every_in_scope_case_passes(self):
        failures = [r for r in self.report["results"] if not r["ok"]]
        detail = "\n".join(f"  {f['name']}: {f['detail']}" for f in failures)
        self.assertEqual(self.report["failed"], 0, f"rad conformance failures:\n{detail}")

    def test_the_suite_actually_ran_something(self):
        # A report of zero failures over zero assertions is not conformance.
        self.assertGreater(self.report["passed"], 40)

    def test_the_report_names_the_vectors_version(self):
        self.assertEqual(self.report["version"], "0.3.0")

    def test_out_of_scope_suites_are_skipped_not_claimed(self):
        # Carlos implements the three governed artifacts. The chord, tempo,
        # quantize and speed-axis suites belong to rad features this consumer
        # does not carry, and reporting them as passes would be a false claim.
        self.assertGreater(self.report["skipped"], 0)
        skipped = [r["name"] for r in self.report["results"] if r.get("skipped")]
        self.assertTrue(any("chord" in n for n in skipped))


@unittest.skipUnless(NODE, "node is not installed")
class ResolverTests(unittest.TestCase):
    """The menu model: a resolver builds a MenuSpec per context, and the ring
    ceiling is enforced by the resolver rather than by a reviewer."""

    def resolve(self, script):
        full = """
        const rad = require('./static/rad-core.js');
        globalThis.RAD_GEOMETRY = rad.RAD_GEOMETRY;
        const m = require('./static/menus.js');
        %s
        """ % script
        result = subprocess.run(
            [NODE, "-e", full], capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            self.fail(f"resolver failed:\n{result.stderr}")
        return json.loads(result.stdout)

    def fake_state(self, devices=9, groups=0):
        return """
        const definitions = {};
        for (let i = 0; i < %d; i++) {
            definitions['maker.d' + i] = {
                id: 'maker.d' + i, maker: 'M', model: 'D' + i,
                category: 'cat' + (i %% 3),
            };
        }
        const groups = [];
        for (let i = 0; i < %d; i++) {
            groups.push({ id: 'row-' + i, label: 'Row ' + i, members: [] });
        }
        const state = { definitions, groups, modules: new Map() };
        """ % (devices, groups)

    def test_canvas_menu_fits_the_ring(self):
        spec = self.resolve(self.fake_state() + """
        const spec = m.carlosResolve({type:'canvas', targetIds:[], position:{x:0,y:0}}, state);
        console.log(JSON.stringify(spec));
        """)
        self.assertLessEqual(len(spec["items"]), 8)
        self.assertTrue(spec["title"])

    def test_every_submenu_also_fits_the_ring(self):
        spec = self.resolve(self.fake_state(devices=40, groups=25) + """
        const spec = m.carlosResolve({type:'canvas', targetIds:[], position:{x:0,y:0}}, state);
        const rings = [];
        (function walk(items) {
            rings.push(items.length);
            items.forEach(i => { if (i.children) walk(i.children); });
        })(spec.items);
        console.log(JSON.stringify(rings));
        """)
        self.assertTrue(spec)
        for size in spec:
            self.assertLessEqual(size, 8, f"a ring of {size} exceeds the ceiling")

    def test_overflow_becomes_submenus_rather_than_a_longer_ring(self):
        rings = self.resolve(self.fake_state(devices=40, groups=25) + """
        const spec = m.carlosResolve({type:'canvas', targetIds:[], position:{x:0,y:0}}, state);
        const add = spec.items.find(i => i.id === 'add');
        console.log(JSON.stringify({ categories: add.children.length }));
        """)
        self.assertLessEqual(rings["categories"], 8)

    def test_a_ring_of_nine_raises(self):
        outcome = self.resolve("""
        let threw = false;
        try { rad.radAssertRing(Array.from({length: 9}, (_, i) => ({id: i}))); }
        catch { threw = true; }
        console.log(JSON.stringify({ threw }));
        """)
        self.assertTrue(outcome["threw"])

    def test_a_cable_resolves_as_an_edge(self):
        # `edge` is in rad's MenuContext vocabulary and Carlos never resolved
        # it, which is why a lead could be run and not pulled out again.
        spec = self.resolve("""
        const state = {
            definitions: {}, groups: [], modules: new Map(),
            cables: new Map([['a:out->b:in', { label: 'A out -> B in' }]]),
        };
        const spec = m.carlosResolve(
            {type:'edge', targetIds:['a:out->b:in'], position:{x:0,y:0}}, state);
        console.log(JSON.stringify(spec));
        """)
        self.assertEqual(spec["title"], "A out -> B in")
        actions = [i["action"] for i in spec["items"]]
        self.assertIn("cable:remove", actions)
        unpatch = next(i for i in spec["items"] if i["action"] == "cable:remove")
        self.assertTrue(unpatch["destructive"], "pulling a lead out is destructive")
        self.assertLessEqual(len(spec["items"]), 8)

    def test_an_edge_menu_survives_a_cable_it_cannot_name(self):
        # The menu resolves against state gathered when it opened. A cable
        # removed in between must give a menu, not a thrown resolver.
        spec = self.resolve("""
        const state = { definitions: {}, groups: [], modules: new Map(), cables: new Map() };
        const spec = m.carlosResolve(
            {type:'edge', targetIds:['gone'], position:{x:0,y:0}}, state);
        console.log(JSON.stringify(spec));
        """)
        self.assertEqual(spec["title"], "Cable")

    def test_unpatch_is_offered_only_when_something_is_patched(self):
        spec = self.resolve("""
        const module = { id: 'm1', name: 'VCO', type: 'carlos.vco',
                         sides: ['front', 'back'], view: 'front' };
        const base = { definitions: {}, groups: [], modules: new Map([['m1', module]]) };
        const context = {type:'node', targetIds:['m1'], position:{x:0,y:0}};
        const bare = m.carlosResolve(context, base);
        const patched = m.carlosResolve(
            context, { ...base, cableCounts: new Map([['m1', 3]]) });
        const pick = (spec) => spec.items.find(i => i.action === 'cable:remove-node');
        console.log(JSON.stringify({
            bare: pick(bare), patched: pick(patched),
            ring: [bare.items.length, patched.items.length],
        }));
        """)
        self.assertFalse(spec["bare"]["enabled"])
        self.assertTrue(spec["patched"]["enabled"])
        self.assertIn("3", spec["patched"]["label"])
        for size in spec["ring"]:
            self.assertLessEqual(size, 8, "the node ring outgrew the ceiling")

    def test_intents_carry_no_colour_literals(self):
        # The contract: `color:*` names a palette token, never a hex. A hex in
        # an intent cannot survive a theme change.
        for path in (Path("static/menus.js"), Path("static/main.js")):
            source = path.read_text(encoding="utf-8")
            with self.subTest(path.name):
                self.assertNotRegex(source, r"['\"]color:#")


@unittest.skipUnless(NODE, "node is not installed")
class ClickLayerTests(unittest.TestCase):
    """Carlos stacks several things that all want a click: the radial menu,
    device selection, jacks, knobs, row chrome, the rack background.

    `tests/click_layers.js` replays each collision found on 2026-08-17 against
    a DOM stub that really dispatches and really bubbles. It runs here so the
    reproductions are a gate rather than a script somebody remembers.
    """

    def run_harness(self):
        return subprocess.run(
            [NODE, "tests/click_layers.js"],
            capture_output=True, text=True, timeout=180,
        )

    def test_no_click_layers_collide(self):
        result = self.run_harness()
        self.assertEqual(
            result.returncode, 0,
            f"click layers collide:\n{result.stdout}\n{result.stderr}",
        )

    def test_the_harness_checked_something(self):
        # "0 collisions" over 0 checks is not a clean bill of health.
        result = self.run_harness()
        self.assertIn("clean", result.stdout)
        self.assertNotIn("0/0", result.stdout)


@unittest.skipUnless(NODE, "node is not installed")
class CableTracingTests(unittest.TestCase):
    """A cable you cannot follow is the one thing a patch exists to tell you.

    Devices turn independently, so a cable's ends are often on faces that are
    not both showing. `tests/cable_tracing.js` asserts every connection renders
    as one continuous line in every view — including when neither end is
    visible, which used to draw a stub that trailed off.
    """

    def run_harness(self):
        return subprocess.run(
            [NODE, "tests/cable_tracing.js"],
            capture_output=True, text=True, timeout=180,
        )

    def test_every_cable_stays_traceable(self):
        result = self.run_harness()
        self.assertEqual(
            result.returncode, 0,
            f"cable tracing regressed:\n{result.stdout}\n{result.stderr}",
        )

    def test_the_harness_checked_something(self):
        result = self.run_harness()
        self.assertRegex(result.stdout, r"\d+/\d+ passed")
        self.assertNotIn("0/0", result.stdout)


@unittest.skipUnless(NODE, "node is not installed")
class ViewReachesTheScreenTests(unittest.TestCase):
    """Every other harness asserts the model. This one asserts the tree.

    A device that reports turning and does not turn passes every model test
    there is, which is exactly how "devices not switching on Tab, no errors,
    reports success" gets to a person instead of to a test.
    """

    def run_harness(self):
        return subprocess.run(
            [NODE, "tests/view_toggle.js"],
            capture_output=True, text=True, timeout=180,
        )

    def test_turning_a_device_reaches_the_dom(self):
        result = self.run_harness()
        self.assertEqual(
            result.returncode, 0,
            f"the view did not reach the tree:\n{result.stdout}\n{result.stderr}",
        )

    def test_the_harness_checked_something(self):
        result = self.run_harness()
        self.assertRegex(result.stdout, r"\d+/\d+ passed")
        self.assertNotIn("0/0", result.stdout)


class StaticAssetFreshnessTests(unittest.TestCase):
    """A stale asset is the worst kind of bug report: clean server log, a status
    line reporting success, and nothing on screen moving."""

    def test_every_asset_in_the_page_is_cache_busted(self):
        markup = Path("templates/demo.html").read_text(encoding="utf-8")
        raw = re.findall(r'(?:src|href)="/static/([^"?]+)"', markup)
        self.assertEqual(raw, [], f"un-stamped asset URLs: {raw}")

    def test_the_page_asks_for_stamped_urls(self):
        markup = Path("templates/demo.html").read_text(encoding="utf-8")
        self.assertIn("asset('models.js')", markup)
        self.assertIn("asset('demo.css')", markup)

    def test_the_stamp_changes_when_a_file_does(self):
        import os
        import time
        from src.main import asset

        target = Path("static/models.js")
        before = asset("models.js")
        original = target.stat().st_mtime
        try:
            os.utime(target, (original + 5, original + 5))
            self.assertNotEqual(asset("models.js"), before)
        finally:
            os.utime(target, (original, original))
            time.sleep(0)

    def test_a_missing_asset_does_not_raise(self):
        from src.main import asset
        self.assertIn("nope.js", asset("nope.js"))


@unittest.skipUnless(NODE, "node is not installed")
class RackBehaviourTests(unittest.TestCase):
    """Sides, per-device turning, groups, the round trip and the version
    upgrades, driven headlessly. The largest behavioural suite here — it lived
    outside the repository for several sessions, which meant nothing ran it."""

    def run_harness(self):
        return subprocess.run(
            [NODE, "tests/rack_behaviour.js"],
            capture_output=True, text=True, timeout=180,
        )

    def test_rack_behaviour_holds(self):
        result = self.run_harness()
        self.assertEqual(
            result.returncode, 0,
            f"rack behaviour regressed:\n{result.stdout}\n{result.stderr}",
        )

    def test_the_harness_checked_something(self):
        result = self.run_harness()
        self.assertRegex(result.stdout, r"\d+/\d+ passed")
        self.assertNotIn("0/0", result.stdout)


class DeprecatedMenuTests(unittest.TestCase):
    """The old menus are gone, not merely unused."""

    def test_no_options_drawer_remains(self):
        markup = Path("templates/partials/controls_panel.html").read_text(encoding="utf-8")
        # Strip Jinja comments first: the file explains what was removed, and
        # naming the old menus in that explanation is not carrying them.
        markup = re.sub(r"\{#.*?#\}", "", markup, flags=re.S)

        for gone in ("options-drawer", "drawer-handle", "drawer-body",
                     "palette", "example-device", "row-target"):
            with self.subTest(gone):
                self.assertNotIn(gone, markup)

    def test_the_frontend_no_longer_builds_a_palette_or_row_picker(self):
        # Both files. `toggleDrawer` survived this check for a release by
        # living in models.js while the check only read main.js - dead code
        # addressing an element no template renders.
        main = "".join(
            Path(f).read_text(encoding="utf-8")
            for f in ("static/main.js", "static/models.js")
        )
        for gone in ("renderPalette", "refreshRowTargets", "toggleDrawer", "drawerOpen"):
            with self.subTest(gone):
                self.assertNotIn(gone, main)

    def test_the_radial_menu_is_wired_in(self):
        main = Path("static/main.js").read_text(encoding="utf-8")
        self.assertIn("new RadMenu", main)
        self.assertIn("routeIntent", main)
        self.assertIn("contextmenu", main)

    def test_the_page_loads_the_rad_files_in_dependency_order(self):
        html = Path("templates/demo.html").read_text(encoding="utf-8")
        order = [html.index(f"asset('{name}.js')") for name in
                 ("rad-core", "menus", "rad-menu", "models", "main")]
        self.assertEqual(order, sorted(order), "rad scripts load out of order")


if __name__ == "__main__":
    unittest.main()
