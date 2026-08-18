"""`carlos` dispatches, and the documentation names what it dispatches.

Two properties worth holding. The first is the CLI's own doctrine, borrowed
from `governance/qm/ci/cli.py`: a command that recomputed a verdict, prettified
an exit code or defaulted a flag differently would be a second definition of a
rule, and two definitions drift the first time one is fixed. So every command
here is checked for running the canonical command and nothing else.

The second is cohesion. A CLI whose commands the documentation does not name,
or documentation naming commands the CLI does not have, is two instruction sets
for one repository — which is the failure the walkthrough record is about,
arriving by a different door.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

from click.testing import CliRunner

from tools import cli

# Every durable round, and the command each one must resolve to. The right-hand
# side is what the documentation tells a reader to type, so if these two ever
# disagree the documentation is wrong or this is.
ROUNDS = {
    "check": "uv run pytest tests walkthrough --doctest-glob=*.md",
    "harness": "node tests/view_toggle.js",
    "shots": "uv run pytest walkthrough/05-in-the-browser.md --doctest-glob=*.md",
    "gates": (
        "python governance/qm/project-seed/ci/run_workflows_locally.py "
        "--base-ref they"
    ),
    "signatures": (
        "python governance/qm/project-seed/ci/check_signatures.py "
        "--base-ref they --head-ref HEAD --source git"
    ),
    "serve": "uv run python src/main.py",
}


class CommandSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_every_round_is_a_command(self):
        commands = set(cli.main.commands)
        for round_ in (*ROUNDS, "stop", "status"):
            with self.subTest(round_):
                self.assertIn(round_, commands)

    def test_every_command_explains_itself(self):
        # `--help` is where somebody meets this. A command whose help is a
        # restatement of its own name has told them nothing.
        for name, command in cli.main.commands.items():
            with self.subTest(name):
                self.assertIsNotNone(command.help, f"{name} has no help")
                self.assertGreater(len(command.help), 60)

    def test_dry_run_prints_the_command_the_documentation_names(self):
        for round_, expected in ROUNDS.items():
            with self.subTest(round_):
                result = self.runner.invoke(cli.main, ["--dry-run", round_])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn(expected, result.output)

    def test_dry_run_prints_a_command_and_runs_nothing(self):
        # The point of it: you should be able to type any of these yourself.
        # A resolved interpreter path inside a virtual environment is the same
        # command and is not one anybody can use.
        result = self.runner.invoke(cli.main, ["--dry-run", "check"])
        self.assertNotIn(".venv", result.output)
        self.assertNotIn(sys.executable, result.output)


class ItDispatchesTests(unittest.TestCase):
    """No verdicts are formed here, and no exit code is prettified."""

    def test_a_failing_command_returns_its_own_status(self):
        # The property, checked on `run` itself rather than by invoking a real
        # round. `carlos gates` would have been the honest subject and is the
        # one thing this test may not use: the gates run `tests.yml`, which
        # runs this suite, which would run the gates again.
        status = cli.run(
            [sys.executable, "-c", "raise SystemExit(3)"],
            dry_run=False,
            root=cli.repository_root(),
        )
        self.assertEqual(status, 3, "the status the command returned was not passed on")

    def test_a_succeeding_command_returns_zero(self):
        status = cli.run(
            [sys.executable, "-c", "pass"],
            dry_run=False,
            root=cli.repository_root(),
        )
        self.assertEqual(status, 0)

    def test_what_it_prints_is_what_it_runs(self):
        # The principle, and the bug that earned it a test: `gates` printed
        # `python <seed script>` and executed it with this process's
        # interpreter, which inside `uv run carlos` is the project environment
        # — no pyyaml, and no reason to have any. The printed command worked
        # and the executed one did not, which is exactly how a divergence
        # between the two hides.
        #
        # The seed scripts run on a plain interpreter by design, so for those
        # the two must be the same list, not merely equivalent.
        self.assertEqual(cli.SEED, ["python"])
        for source in Path("tools/cli.py").read_text(encoding="utf-8").splitlines():
            if "GATES" in source or "SIGNATURES" in source:
                with self.subTest(source.strip()[:50]):
                    self.assertNotIn("sys.executable", source)

    def test_dry_run_runs_nothing_at_all(self):
        # It would have to, to return a status it did not invent.
        marker = cli.repository_root() / "data" / "cli-dry-run-probe"
        self.assertFalse(marker.exists())
        cli.run(
            [sys.executable, "-c", "open(r'" + str(marker) + "', 'w').close()"],
            dry_run=True,
            root=cli.repository_root(),
        )
        self.assertFalse(marker.exists(), "--dry-run ran the command")



class WhereItRunsTests(unittest.TestCase):
    def test_it_finds_the_repository_from_below(self):
        # Every path in this repository resolves against the working directory,
        # so a command run from `src/` writes a second database and reads no
        # catalogue at all.
        found = cli.repository_root(Path("src").resolve())
        self.assertTrue((found / "catalogue/devices").is_dir())

    def test_it_refuses_to_run_outside_the_repository(self):
        import tempfile

        with tempfile.TemporaryDirectory() as elsewhere:
            with self.assertRaises(Exception) as caught:
                cli.repository_root(Path(elsewhere))
            self.assertIn("not inside", str(caught.exception))


class TheDocumentationNamesTheseTests(unittest.TestCase):
    """One instruction set, not two.

    Every round has to appear where a reader looks for it, and nothing may
    advertise a command that does not exist.
    """

    SURFACES = (
        Path("README.md"),
        Path("CONTRIBUTING.md"),
        Path("walkthrough/04-cookbook.md"),
    )

    def test_the_cookbook_names_every_round(self):
        cookbook = Path("walkthrough/04-cookbook.md").read_text(encoding="utf-8")
        for round_ in (*ROUNDS, "stop", "status"):
            with self.subTest(round_):
                self.assertIn(f"carlos {round_}", cookbook)

    def test_nothing_advertises_a_command_that_does_not_exist(self):
        known = set(cli.main.commands)
        for surface in self.SURFACES:
            body = surface.read_text(encoding="utf-8")
            for advertised in set(re.findall(r"carlos ([a-z][a-z-]*)", body)):
                # Prose names the tool; a command is the word after it,
                # and an option is not a command.
                if advertised in {"repository", "is", "as", "at", "and",
                                  "the", "command", "commands"}:
                    continue
                with self.subTest(f"{surface.name}: {advertised}"):
                    self.assertIn(advertised, known)
