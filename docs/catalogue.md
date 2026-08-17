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
  "aspect": 3.2,
  "controls": { "gain_1": { "x": 0.22, "y": 0.36, "side": "front", "size": 1.3 } },
  "jacks":    { "input_1": { "x": 0.10, "y": 0.74, "side": "front", "size": 1.4 } }
}
```

`aspect` is width over height and is most of what makes a rack recognisable at a
glance: a Eurorack module is 0.38, a Scarlett 3.2, a DFAM 2.3. Coordinates are
fractions of the panel, origin top-left — fractions rather than millimetres
because the drawing is abstract, and what has to be right is the arrangement
rather than the absolute size.

The loader refuses a layout that places a jack or control the device does not
have, or that puts a jack on a different side than the entry declares. **A
layout describing a different device is worse than no layout**, which is why
both are checked rather than trusted.

**A device without a layout still draws in `irl`**, falling back to the minimal
arrangement. Six of the nine carry one today; the Hapax, Stage 3 and K.O. II do
not, which is what keeps that fallback exercised.

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

## Examples

Every device ships two worked examples:

- `catalogue/examples/<id>.simple.json` — the smallest thing worth doing with it
- `catalogue/examples/<id>.complex.json` — one that earns the device

Both are ordinary [`carlos.patch`](patch-format.md) documents, so an example is
a file a reader can import and take apart rather than a screenshot of one. They
are loaded in the browser from the Examples row of the options drawer, and over
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
