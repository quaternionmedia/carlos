"""The walkthrough's own properties, per the one-executable-walkthrough record.

Everything here is about the page set rather than about the pages' contents:
the contents are checked by running them, which is the point of the form. What
running them cannot check is whether the set is well formed, whether a page
declares a runtime it does not have, and whether the media a page shows is
media a page produced.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

WALKTHROUGH = Path("walkthrough")
MEDIA = WALKTHROUGH / "media"

# `NN-<slug>.md`, ordinal first, ordered by filename. The convention is
# identical in the corpus and in every adopting project: one with a
# project-shaped hole in it gets re-derived per project.
PAGE_NAME = re.compile(r"^(\d{2})-[a-z0-9-]+\.md$")

# A page declares its runtime in its opening line. Hermetic pages need nothing
# provisioned; runtime-bound pages need a service and must fail rather than
# skip when it is absent.
TIERS = ("Runtime: hermetic", "Runtime-bound")


def pages() -> list[Path]:
    return sorted(p for p in WALKTHROUGH.glob("*.md") if p.name != "README.md")


class PageSetTests(unittest.TestCase):
    def test_there_is_a_walkthrough(self):
        self.assertTrue(WALKTHROUGH.is_dir(), "every QM repository carries one")
        self.assertTrue(pages(), "a walkthrough with no pages is not one")

    def test_every_page_is_named_for_its_place_in_the_order(self):
        for page in pages():
            with self.subTest(page.name):
                self.assertRegex(page.name, PAGE_NAME)

    def test_the_ordinals_are_a_run_with_no_gaps_and_no_repeats(self):
        ordinals = [int(PAGE_NAME.match(p.name).group(1)) for p in pages()]
        self.assertEqual(ordinals, sorted(ordinals))
        self.assertEqual(len(set(ordinals)), len(ordinals), "a repeated ordinal")
        self.assertEqual(
            ordinals, list(range(ordinals[0], ordinals[0] + len(ordinals))),
            "a gap in the order",
        )

    def test_every_page_declares_its_runtime_in_its_opening_line(self):
        for page in pages():
            head = page.read_text(encoding="utf-8").split("\n", 4)
            opening = "\n".join(head[:4])
            with self.subTest(page.name):
                self.assertTrue(
                    any(tier in opening for tier in TIERS),
                    f"{page.name} does not say what it needs to run",
                )

    def test_hermetic_pages_come_first(self):
        # Pages 01 upward are hermetic until one genuinely cannot be. A
        # runtime-bound page early in the order makes the whole set need a
        # browser to read.
        seen_bound = False
        for page in pages():
            bound = "Runtime-bound" in page.read_text(encoding="utf-8")[:400]
            if bound:
                seen_bound = True
            elif seen_bound:
                self.fail(f"{page.name} is hermetic and sits after a bound page")

    def test_this_suite_does_not_skip_either(self):
        # The guard that exempts itself is the oldest hole there is. This file
        # enforces "a skip is not a pass" over the pages, so it may not contain
        # one - and it did, until a from-scratch regeneration exposed it.
        body = Path("tests/test_walkthrough.py").read_text(encoding="utf-8")
        body = re.sub(r"#.*$", "", body, flags=re.M)
        body = re.sub(r'""".*?"""', "", body, flags=re.S)
        self.assertNotIn("self." + "skipTest(", body)

    def test_no_page_declares_a_skip(self):
        # A skip is not a pass. A page that vanishes into a skip count reports
        # green for a demonstration nobody ran.
        for page in pages():
            body = page.read_text(encoding="utf-8")
            with self.subTest(page.name):
                self.assertNotIn("pytest.skip", body)
                self.assertNotIn("SkipTest", body)
                self.assertNotIn("skipUnless", body)


class ExampleDisciplineTests(unittest.TestCase):
    """An example may not discard a failure.

    doctest reports success for an example that raises nothing and declares no
    output, so `subprocess.run([...])` against a command exiting non-zero
    passes. Every example that runs a process carries `check=True` or puts its
    `returncode` in the expected output.
    """

    def test_no_example_runs_a_process_without_checking_it(self):
        for page in pages():
            body = page.read_text(encoding="utf-8")
            for line in body.splitlines():
                if "subprocess.run" not in line or not line.strip().startswith(">>>"):
                    continue
                with self.subTest(f"{page.name}: {line.strip()}"):
                    self.assertTrue(
                        "check=True" in line or "returncode" in line,
                        "an example that runs a process must not discard its failure",
                    )


class MediaTests(unittest.TestCase):
    """Recorded, never compared - and never orphaned.

    The pictures are byproducts of the run that asserted the behaviour. What is
    checkable about them here is the joint between the page and the file: a
    page showing an image nothing produces is stale documentation, and a file
    no page shows is a leftover.
    """

    def shown(self) -> set[str]:
        shown = set()
        for page in pages():
            body = page.read_text(encoding="utf-8")
            shown |= set(re.findall(r"!\[[^\]]*\]\(media/([^)]+)\)", body))
        return shown

    # The command that puts it right, named in the failure rather than left for
    # the reader to work out. A shot is only ever missing for one reason.
    REGENERATE = (
        "uv run pytest walkthrough/05-in-the-browser.md --doctest-glob=*.md"
    )

    def test_the_recorded_media_is_in_the_checkout(self):
        # Committed, so a fresh clone has it. This is checked before the two
        # below, because "the directory is not there" and "this page shows an
        # image nothing produces" are different problems with different fixes,
        # and the second message is misleading when the first is the truth.
        self.assertTrue(
            MEDIA.is_dir(),
            f"walkthrough/media is missing. It is committed, so either the "
            f"checkout is broken or it was deleted: {self.REGENERATE}",
        )

    def test_every_image_a_page_shows_exists(self):
        for name in self.shown():
            with self.subTest(name):
                self.assertTrue(
                    (MEDIA / name).is_file(),
                    f"a page shows {name} and nothing recorded it: {self.REGENERATE}",
                )

    def test_every_recorded_image_is_shown_by_a_page(self):
        # No skip when the directory is absent. A skip is not a pass, and this
        # is the suite that holds the walkthrough pages to exactly that - one
        # here would have been the guard exempting itself.
        shown = self.shown()
        for path in MEDIA.glob("*.png"):
            with self.subTest(path.name):
                self.assertIn(path.name, shown, "recorded but shown by no page")

    def test_the_recorder_never_compares(self):
        # The clause the record is emphatic about. A test that diffs images
        # fails on a font and gets switched off, taking the assertions beside
        # it; regression protection belongs in the assertions and the picture
        # is output.
        source = (WALKTHROUGH / "support.py").read_text(encoding="utf-8")
        source = re.sub(r'""".*?"""', "", source, flags=re.S)
        for comparison in ("assert_snapshot", "to_match_snapshot",
                           "image_diff", "compare_images", "baseline"):
            with self.subTest(comparison):
                self.assertNotIn(comparison, source)


class RegistryTests(unittest.TestCase):
    """One registry is the content; every surface reads it.

    The filenames are the registry. Anything else that lists the pages is a
    rendering of it, and a hand-maintained parallel list is not permitted to
    shadow it - that is the one fragile joint the record names in the
    repository it holds up as the worked example.
    """

    def test_nothing_un_ignores_the_media_by_hand(self):
        # `qmetronome`'s single fragile joint is a .gitignore that un-ignores
        # each generated asset with forty-seven hand-written lines, checked
        # against nothing. Media here is tracked normally, so there is no list
        # to fall out of step.
        ignore = Path(".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("walkthrough", ignore)

    def test_the_command_that_runs_the_pages_names_them(self):
        # `testpaths` is ignored the moment pytest receives a path argument, so
        # a walkthrough wired that way is collected by nobody and stays green
        # forever. The invocation has to name the directory.
        config = Path("pyproject.toml").read_text(encoding="utf-8")
        # Comments stripped first: the file explains at length why it sets no
        # `testpaths`, and naming the setting in that explanation is not
        # setting it. A guard that cannot tell those apart makes the
        # explanation unwritable, which is how the reasoning gets lost.
        settings = chr(10).join(
            line for line in config.splitlines()
            if not line.lstrip().startswith("#")
        )
        self.assertNotRegex(settings, r"(?m)^\s*testpaths\s*=")

        for surface in (Path("README.md"), Path("AGENTS.md"),
                        Path("CONTRIBUTING.md"),
                        WALKTHROUGH / "04-cookbook.md"):
            with self.subTest(surface.name):
                body = surface.read_text(encoding="utf-8")
                self.assertIn("pytest tests walkthrough", body)
                self.assertIn("--doctest-glob=*.md", body)


class CollectionTests(unittest.TestCase):
    def test_pytest_collects_every_page(self):
        # The property the record measured and this project would otherwise
        # have got wrong: the pages are collected by the command that names
        # them, and the count is the count of pages rather than whatever
        # happened to be found.
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "walkthrough",
             "--doctest-glob=*.md", "--collect-only", "-q"],
            capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        collected = [
            line for line in result.stdout.splitlines()
            if line.startswith("walkthrough/") or line.startswith("walkthrough\\")
        ]
        self.assertEqual(len(collected), len(pages()), result.stdout)


class ContributingTests(unittest.TestCase):
    """Onboarding lives in one place, and it is the page that runs.

    Decision 9 of the one-executable-walkthrough record: onboarding and the
    cookbook are separate documents and stay separate, and the contributing
    guide refuses to duplicate the onboarding page. Setup instructions kept in
    two places are setup instructions that disagree within a month - which is
    the failure this whole record exists about, measured across six of the
    org's repositories.
    """

    def setUp(self):
        self.body = Path("CONTRIBUTING.md").read_text(encoding="utf-8")

    def test_it_points_at_the_onboarding_page(self):
        self.assertIn("walkthrough/01-onboarding.md", self.body)

    def test_it_does_not_restate_the_setup(self):
        # The commands that belong to onboarding and nowhere else. A guide that
        # carries these has started a second copy, whatever it says about not
        # duplicating one.
        for owned in ("uv sync", "git clone", "submodule update --init"):
            with self.subTest(owned):
                self.assertNotIn(owned, self.body)

    def test_it_says_to_commit_regenerated_media(self):
        # The mechanism only works if the diff gets committed. A contributor
        # who leaves it uncommitted has a green build and a stale picture,
        # which is the state this whole arrangement is designed to prevent.
        self.assertIn("walkthrough/media", self.body)
        self.assertRegex(self.body, r"(?i)commit .{0,40}screenshot")

    def test_the_gate_count_it_claims_is_the_gate_count_there_is(self):
        # A number written out in prose is the kind of thing that is right when
        # typed and wrong a year later, and nothing else would notice.
        #
        # "Seed workflows" means the ones that call into the corpus's own CI
        # scripts, which is what makes them the org's gates rather than this
        # project's. Counting every file in the directory was wrong the moment
        # the project added a workflow of its own - this guard caught that on
        # the commit that added `tests.yml`, which is what it is for.
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
        claimed = re.search(r"(\w+) seed workflows", self.body)
        self.assertIsNotNone(claimed, "CONTRIBUTING.md no longer counts them")
        spelled = claimed.group(1).lower()

        # Named rather than sniffed. Two of the gates run a tool directly
        # rather than a seed script, so "calls into project-seed/ci" is not the
        # discriminator it looks like - and a workflow added later has to be
        # put in a bucket deliberately rather than silently counted as a gate.
        ours = {"tests.yml"}
        present = {p.name for p in Path(".github/workflows").glob("*.yml")}
        gates = present - ours

        self.assertEqual(words.get(spelled, spelled), len(gates))
        self.assertTrue(
            ours <= present, f"{ours - present} is named here and is not there"
        )

    def test_the_project_runs_its_own_tests_in_ci(self):
        # Every other workflow is a governance gate. Until one of them ran the
        # suite, a reviewer seeing green checks was reading six gates about
        # records, signatures and licensing - and could reasonably have believed
        # the tests had passed. They had only ever run on one workstation.
        workflows = {
            path.name: path.read_text(encoding="utf-8")
            for path in Path(".github/workflows").glob("*.yml")
        }
        runs_tests = [n for n, body in workflows.items() if "pytest tests" in body]
        self.assertTrue(runs_tests, "no workflow runs the test suite")

        body = "".join(workflows.values())
        # And the halves the walkthrough record's tiering requires.
        self.assertIn("walkthrough/05-in-the-browser.md", body)
        self.assertIn("playwright install", body)
        for harness in ("view_toggle", "rack_behaviour", "cable_tracing",
                        "click_layers", "palette"):
            with self.subTest(harness):
                self.assertIn(f"tests/{harness}.js", body)

    def test_the_expected_failures_it_names_are_the_ones_governance_records(self):
        governance = Path("GOVERNANCE.md").read_text(encoding="utf-8")
        for gate in ("reuse-lint", "submodule-check", "signature-check"):
            with self.subTest(gate):
                self.assertIn(gate, self.body)
                self.assertIn(gate, governance)
