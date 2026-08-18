# 04 — Cookbook

> **Runtime: hermetic.** No port, no browser. Reads the app's own registries.

For somebody already set up. `01-onboarding.md` is the other document and they
stay separate on purpose: one page trying to be both serves neither.

## The rounds

One entry point. Every command below runs a command you could type yourself,
and `--dry-run` prints it:

```python
>>> from click.testing import CliRunner
>>> from tools import cli
>>> print(CliRunner().invoke(cli.main, ['--dry-run', 'check']).output.strip())
uv run pytest tests walkthrough --doctest-glob=*.md

```

| Round | What it does |
| --- | --- |
| `carlos check` | The suite **and** the walkthrough. Run this before a pull request |
| `carlos harness` | The five frontend harnesses, under Node. Name one to run just it |
| `carlos browser` | The browser suite, in real Chromium |
| `carlos serve` | Run the app, on a predictable port |
| `carlos stop` | Free the port, and prove it is free |
| `carlos shots` | Regenerate the walkthrough screenshots |
| `carlos gates` | The governance gates, as CI runs them |
| `carlos signatures` | Verify commit signatures locally, where the key is |
| `carlos status` | What state this checkout is in |

That list is not written twice — the page and the CLI are checked against each
other, so a round the CLI grows and this page does not name is a failing test:

```python
>>> sorted(cli.main.commands)
['browser', 'check', 'gates', 'harness', 'serve', 'shots', 'signatures',
 'status', 'stop']

```

**The CLI dispatches and implements nothing.** No verdict is formed in it, no
exit code is prettified, and `carlos gates` exits non-zero today because the
runner does. A command that recomputed any of that would be a second definition
of a rule, and two definitions drift the first time one is fixed.

So these still work, and CI types them directly rather than installing anything:

| Instead of | You can type |
| --- | --- |
| `carlos check` | `uv run pytest tests walkthrough --doctest-glob=*.md` |
| `carlos harness palette` | `node tests/palette.js` |
| one page | `uv run pytest walkthrough/02-the-catalogue.md --doctest-glob=*.md` |

Both paths are named in that first command deliberately. `testpaths` is ignored
the moment pytest is handed a path argument, so a walkthrough wired that way
runs for nobody.

## Two things about running it here

**Reload is off, and that is why stopping works.** It never reloaded here —
uvicorn reports a reload it did not perform — and the reloader process it added
was the whole of the stale-server problem: it owned the socket, so killing the
server that answered left a parent to spawn another. Restart by hand after any
change under `src/`. Templates and static files are a browser refresh.

**Stopping the server is still its own round.** `netstat` attributes the
listening socket to the parent that bound it, and that parent has exited by the
time you look, so it names a process `taskkill` says does not exist. `carlos
stop` asks the server which process it is, via `/healthz`, kills that, and then
verifies by probing the port rather than by counting rows in a process table.

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
/api/cadence
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

## Telling another application how often to ask

```python
>>> from src import cadence
>>> policy = cadence.declaration()
>>> len(policy['endpoints']) == len(cadence.CADENCE)
True

```

Every endpoint declares what calling it costs and how long the answer is good
for. Nothing this build serves writes:

```python
>>> sorted({e['side_effect'] for e in policy['endpoints']})
['none']

```

That is a claim, and `tests/test_cadence.py` is where it is held to — it calls
every endpoint declared `none` twice and measures the disk. The budgets live in
`src/cadence.py` rather than a data file, so two machines cannot disagree about
when a figure stops being quotable.

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
