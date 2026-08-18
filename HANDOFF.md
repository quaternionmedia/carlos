# Carlos Handoff

Date: 2026-08-17

## Operating Constraint

Keep work local unless the user explicitly asks for a remote write. Nothing in
this repository has been pushed. Do not push, open pull requests, or change
GitHub settings without direct instruction.

## Read Governance From The Submodule

`governance/qm` is the corpus this project is pinned to. Read it there.

There is another clone at `../qm` on this machine. It was **62+ commits behind**
`main` when last checked, and its own `origin/main` ref was stale on top of that.
Reading it produced a picture that was wrong in ways that mattered: 10 records
instead of 18, and a fork procedure naming three seed workflows where six carry
copy-verbatim banners. Do not read governance from it.

**`AGENTS.md` at this repo's root is the current seed plus a project section.**
It carries guidance that supersedes older habits — one open PR per contributor,
merge your own PR once the gates are green, never request a review. Read it
before your first commit.

## Current State

Branch: `adopt/qm-governance`, cut from `they`. **Every commit is signed. Nothing is
pushed.** Work inherited from the previous
session (the README rewrite, the TinyDB cleanup, the community files) is
committed here too rather than left loose.

```text
Correct the docs the drawer deletion left behind, and record the edge context
Make the rack operable: pull a lead out, reach a knob without a mouse
Put the status line back on screen, and the facing indicator with it
Lock the declared dependency
Land the inherited TinyDB cleanup
Document the build, and state what is not done
Declare pydantic, which five modules import directly
Gate the behaviour that model-level tests cannot see
Adopt the rad interaction contract, and delete the other menus
Add the device catalogue, the patch format, and worked examples
Adopt the QM constitution: submodule, gates, and agent discovery
```

Listed newest first, by subject rather than by hash: a document that records
its own commit hash is wrong the moment it is committed, which is a small
instance of the staleness this file exists to prevent. `git log --oneline -6`
gives the hashes.

**The branch name describes only the last of these.** It carries two distinct
bodies of work — the governance adoption, and everything the application gained
since. A publisher may reasonably want them split; they were kept on one branch
because the async contract allows one open pull request per contributor, so two
branches would only be two PRs that cannot both be open.

The submodule is on `project/carlos` at a signed commit (`5bebfa6`), created
from the corpus's real `main`. **That branch is not pushed**, which is why
`submodule-check` fails.

## Validated Commands

`uv` is at `C:\Users\peter\.local\bin\uv.exe`. It resolves as a bare `uv` under
Git Bash but **not** under PowerShell, which needs the absolute path.

```bash
uv sync
uv run python -m unittest discover   # 210 tests
uv run python src/main.py            # http://localhost:8000
```

A bare `python -m unittest discover` fails — `ModuleNotFoundError: No module
named 'fastapi'`. Use `uv run`.

**Auto-reload does not work here, and its log lies.** uvicorn prints
`StatReload detected changes ... Reloading...` and never starts the replacement
process; the original child keeps serving. **Restart manually after any
`src/*.py` change.** `templates/**` and `static/**` are picked up on the next
request — those were checked by fetching the changed bytes, not by reading a log
line.

Gates:

```bash
python governance/qm/project-seed/ci/run_workflows_locally.py --base-ref they
```

Pass `--base-ref they`; the runner defaults to `main` and this repository's
default branch is `they`.

## What This Build Is

A browser workspace for sketching rigs of real gear.

- **A device catalogue** — nine devices across seven categories, each a JSON
  file under `catalogue/devices/`. Adding one is a file and no code. Every
  device ships a simple and a complex worked example.
- **A versioned interchange format**, `carlos.patch` v3, implemented on both
  sides of the seam and validated server-side. Reads v1 and v2 through named
  upgrade steps; refuses v4.
- **n-sided devices** that turn independently and in place, gathered into rows.
- **One menu**, implementing `quaternionmedia/rad`'s interaction contract, with
  rad's own conformance vectors vendored and passing.
- **MIDI mapping** — bind a device to a channel, note, controller or transport
  and it lights when that arrives. Works with no hardware via a synthetic
  source.
- **Two display modes**, `minimal` and `irl`.
- **An interop seam** — callable over REST+JSON+OpenAPI, five transforms, and
  outbound calls that are *planned* and never sent.

Docs: `docs/patch-format.md`, `docs/catalogue.md`, `docs/interop.md`,
`docs/rad-integration.md`, `docs/midi-and-display.md`.

## Verification, As Last Run

