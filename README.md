# Carlos

Carlos is a browser workspace for sketching rigs. Drop in devices from a
catalogue of real gear — a Moog DFAM, a Squarp Hapax, an Allen & Heath Qu-24 —
adjust their knobs, and patch cables between them on whichever face the sockets
are actually on. Devices turn individually, so you can work on the back of one
while the rest face forward, and gather into rows. A whole rig exports to and
imports from a single versioned JSON document.

Carlos is named for Wendy Carlos, whose work helped bring electronic music and
synthesizers into wider public view.

## Status

This repository is pre-release. The UI prototype is usable locally, but patch
persistence and full patch management workflows are not complete yet.

## Requirements

- Python 3.12 or newer
- `uv`

Clone with submodules — the governance corpus is vendored at `governance/qm`:

```bash
git clone --recurse-submodules git@github.com:quaternionmedia/carlos.git
```

On an existing clone: `git submodule update --init --recursive`.

## Development Loop

Check first, then run. The server stays up while you work.

**1. Run the checks.**

```bash
uv run pytest tests walkthrough --doctest-glob=*.md
```

That runs the test suite *and* the walkthrough, whose pages are executable —
the examples a reader reads are the examples that ran. Both paths are named
deliberately: `testpaths` is ignored the moment pytest is handed a path
argument, so a walkthrough wired that way is collected by nobody.

`uv run` is required, not a convenience — the checks import FastAPI, and a bare
`pytest` fails with `ModuleNotFoundError: No module named 'fastapi'` unless you
have the project environment activated yourself.

The last page drives the real app in a real browser and records what it saw
into `walkthrough/media/`. It does not skip when the browser is missing; it
fails. On a fresh checkout, `uv run playwright install chromium` once.

**2. Start the server.**

```bash
uv run python src/main.py
```

Open `http://localhost:8000`. It binds `0.0.0.0:8000`.

**3. Edit.** What needs what, measured on Windows on 2026-08-17:

| You changed | What to do |
| --- | --- |
| `src/*.py` | **Restart the server yourself.** Auto-reload does not work here — see below |
| `templates/**` | Refresh the browser — Jinja re-reads the template per request |
| `static/**` | Refresh the browser — files are served from disk each request |

**Auto-reload is broken in this environment, and it fails misleadingly.**
uvicorn logs `StatReload detected changes in 'src\main.py'. Reloading...` and
then never starts the replacement process; the original keeps serving. So the
log says it reloaded, the code did not change, and no further reload is ever
detected. It behaves the same whether started via `src/main.py` or
`python -m uvicorn ... --reload`.

The failure is worth knowing about because the log line is not evidence. If you
change a route and it 404s, restart before debugging the route.

Front-end changes genuinely are a refresh away — that part was verified by
fetching the changed bytes, not by reading a log line.

**4. Re-run the checks before you call it done**, and see the frontend contract
tests in particular — they are what catch `static/models.js` and
`src/patch_format.py` drifting apart.

Regeneration rides that same command, so a screenshot that no longer matches
what the app draws turns up as an uncommitted diff in `git status` rather than
as staleness nobody sees.

To pick the port explicitly:

