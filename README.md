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
uv run carlos check
```

Every durable round in this repository is a `carlos` command, and each one runs
a command you could type yourself — `carlos --dry-run check` prints exactly
that, and `carlos --help` lists them all.

| Round | What it does |
| --- | --- |
| `carlos check` | The suite **and** the walkthrough. What to run before a pull request |
| `carlos harness` | The five frontend harnesses, under Node |
| `carlos serve` | Run the app |
| `carlos stop` | Free the port, and prove it is free |
| `carlos shots` | Regenerate the walkthrough screenshots |
| `carlos gates` | The governance gates, as CI runs them |
| `carlos signatures` | Verify commit signatures locally |
| `carlos status` | What state this checkout is in |

`check` runs the tests *and* the walkthrough, whose pages are executable — the
examples a reader reads are the examples that ran. Both paths are named
deliberately: `testpaths` is ignored the moment pytest is handed a path
argument, so a walkthrough wired that way is collected by nobody.

The last page drives the real app in a real browser and records what it saw
into `walkthrough/media/`. It does not skip when the browser is missing; it
fails. On a fresh checkout, `uv run playwright install chromium` once.

**2. Start the server.**

```bash
uv run carlos serve
```

Open `http://localhost:8000`. It lands on a splash that says what this is, with
one link into the workspace at `/rack` — opening a rack is a thing you choose,
and a tool that drops you into an editable document has decided for you what
you came for.

The address is predictable on purpose — this is a
thing you open in a browser — and `CARLOS_HOST`, `CARLOS_PORT` and `CARLOS_DB`
move a process without editing anything committed.

`/healthz` says which instance answered: its id, the process serving, the port
actually bound and the resolved database path. That is the fastest way to catch
this environment's favourite failure, a server from an earlier session still
holding the port.

Stopping it is its own round, because the obvious way does not work here:

```bash
uv run carlos stop
```

**3. Edit.** What needs what, measured on Windows on 2026-08-17:

| You changed | What to do |
| --- | --- |
| `src/*.py` | **Restart the server yourself.** Auto-reload does not work here — see below |
| `templates/**` | Refresh the browser — Jinja re-reads the template per request |
| `static/**` | Refresh the browser — files are served from disk each request |

**Auto-reload is off, because it does not work here and is not free.**
uvicorn logs `StatReload detected changes in 'src\main.py'. Reloading...` and
goes on serving the old code — measured by editing a value and watching
`/healthz` keep the old one.

What it *did* deliver was a second process that owns the socket and hands it to
a child. Kill the server that answers and the parent spawns a replacement; kill
the parent and the socket is left listening with nothing behind it. That is
this environment's phantom-listener trap in full, bought for a feature that
logs a lie. With reload off, one `carlos stop` leaves no processes and no
orphaned port.

`CARLOS_RELOAD=1` turns it back on if you want to watch it not work.

Front-end changes genuinely are a refresh away — that part was verified by
fetching the changed bytes, not by reading a log line.

**4. Re-run the checks before you call it done**, and see the frontend contract
tests in particular — they are what catch `static/models.js` and
`src/patch_format.py` drifting apart.

Regeneration rides that same command, so a screenshot that no longer matches
what the app draws turns up as an uncommitted diff in `git status` rather than
as staleness nobody sees.

To pick the port:

```bash
uv run carlos serve --port 8123
```

## Current Features

- Add devices from the catalogue, grouped by category
- Adjust rendered knob values
- Connect compatible input and output jacks
- **Devices are n-sided, and each has only the sides its sockets are on.** A
  DFAM has a front and a back; a K.O. II has a face and a top edge and no back
  at all. Cables may run between any two sides. Losing track of a lead is part
  of the instrument.
- **It opens on a rig, not a demonstration.** Every device in the catalogue, in
  three rows — control into voices, voices into the desk, desk into the
  interface — with seventeen leads and two of them carrying channels. It is
  fetched from `/api/opening`, not built in the browser: `catalogue/opening.json`
  is an ordinary patch document, so the first thing you see is a file you can
  export, edit and import again.

- **One menu, in two states.** No floating panel and no status bar — both were
  second surfaces, saying things *about* the rack while the ring said things
  *to* it. A pinned ring is what they were: at rest it is a strip across the
  navy above the rack, saying two things with a rule between them — what the
  rack **is**, and what the app last **answered**. Hold it and the ring blooms; double-tap and drag moves it; `View ▸ Unpin
  ring` puts it away. It rests rather than staying open because a ring left over
  the rack is a ring in the way of the rack.

