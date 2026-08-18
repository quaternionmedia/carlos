# MIDI Mapping and Display Modes

Two things that arrived together because they answer the same question from
opposite ends: *which thing on screen is which thing in the room?*

## MIDI: activity, mapped to a device

Carlos makes no sound. A MIDI message here is not a note to play — it is
evidence that something in the rig did something, and the only question worth
answering is **which device on screen was it**.

### The seam is MIDI itself

MIDI has more independent implementations than anyone can count, which is what
the QM seams record asks of anything reaching a third party: a from-scratch
implementation of the protocol alone is enough to drive this rack, and nothing
about Carlos needs to be known on the other side.

`src/midi.py` and `static/midi.js` are two implementations of the same three
things — parse, match, route — and a cross-implementation test asserts they
agree on the same bytes. A mapping that behaved differently depending on
whether the message came from a local port or over HTTP would not be a mapping.

### Bytes, not a description of bytes

Real MIDI arrives as status and data bytes, so that is what `parse` takes. A
build that only accepts a friendly JSON shape has anticipated a *description* of
a signal, not a signal.

The three cases that make this worth having a parser at all:

| Case | Why it matters |
| --- | --- |
| **Note-on with velocity 0 is a note-off** | Devices really send this. Reading it as a note-on leaves the device lit with nothing playing. |
| **Pitch bend is 14-bit, LSB first** | `[0xE0, 0x00, 0x40]` is centre — 8192, not 64. |
| **Channels are 0-based on the wire** | Channel 10 arrives as `0x?9`. Humans count from 1, so the parsed message does too. |

### Bindings

A binding says which messages belong to which device.

```json
{
  "id": "kick",
  "source": { "type": "note", "channel": 10, "note": 36 },
  "module": "dfam",
  "label": "note 36 ch 10"
}
```

| Source type | Selects |
| --- | --- |
| `channel` | Everything on one channel |
| `note` | One note, or all notes |
| `cc` | One controller, or all |
| `program` | Program changes |
| `pitchbend` | Bend |
| `transport` | Clock, start, stop, continue |

**A field left out is a wildcard.** `{type: note, note: 36}` is "kick, on any
channel". That is deliberate rather than lazy: a rig where one machine moves to
another channel should not need its bindings rewritten.

**All matching bindings fire.** One message genuinely can concern two devices —
a clock lights everything following it — and picking a single winner would hide
that. Two bindings fighting over one parameter is a mapping to fix, not a tie
for the router to break silently.

Bindings are **rack state** and live in the patch document. The activity they
produce is transient and is never exported: the mapping is the state, the flash
is not, and a test asserts the flash cannot reach `exportState`.

### Binding a device

Right-click a device → **MIDI → Bind next message**. The next message that
arrives binds to it, and what gets bound is the *shape* of the message rather
than the message: a C1 on channel 10 becomes "note 36 on channel 10", so the
same pad matches next time and a different pad does not.

**No hardware needed to see it work.** The canvas menu's **MIDI → Send test
note** injects a synthetic message down the same path a real port uses. A
feature only visible with a keyboard plugged in is a feature nobody reviews.

**MIDI → Status** reports ports, bindings, messages received and messages
matched. Counted rather than inferred, because a rack with no bindings and a
rack with no cable both show nothing on screen, and only one of them is a
problem.

### What Carlos will not touch

RAD drives its speed axes from **CC 20–23** (bpm, aps, div, quantize). A binding
here may watch them; Carlos does not give them a second meaning. The seams
record permits extending a shared vocabulary and forbids repurposing it, and
`GET /api/midi` reports the reserved set so a peer can see the same rule.

### The API

| Route | Purpose |
| --- | --- |
| `GET /api/midi` | What this build understands, and what is reserved |
| `POST /api/midi/parse` | Raw bytes → a message |
| `POST /api/midi/route` | Bindings + a message → which devices light |

Both are stateless: the caller supplies the bindings, so the endpoint answers
for the caller's rack rather than one this process happens to hold. The parse is
exposed because it is the fiddly half, and a peer should not reimplement
note-on-velocity-zero to talk to this rack.

```sh
curl -s -X POST http://127.0.0.1:8000/api/midi/route \
  -H 'Content-Type: application/json' \
  -d '{"bindings":[{"id":"kick","module":"dfam",
       "source":{"type":"note","channel":10,"note":36}}],
       "bytes":[153,36,100]}'
```

## Display modes

Two ways to draw the same rack, switched from **Display** in the canvas menu and
carried in the patch document.

| Mode | What it draws |
| --- | --- |
| `minimal` | The abstract box every device shares: title, knobs, jacks in labelled columns |
| `irl` | Each device at its own panel proportions, with controls and sockets where they actually sit |

**`irl` is accurate, not photographic.** Rings and circles, arranged correctly —
the aim is that a rack is recognisable at a glance rather than a row of
identical boxes. Getting the *aspect* right is most of that: a Eurorack module
is tall and narrow (0.38), a Scarlett is wide and shallow (3.2), a DFAM is 2.3.

### Panel layouts

A catalogue entry may carry a `layout`:

```json
"layout": {
  "aspect": 3.2,
  "controls": { "gain_1": { "x": 0.22, "y": 0.36, "side": "front", "size": 1.3 } },
  "jacks":    { "input_1": { "x": 0.10, "y": 0.74, "side": "front", "size": 1.4 } }
}
```

Coordinates are fractions of the panel, origin top-left. Fractions rather than
millimetres because the placement is abstract: what has to be right is the
arrangement — which knob is above which socket, what is in a row together.

The *size* is not abstract. Each entry declares its real outside dimensions and
every face's proportion is derived from them, so a device's top is drawn as a
top rather than at its front's shape.

The loader refuses a layout that places a jack or control the device does not
have, that puts a jack on a different side than the entry declares, that faces a
side the device has not, or whose feature runs off the edge of its panel. A
layout describing a different device is worse than no layout.

A panel is more than its knobs and sockets: keybeds, pad grids, screens, wheels
and section plates are declared too, and a grid may say what pressing it sends.
[catalogue.md](catalogue.md) has the whole vocabulary and the six steps for
measuring a device.

**Layouts are optional, and a device without one still draws in `irl`** — it
falls back to the minimal arrangement. The catalogue accepts a device the moment
someone describes it, and holding one back for want of a measured panel would
collect fewer devices.

Every entry carries one today, so **adding a device is the only way to exercise
that fallback** — which is why `tests/test_midi_and_modes.py` builds a device
without a layout rather than relying on some shipped entry staying unfinished.
Covering a path with an incomplete catalogue means finishing the catalogue
breaks the test.

## Format version 3

Both features are document state, so both are a version bump.

- **`midi`** — the bindings.
- **`display`** — `{mode}`.

Both additive, so `_v2_to_v3` adds the two fields at their version-2 defaults
(no mapping, minimal drawing) and changes nothing else. Version 1 still loads,
walking `1 → 2 → 3`. Version 4 is refused.
