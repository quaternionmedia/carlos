# AGENTS.md

This project is governed by the Quaternion Media constitution, vendored at
`governance/qm` (a submodule pinned to this project's `project/carlos`
branch of that repo). If you are an AI coding agent opening this repo with
no other briefing, read this file fully before your first commit or edit.

## Before you do anything

**Establish four facts about this session before you write anything**, by
asking the repository rather than inheriting a previous session's belief.
Each says what it needs.

- **A. The commit you are working against**, and the branch. `git log -1` and
  `git status` answer it, and need nothing but the clone.
- **B. Which pull requests you already hold open, and how they stack** — small,
  atomic pull requests, a dependent one stacked on its parent as a draft:
  `python governance/qm/project-seed/ci/check_one_pr.py --repo <owner/name>`.
  It asks the host, so it needs a signed-in `gh`; without one it says
  `gh auth login` and stops, and with no account the answer is none.
- **C. What else is in flight in this clone** — a dirty tree you did not dirty,
  a sibling branch, an unpushed commit. `git status` and `git branch -vv`
  answer it. Other sessions are likely running right now, in other
  repositories, for the same reviewer;
  `governance/qm/handbook/async-contract.md` is the short set of rules for
  working alongside them.
- **D. Which gates exist**, and what each cannot see:
  `python governance/qm/project-seed/ci/run_workflows_locally.py`, which
  needs pyyaml, a signed-in `gh` and an `origin` to run every step.

Those are the invariants. **How** you gather them is yours to choose — read the
repository, run the scripts above, or use an adapter if one exists for your
tooling. `governance/qm/adapters/` holds any that do, each named for the product
it targets and none of them required. This file names no vendor, and neither
should anything you add to it.

**Read the corpus's committed status documents before re-deriving what they
hold.** `governance/qm/status/harness.yaml` and
`governance/qm/status/governance.yaml` each carry their own refresh command and
staleness budget in a `reading:` block inside the file. Check the age before
quoting a figure.

1. Read `governance/qm/PRINCIPLES.md` in full and the opening points of `governance/qm/README.md`. For namespaces and precedence, see `governance/qm/docs/ref/namespaces.md` and `governance/qm/docs/ref/precedence.md`.
2. This project's own decision records live in `governance/qm/adr/` — inside
   the submodule, on this project's own branch, not at this repo's root — as
   `ADR-NNNN` (numbered locally, at ratification) or `DRAFT-*.md` before
   ratification. A human ratifies; you draft.
3. **Everything you produce arrives as a pull request, and the pull request is
   an audit record rather than a request for anyone's attention.** Work on a
   branch and open a PR — in this repo, and in the `governance/qm` submodule
   when you touch this project's records there — then **merge it yourself once
   every gate is green.** Your job is a default branch that is clean and
   working, entered through a pull request so the gates ran and the diff stays
   readable afterwards. That route is a maintainer's. An outsider with this
   project's records to change opens an issue or a pull request here, and a
   maintainer pushes the project's `project/carlos` branch in the corpus on
   their behalf. An outside tester's pull request is merged by its assignee,
   a maintainer. **Never push
   a shared branch directly**: that is the one act that destroys the audit
   record.
   **The default branch is not a claim, so merging into it is not a release.**
   Per `governance/qm/records/DRAFT-version-tags-are-claims.md` §4, the default
   branch, a pull request and a local build are all drafts — they may be
   perfectly good and they assert nothing. **The two human gates are
   ratification, for what a record says, and the version tag, for what this
   project ships.** A `v*` tag asserts a human reviewed the change set, a human
   manually tested it against its real runtime, and deterministic automated
   validation passed. Keeping the default branch clean is what makes cutting
   one cheap.
   **Never request a review**, and add the person who asked for the work as
   **assignee**. Reviewers are named at the tag, by the human cutting it. A
   review request pulls a second person into work that asserts nothing yet, and
   against a branch carrying a live `CODEOWNERS` it fires the moment the PR
   opens — you name no one, and the notification cannot be recalled.
   **Draft means unfinished, or stacked on an open PR, and nothing else.** It
   is not a holding pen for finished work: a green PR left in draft against
   the default branch is a change that never landed.
   **One change per PR; parallel when independent, stacked when dependent.**
   Two changes that could land alone are two PRs, each ready against its base.
   A PR that needs another's work is cut from that branch, targets it as its
   base, and stays a draft until the one beneath it merges, however finished
   it is. When it does, retarget the next PR onto the target *before*
   deleting the merged branch — deleting it first closes every PR based on
   it. Never close a PR in favour of one that contains it
   (`governance/qm/handbook/async-contract.md` §1).
   `.github/workflows/one-pr-check.yml` refuses a ready stacked PR; run
   `governance/qm/project-seed/ci/check_one_pr.py` before you open anything.
   One active stack at a time is the habit to aim for, never a limit.
   **The pull request body speaks as the contributor, to the world.** It is
   posted under a human's account and addresses nobody — a question or a
   handling instruction for the person who asked belongs in the session,
   never in the body (`governance/qm/handbook/async-contract.md` §3;
   `check_pr_voice.py` refuses the second person).
