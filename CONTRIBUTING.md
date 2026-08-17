# Contributing

Carlos is pre-release. Keep changes small, local, and easy to review.

## Local Setup

The governance corpus is vendored as a submodule at `governance/qm`, and the CI
gates run out of it. A clone without it looks fine until a gate fails.

```bash
git clone --recurse-submodules git@github.com:quaternionmedia/carlos.git
cd carlos
uv sync
```

On a clone you already have:

```bash
git submodule update --init --recursive
```

## Development Loop

```bash
uv run python -m unittest discover   # check
uv run python src/main.py            # run, on http://localhost:8000
```

Use `uv run`. A bare `python -m unittest discover` fails with
`ModuleNotFoundError: No module named 'fastapi'` unless you have activated the
project environment yourself.

Changes under `templates/` and `static/` need only a browser refresh. **Python
changes need you to restart the server**: auto-reload does not work in this
environment. uvicorn logs `StatReload detected changes ... Reloading...` and
then never starts the replacement process, so the log claims a reload that did
not happen and the old code keeps serving. If an edit seems to have no effect,
restart before you debug it.

Run the checks again before opening a pull request, and say in the description
which command you ran.

## Governance Gates

Six seed workflows run in CI, and they run locally too:

```bash
python governance/qm/project-seed/ci/run_workflows_locally.py --base-ref they
```

This executes the workflows' actual steps rather than an approximation of them.
Three failures are expected today, all recorded in [GOVERNANCE.md](GOVERNANCE.md):

- `reuse-lint` — the licensing pass has not been done.
- `submodule-check` — `project/carlos` is not pushed.
- `signature-check` — it asks the forge about commits the forge has never seen.
  Check this one locally instead, where the key is available:

  ```bash
  python governance/qm/project-seed/ci/check_signatures.py \
    --base-ref they --head-ref HEAD --source git
  ```

Anything else failing is yours.

The runner cannot reproduce `uses:` steps, the runner image, or secrets. A local
pass is not a remote pass — say which you ran.

## Conventions

- **No CDN references.** Frontend assets are vendored or local. A test asserts
  this, because the rule is a governance requirement rather than a preference.
- **The patch format is specified before it is implemented.**
  `docs/patch-format.md` is the contract; `src/patch_format.py` and
  `static/models.js` are two implementations of it. Change them together — the
  frontend contract tests exist to catch them drifting apart.
- **Derived state is not stored.** Knob rotation derives from the parameter
  value; a jack's side derives from its module definition. Neither belongs in an
  exported document.

## Pull Requests

- Use a focused branch.
- Describe the user-visible change.
- Include the check command you ran.
- Keep unrelated formatting and refactors out of the same change.
- One open pull request per contributor, per repository — the org-wide slot rule
  in `governance/qm/handbook/async-contract.md`, enforced by `one-pr-check`.

## Governance

Carlos is not fully adopted into the Quaternion Media governance corpus yet.
Until that adoption is complete, [GOVERNANCE.md](GOVERNANCE.md) is the local
source of truth for publish readiness.
