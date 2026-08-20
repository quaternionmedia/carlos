"""The walkthrough's own properties, per the one-executable-walkthrough record.

Everything here is about the page set rather than about the pages' contents:
the contents are checked by running them, which is the point of the form. What
running them cannot check is whether the set is well formed, whether a page
declares a runtime it does not have, and whether the media a page shows is
media a page produced.
"""

import json
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

    def test_the_readme_shows_a_screen_the_walkthrough_recorded(self):
        """The homepage picture is the walkthrough's, not a second one.

        A README screenshot taken by hand is a picture of whatever the program
        looked like the day somebody remembered - and nothing turns red when it
        stops being true. Pointing at the recorded artifact makes the homepage
        ride decision 5's regeneration: the screen changes, the file changes,
        and `git status` says so.

        This is the joint from the README's side. `walkthrough/media` is the
        registry; a path spelled by hand into another surface is exactly the
        shadowing decision 6 forbids unless it bottoms out in the registry.
        """
        readme = Path("README.md").read_text(encoding="utf-8")
        shown = re.findall(r"!\[[^\]]*\]\(walkthrough/media/([^)]+)\)", readme)

        self.assertTrue(
            shown,
            "the README shows no recorded screen. The project's subject is a "
            f"user interface: {self.REGENERATE}",
        )
        for name in shown:
            with self.subTest(name):
                self.assertTrue(
                    (MEDIA / name).is_file(),
                    f"the README shows {name} and nothing recorded it: "
                    f"{self.REGENERATE}",
                )
                # And it is recorded by a page, so it cannot be a stray file
                # somebody dropped in beside the real ones.
                self.assertIn(name, self.shown(), "shown by no page")

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

        # Every surface has to get a reader to that command, and there are two
        # honest ways: spell it, or name the round that runs it. `carlos check`
        # is checked in `tests/test_cli.py` for resolving to exactly this, so
        # naming the round is naming the command by one indirection rather than
        # a second definition of it.
        for surface in (Path("README.md"), Path("AGENTS.md"),
                        Path("CONTRIBUTING.md"),
                        WALKTHROUGH / "04-cookbook.md"):
            with self.subTest(surface.name):
                body = surface.read_text(encoding="utf-8")
                spelled = "pytest tests walkthrough" in body and "--doctest-glob=*.md" in body
                named = "carlos check" in body
                self.assertTrue(
                    spelled or named,
                    f"{surface.name} neither spells the check command nor names "
                    "the round that runs it",
                )

        # And it is spelled somewhere, verbatim, so the indirection bottoms out.
        cookbook = (WALKTHROUGH / "04-cookbook.md").read_text(encoding="utf-8")
        self.assertIn("pytest tests walkthrough --doctest-glob=*.md", cookbook)


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