4. **Human-only contributorship applies to every commit you make here** (see
   `governance/qm/records/DRAFT-human-only-contributorship.md`): do not add
   yourself, your model name, or any co-author trailer naming an unmonitored
   address (e.g. a vendor `noreply@` address) to any commit. If your default
   tooling normally appends a `Co-Authored-By:` trailer, suppress it for
   this repo. Tool involvement is disclosed as a `Tools:` note where the
   artifact calls for one, never as a byline.
5. Follow the drafting-session handoff contract in
   `governance/qm/adr/README.md` before writing or amending any record.
6. A QM record may be tightened by this project's own records, never
   relaxed — see `governance/qm/docs/ref/precedence.md`.
7. **Put explanation in one place**, per
   `governance/qm/handbook/style-guide.md`: inline comments carry clarifying
   facts about the code, `README.md` is a shallow onramp to the docs, `docs/`
   is reference, and **every why goes to a retrospective in
   `governance/qm/perspectives/`**. A record's Context and Alternatives are
   the one exception, answering *why this decision* rather than *why it went
   that way*.
8. Banned in any pre-ratification `DRAFT-*.md` record: "previously",
   "originally", "earlier draft", "re-review", "renumber", "retroactive",
   "supersedes the ... (stance|finding)", "corrected". Drafts are rewritten
   in place, not narrated. The ADR lint enforces this over prose only, so
   quoting the list in a code span is fine.
9. **Establish a fact before asserting it, and check a signal before reading
   it.** A claim that something is broken, unsupported or behaves a certain way
   carries the command you ran and what it returned. Before reporting what a
   result means, name one other thing that would produce the same output — a
   tool version, a flag's semantics, stale local state, the working directory,
   a substring matching prose. An unexpected uniform result is a tooling fault
   until shown otherwise, and a check that has only ever been seen green has
   not been tested: break the thing it names and watch it go red.
10. **A claim about what facts *mean* names what else could produce them.**
    This is the sibling of the rule above and catches a different failure: the
    facts are all true and the sentence built from them is wrong. Name the
    ordinary cause before the interesting one — same author, same source, same
    tooling, same period — and state direction and date, because "A resembles
    B" is symmetric and the useful version rarely is. **A correction carries
    the same burden as the claim it replaces**: an overclaim gets caught by a
    reader who knows better, while a deflation reads as rigour, closes the
    topic, and can quietly delete something real. See
    `governance/qm/records/DRAFT-decision-record-discipline.md` §7 and §8.
11. **The scaffolding you measure with is part of the measurement.** Item 9 is
    the tool answering a different question than you asked. This is the tool
    being fine and the setup not — nothing errors, and the result describes your
    own scaffolding rather than the subject. Its shapes: a diff against files a
    redirect never wrote; a working tree read after a merge that exited
    non-zero; file copies written through a text API that converts every line
    ending, so the diff is all encoding; a mutation test whose baseline is
    already failing, so it proves nothing either way. **Prefer the artefact you
    did not create** — read a document's own answer instead of recomputing one —
    and assert the intermediate: non-empty, exit zero, baseline green.
12. **A guard is not finished until someone has tried to route around it.**
    Breaking it and watching it go red proves it fires on the case you thought
    of; it cannot find the case you did not. Ask for a pass whose brief is to
    satisfy the check while doing the thing it forbids. A guard with a hole is
    worse than no guard — it is a green check standing exactly where a reader
    believes something is enforced. See the same record's §9 and §10.

13. **Show it by running it** — `show-it-by-running-it` of the charter, with
    `governance/qm/records/DRAFT-one-executable-walkthrough.md` as the record.
    This project's `walkthrough/` is one ordered set of pages that the ordinary
    test command executes: `walkthrough/NN-<slug>.md`, run by pytest with
    `--doctest-glob=*.md`. The example a reader reads is the example that ran.
    Do not write a second copy of a behaviour beside the code — no prose example
    that is not executed, no screenshot that is not a byproduct of a test
    asserting what the code did. What text cannot hold is emitted by that test
    and **recorded, never compared**: a test that diffs images fails on a font
    and gets switched off. Regeneration rides the command you already run before
    a pull request, so drift shows up as an uncommitted diff rather than as
    staleness nobody sees. A skip is not a pass, and a page that always skips is
    deleted.