```bash
uv run python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

## Current Features

- Add devices from the catalogue, grouped by category
- Adjust rendered knob values
- Connect compatible input and output jacks
- **Devices are n-sided, and each has only the sides its sockets are on.** A
  DFAM has a front and a back; a K.O. II has a face and a top edge and no back
  at all. Cables may run between any two sides. Losing track of a lead is part
  of the instrument.
- **Turn devices individually.** `Tab` turns the whole rack, `Shift`+`Tab` goes
  back; click a device to select it and `Tab` turns just that one (`Esc`
  deselects). Each module carries its own turn button, disabled when it has only
  one side. A cable with one end out of sight is still drawn end to end, dashed
  and anchored to the device's outline, so a lead can always be followed to both
  of the devices it joins.
- **Gather devices into rows.** Make a row, move the selected device into it, or
  loosen it again. Deleting a row never deletes devices — a grouping is a way of
  reading a rack, not a container the gear lives in. Rows are the first kind of
  grouping; the format is shaped for more.
- **Unpatch a single lead.** Open the menu on a cable and it offers to pull it
  out; open it on a device and it offers to pull out every lead running to it.
  An output feeding three inputs loses the one you picked, not all three.
- **Every control answers to the keyboard.** Knobs are sliders: `Tab` to one and
  the arrow keys turn it, `Shift` for fine, `PageUp`/`PageDown` for a tenth of
  the range, `Home`/`End` for the ends, double-click to put it back where the
  catalogue had it. Sockets are buttons — `Enter` or `Space` patches. `Esc` lets
  go of both the selection and the focus.
- Knobs also answer to the scroll wheel, and to a finger — they are pointer
  events, so a touchscreen turns them.
- **The patch name and the import live in a floating tool palette**, not a bar
  pinned across the bottom — a rack is the width of the window. It opens at a
  default corner, drags by its grip or moves with the arrow keys, and comes back
  where you left it. `Home` on the grip, or Display → Reset palette, puts it
  back to the default.
- Randomize all module parameters
- Export and import the whole rack as a `carlos.patch` document
- Persist a local TinyDB file for future patch storage work

## Device Catalogue

Carlos ships a catalogue of real devices — an Allen & Heath Qu-24, a Focusrite
Scarlett 2i2, a Squarp Hapax, a Nord Stage 3, a Teenage Engineering K.O. II, a
Moog Subharmonicon and a Moog DFAM — alongside two generic Eurorack modules.
Each carries its real sockets on whichever face they are actually on.

**Adding a device is one JSON file and no code.** Entries live in
`catalogue/devices/<id>.json` and become available in the palette, over the API,
and to any application on the other side of the seam. Every device ships a
simple and a complex worked example, loadable from the menu's Examples ring —
which replaces the rack, and is marked destructive because it does. See
[docs/catalogue.md](docs/catalogue.md).

Devices are addressed by a stable id — `moog.dfam`, `allen-heath.qu24` — which
is the same string in a patch document, in an API route, and to a peer
application.

## Working With Other Applications

Carlos is callable over REST + JSON with an OpenAPI description, and it can
reshape what it sends with named transforms — a cable list, an inventory, a
routing with the sound stripped out. Outbound calls to peer applications are
specified and can be *planned*, showing exactly what would be sent, but this
build does not send them. See [docs/interop.md](docs/interop.md) for the
contract and for why it stops there.

## MIDI and Display Modes

Map MIDI activity onto the rack: bind a device to a channel, a note, a
controller or the transport, and it lights when that arrives. Bindings are rack
state and travel in the patch document; the flash is transient and never
exported. No hardware needed to try it — the menu can inject a test message
down the same path a real port uses.

Two ways to draw the same rack: **minimal** (the abstract box every device
shares) and **irl** (each device at its own panel proportions with controls
where they actually sit — accurate, not photographic). Devices without a
measured panel fall back to minimal rather than being held back.

See [docs/midi-and-display.md](docs/midi-and-display.md).

## Patch Interchange

A rack exports to one versioned JSON document — its modules, which way each is
facing, their parameter values, the cables between them, and how they are
grouped into rows. The format is specified in
[docs/patch-format.md](docs/patch-format.md) and implemented on both sides of
the seam: `static/models.js` writes and reads it in the browser, and
`src/patch_format.py` validates it on the server.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/patch/format` | The format name and the version this build writes |
| `POST /api/patch/validate` | Validate a document; `422` names what is wrong |

Validation stores nothing. Persisting *named* patches is a separate decision,
blocked on the datastore question in [GOVERNANCE.md](GOVERNANCE.md).

## Planned Work

- Save and load named patches
- Delete patches
- Panel layouts for the devices that still fall back to minimal
- Add more module definitions
- Preserve device positions within a row (a version 4 change)
- More grouping kinds: cases, channel strips, stage positions
- Settle the motion library. `static/anime-shim.js` is a 25-line local stand-in
  covering the three properties this app animates, not the vendored `anime.js`
  the QM house-stack record names. Either vendor the real library or record the
  shim as a decision — see [GOVERNANCE.md](GOVERNANCE.md).

## Governance

Carlos is intended to adopt the Quaternion Media governance corpus. The local
status and adoption checklist live in [GOVERNANCE.md](GOVERNANCE.md).

## License

MIT. See [LICENSE](LICENSE).
