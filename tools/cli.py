"""`carlos` — one entry point for every durable round in this repository.

    uv run carlos --help

WHAT THIS IS, AND WHAT IT REFUSES TO BE.

This dispatches. Every command runs the canonical command for that round and
exits with exactly the status it returned. Nothing here forms a verdict,
prettifies an exit code, or defaults a flag that the underlying tool would have
defaulted differently — a command that did any of those would be a second
definition of a rule, and two definitions drift the first time one is fixed.
The doctrine is `governance/qm/ci/cli.py`'s, which says the same about itself.

So if `carlos check` reads wrongly, the fix is in pytest's invocation, not
here; and `carlos gates` exits non-zero for the three gates that fail today
because that is what the runner returns.

WHY THE COMMANDS STILL RUN WITHOUT IT. Every round below is a command you can
type yourself, and `--dry-run` prints exactly that command without running it.
CI does type them: `.github/workflows/tests.yml` invokes pytest and node
directly, so a gate cannot fail for want of an installed package. One
definition, two entry points.

WHERE IT RUNS. Every path in this repository resolves against the working
directory — `Settings` resolves `data/db.json`, the harnesses read
`catalogue/devices/`, the walkthrough writes `walkthrough/media/`. Starting
from `src/` therefore writes a second database at `src/data/` and reads no
catalogue at all. So this locates the repository root by marker, walking up,
and runs everything from there rather than from wherever you happened to be.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import click

# A directory is this repository if it holds the application and the catalogue.
# Checking one would match a stray copy of either.
MARKERS = ("src/main.py", "catalogue/devices", "walkthrough")

# The four frontend harnesses, in the order they are named everywhere else.
# The model is not the screen: two of this project's real bugs were invisible
# to every model-level test and were caught only by these.
HARNESSES = (
    "view_toggle",
    "rack_behaviour",
    "cable_tracing",
    "click_layers",
    "midi_diagnose",
)

# The one check command, spelled once. Both paths are named deliberately:
# `testpaths` is ignored the moment pytest is handed a path argument, so a
# walkthrough wired that way is collected by nobody and stays green forever.
CHECK = ("pytest", "tests", "walkthrough", "--doctest-glob=*.md")

# The runtime-bound page, which is also what regenerates the screenshots.
BROWSER_PAGE = "walkthrough/05-in-the-browser.md"

# The seed scripts run on a plain interpreter by design: a fork executes them
# in place without installing anything, and the workflows invoke them directly
# so a gate cannot fail for want of a venv. So they are run with the `python`
# on PATH and not with this process's interpreter — inside `uv run carlos` that
# is the project's environment, which has no pyyaml and no reason to.
#
# Found by running it: `--dry-run` printed the command that works while the
# command that ran was a different one. Printing something other than what you
# execute is how that hides.
SEED = ["python"]

GATES = "governance/qm/project-seed/ci/run_workflows_locally.py"
SIGNATURES = "governance/qm/project-seed/ci/check_signatures.py"

# This repository's default branch is `they`, and the seed runner defaults to
# `main` — which fails two gates for a reason that is about the flag rather
# than the code.
BASE_REF = "they"


def repository_root(start: Path | None = None) -> Path:
    """The repository, found by marker rather than assumed to be `.`."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if all((candidate / marker).exists() for marker in MARKERS):
            return candidate
    raise click.ClickException(
        "not inside the Carlos repository — no directory above "
        f"{here} holds all of {', '.join(MARKERS)}"
    )


def run(
    argv: list[str],
    *,
    dry_run: bool,
    root: Path,
    canonical: list[str] | None = None,
    env: dict | None = None,
) -> int:
    """Run one command from the repository root, or print it.

    Its exit status is this command's exit status. Nothing is interpreted.

    What is printed is `canonical` — the command as the documentation spells
    it — rather than what is executed, which inside an active environment is
    the resolved interpreter. Those are the same command, and only one of them
    is worth typing. A `--dry-run` that emitted an absolute path into a venv
    would be teaching something nobody can use.
    """
    shown = " ".join(canonical or argv)
    if dry_run:
        click.echo(shown)
        return 0

    click.secho(f"$ {shown}", fg="cyan")
    completed = subprocess.run(argv, cwd=root, env={**os.environ, **(env or {})})
    return completed.returncode


