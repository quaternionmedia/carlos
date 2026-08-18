# The Device Catalogue

A catalogue entry describes one real piece of gear: what it is, what sockets it
has, and which face of the device each one is on.

**Adding a device is one JSON file and no code.** Entries live in
`catalogue/devices/<id>.json`, are validated on load, and become available in
the browser palette, over the API, and to any application on the other side of
the seam without a line of Python or JavaScript changing.

## What is in it today

| Category | Devices |
| --- | --- |
| `mixer` | Allen & Heath Qu-24 |
| `audio-interface` | Focusrite Scarlett 2i2 |
| `sequencer` | Squarp Hapax |
| `keyboard` | Nord Stage 3 |
| `sampler` | Teenage Engineering EP-133 K.O. II |
| `semi-modular` | Moog Subharmonicon, Moog DFAM |
| `eurorack` | Carlos VCO, Carlos VCF (generic, not real products) |

Nine entries is a seed, not a library. The point of the schema is that the
tenth costs a file.

## Addressing

Every device has a stable id of the form `<maker>.<model>`, lower kebab:
`moog.dfam`, `allen-heath.qu24`, `teenage-engineering.ep-133`.

**The id is the address.** It is what a patch document puts in `type`, what the
API routes accept, and what another application uses to mean "this device". It
is treated as permanent once published — renaming one breaks every patch and
every peer that referred to it. The filename must match the id, so the file
system and the addressing scheme cannot disagree.

## The file

```json
{
  "id": "focusrite.scarlett-2i2",
  "maker": "Focusrite",
  "model": "Scarlett 2i2",
  "category": "audio-interface",
  "summary": "A two-in, two-out USB audio interface...",
  "fidelity": "detailed",
  "jacks": [
    {
      "name": "input_1",
      "label": "INPUT 1",
      "type": "input",
      "signal": "audio",
      "side": "front",
      "connector": "XLR/TRS combo",
      "note": "Mic, line or instrument."
    }
  ],
  "parameters": [
    { "name": "gain_1", "label": "GAIN 1", "min": 0, "max": 127, "default": 45 }
  ]
}
```

| Field | Rule |
| --- | --- |
| `id` | `<maker>.<model>`, `[a-z0-9-]+\.[a-z0-9-]+`. Must match the filename. |
| `maker`, `model` | As the manufacturer writes them. |
| `category` | One of the categories below. An unknown one is refused. |
| `summary` | A sentence or two. Say what the device is *for*. |
| `fidelity` | `sketch` or `detailed` — see *Honesty about fidelity*. |
| `jacks` | Sockets. May be empty, though a device with none is odd. |
| `parameters` | Continuous controls worth turning. |
| `layout` | Optional panel arrangement for `irl` display. See below. |

### Jacks

| Field | Rule |
| --- | --- |
| `name` | Stable, unique within the device. Referred to by patch documents. |
| `label` | What is silkscreened next to the socket. Shown in the UI. |
| `type` | `input` or `output`. |
| `signal` | `audio`, `cv`, `gate`, `clock`, `midi`, `usb`, `network`, `digital`, `power`. |
| `side` | `front`, `back`, `top`, `bottom`, `left` or `right`. Defaults to `front`. |
| `connector` | Free text: `3.5mm`, `1/4in`, `XLR`, `DIN-5`, `USB-C`, … |
| `note` | Anything a patcher would want to know. |

**Which side is a judgement, and it is about use rather than geometry.** The
front is what a player reaches for while playing; the back is what a rack
builder wires once and forgets. A semi-modular's patch bay is on the front even
though it is a panel; a Hapax's CV outputs are on the back even though you
patch them, because you patch them when you set the rig up.

**A device has only the sides its jacks are on.** The side list is derived, not
declared, so an entry cannot claim a face with nothing on it. `front` is always
included, because every device has a face you look at and it is where the knobs
are drawn — a Nord Stage 3 wires entirely from the back and still has a front.
The K.O. II has every socket along its top edge, so it is `front` then `top`,
with no back at all; that is what the six sides are for, and it is more honest
than splitting one edge across a front and a back to fit a two-sided model.

### Layout

Optional. Carried only for devices whose panel someone has laid out, and used by
`irl` display mode — see [midi-and-display.md](midi-and-display.md).

```json
"layout": {
  "box":   { "width": 1284, "height": 120, "depth": 334 },
  "face":  "top",
  "controls": { "master_level": { "x": 0.045, "y": 0.17, "side": "top", "size": 1.5 },
                "organ_db1":    { "x": 0.150, "y": 0.30, "side": "top",
                                  "kind": "drawbar", "length": 0.30 } },
  "jacks":    { "out_l": { "x": 0.50, "y": 0.5, "side": "back", "size": 1.1 } },
  "features": [ { "kind": "keybed", "keys": 88, "from_note": "A",
                  "x": 0.565, "y": 0.775, "w": 0.865, "h": 0.44, "side": "top" } ]
}
```

Coordinates are fractions of the panel, origin top-left — fractions rather than
millimetres because the placement is abstract, and what has to be right is the
arrangement rather than the absolute size.