14. **The workstation, the agent and the conversation are not the
    organisation** — record
    `governance/qm/records/DRAFT-what-is-not-the-organisation.md`, with
    `governance/qm/handbook/what-is-not-the-organisation.md` as the thing to
    do. A committed file states what is true of this project: not where a
    clone sits on one disk, which editor held it, what the tool driving a
    session did with its shell, or what anybody said. A decision enters as a
    decision, never as reported speech; a commit message describes the change
    and not the conversation behind it. The seed's `leak-check.yml` runs
    `check_leaks.py` on the mechanical part — a home path, a personal folder,
    a scratch path, a shared link; the rest is yours to read for before you
    push.
15. **Work is delivered into a repository, never to a hosted page** — record
    `governance/qm/records/DRAFT-work-is-delivered-into-a-repository.md`. A
    report, a demo, a preview or a handoff is a committed file, and reaches a
    reviewer as a pull request or as a page the reviewer builds and serves
    locally. Nothing goes to a page an assistant's host keeps outside the
    org's repositories, such as a chat product's shareable artifact or canvas:
    it is not versioned with the code, cannot be reviewed as a diff, and goes
    stale unseen. `check_leaks.py` refuses a committed link to one.
16. **A shared allowance is drawn on politely** — record
    `governance/qm/records/DRAFT-a-shared-allowance-is-drawn-on-politely.md`.
    Before many calls to one service, read what remains of its allowance and
    state the count; past a tenth, ask first. Sample for an estimate, keep each
    response as it arrives, send a few at a time, and stop at the first refusal
    that names a limit, saying when it resets. The allowance belongs to every
    caller on the credential.
17. **Check what your branch carries before you open the pull request.**
    `python governance/qm/project-seed/ci/check_pr_base.py --base <base> --head
    <branch>` reports the merge-base, the commit and file counts, the authors,
    and any commit that also lives on another branch; paste its output into the
    description. A branch cut from the wrong parent passes every other check,
    because tests and lint measure the branch and not where it came from. It
    refuses the directions the namespaces forbid, such as a `project/carlos`
    head aimed at the default branch.
18. **Run the CI locally before you call a pull request ready.**
    `python governance/qm/project-seed/ci/run_workflows_locally.py` executes the
    workflows' actual steps; reading a workflow and running the commands you
    think it contains is not the same thing. Report what you ran and what it
    said, including the steps the runner cannot reproduce, and say whether a
    local failure is a defect or a difference in the environment.
19. **Durable text carries as few integers as it can** — record
    `governance/qm/records/DRAFT-few-integers-in-durable-text.md`. A number in
    prose is a claim with an expiry date that the prose does not carry. Prefer
    the relation to the count ("every service", not a total), and where a
    figure is the point, name the command and the commit that produced it.
    Never restate a figure a generated document already holds. A verification
    section is the one place a bare count belongs. An assertion in code that goes
    stale fails, which is the property prose lacks.
20. **This page is read first, so it restates decisions it does not own** —
    record `governance/qm/records/DRAFT-the-read-document-governs.md`. Where a
    passage here summarizes a record, it names the record's path. When the
    summary and the record disagree, the record is what was decided and the
    summary is repaired, never the other way round.
21. **Durable text states what is true now, for a reader who was not there** —
    record `governance/qm/records/DRAFT-durable-text-states-what-is-true.md`. A
    docstring, a page or a record says what the thing is, what it does, what it
    cannot do and what to do with it, in the present tense. It does not tell how
    it came to be: what it replaced, what was found, when or by whom. The
    commit, the pull request and the retrospective hold that. The seed's
    `timeless-check.yml` runs `check_timeless.py` on the lines a pull request
    adds and refuses a phrase set in capitals and a phrase that only narrates.

## The instruction files

`CLAUDE.md` is a regular file holding the one line `@AGENTS.md`: an import
the tool that reads it expands into this page, on every platform, with no
setup. This file is the one every tool reads, and no other instruction file
is carried.
`governance/qm/records/DRAFT-ide-integrated-governance-discovery.md` is the
decision behind the file, and says when a project adds a
`.github/copilot-instructions.md`.