def uv(argv: list[str]) -> list[str]:
    """How the documentation spells this command: `uv run <it>`."""
    return ["uv", "run", *argv]


def here(argv: list[str]) -> list[str]:
    """How to execute it in whatever environment is already active.

    Inside `uv run carlos` the environment is the project's already, so calling
    `uv run` again would resolve a second one for no reason. Outside it, the
    prefix is what makes the dependencies resolve at all.
    """
    inside = bool(os.environ.get("VIRTUAL_ENV") or os.environ.get("UV_PROJECT_ENVIRONMENT"))
    if not inside:
        return ["uv", "run", *argv]
    if argv[0] == "pytest":
        return [sys.executable, "-m", *argv]
    if argv[0] == "python":
        return [sys.executable, *argv[1:]]
    return argv


def _tolerate_closed_output() -> None:
    """A closed pipe is not an error worth a traceback.

    `carlos status | head` closes stdout part way through, and Python answers
    with `OSError: [Errno 22]` from the flush — a wall of traceback for the
    most ordinary thing anyone does to a status command.
    """
    try:
        sys.stdout.flush()
    except OSError:
        os._exit(0)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--dry-run", is_flag=True,
    help="Print the command this would run, and run nothing.",
)
@click.pass_context
def main(ctx: click.Context, dry_run: bool) -> None:
    """Every durable round in this repository, in one place.

    Each command runs the canonical command for that round and exits with its
    status. `--dry-run` prints it instead, because you should be able to type
    any of these yourself.
    """
    ctx.ensure_object(dict)
    ctx.obj["dry_run"] = dry_run
    ctx.obj["root"] = repository_root()


@main.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """The suite and the walkthrough. The command to run before a pull request.

    Runs the tests *and* the executable documentation, because the pages are
    where the examples a reader copies are proved.
    """
    ctx.exit(run(here(list(CHECK)), canonical=uv(list(CHECK)), **_opts(ctx)))


@main.command()
@click.argument("only", required=False,
                type=click.Choice(HARNESSES, case_sensitive=False))
@click.pass_context
def harness(ctx: click.Context, only: str | None) -> None:
    """The frontend harnesses, under Node.

    They assert the tree rather than the model. Naming one runs just that one.
    """
    chosen = [only] if only else list(HARNESSES)
    status = 0
    for name in chosen:
        status = run(["node", f"tests/{name}.js"], **_opts(ctx)) or status
    ctx.exit(status)


@main.command()
@click.pass_context
def shots(ctx: click.Context) -> None:
    """Regenerate the walkthrough screenshots.

    They are byproducts of the run that asserts the behaviour they show, so
    this is the browser page and nothing else. Drift arrives as an uncommitted
    diff — commit what changes.
    """
    ctx.exit(run(here(["pytest", BROWSER_PAGE, "--doctest-glob=*.md"]), canonical=uv(["pytest", BROWSER_PAGE, "--doctest-glob=*.md"]), **_opts(ctx)))


@main.command()
@click.pass_context
def browser(ctx: click.Context) -> None:
    """The browser suite, in real Chromium.

    Separate from `check` only so it can be run alone while working on the
    front end; `check` runs it too, because it is tests. It needs a browser
    once per clone: `uv run playwright install chromium`.
    """
    ctx.exit(run(
        here(["pytest", "tests/browser", "-q"]),
        canonical=uv(["pytest", "tests/browser", "-q"]),
        **_opts(ctx),
    ))


@main.command()
@click.pass_context
def gates(ctx: click.Context) -> None:
    """The governance gates, as CI runs them.

    Three fail today for reasons recorded in GOVERNANCE.md, so a non-zero exit
    is expected. The runner cannot reproduce `uses:` steps, the runner image or
    secrets: a local pass is not a remote pass.
    """
    ctx.exit(run(SEED + [GATES, "--base-ref", BASE_REF], **_opts(ctx)))


# Everything, including the parts that skip themselves when a fixture is
# missing. A release gate that quietly drops the browser suite because no
# browser was provisioned is the exact failure the version-tags record names.
RELEASE_CHECK = (
    "pytest", "tests", "walkthrough", "--doctest-glob=*.md",
    "-q", "-rs", "-p", "no:randomly",
)