- **The ring is yours to arrange.** `Edit ▸` moves families round the ring,
  hides the ones you never use, and puts it all back. It remembers on this
  browser; a ring nobody has edited resolves exactly as it ships.
- **One ring of six.** Right-click the rack and every wedge opens something:
  Add, Rows, View, Patch, MIDI, All Devices. The ring used to mix families with
  actions, and which was which you learned by trying.
- **Four things you can point at.** Right-click a device, a cable, a row, or the
  rack itself, and each gives you its own ring. A row can be turned, emptied or
  deleted — and deleting one never deletes gear, because a grouping is a way of
  looking at a rack rather than a container the gear lives inside.
- **Cables route behind the gear when they run behind it.** Two cable layers,
  one over the devices and one under: a lead across a front panel runs over the
  rack, and one going round the back is drawn under it, dashed. A lead with one
  end each way is cut in half — solid and in front where it leaves the socket
  you can see, dashed and underneath where it arrives behind the other device.
  Read off the geometry every redraw, so turning a device moves its lead.
- **A lead carrying channels is drawn as the channels.** One USB cable, four
  strands, one per channel bound to the device at the far end. The split is
  derived from the MIDI bindings rather than stored on the cable, so rebinding a
  group redraws it and nothing has to be kept in step. Audio leads stay one
  line: audio has no channel 10.
- **USB is a bus, not a direction.** Two USB ports may be linked even though the
  catalogue types both `output`, because host and device is a role the two ends
  negotiate rather than a property of either socket. The cable says `through a
  host`, because on a real desk a computer or a host adapter sits between them.
- **Devices open on the face you look at.** A rack-mount opens on its front, a
  stage piano or a grid controller on its top, and a side with nothing on it —
  the blank lip under a Launchpad's pads — is not drawn and not turned to. What
  the entry names as the face is where the controls go, in both display modes.
- **Turn devices individually.** `t` turns the whole rack, `Shift`+`T` goes
  back; click a device to select it and `t` turns just that one (`Esc`
  deselects). Turning is on a letter rather than on `Tab` because `Tab` is how
  a keyboard reaches the controls, and a gesture that costs the keyboard the
  whole interface is not worth the key it is on. Each module carries its own turn button, disabled when it has only
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
- **Everything drawn does something.** A pad on a drawn Launchpad X sends a
  note down the same path a real MIDI port uses, so a device bound to it lights
  up. Screens show what their catalogue entry says they read — the last event,
  the control being moved, the patch name, the tempo — and never a message
  baked into the markup. Every fader on a desk moves.
- **Every control answers to the keyboard.** Knobs are sliders: `Tab` to one and
  the arrow keys turn it, `Shift` for fine, `PageUp`/`PageDown` for a tenth of
  the range, `Home`/`End` for the ends, double-click to put it back where the
  catalogue had it. Sockets are buttons — `Enter` or `Space` patches. `Esc` lets
  go of both the selection and the focus. Seventeen controls are reachable this
  way, and a browser test counts them rather than trusting the markup.
- Knobs also answer to the scroll wheel, and to a finger — they are pointer
  events, so a touchscreen turns them.
- **The patch name and the import are ring verbs** — `Patch ▸ Name`,
  `Patch ▸ Import`. A ring has no text entry, so naming uses the prompt the
  browser already has rather than growing a dialog inside the menu.
- Randomize all module parameters
- Export and import the whole rack as a `carlos.patch` document
- Persist a local TinyDB file for future patch storage work

## Device Catalogue

Carlos ships a catalogue of real devices — an Allen & Heath Qu-24, a Focusrite
Scarlett 2i2, a Squarp Hapax, a Nord Stage 3, a Teenage Engineering K.O. II, a
Novation Launchpad X, a Moog Subharmonicon and a Moog DFAM — alongside three
generic Eurorack modules, including a drum voice for the Launchpad to play.

Each carries its real outside dimensions, its sockets on whichever face they
are actually on, and the face you look at first: a stage piano and a mixing
desk are played from their tops, and their fronts are the thin lips below.

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
- Add more module definitions — every entry in the catalogue is laid out today,
  so a new one is the only way to exercise the `irl` fallback
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
