# Contributing

Carlos is pre-release. Keep changes small, local, and easy to review.

## Setting up, and the development loop

**This document does not explain either.** [`walkthrough/01-onboarding.md`](walkthrough/01-onboarding.md)
does, and it is a page you *run* rather than read — if it passes, your checkout
is built, because the assertions in it executed on your machine. Setup
instructions kept in two places are setup instructions that disagree within a
month, and this repository has the org's own measurement of that behind it:
see `governance/qm/records/DRAFT-one-executable-walkthrough.md`.

Start there. Come back here when you have something to change.

## Before you open a pull request

```bash
uv run carlos check      # the suite and the walkthrough
uv run carlos harness    # the four frontend harnesses, under Node
```

`carlos --help` lists every round; `carlos --dry-run <round>` prints the command
it would run, because you should be able to type any of them yourself. The CLI
dispatches and implements nothing — if a round reads wrongly, the fix is in what
it runs rather than in the CLI.

`check` runs the suite **and** the walkthrough, and both paths are named
deliberately: `testpaths` is ignored the moment pytest is handed a path
argument, so a walkthrough wired that way would be collected by nobody and stay
green forever.

Say in the pull request which rounds you ran.

### The walkthrough is documentation, a demo and a test at once

That is not a slogan; it changes what a behaviour change costs you.

- **A page fails when the behaviour it demonstrates changes.** The example a
  reader reads is the example that ran, so there is no separate copy to update
  and no authority question about which one is right.
- **`walkthrough/05-in-the-browser.md` drives the real app in real Chromium**
  and rewrites the screenshots under `walkthrough/media/` every run —
  `carlos shots` runs just that page. If your change alters what the app draws,
  those files turn up as an uncommitted diff in `git status` — **commit them**.
  That is the whole mechanism: drift arrives as a diff nobody can miss rather
  than as staleness nobody sees.
- It needs a browser once per clone: `uv run playwright install chromium`.
- **It does not skip when the browser is missing — it fails.** A skip is not a
  pass, and a demonstration nobody can run is a claim.

## Governance gates

Six seed workflows run in CI — they are governance gates, about records,
signatures and licensing rather than about whether the code works. **The suite
runs beside them**, in `.github/workflows/tests.yml`: until that existed nothing
ran the tests, and a reviewer seeing green checks was reading six gates and
could reasonably have believed the suite had passed.

The gates run locally too:

```bash
uv run carlos gates
```

It passes `--base-ref they`, because this repository's default branch is `they`
and the runner defaults to `main` — which fails two gates for a reason that is
about the flag rather than the code. This executes the workflows' actual steps
rather than an approximation of them.

Three failures are expected today, all recorded in [GOVERNANCE.md](GOVERNANCE.md):

- `reuse-lint` — the licensing pass has not been done.
- `submodule-check` — `project/carlos` is not pushed.
- `signature-check` — it asks the forge about commits the forge has never seen.
  Check this one locally instead, where the key is available:

  ```bash
  uv run carlos signatures
  ```

Anything else failing is yours.

The runner cannot reproduce `uses:` steps, the runner image, or secrets. A local
pass is not a remote pass — say which you ran.

## Conventions

These are rules about changes. The conventions about *code* live in
[AGENTS.md](AGENTS.md), which is one file rather than two so they cannot drift
apart; read that before your first commit whether or not you are an agent.

- **Change the contract and both implementations together.**
  `docs/patch-format.md` is the contract; `src/patch_format.py` and
  `static/models.js` are two implementations of it. The frontend contract tests
  exist to catch them drifting apart, and a failure there is real drift rather
  than a flaky test.
- **Adding a device is a JSON file and no Python.** If your change needs code to
  add a device, the schema is missing something — extend that instead.
  [docs/catalogue.md](docs/catalogue.md) has the six steps.
- **Assert the tree, not the model.** Two of this project's real bugs were a
  device that reported turning without turning, and a facing indicator that read
  `EMPTY` on a rack with two devices in it. Every model-level test agreed with
  the model both times. If you change rendering, assert what is on screen.
- **A guard is not finished until someone has tried to route around it.** Break
  a new check and watch it go red before you keep it. A check that has only ever
  been seen green has not been tested.

## Pull requests

- Use a focused branch.
- Describe the user-visible change.
- Include the check commands you ran.
- Commit any regenerated screenshots.
- Keep unrelated formatting and refactors out of the same change.
- **One open pull request per contributor, per repository** — the org-wide slot
  rule in `governance/qm/handbook/async-contract.md`, enforced by
  `one-pr-check`. It is a sequencing constraint rather than a bandwidth one: a
  green pull request frees its own slot.
- **Do not disable commit signing**, and do not add `--no-verify`.
  `commit.gpgsign` is on and a gate checks it.

## Governance

Carlos is not fully adopted into the Quaternion Media governance corpus yet.
Until that adoption is complete, [GOVERNANCE.md](GOVERNANCE.md) is the local
source of truth for publish readiness, and it carries the conflicts with org
records that are still open.