def pytest_summary(stdout: str) -> str:
    """The last non-blank line pytest wrote, and only what pytest wrote.

    This used to read `stdout + stderr` and take the last line of the
    concatenation, so any line on stderr became "the summary" and the scan below
    examined the wrong text. Measured: with stderr empty it caught
    `1 passed, 161 skipped`; with one line on stderr it reported the run clean.
    `here()` returns `uv run ...` outside a virtualenv and uv writes its sync
    lines to stderr, so it was reachable rather than theoretical.
    """
    for line in reversed((stdout or "").strip().splitlines()):
        if line.strip():
            return line
    return ""


# Words that mean the run is not evidence. `rerun` and `retried` need
# pytest-rerunfailures and cannot appear without it; they are kept because they
# cost nothing and the plugin may arrive, but the ones carrying the weight today
# are the three pytest itself emits.
NOT_VALIDATION = ("skipped", "rerun", "retried", "xfailed", "xpassed")

# What pytest's own summary line always contains. Requiring it is what stops the
# scan examining a blank string and finding nothing wrong in it -- which reads
# exactly like a clean run.
SUMMARY_SHAPE = re.compile(r"\d+ (passed|failed|error|skipped|deselected)")


def determinism_problems(summary: str) -> list[str]:
    """What is wrong with a run, judged from its summary line."""
    if not SUMMARY_SHAPE.search(summary):
        return [
            f"could not find pytest's summary line to check; the last line of "
            f"stdout was {summary[:60]!r}"
        ]
    return [
        f"the run reports {word}, which is not validation"
        for word in NOT_VALIDATION if word in summary
    ]


@main.command("release-check")
@click.option("--tag", default=None,
              help="Also check this tag's annotation says what it asserts.")