| Check | Result |
| --- | --- |
| `uv run python -m unittest discover` | 210 tests, OK |
| `node tests/view_toggle.js` | 48/48 |
| `node tests/rack_behaviour.js` | 87/87 |
| `node tests/cable_tracing.js` | 22/22 |
| `node tests/click_layers.js` | 9/9 |
| rad conformance | 66 passed, 0 failed, 16 skipped |
| Live end-to-end, cold start | all green, 15 OpenAPI paths |

Every new check above was watched go red against the code it names before being
kept: the fan-out assertion against a `disconnect`-based unpatch, the `irl` knob
assertion against the selector that only read `.knob`, and C5/C6 against a
`contextAt` that never consults the probe and a Tab handler that never yields.

The 16 skipped conformance cases are rad features Carlos does not implement —
chorded input, tempo estimation, quantized commit, the speed axes. They sit
outside rad's three governed artifacts. Skipping them is not a gap; **claiming
them would be a false report.**

## Gate Status

`adr-lint` and `one-pr-check` pass. Three fail, all expected:

- **`reuse-lint`** — the licensing pass has not been done. 3 of 95 files carry
  copyright information. This job got bigger as the project grew.
- **`submodule-check`** — `project/carlos` is unpushed.
- **`signature-check`** — asks the forge about commits it has never seen.
  Verify locally instead, where the key exists:
  `python governance/qm/project-seed/ci/check_signatures.py --base-ref they --head-ref HEAD --source git`
  reports `G`, good signature, for every commit.

## Cautions

- **Do not add `--no-verify` or disable signing.** `commit.gpgsign` is true and
  the corpus runs a signature gate. Its own header records that signing
  "silently stopped three days earlier when a session added a flag disabling
  it". I made that mistake once this session and had to re-sign.
- **Suppress `Co-Authored-By` trailers** naming vendor `noreply@` addresses, per
  the human-only contributorship record.
- **A browser JS error never reaches the server log.** "No errors in the log" is
  what you see whether the page works perfectly or throws on every keypress.
- **The model is not the screen.** Two real bugs this session — a device that
  reported turning without turning, and a device rendered twice — were invisible
  to every model-level test and were caught only by `tests/dom.js`. If you change
  rendering, assert the tree.
- **Verify the artifact, not that the step ran.** Reload was recorded as working
  on the evidence of a log line. It does not work.
- **Rule out the harness before reporting a defect.** Twice this session a
  harness measured a different object than the app used, or never invoked the
  handler it was testing, and reported a bug against code it had not executed.

## Next Useful Work

Ordered by what unblocks the most.

1. **Push `project/carlos`** to `quaternionmedia/qm`. This is a remote write and
   needs authorization. It closes `submodule-check` and completes fork steps 2
   and 3.
2. **Draft ADR-0001** — the adoption and scope record, carrying the conflict
   table in `GOVERNANCE.md`. The fork procedure requires it, and each row needs
   the reproduction that established it.
3. **The licensing pass.** Settle the MIT/AGPL class question first
   (outbound-licensing §4 puts services at AGPL-3.0-or-later), then `LICENSES/`,
   SPDX headers, and `reuse-lint` green. 95 files.
4. **Add `walkthrough/`**, which every QM repository owes and this one lacks.
   Note it implies pytest, which is a second open conflict.
5. **Give `/healthz` a real identity** — resolved database path, bound port,
   start time — so a collector can attribute a measurement. The monitoring-seam
   record names the current state as a defect.
6. **Settle the frontend conflict.** `static/` is now five modules with no build
   step; the house-stack set names mithril with parcel. Neither the blessed
   answer nor a recorded exception.
7. **Finish the UI pass this session started.** Left undone, in order:
   - **The radial menu has no ARIA at all.** It handles its own keys, so it is
     operable; it is not announced. Everything else on the page now is, which
     makes the menu the remaining gap rather than one of several.
   - **Undo.** Double-click resets one knob and that is the whole of it. Unpatch
     and Delete are both a single act with no way back.
   - **No browser ran this session.** Every claim above is the served bytes, the
     DOM harness, or the model. A JS error still never reaches the server log,
     so "the page loads" has not been established by anyone looking at it.

## What Was Reported Upstream

`docs/rad-integration.md` records four findings about `quaternionmedia/rad` that
belong to rad rather than here — no consumable core, "RAD consumer" undefined,
vectors carrying no scope metadata, and no `project/rad` branch in the corpus.
Under the audit queue's rule, a defect two consumers could share is fixed at the
source. None has been raised with rad yet.
