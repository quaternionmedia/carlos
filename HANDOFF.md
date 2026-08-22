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

Branch: `they`, the default branch — `adopt/qm-governance` merged and the
work since has landed through pull requests off it. **Every commit is signed**,
all verified by `carlos signatures`. The `governance/qm` submodule branch is
**pushed**; see Gate Status for what that closed.

`RETROSPECTIVE.md` is the account of how this cycle went, and is the more useful
read if you are picking the work up rather than operating it.

The workspace opens on a rig: every device in the catalogue, in three rows,
patched the way it would be on a desk — control into voices, voices into the
desk, desk into the interface. It is fetched from `/api/opening` as an ordinary
`carlos.patch` document, so the first thing anyone sees is a file they can
export, edit and import again.

**There is one menu, and one surface.** The options drawer, the device palette,
the example picker, the row controls, the floating tool palette, the status bar
and the info dock have all been deleted over this cycle. What is left is rad's
ring. Pinned, it rests as a title bar across the navy above the rack, saying
what the rack is and what the app last answered; hold it and the ring blooms;
double-tap and drag moves it, which detaches it into a panel the width of its
own contents.

## Running It Somewhere Else

`DEPLOYING.md` is the answer: a two-stage image built from the same lockfile the
tests ran under, running as a non-root user, with the environment variables that
decide the bind, the database and which proxies are believed.

`.github/workflows/image.yml` builds it on every pull request and proves it
answers — a `Dockerfile` nobody has run is a `Dockerfile` that does not work
yet. **That workflow has not run on this workstation**: the Docker daemon was
not up when it was written, so CI is the first thing to build this image.

## Validated Commands

`uv` resolves on `PATH` under some shells and not others. It is commonly found under
Git Bash but **not** under PowerShell, which needs the absolute path.

```bash
uv sync
uv run playwright install chromium   # once, for the runtime-bound page
uv run carlos check                  # the suite and the pages
uv run carlos dev                  # http://localhost:4186 (not the 0.0.0.0 uvicorn prints)
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
  Each carries two corner handles: the flip on the right, and on the left a grip
  that picks the whole device up. Dragging it carries the device itself — leads
  attached and bending as it goes, a gap its own width open where it would land
  — rather than drawing a stand-in, so the preview cannot disagree with what it
  previews. The arrow keys do the same, because a grip you can only drag is a
  grip a keyboard cannot reach.
- **One menu**, implementing `quaternionmedia/rad`'s interaction contract, with
  rad's own conformance vectors vendored and passing.
- **No second surface.** The floating tool palette is deleted too, and with it
  the status bar and the info dock. A pinned ring rests as a title bar and is
  what all of them were; the guard is on shape rather than name — the page is
  checked for buttons, lists and device ids, so a rename cannot route around
  it.
- **MIDI mapping** — bind a device to a channel, note, controller or transport
  and it lights when that arrives. Works with no hardware via a synthetic
  source.
- **Two display modes**, `minimal` and `irl`. Everything `irl` draws does
  something: a pad sends MIDI down the real path, screens read a declared
  source, and every fader on a desk moves.
- **The opening rack is a file.** `catalogue/opening.json`, served from
  `/api/opening` — every device, three rows, seventeen leads, two of them
  carrying MIDI channels and drawn as the channels they carry.
- **An interop seam** — callable over REST+JSON+OpenAPI, five transforms, and
  outbound calls that are *planned* and never sent. `GET /api/cadence` tells
  another application what each call costs it and how often to ask; every
  endpoint declared a read is called twice by a test that measures the disk.

Docs: `docs/patch-format.md`, `docs/catalogue.md`, `docs/interop.md`,
`docs/rad-integration.md`, `docs/midi-and-display.md`.

## Verification, As Last Run

Everything below was run on this workstation against this commit.

| Check | Result |
| --- | --- |
| `pytest tests` + four hermetic pages | 354 passed, 1450 subtests |
| `pytest tests/browser` | 161 passed |
| `node tests/view_toggle.js` | 92/92 |
| `node tests/rack_behaviour.js` | 98/98 |
| `node tests/cable_tracing.js` | 92/92 |
| `node tests/click_layers.js` | 14/14, 0 collisions |
| `walkthrough/05-in-the-browser.md` | real Chromium, 5 shots, console clean |
| `carlos release-check` | 516 passed, nothing skipped, reran or retried |
| `carlos gates` | 18 of 20 steps pass; the two reds are below |

And, which is the part no workstation can supply, **it has run where people
merge**: run
[32367009542](https://github.com/quaternionmedia/carlos/actions/runs/32367009542)
on `they`, both jobs green. That identifier is what satisfies
`DRAFT-one-executable-walkthrough.md` decision 7 — a page that ran on a branch
no remote carries has not run, and a workflow file that would have run is not a
run.

The fifth frontend harness is gone: `tests/palette.js` tested the floating
panel, and the panel was deleted. Four remain.

**A test that has not been watched fail is a test whose subject is unproven.**
This cycle learned that the expensive way — five tests passed against a screen
with no cables on it, because they asked where a cable was *filed* rather than
whether it could be *seen*. Every check added since has been run against the
code it names, red, before being kept.

## Gate Status

Run them yourself rather than trusting this table: `carlos gates`. What follows
is the state on the forge, not a prediction — run
[32367009542](https://github.com/quaternionmedia/carlos/actions/runs/32367009542)
on `they` and the checks on the pull request before it.

| Gate | State |
| --- | --- |
| `Suite and hermetic pages` | pass |
| `The browser page` | pass — 161 browser tests, on Linux |
| `It builds, and it answers` | pass |
| `adr-lint` | pass |
| `check-submodule-refs` | pass |
| `signatures` | pass |
| `one-pr-check` (`slot`) | pass |
| `reuse` | **fail, deliberately** |

`carlos gates` runs the same workflows locally and reports one more red:
`image.yml :: Start it` wants a running Docker daemon. That is a missing local
runtime rather than a finding — the same job passes on the forge, which is
where it counts.

`reuse` is red because the licensing pass is gated on the outbound licence
class, which is a human decision nobody has made. Settling one to turn a check
green decides the wrong question for the wrong reason. Publishing with this red
is the accepted state, recorded in `GOVERNANCE.md`.

The other two long-standing reds closed on this push, as `GOVERNANCE.md`
predicted: `check-submodule-refs` once `project/carlos` was pushed to
`quaternionmedia/qm`, and `signatures` once the forge could see the commits.

**The first remote run found three things this workstation could not.** They are
in `RETROSPECTIVE.md` §2; the shortest of them is that `contextmenu` fires on
pointer down on Linux and pointer up on Windows, which took thirty-nine browser
tests down.

## Cautions

- **Keep a shutter next to the assertions that earn it.** `shots.take(page,
  'boot')` sat at the end of the section about the bar, two mutations after the
  assertions it illustrated — so the file called `boot` showed `12 devices · 7
  front` and the README showed it as the homepage. The picture was a correct
  picture, the assertions were true, and the caption matched a state the file
  did not hold; nothing was individually wrong and no test can see an order. The
  page now asserts the state on the line above the shutter. Two guards were
  added with it, both watched failing: a page may only show a screen it takes,
  and `carlos check` has to name `walkthrough` or nothing regenerates anything.

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
  Windows left three uvicorn processes bound to `:4186` at once. `/healthz`
  answered from an hour-old one, so a restarted server looked healthy while
  serving code from before the change. `netstat -ano | grep :4186` shows how
  many are really listening; kill by PID with `taskkill //F //PID`.
  **Count the listeners before trusting a response** - and `/healthz` reports
  `instance` and `started_at`, so if the id is not the one you just started you
  are reading somebody else's process. That is the fastest way to catch it.
  The *cause* was `reload=True`, now off by default: it bought a third process
  that respawned whatever you killed, in exchange for a reload it never
  performed. Turning it off did not paper over this - it ended it.

