# 04 — Cookbook

> **Runtime: hermetic.** No port, no browser. Reads the app's own registries.

For somebody already set up. `01-onboarding.md` is the other document and they
stay separate on purpose: one page trying to be both serves neither.

## Commands

| What | Command |
| --- | --- |
| Everything | `uv run pytest tests walkthrough --doctest-glob=*.md` |
| Python tests only | `uv run pytest tests -q` |
| The walkthrough only | `uv run pytest walkthrough --doctest-glob=*.md` |
| One page | `uv run pytest walkthrough/02-the-catalogue.md --doctest-glob=*.md` |
| The frontend harnesses | `node tests/rack_behaviour.js` (and `view_toggle`, `cable_tracing`, `click_layers`, `palette`) |
| Run the app | `uv run python src/main.py` |
| Pick the port | `uv run python -m uvicorn src.main:app --host 127.0.0.1 --port 8000` |
| Governance gates | `python governance/qm/project-seed/ci/run_workflows_locally.py --base-ref they` |
| Signatures, locally | `python governance/qm/project-seed/ci/check_signatures.py --base-ref they --head-ref HEAD --source git` |

Both paths are named in the first command deliberately. `testpaths` is ignored
the moment pytest is handed a path argument, so a walkthrough wired that way
runs for nobody.

## Adding a device

One JSON file under `catalogue/devices/<id>.json` and no Python. The loader
refuses an entry that places something the device does not have, that faces a
side it has not, or whose feature runs off its own panel.

The six steps and the whole panel vocabulary are in
[docs/catalogue.md](../docs/catalogue.md). The Stage 3 and the Launchpad X are
the worked examples.

Every device owes a simple and a complex example:

```python
>>> from src import catalogue
>>> for device_id in sorted(catalogue.load_all()):
...     shipped = catalogue.examples_for(device_id)
...     assert set(shipped) == {'simple', 'complex'}, device_id

```

## The API

```python
>>> from src.main import app
>>> routes = sorted(r.path for r in app.routes if getattr(r, 'path', '').startswith('/api'))
>>> for route in routes:
...     print(route)
/api/catalogue
/api/catalogue/categories
/api/catalogue/devices/{device_id}
/api/catalogue/devices/{device_id}/examples
/api/midi
/api/midi/parse
/api/midi/route
/api/patch/format
/api/patch/validate
/api/peers
/api/peers/{peer_id}/{endpoint_name}/plan
/api/transforms
/api/transforms/{name}

```

## Reshaping a patch for somebody else

Five named transforms. `identity` is the honest default:

```python
>>> from src import interop
>>> sorted(interop.TRANSFORMS)
['identity', 'inventory', 'patchbay', 'summary', 'topology']

```

Outbound calls to peers can be *planned* — showing exactly what would be sent —
and this build never sends them. See [docs/interop.md](../docs/interop.md) for
why it stops there.

## The interchange format

`carlos.patch`, version 3. Reads 1 and 2 through named upgrade steps and
refuses 4:

```python
>>> from src import patch_format
>>> patch_format.FORMAT_NAME
'carlos.patch'
>>> patch_format.FORMAT_VERSION
3
>>> sorted(patch_format.SUPPORTED_VERSIONS)
[1, 2, 3]

```

## What is not automated

Real MIDI hardware. Everything else about MIDI is exercised through a synthetic
source down the same path a real port uses, but a real port needs a real
device. That boundary is stated rather than papered over: an unstated boundary
reads as coverage.