The loader refuses a layout that places a jack or control the device does not
have, that puts a jack on a different side than the entry declares, that faces a
side the device has not, or that places a feature running off the edge of its
panel. **A layout describing a different device is worse than no layout**, which
is why all of them are checked rather than trusted.

**A device without a layout still draws in `irl`**, falling back to the minimal
arrangement.

#### `box` — the device's real size

```json
"box": { "width": 1284, "height": 120, "depth": 334 }
```

Millimetres. One measurement set, six faces derived from it:

| Face | Proportion |
| --- | --- |
| `front`, `back` | width ÷ height |
| `top`, `bottom` | width ÷ depth |
| `left`, `right` | depth ÷ height |

`aspect` is the older single number and still works for an entry with no box.
It only ever described the front, and was applied to every side because nothing
else was there to apply — a device whose top was drawn at its front's proportion
was drawn as a shape it is not. **Prefer the box.**

Two things are drawn from the box rather than to scale, and both are named
constants in `static/models.js` rather than per-device fudges:

- **Width** is `√(mm)`-scaled between 150px and 680px. A Eurorack module beside
  an 88-key stage piano is a twentieth of its width; drawn to scale either the
  piano does not fit on a screen or the module is a sliver.
- **Proportion** is compressed toward square by a fixed exponent. A Stage 3's
  front is 10.7 wide-to-tall; drawn true at a usable width it is fifty pixels
  tall, which cannot hold the keybed and three screens that are the reason to
  draw it. The measured value stays on the element as `--true-aspect`, so what
  was measured is readable off what was drawn.

This is why the mode is called a caricature. The ordering and the obviousness of
the difference survive; the absolute numbers do not, and the entry keeps them.

#### `face` — the side you look at first

```json
"face": "top"
```

`front` for almost everything, because almost everything is a box you face. A
stage piano is not: its controls and its keybed are on its top, and its front is
the thin blank lip below the keys.

This exists because an empty face means one of two things and only the entry can
tell them apart. A Stage 3's front is genuinely blank. A K.O. II's front is its
pads and its screen and **nobody has measured them yet**. Naming the face is one
field; deriving it from whichever side carries the most would silently reface
every device nobody has laid out.

#### `features` — everything that is not a socket and carries no value

This is what makes a device recognisable rather than what makes it playable
here: a Stage 3 with its knobs and its sockets and no keybed is not a Stage 3.

```json
{ "kind": "keybed", "keys": 88, "from_note": "A",
  "x": 0.565, "y": 0.775, "w": 0.865, "h": 0.44, "side": "top" }
```

Placed by centre like everything else, and sized too — a keybed and a screen are
areas, not points.

| `kind` | Also needs | Draws as |
| --- | --- | --- |
| `keybed` | `keys`, `from_note` | naturals with the sharps hung between them |
| `pads` | `rows`, `cols` | a grid of performance pads |
| `buttons` | `rows`, `cols` | a grid of small buttons |
| `screen` | `source` | a lit display, showing what that source reads |
| `wheel` | | a pitch or modulation wheel, seen edge-on |
| `grille` | | a speaker |
| `vent` | | a slot or a fan |
| `logo` | `text` | the maker's mark |
| `label` | `text` | a panel legend or section name |
| `plate` | | a section boundary |

`from_note` matters: an 88 runs from A and one drawn from C has the wrong key
under every hand position. 88 keys from A is 52 naturals and 36 sharps, which is
what `tests/view_toggle.js` asserts.

Decoration is `aria-hidden`: a keybed this app cannot play, a logo, a plate.
Announcing 88 keys ahead of the controls would bury the controls. A grid that
emits is not decoration — it is announced, and so is every cell in it.

#### What a grid sends

A grid of pads or buttons may declare what a press sends, and then every cell
in it is a real button — focusable, pressable by pointer or keyboard.

```json
{ "kind": "pads", "rows": 8, "cols": 8, "emits": "midi-note",
  "channel": 10, "note": 36, "x": 0.465, "y": 0.575, "w": 0.79, "h": 0.72 }
```

| `emits` | Also needs | A press sends |
| --- | --- | --- |
| `midi-note` | `channel`, `note` | a note, through `MidiInput` |
| `midi-cc` | `channel`, `controller` | a controller change |
| `event` | | a named device event, no MIDI |

**Cells are numbered across then down, and what they send climbs with them.**
The first cell sends what the entry declares; each one after it sends the next.
An 8×8 grid is two numbers rather than sixty-four, and a Launchpad X's grid
starting at note 36 on channel 10 is where a drum machine has always listened.

`midi-note` and `midi-cc` go down the same path a real port uses, so a device
bound to that note lights up. That is the difference between a pad that looks
like one and a pad that is one. A grid with no `emits` is still drawn — the
shape of a device is worth drawing — it just answers to nobody.

#### What a screen shows

Every screen names one source, and none of it is stored: a screen showing a
remembered message would disagree with the panel the moment anything moved,
which is the reason knob rotation is derived too.