## Next Useful Work

In the order a next session would find them useful. Nothing here is blocked on
code; the first four are decisions, and one of them needs repository admin.

### Decisions, not tasks

1. **The outbound licence class — MIT or AGPL.** One red gate is waiting on it,
   and so is the licensing pass behind it.
2. **Ratify the adoption record**, or don't. `governance/qm/adr/` holds it,
   numberless and Proposed. The branch merges either way; ratification is what
   lets Carlos be described as carrying governance rather than improvising it.
3. **Apply the tag-protection ruleset, or decide not to.** §7 of the
   version-tags record asks for one restricting who may create `v*`, so that
   "a human cuts the tag" is a permission rather than a custom. The payload is
   `.github/tag-ruleset.json` and `RELEASING.md` carries the one-line call; it
   needs admin on the repository, which is why it is a decision here rather
   than a task. `gh api repos/quaternionmedia/carlos/rulesets` returns empty
   today.
4. **Two things the deleted panel took with it.** The key hints are gone
   entirely — the ring is the reference now — and the patch name is only visible
   inside `Patch ▸ Name`, where it used to sit on screen. Either can come back
   in the bar; neither has been missed yet on one workstation, which is not
   evidence.

### Work with a clear shape

5. **Multiple palettes.** rad-android's own record (§12) has several
   independently configured rings, each with its own arrangement and contrast
   choice. The per-ring store and the arrangement mechanism both exist here now,
   which was the prerequisite. What it needs first is an answer to *what a
   second ring points at* — a second rack, a second view of one rack, or a ring
   bound to a device.
6. **The bar's position is not remembered** across a reload, while the hint and
   the ring's arrangement are. The hook (`onBarMoved`) exists and is unwired.
   One line, and an inconsistency until it is.
7. **Device entries are still caricatures of varying depth.** Five were filled
   out this cycle; a Launchpad X declaring one control is honest, a Qu-24
   declaring 27 faders for a 24-channel desk is close enough, and the middle of
   that range is where the next measuring session pays off.
8. **`Assign function…` is deliberately not ported** from rad-android. Its verbs
   are Android intents; this app's are its own actions and are not
   user-composable. If Carlos ever grows composable verbs, this is where they
   would surface.

### Kept honest

9. **The version tag is a human gate, and now has a machine half.**
   `RELEASING.md` is the record applied to this project: what a `v*` tag
   asserts, who may cut one, and the annotation form. `carlos release-check`
   runs the whole suite and **fails on a skip** — a skipped test is an absent
   test that has announced itself, and this suite skips whole classes without
   `node` and the entire browser suite without a browser.

   It asserts one of the three claims and says in its own output that it has
   not made the other two. Carlos has never been tagged; nothing here is a
   release.

## What Was Reported Upstream

`docs/rad-integration.md` records four findings about `quaternionmedia/rad` that
belong to rad rather than here — no consumable core, "RAD consumer" undefined,
vectors carrying no scope metadata, and no `project/rad` branch in the corpus.
Under the audit queue's rule, a defect two consumers could share is fixed at the
source. None has been raised with rad yet.
