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
Put every durable round behind one entry point
Add the pre-publication review packet
Blind review: six findings, and CI that runs the tests
Say how to tell two servers apart, now that they can be
Wire up healthz, and say which instance answered
Record the cadence work in the handoff
Declare what asking this seam costs, and how often to ask
Record the stability pass in the handoff
Chase stability: stop leaking servers, stop sleeping, stop drifting
Stop the onboarding docs disagreeing with each other
Make every drawn thing a thing that does something
Bring the handoff up to date with the walkthrough and the catalogue
Record the keybed and the desk, and let a named face win
Make the walkthrough, the demo and the tests one object
Add a modular drum rig, and finish the catalogue to the same standard
Bring the handoff up to date with the tool palette
Float the bottom bar as a tool palette with a default starting position
Record the panel work, and the stale-server trap
Lay out the Nord Stage 3, and say how to lay out the next one
Draw devices as caricatures, and stop a hidden pair collapsing into one line
Give the catalogue a box, panel features, and control kinds
Correct the test counts the UI pass moved
Bring the handoff up to date with the UI pass
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
uv run playwright install chromium   # once, for the runtime-bound page
uv run carlos check                  # the suite and the pages
uv run carlos serve                  # http://localhost:8000 (not the 0.0.0.0 uvicorn prints)
uv run carlos stop                   # which is its own round here
```

`carlos --help` lists every durable round; `--dry-run` prints what each runs.

**Both paths are named on purpose.** `testpaths` is ignored the moment pytest
receives a path argument, so a walkthrough wired that way runs for nobody.
`uv run python -m unittest discover` still works and still runs the same tests;
it does not run the walkthrough, which is why it is not the command.

A bare `python -m unittest discover` fails — `ModuleNotFoundError: No module
named 'fastapi'`. Use `uv run`.

**Reload is off, and it is the answer to the stale-server problem.** It does
not reload here — uvicorn prints `StatReload detected changes ... Reloading...`
and goes on serving the old code, measured by editing a value and watching
`/healthz` keep the old one. What it did deliver was a reloader parent that owns
the socket: kill the child that answers and the parent spawns another, kill the
parent and the socket is left listening with nothing behind it. Measured both
ways, one server, one `carlos stop`:

| | processes started | left after stop | orphaned listeners |
|---|---|---|---|
| reload on | 3 | 2 | 1 |
| reload off | 2 | 0 | 0 |

Every stale-server hunt in this repo's history is the right-hand column of the
first row. **Restart manually after any `src/*.py` change.** `templates/**` and
`static/**` are picked up on the next request — those were checked by fetching
the changed bytes, not by reading a log line. `CARLOS_RELOAD=1` puts it back.

Gates:

```bash
python governance/qm/project-seed/ci/run_workflows_locally.py --base-ref they
```

Pass `--base-ref they`; the runner defaults to `main` and this repository's
default branch is `they`.

## What This Build Is

A browser workspace for sketching rigs of real gear.

- **A device catalogue** — eleven devices across nine categories, each a JSON
  file under `catalogue/devices/`. Adding one is a file and no code. Every
  device ships a simple and a complex worked example, carries its real
  dimensions in millimetres, and names the face it opens on.
- **A versioned interchange format**, `carlos.patch` v3, implemented on both
  sides of the seam and validated server-side. Reads v1 and v2 through named
  upgrade steps; refuses v4.
- **n-sided devices** that turn independently and in place, gathered into rows.
- **One menu**, implementing `quaternionmedia/rad`'s interaction contract, with
  rad's own conformance vectors vendored and passing.
- **A floating tool palette** for what a ring cannot express - the patch name and
  the file input. Not the device palette that was deleted; the guard on that is
  now on shape rather than name, and was tested by routing a renamed device tray
  around the old one.
- **MIDI mapping** — bind a device to a channel, note, controller or transport
  and it lights when that arrives. Works with no hardware via a synthetic
  source.
- **Two display modes**, `minimal` and `irl`. Everything `irl` draws does
  something: a pad sends MIDI down the real path, screens read a declared
  source, and every fader on a desk moves.
- **An interop seam** — callable over REST+JSON+OpenAPI, five transforms, and
  outbound calls that are *planned* and never sent. `GET /api/cadence` tells
  another application what each call costs it and how often to ask; every
  endpoint declared a read is called twice by a test that measures the disk.

Docs: `docs/patch-format.md`, `docs/catalogue.md`, `docs/interop.md`,
`docs/rad-integration.md`, `docs/midi-and-display.md`.

## Verification, As Last Run

| Check | Result |
| --- | --- |
| `uv run carlos check` | 289 passed |
| `node tests/view_toggle.js` | 83/83 |
| `node tests/rack_behaviour.js` | 95/95 |
| `node tests/cable_tracing.js` | 52/52 |
| `node tests/click_layers.js` | 10/10 |
| rad conformance | 66 passed, 0 failed, 16 skipped |
| Live end-to-end, cold start | all green, 15 OpenAPI paths |
| `walkthrough/05-in-the-browser.md` | real Chromium, 5 shots, console clean |

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

- **`reuse-lint`** — the licensing pass has not been done. three files carry
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
- **Measure the flake, do not reason about it.** Three of this session's
  stability fixes were found by running the same thing repeatedly and hashing
  the output: a screenshot that was bistable between two renders of an
  identical DOM, a failing page that leaked its server, and six sleeps standing
  in for waits. None was visible from reading the code, and the screenshot one
  would have quietly destroyed the uncommitted-diff signal the walkthrough
  depends on.
- **The model agreeing with itself is not evidence.** `#view-indicator` read
  `EMPTY` on a rack with two devices in it for two sessions. Every model-level
  test agreed, because the model was right and nothing wrote it to the screen.
  The first run of the browser page found it in seconds. Anything that only the
  screen can be wrong about needs `walkthrough/05-in-the-browser.md`.
- **Rule out the harness before reporting a defect.** Twice this session a
  harness measured a different object than the app used, or never invoked the
  handler it was testing, and reported a bug against code it had not executed.
  Three more turned up since, all the same shape: a stub that swallows what it
  is given. `click_layers` had a no-op `setAttribute` and no `getAttribute`;
  its selector matcher could not read `[tabindex]`, so it reported the app
  broken for a guard it could not see; `dom.js` stubbed `style` as two no-ops,
  so a custom property could not be read back. **A stub that forgets does not
  model a thin DOM, it models a lying one.**
- **`pkill -f` does not stop the server here, and the port does not tell you.**
  Windows left three uvicorn processes bound to `:8000` at once. `/healthz`
  answered from an hour-old one, so a restarted server looked healthy while
  serving code from before the change. `netstat -ano | grep :8000` shows how
  many are really listening; kill by PID with `taskkill //F //PID`.
  **Count the listeners before trusting a response** - and `/healthz` reports
  `instance` and `started_at`, so if the id is not the one you just started you
  are reading somebody else's process. That is the fastest way to catch it.
  The *cause* was `reload=True`, now off by default: it bought a third process
  that respawned whatever you killed, in exchange for a reload it never
  performed. Turning it off did not paper over this - it ended it.

## Next Useful Work

Ordered by what unblocks the most.

1. **Push `project/carlos`** to `quaternionmedia/qm`. This is a remote write and
   needs authorization. It closes `submodule-check` and completes fork steps 2
   and 3.
2. **Ratify the adoption record.** It is drafted, at
   `governance/qm/adr/DRAFT-adopt-the-qm-constitution.md` — numberless and
   Proposed, because a number is assigned by the index at ratification and a
   human ratifies. It carries the component audit, the seam protocol, the
   service inventory, the risk register and twelve named conflicts. Ratifying
   is a human commit: flip the status, assign the number, update the index.
3. **The licensing pass.** Settle the MIT/AGPL class question first
   (outbound-licensing §4 puts services at AGPL-3.0-or-later), then `LICENSES/`,
   SPDX headers, and `reuse-lint` green. `python -m reuse lint` counts what is left.
4. **The frontend build-step conflict.** `static/` is plain modular
   JavaScript with no build step; the house-stack set names mithril with
   parcel. Neither the blessed answer nor a recorded exception, and the
   adoption record names it.
5. **Instance discovery.** `/healthz` now names the instance, its start time,
   the port actually bound and the resolved database path, so a measurement can
   be attributed — the identity half is done. What is not done is *discovery*:
   a collector has to be told where to look, because the record's mechanism
   (bind port 0, write a run-file) is declined in `GOVERNANCE.md` for costing
   the predictable address. If the family's harness ever needs to enumerate
   Carlos instances, that is the conversation.
6. **Settle the frontend conflict.** `static/` is now five modules with no build
   step; the house-stack set names mithril with parcel. Neither the blessed
   answer nor a recorded exception.
7. **Get a human eye on the five screenshots.** They are asserted for counts,
   geometry and behaviour and nothing else. Nobody has judged whether the
   shapes read as the devices they stand for.
8. **Finish the UI pass this session started.** Left undone, in order:
   - ~~The radial menu has no ARIA.~~ Done: the ring is a `menu`, each wedge a
     `menuitem` that names itself and says which of how many it is, and the
     highlighted one carries `aria-current`. The labels are hidden from a
     reader because the wedge already carries them.
   - **Undo.** Double-click resets one knob and that is the whole of it. Unpatch
     and Delete are both a single act with no way back.
   - **A browser runs now, and nobody has looked at what it drew.**
     `walkthrough/05-in-the-browser.md` drives real Chromium and records five
     screenshots under `walkthrough/media/`. Every *countable* claim is
     asserted there — 88 keys as 52 naturals and 36 sharps, 21 bank faders, a
     square Launchpad panel, an empty console. What no assertion can settle is
     whether those shapes read as the devices they stand for. **The screenshots
     are waiting for a human eye**, and the list of what to judge is in the
     session notes rather than here.

## What Was Reported Upstream

`docs/rad-integration.md` records four findings about `quaternionmedia/rad` that
belong to rad rather than here — no consumable core, "RAD consumer" undefined,
vectors carrying no scope metadata, and no `project/rad` branch in the corpus.
Under the audit queue's rule, a defect two consumers could share is fixed at the
source. None has been raised with rad yet.