@click.pass_context
def release_check(ctx: click.Context, tag: str | None) -> None:
    """The machine half of what a `v*` tag asserts.

    `DRAFT-version-tags-are-claims.md` section 2 says a tag asserts three things: a
    human reviewed the change set, a human manually tested it against its real
    runtime, and automated validation passed *and is deterministic*.

    Only the third is mechanical, and this is it. The first two are human acts
    and this command cannot perform them, check them, or stand in for them —
    section 1 draws that line and it is the same line as ratification.

    What it does check is section 3, which is the clause with teeth: **a skipped test
    is an absent test that has announced itself.** This suite skips whole
    classes when `node` is missing and the whole browser suite when no browser
    was provisioned, so a run that looks green on a bare machine has verified
    a fraction of what a reader would assume. A skip here is a failure.

    Reruns and retries are refused for the same reason: a suite whose result
    changes between runs on unchanged input is not evidence of anything.
    """
    root, dry_run = ctx.obj["root"], ctx.obj["dry_run"]
    argv = here(list(RELEASE_CHECK))

    if dry_run:
        click.echo(f"$ {' '.join(uv(list(RELEASE_CHECK)))}")
        if tag:
            click.echo(f"$ git tag -n99 --list {tag}")
        ctx.exit(0)

    completed = subprocess.run(
        argv, cwd=root, text=True, capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    report = (completed.stdout or "") + (completed.stderr or "")
    click.echo(report.rstrip())

    problems = []
    if completed.returncode != 0:
        problems.append("the suite did not pass")

    problems.extend(determinism_problems(pytest_summary(completed.stdout)))

    if tag:
        problems.extend(_tag_problems(root, tag))

    if problems:
        for problem in problems:
            click.secho(f"  not a release: {problem}", fg="red")
        click.secho(
            "\nsection 3 counts only deterministic validation. Provision what the "
            "suite needs and run it again.", fg="red")
        ctx.exit(1)

    click.secho("\nDeterministic validation passed, with nothing skipped.",
                fg="green")
    click.echo(
        "That is one of the three claims a `v*` tag makes. The other two are\n"
        "human acts and this command has not made them: a human reviews the\n"
        "change set, and a human manually tests it against its real runtime.\n"
        "See RELEASING.md.")
    ctx.exit(0)


def _tag_problems(root: Path, tag: str) -> list[str]:
    """Whether a tag records its own basis, per section 6.

    Annotated, never lightweight, and the annotation names who reviewed, what
    was manually tested, and what the automated gate covered. A tag whose
    annotation cannot state the manual test performed is a tag that should not
    exist yet — so this checks the words are there rather than trusting that
    somebody meant them.
    """
    kind = subprocess.run(
        ["git", "cat-file", "-t", tag], cwd=root, text=True, capture_output=True)
    if kind.returncode != 0:
        return [f"there is no tag {tag!r}"]
    if kind.stdout.strip() != "tag":
        return [f"{tag} is lightweight; section 6 requires an annotated tag"]

    message = subprocess.run(
        ["git", "tag", "-n99", "--list", tag],
        cwd=root, text=True, capture_output=True).stdout.lower()

    missing = [need for need, words in (
        ("who reviewed it", ("reviewed",)),
        ("what was manually tested", ("manually tested", "manual test")),
        ("what the automated gate covered", ("automated", "validation")),
    ) if not any(word in message for word in words)]

    return [f"{tag}'s annotation does not say {need}" for need in missing]


@main.command()
@click.pass_context
def signatures(ctx: click.Context) -> None:
    """Verify commit signatures locally, where the key is.

    The CI gate asks the forge about commits it has never seen and reports that
    it could not check them, which is not the same as a bad signature.
    """
    ctx.exit(run(
        SEED + [SIGNATURES, "--base-ref", BASE_REF,
                "--head-ref", "HEAD", "--source", "git"],
        **_opts(ctx),
    ))


@main.command()
@click.option("--port", type=int, help="Bind somewhere other than the default.")
@click.pass_context
def serve(ctx: click.Context, port: int | None) -> None:
    """Run the app.

    Reload is off. It never worked in this environment — uvicorn reports a
    reload it did not perform — and the reloader process it added is what left
    listening sockets with nothing behind them. Restart by hand after changing
    anything under `src/`; templates and static files are a browser refresh.
    """
    env = {"CARLOS_PORT": str(port)} if port else None
    click.secho(
        "reload is off (it never worked here) — restart by hand after any "
        "src/ change",
        fg="yellow",
    )
    ctx.exit(run(
        here(["python", "src/main.py"]),
        canonical=uv(["python", "src/main.py"]),
        env=env, **_opts(ctx),
    ))


@main.command()
@click.option("--port", default=8000, show_default=True)
@click.pass_context
def stop(ctx: click.Context, port: int) -> None:
    """Stop every server holding the port, and prove the port is free.

    A round in its own right because it is not one command and the obvious one
    is wrong. Windows leaves several uvicorn processes bound at once, and
    `/healthz` answers from whichever stale process is still listening, so a
    restarted server looks healthy while serving code from an hour ago. This
    used to be unwinnable rather than merely awkward: with reload on, killing
    the child that answered made the parent spawn another. Reload is off now,
    and this command's own measurement is what turned it off.
    """
    root, dry_run = ctx.obj["root"], ctx.obj["dry_run"]
    if dry_run:
        click.echo(f"curl -s http://127.0.0.1:{port}/healthz   # it names its own pid")
        ctx.exit(0)

    for attempt in range(1, 5):
        serving = _who_is_serving(port)
        if serving is None and not _answers(port):
            break

        if serving is not None:
            click.echo(
                f"attempt {attempt}: instance {serving['instance']} "
                f"is serving as pid {serving['pid']}"
            )
            _kill(str(serving["pid"]))
        else:
            # Something answers and it is not Carlos, so fall back to asking
            # the operating system - and kill only the pids that exist, since
            # the one it names may already be gone.
            holders = {pid for pid in _listeners(port, root) if _exists(pid)}
            click.echo(f"attempt {attempt}: {len(holders)} process(es) on :{port}")
            for pid in holders:
                _kill(pid)
            if not holders:
                break
        time.sleep(1.0)

    # The port answering is the only thing that settles this. A process table
    # that has stopped naming an owner is not the same as a port that has
    # stopped serving, and on Windows the two disagree routinely.
    if _answers(port):
        click.secho(f"something is still serving on :{port}", fg="red")
        orphans = _listeners(port, root)
        if orphans and not any(_exists(pid) for pid in orphans):
            click.echo(
                f"  netstat blames {', '.join(sorted(orphans))}, which no longer "
                "exists - the socket outlived the process that bound it"
            )
        ctx.exit(1)

    click.secho(f":{port} is free", fg="green")


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """What state this checkout is in.

    Reads; changes nothing. Every figure is measured here rather than quoted
    from a document, because a document is only as fresh as its last write.
    """
    root = ctx.obj["root"]
    _line_writer()("Carlos")

    echo = _line_writer()

    def line(label: str, value: str) -> None:
        echo(f"  {label:<22}{value}")

    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    ahead = _git(["rev-list", "--count", f"{BASE_REF}..HEAD"], root)
    dirty = _git(["status", "--porcelain"], root)

    line("branch", branch or "unknown")
    line("unpushed commits", ahead or "unknown")
    if dirty is None:
        line("working tree", "unknown")
    else:
        changed = len(dirty.splitlines())
        line("working tree", "clean" if changed == 0 else f"{changed} changed")
    line("devices", str(len(list((root / "catalogue/devices").glob("*.json")))))
    line("walkthrough pages", str(len(list((root / "walkthrough").glob("*.md")))))
    line("screenshots", str(len(list((root / "walkthrough/media").glob("*.png")))))
    # Asked the same way `stop` asks: does anything answer. Counting rows in a
    # process table reports a server that is not there, because a socket can
    # outlive the process that bound it and `netstat` goes on naming it.
    serving = _who_is_serving(8000)
    if serving:
        line("serving on :8000", f"instance {serving['instance']}, pid {serving['pid']}")
    elif _answers(8000):
        line("serving on :8000", "something, and it is not Carlos")
    else:
        line("serving on :8000", "nothing")
        phantoms = _listeners(8000, root)
        if phantoms:
            line("", f"({len(phantoms)} stale netstat row(s), no process behind them)")

    echo("")
    echo("  next: carlos check, carlos harness, carlos gates")


def _line_writer():
    """Echo that gives up quietly when the reader has gone."""
    def write(text: str) -> None:
        try:
            click.echo(text)
        except OSError:
            os._exit(0)
    return write


def _opts(ctx: click.Context) -> dict:
    return {"dry_run": ctx.obj["dry_run"], "root": ctx.obj["root"]}


def _git(argv: list[str], root: Path) -> str | None:
    """git's answer, or None when it could not be asked.

    None rather than a placeholder string, because for some of these commands
    *no output is the answer*: `status --porcelain` says nothing when the tree
    is clean. Folding that into "?" made `status` report one changed file on a
    clean checkout — the placeholder counted as a line.
    """
    try:
        done = subprocess.run(
            ["git", *argv], cwd=root, capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _answers(port: int) -> bool:
    """Does anything serve HTTP here? The only question that settles it."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/healthz", timeout=2
        ):
            return True
    except urllib.error.HTTPError:
        return True  # it answered, just not with a 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _who_is_serving(port: int) -> dict | None:
    """Ask the server which process it is, per `/healthz`."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/healthz", timeout=2
        ) as answer:
            body = json.load(answer)
    except Exception:
        return None
    if "pid" in body and "instance" in body:
        return body
    return None


def _exists(pid: str) -> bool:
    if os.name != "nt":
        return True
    done = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True
    )
    return pid in done.stdout


def _listeners(port: int, root: Path) -> set[str]:
    """PIDs listening on a port. Empty when the tooling cannot tell us."""
    if not shutil.which("netstat"):
        return set()
    try:
        done = subprocess.run(
            ["netstat", "-ano"], cwd=root, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return set()

    found = set()
    for row in done.stdout.splitlines():
        parts = row.split()
        if len(parts) < 5 or "LISTENING" not in row:
            continue
        if parts[1].endswith(f":{port}"):
            found.add(parts[-1])
    return found


def _kill(pid: str) -> None:
    command = (
        ["taskkill", "/F", "/PID", pid] if os.name == "nt" else ["kill", "-9", pid]
    )
    subprocess.run(command, capture_output=True)


if __name__ == "__main__":
    main()