| `source` | Shows |
| --- | --- |
| `device` | the maker and model — what an idle panel shows |
| `last-event` | the most recent thing that happened on this device |
| `parameter` | the control being moved, and its value |
| `patch` | the name of the rack being worked on |
| `transport` | tempo, for a device that has one |
| `static` | only ever its own `text` |

#### Control `kind` — a fader is not a knob turned sideways

A `controls` entry may say what shape it is: `knob` (the default), `fader`,
`drawbar`, `encoder` or `switch`. A mixer drawn as a field of circles is
recognisable as nothing at all.

**Everything drawn as a control is a control.** There was briefly a `faders`
feature kind, for a bank drawn as the shape of a device rather than as things
to move — a desk has twenty-five and this catalogue described four channels. It
is gone: a desk you cannot move a fader on is a photograph. The Qu-24's
twenty-four channel faders and the DFAM's two eight-step rows are parameters,
and the fidelity question they were dodging is a claim about *sockets*, which
is a different claim.

`fader` and `drawbar` also take `orient` (`vertical` or `horizontal`) and
`length`, the travel as a fraction of the panel. Every kind is driven by the one
painting path every control shares, so all of them turn, scroll and answer to
the keyboard.

### Measuring a device

1. **The box first.** Three numbers off the maker's spec sheet. Everything else
   is placed relative to the face they produce.
2. **Name the face** if the device is not one you look at front-on.
3. **Features before controls.** They are the panel the controls sit on, and
   they are drawn first for the same reason.
4. **Work in fractions off a straight-on photograph.** Centre, then extent.
5. **Run the loader.** It refuses a placement naming something the device has
   not, and a feature running off its own panel.
6. **Assert the tree, not the model.** `tests/view_toggle.js` is where a device
   is checked for having actually drawn what it claims.

The Stage 3 is the worked example: `catalogue/devices/nord.stage-3.json`. The
Qu-24 is the obvious next one — a desk's control surface is its top, and it is
currently described as a front.

### Parameters

`name` is stable and referred to by patch documents; `label` is the panel
legend. `min`/`max` bound the knob, `default` is where it starts, `unit` is
free text for display. `max` must be above `min`.

### Categories

`mixer`, `audio-interface`, `sequencer`, `keyboard`, `sampler`,
`semi-modular`, `eurorack`.

Adding a category means editing `CATEGORIES` in `src/catalogue.py` — one line,
with a sentence saying what belongs in it. Categories are deliberately coarse:
a taxonomy fine enough to be exactly right about every device is too fine to be
useful about any of them.

## Honesty about fidelity

A Qu-24 has 24 mic inputs. The catalogue entry has four, and says so in its
summary and its `fidelity: "sketch"`.

This is the field that keeps the catalogue honest. `detailed` claims the entry
covers the device's real connections; `sketch` says it covers the ones worth
patching in a sketch and no more. Marking something `detailed` that is not is
the one way to make this catalogue actively misleading, so when in doubt use
`sketch` and say what was left out.

A layout carries the same obligation and one more. `irl` draws a caricature —
the arrangement is accurate, the proportions are compressed and the mechanisms
are not claimed. The Stage 3's nine organ drawbars are drawn as drawbars; on the
88 and the 76 they are LED drawbars driven by button pairs. That is in the
entry's summary, because a drawing that is wrong about a device is the same
problem as a socket list that is, and it is harder to notice.

## Examples

Every device ships two worked examples:

- `catalogue/examples/<id>.simple.json` — the smallest thing worth doing with it
- `catalogue/examples/<id>.complex.json` — one that earns the device

Both are ordinary [`carlos.patch`](patch-format.md) documents, so an example is
a file a reader can import and take apart rather than a screenshot of one. They
are loaded in the browser from the menu's Examples ring, and over
`GET /api/catalogue/devices/<id>/examples`.

A device with no examples still loads — that is a gap to fill, not a reason to
hold the device back. But the test suite asserts every shipped device has both,
so adding a device to *this* repository means adding its pair.

An example may use any device in the catalogue, not only its own. The
interesting examples are the ones that show a device in a rig: the Hapax
complex example drives four other machines.

## The API

| Route | Returns |
| --- | --- |
| `GET /api/catalogue` | Everything: categories and full device definitions |
| `GET /api/catalogue/categories` | Categories with device counts |
| `GET /api/catalogue/devices/{id}` | One device |
| `GET /api/catalogue/devices/{id}/examples` | That device's simple and complex examples |

`GET /api/catalogue` is what the browser fetches at startup to build its
palette. **There is no second copy of the device definitions in JavaScript** —
that was the arrangement before this catalogue existed, and keeping two copies
in step was a losing game the frontend contract tests were invented to chase.

## Adding a device

1. Write `catalogue/devices/<maker>.<model>.json`.
2. Write its two examples under `catalogue/examples/`.
3. `uv run python -m unittest discover` — the suite validates every entry,
   every example, and every jack an example refers to.
4. Restart the server and check the palette.

The loader refuses, with the file named and the reason given: unknown category
or signal, a malformed or mismatched id, duplicate jack or parameter names, an
inverted range, an unknown field, or JSON that does not parse.