class ReleaseGateTests(unittest.TestCase):
    """What a version tag asserts, and which part of it a machine can do.

    `DRAFT-version-tags-are-claims.md` §2 names three claims. Only the third is
    mechanical. These tests are mostly about the other two staying *un*claimed:
    a gate that exits zero without saying what it did not check is a gate that
    lets a green tick assert diligence nobody performed.
    """

    def cli(self):
        return Path("tools/cli.py").read_text(encoding="utf-8")

    def test_the_command_exists_and_runs_everything(self):
        # `tests` alone would drop the browser suite and the pages, which is
        # most of what a reader would assume a release was validated against.
        body = self.cli()
        self.assertIn("release-check", body)
        self.assertIn("RELEASE_CHECK", body)
        for named in ("tests", "walkthrough"):
            self.assertIn(named, body)

    def test_a_skip_is_refused(self):
        # §3: a skipped test is an absent test that has announced itself. The
        # suite skips whole classes without `node` and the whole browser suite
        # without a browser, so this is the clause that decides whether a green
        # run on a bare machine can be read as validation.
        body = self.cli()
        self.assertIn("skipped", body)
        for word in ("rerun", "retried"):
            with self.subTest(word):
                self.assertIn(word, body)

    def test_it_does_not_claim_the_human_half(self):
        # The whole point. Exiting zero is allowed to mean "validation passed";
        # it is not allowed to mean "reviewed and manually tested".
        body = self.cli()
        self.assertIn("human", body)
        self.assertIn("manually test", body)

    def test_there_is_no_flag_to_skip_the_gate(self):
        # A flag to skip it would be the failure the record describes, arriving
        # by the front door.
        body = self.cli()
        for escape in ("--no-skip-check", "--allow-skips", "--force"):
            with self.subTest(escape):
                self.assertNotIn(escape, body)

    def test_the_tag_ruleset_would_do_what_releasing_says(self):
        """§7's ruleset, written down so applying it is one command.

        Nothing here applies it — that is repository settings and an admin's
        act, and `gh api .../rulesets` returns empty today. What this checks is
        that the payload sitting in the repository is not a no-op waiting to be
        pasted: a ruleset that targeted the wrong refs or carried no `creation`
        rule would leave §1 exactly as customary as it is now, while looking
        like it had been dealt with.
        """
        payload = json.loads(
            Path(".github/tag-ruleset.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["target"], "tag")
        self.assertEqual(payload["enforcement"], "active")
        self.assertEqual(
            payload["conditions"]["ref_name"]["include"], ["refs/tags/v*"],
            "the record restricts `v*`; a wider pattern restricts unrelated "
            "tags and a narrower one restricts nothing",
        )
        # Creation is the clause §7 asks for. Update and deletion are here
        # because a tag that can be moved after the fact asserts whatever the
        # mover wants it to.
        self.assertEqual(
            {rule["type"] for rule in payload["rules"]},
            {"creation", "update", "deletion"},
        )
        # And somebody can still cut a release. A ruleset nobody can bypass is
        # not enforcement of "a human cuts the tag"; it is a project that
        # cannot tag.
        self.assertTrue(payload["bypass_actors"], "nobody could cut a tag")

        # RELEASING.md has to point at this file, or it is a payload nobody
        # finds at the moment they need it.
        doc = Path("RELEASING.md").read_text(encoding="utf-8")
        self.assertIn(".github/tag-ruleset.json", doc)

    def test_releasing_names_what_a_tag_asserts(self):
        doc = Path("RELEASING.md").read_text(encoding="utf-8")
        for claim in ("reviewed", "manually tested", "deterministic"):
            with self.subTest(claim):
                self.assertIn(claim, doc.lower())
        # And that nothing untagged is a release.
        self.assertIn("carries no release claim", doc.lower())

    def test_releasing_says_a_human_cuts_the_tag(self):
        # Whitespace-normalised: these sentences wrap, and a test that breaks
        # on a reflow is a test that gets reflowed away.
        doc = " ".join(
            Path("RELEASING.md").read_text(encoding="utf-8").lower().split())
        self.assertIn("a human, and only a human", doc)
        self.assertIn("never cuts the tag", doc)

    def test_the_workflow_triggers_on_a_tag_and_creates_none(self):
        flow = Path(".github/workflows/release-gate.yml").read_text(
            encoding="utf-8")
        self.assertIn("tags:", flow)
        self.assertIn("'v*'", flow)
        # §7: release automation triggers on the tag and never creates one.
        self.assertNotIn("git tag", flow)
        self.assertNotIn("create-release", flow)

    def test_the_workflow_says_what_it_did_not_assert(self):
        flow = Path(".github/workflows/release-gate.yml").read_text(
            encoding="utf-8").lower()
        self.assertIn("what it did not", flow)
        self.assertIn("manually tested", flow)

    def test_this_project_makes_no_release_claim_yet(self):
        # Carlos has never been tagged. If that changes, this test should be
        # the thing that makes somebody say so here rather than let the
        # documentation quietly go stale.
        found = subprocess.run(
            ["git", "tag", "--list", "v*"],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(
            found.stdout.strip(), "",
            "there is a version tag now; RELEASING.md's closing section and "
            "this test both need to say so")


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
        ours = {"tests.yml", "release-gate.yml", "image.yml"}
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
                        "click_layers"):
            with self.subTest(harness):
                self.assertIn(f"tests/{harness}.js", body)

    def test_the_expected_failures_it_names_are_the_ones_governance_records(self):
        governance = Path("GOVERNANCE.md").read_text(encoding="utf-8")
        for gate in ("reuse-lint", "submodule-check", "signature-check"):
            with self.subTest(gate):
                self.assertIn(gate, self.body)
                self.assertIn(gate, governance)