<!-- Project-specific setup commands, test commands, and conventions belong
     below this line. Above it, the governance section of
     governance/qm/project-seed/ide/AGENTS.md stays verbatim apart from the
     project's name. -->

## What Carlos is

A browser workspace for sketching virtual synth patches: a FastAPI service
rendering a Eurorack-style rack, with VCO and VCF modules, knobs, patch
cables, and parameter randomization. Named for Wendy Carlos.

## Requirements

- Python 3.12 or newer (measured here: 3.12.4)
- `uv`

`uv` resolves on `PATH` under some shells and not others on the same
machine — commonly it is found under Git Bash and not under PowerShell. If a
command fails with "uv is not recognized", that is the shell rather than the
project; `uv --version` tells you whether this shell can see it, and
invoking it by absolute path is the workaround.

## Setup

```sh
uv sync
```

The governance corpus is a submodule at `governance/qm`. On a fresh clone,
`git submodule update --init --recursive` before anything else — the CI gates
run out of it, so without it they fail for a reason that has nothing to do with
your change.

## The development loop

**Check, then run, then check again.**

```sh
uv run carlos check      # 1. the suite and the walkthrough
uv run carlos serve      # 2. run it, on :8000
uv run carlos stop       # 3. and stop it, which is its own round here
```

`carlos --help` lists every durable round; `carlos --dry-run <round>` prints the
command it runs, because each is a command you could type yourself. It
dispatches and implements nothing: no verdict is formed in it and no exit code
is prettified, so if a round reads wrongly the fix is in what it runs. The
underlying command for the check is
`uv run pytest tests walkthrough --doctest-glob=*.md`, and CI types that
directly rather than installing anything.

Use `uv run`. A bare `pytest` fails with `ModuleNotFoundError: No module named
'fastapi'` — the system interpreter does not have the project's dependencies.
`uv run python -m unittest discover` still works and still runs the same tests;
it does not run the walkthrough, which is why it is not the command.

**Both paths are named on purpose.** `testpaths` is ignored the moment pytest
receives a path argument, so a walkthrough wired that way is collected by
nobody and stays green forever. `tests/test_walkthrough.py` enforces that this
command appears wherever it is documented.

| Changed | Needed |
| --- | --- |
| `src/*.py` | **restart the server yourself** — auto-reload does not work here |
| `templates/**` | browser refresh — Jinja re-reads per request |
| `static/**` | browser refresh — served from disk per request |

**Reload is off by default**, because it does not reload here and it is the
cause of the phantom listeners. uvicorn prints `StatReload detected changes ...
Reloading...` and goes on serving the old code, while the reloader parent that
owns the socket respawns a child every time you kill the one that answers.
Measured both ways: with reload on, one server leaves two processes and a
listening socket behind after `carlos stop` reports the port free; with it off,
it leaves nothing. `CARLOS_RELOAD=1` restores the old behaviour.

This is worth internalising beyond the symptom: an earlier session recorded
reload as working because it saw that log line. Verifying the artifact — does
the new route answer? — takes one more command and gives the opposite answer.
The template and static rows above were established by fetching the changed
bytes, which is why they survived the same scrutiny.

Confirm it is up:

```sh
curl -s http://127.0.0.1:8000/healthz
```

It answers with `ok`, the app and version, and **which instance answered** —
`instance`, `started_at`, the `port` actually bound, and the resolved
`database` path. That last group is what tells two clones apart, and it is the
fastest way to catch the failure mode this environment produces constantly: a
server from an earlier session still holding the port and answering for the one
you meant. If `instance` is not the one you just started, you are reading
somebody else's process.

**Run from the repository root.** `Settings` resolves `data/db.json`,
`templates/` and `static/` against the working directory, so starting from
`src/` writes a second database at `src/data/`. It is no longer silent:
`/healthz` reports the resolved path, so the way to check which database a
server is actually using is to ask it.

The address is overridable per process — `CARLOS_HOST`, `CARLOS_PORT`,
`CARLOS_DB` — which is how to run two at once without either pretending to be
the other. To choose the port on the command line, or to run without reload:

```sh
uv run python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

## Tests

The suite is `unittest.TestCase` classes run by pytest — the blessed runner,
adopted without rewriting a test. No network, no `httpx`: `fastapi.testclient`
is deliberately unused so the suite has no dependency the project does not
otherwise need.

`walkthrough/` is the other half and it is not optional. Its pages are the
documentation *and* the demo *and* a test: the example a reader reads is the
example that ran, and the screenshots under `walkthrough/media/` are byproducts
of the run that asserted the behaviour they show. They are **recorded, never
compared** — a test that diffs images fails on a font and gets switched off,
taking the assertions beside it with it.

The `FrontendContractTests` are the ones to watch: they assert that
`static/models.js` and `src/patch_format.py` still declare the same format and
version. They are string assertions over the JS source, which is a weaker
mechanism than a shared implementation — treat a failure there as real drift
rather than a flaky test.

## Governance gates

```sh
python governance/qm/project-seed/ci/run_workflows_locally.py --base-ref they
```

Runs the workflows' actual steps. **One** gate fails today for a reason recorded
in `GOVERNANCE.md` — `reuse-lint`, which waits on the outbound licence class.
`submodule-check` and `signature-check` both closed when the branch was pushed.
Locally you will see a second red, `image.yml :: Start it`, whenever no Docker
daemon is running; that is a missing local runtime rather than a finding, and it
passes on the forge. Anything else is yours.

`signature-check` is the one to read carefully. Under the CI path it asks the
forge about commits the forge has never seen and reports `E`, "could not be
checked" — which is not the same as a bad signature. Verify locally, where the
key exists:

```sh
python governance/qm/project-seed/ci/check_signatures.py \
  --base-ref they --head-ref HEAD --source git
```

The runner cannot reproduce `uses:` steps, the runner image, or secrets, so a
local pass is not a remote pass.

Pass `--base-ref they` — this repository's default branch is `they`, not `main`,
and the runner defaults to `main`, which fails two gates for a reason that is
about the flag rather than the code.

## The record speaks in one voice

Every commit, pull request and record here is authored by a human and signed by
one. **The prose in them is that person's, in that person's voice.** An assistant
drafting the text writes as the author, not as a second party narrating over
their shoulder.

Concretely, and this is the shape the mistake takes: no `I` reporting what the
tool did, no `you` addressing the person the artifact is already attributed to.
A pull request that says "you asked me to review first" is a document in which
the author appears to be talking to themselves, because they are the author.

Where the tool's own account genuinely belongs:

- **`governance/qm/perspectives/`** — dated, attributed, non-binding, and
  required to carry a `Tools:` row. First person is the form there.
- **The conversation** that produced the work. Nothing is being hidden by
  keeping it there; it is simply not part of the record.
- **A `Tools:` note** on an artifact that calls for one — provenance, never a
  byline.

This is the same rule as human-only contributorship, one level up from the
trailer. A trailer naming a tool and a paragraph narrated by one put the same
second speaker in a document with one signature. `DRAFT-human-only-contributorship.md`
governs the metadata; this governs the prose, and the corpus record extending it
is not written yet.

What survives a squash merge is the message given at merge time, so that is the
text this applies to most. `tests/test_walkthrough.py` holds new commits to it.

## Conventions

- **The frontend is local-first.** No CDN references — the open-license record
  requires frontend assets be vendored, never CDN-loaded, and
  `tests/test_app.py` asserts `cdnjs.cloudflare.com` is absent from the
  rendered template. Do not reintroduce a CDN tag to save a vendoring step.
- Templates live in `templates/`, partials in `templates/partials/`, browser
  assets in `static/`.
- **The patch format is specified before it is implemented.** `docs/patch-format.md`
  is the contract; `src/patch_format.py` and `static/models.js` are two
  implementations of it. Changing one without the other is the drift the
  `FrontendContractTests` in `tests/test_app.py` exist to catch.
- **Derived state is not stored.** Knob rotation derives from the parameter
  value; a jack's side derives from its module definition. Neither is written
  into an exported document, because a second copy can only ever disagree with
  the first.
- Devices turn individually and in place. There is no rack-level view state —
  what the rack appears to be showing is just what its devices are doing.

## Governance state

Carlos is working toward `v0.0.1` on the phase ladder, not past it. `v0.0.1` is
the rung meaning the constitution has been adopted *and a human has reviewed and
manually tested that it is so*; the mechanical half is in place and the human
half is not, so it is a target rather than an attainment.

The adoption is **incomplete**: the adoption record is drafted but unratified
and carries no number, so there is no ADR-0001 yet. `project/carlos` **is**
pushed to `quaternionmedia/qm`, and this repository pins it. Known conflicts
with org records — packaging, datastore, motion library, outbound licence class,
REUSE compliance — are named in that record and mirrored in `GOVERNANCE.md`.

The declared package version is `0.0.0`, which is a different claim: nothing has
been released and nothing has been tagged. Until the record is ratified, do not
describe Carlos as a governed QM project.
