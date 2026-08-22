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

### Bindings are what splits a cable

A binding says which messages belong to which device. That is also the answer to
"what is going down this lead": the channels bound to the device at the far end
of a cable are the channels the cable carries, so a USB lead into a sampler with
four groups on four channels is drawn as four strands.

Nothing about the split is stored. It is read off the bindings every time the
cables are drawn, which is the same rule that keeps a knob's rotation and a
jack's side out of the document — a stored copy could only ever disagree with
the thing it copied. Rebind a group and the picture follows; pull the lead and
there is nothing left over to clean up.

Two rules on the same channel are one strand, not two. A channel is a lane, and
several bindings sharing one is a distribution down that lane rather than a
second cable — the strand is labelled for the count instead of for whichever
binding happened to be first.

Only `usb` and `midi` split. An audio lead is one line because audio has no
channel 10, and drawing one strand per binding on a patch lead would invent a
distinction the cable does not make.

```sh
curl -s -X POST http://127.0.0.1:8000/api/midi/route \
  -H 'Content-Type: application/json' \
  -d '{"bindings":[{"id":"kick","module":"dfam",
       "source":{"type":"note","channel":10,"note":36}}],
       "bytes":[153,36,100]}'
```

## When no MIDI arrives

Four causes, in the order worth eliminating. `MIDI ▸ Status` names whichever one
it can see; the last two it cannot, because they sit below the browser.

### The page is not a secure context

**The commonest, and the one this project walks people into.** Web MIDI is only
exposed on a secure origin. Measured in Chromium against this server:

| Opened at | `isSecureContext` | `navigator.requestMIDIAccess` |
|---|---|---|
| `http://127.0.0.1:8000` | `true` | present |
| `http://192.168.1.151:8000` | `false` | **absent** |

`carlos serve` prints the LAN address at startup and the onboarding page
recommends it for an on-device test, so this is easy to hit — and until now the
app reported *"this browser has no Web MIDI"*, which blamed the wrong thing. It
says `insecure-context` now.

Three ways out, cheapest first:

```sh
# 1. open it on the machine that is serving
http://localhost:8000

# 2. or forward the port, so it arrives as localhost on the far end
ssh -L 8000:localhost:8000 <host>

# 3. or put it behind HTTPS
```

The tunnel is the one to reach for when the rack runs on a headless box: the
browser sees `localhost`, so the origin is secure, and nothing about the server
changes.

### The browser is blocking it

Chromium-family browsers gate Web MIDI behind a permission, and some — Brave
among them — add their own shield on top of the standard site setting. Two
different things can say no, and a refusal alone does not tell you which:

- the site setting, under the browser's MIDI content settings
  (`brave://settings/content/midi`, `chrome://settings/content/midi`);
- a shield or extension blocking device access for that site.

`MIDI ▸ Status` now reports the permission state — `granted`, `denied`,
`prompt`, or `unknown`. **`denied` without ever having seen a prompt means
something decided for you**, which points at the second list item rather than
the first. `unknown` means the browser declined to answer the query, which is
not the same as refusing MIDI.

### On Linux, ALSA has not got the device either

A browser on Linux reaches MIDI through ALSA, so a port ALSA cannot see is
invisible to every browser on the machine. This is the layer the app cannot
inspect, so `MIDI ▸ Status` says so and names the command instead:

```sh
aconnect -l          # every sequencer port ALSA knows about
amidi -l             # raw MIDI devices
```

Nothing listed means the problem is below the browser. Then:

```sh
lsmod | grep snd_seq        # the sequencer module must be loaded
sudo modprobe snd-seq       # load it now
groups | grep audio         # your user needs to be in `audio`
```

On a Raspberry Pi the sequencer module is the usual culprit — it is not always
loaded by default, and `snd_seq` in `/etc/modules` makes it stick across a
reboot. A class-compliant USB device that appears in `lsusb` but not in
`aconnect -l` is almost always this.

### A port is open and nothing is coming down it

`MIDI ▸ Status` reports `N port(s)` and `N message(s) in` separately for exactly
this. A port with zero messages after you have played something means the device
is connected and silent: wrong cable, wrong DIN direction, or a controller with
local control on and its output off. `MIDI ▸ Test` sends a synthetic note
through the same path, so a rack that lights up on the test and not on the
hardware has narrowed the fault to the hardware side.

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

### Leads

A lead is drawn from where its sockets actually are, measured off the laid-out
elements rather than stored. That is what lets a cable follow a device being
dragged, a window being resized, or a row being scrolled — and it is why
anything that moves an element under a drawn path has to ask for a redraw.
Three things do: a resize, a scroll, and a drag. All three are coalesced to an
animation frame, because a scroll fires per pixel of travel and a redraw is
every lead in the rack.

**A scroll listener has to be on the document and in the capture phase.** A
scroll event does not bubble, so a listener on `window` never hears a row
scroll at all. This was found by measuring: scrolling a shelf 180px moved the
device -180px and its lead 0.

Each end of a lead wears a shallow trapezium — wide where it meets the socket,
narrowing back into the cable — so a run reads as something with two ends
rather than as a line that stops. It is an SVG marker, which buys three things
that geometry would not: `orient="auto"` follows the curve without anything
computing a tangent, `markerUnits="strokeWidth"` scales it with the lead so a
thin lane strand does not wear a full-weight plug, and `context-stroke` takes
the lead's own colour, keeping a rear cable's plug the rear colour and a drum
lane's the lane tint.

**One plug per socket.** A lead carrying several MIDI channels is drawn as
several strands converging on one socket, and a lead split across two layers is
drawn in two pieces whose inner ends are a join rather than a connector. Only
the first strand wears a plug, and only at an end that is really a socket —
otherwise a four-lane USB lead wears eight, and a split lead grows a connector
in mid-air.

### A lead shows which plug is on it

Each end of a lead wears the plug of the socket it is actually in, taken from
the connector axis rather than from the lead. There are seven shapes — a slim
mini jack, a fuller 1/4in, a collared XLR, a round DIN shell, a flat USB tab, an
RJ45 with its latch, and a flat ribbon header — and they are deliberately close
cousins. At a glance a rack should read as leads, not as a key of connector
types; the difference is there when looked at.

**The two ends need not match.** A 3.5mm output into a 1/4in input is a real
patch made with a real cable, and drawing both ends alike is the tool quietly
asserting that one plain lead would do. Where they differ, the status line names
the cable as the lead is dropped — `needs a 3.5mm-to-1/4in lead`. A patch made
with a lead whose ends match says nothing, so the advice means something when it
appears.

Weight comes off the same axis: a Eurorack patch cable and a 1/4in line lead are
not the same object. The multiples live in the palette beside the base weight,
written out rather than multiplied in the rule —
`calc(var(--cable-weight) * 0.85)` renders correctly but a computed
`stroke-width` holding a calc serialises as `calc(0.935px)`, which `parseFloat`
reads as NaN. That was measured: it broke the test asserting the drum strand is
the thickest, because `2 > NaN` is false.

**A patch you own no cable for is refused, and the refusal says which kind of
disappointment it is.** Reasons are ordered by how concrete they are, so this is
the first one asked after patching a socket into itself, and there are two of
them. Same protocol, wrong plug: `No midi lead goes from DIN-5 to 3.5mm` — MIDI
runs on DIN-5, on 3.5mm TRS and over USB, and none of those reach each other.
Same plug, wrong protocol: `midi does not go into a cv socket, even on the same
plug` — a TRS MIDI lead fits a CV input perfectly, which is exactly why it needs
saying.

Asked about a USB-C going into a 3.5mm socket this used to answer `midi does not
go into clock` — true, about a different axis, and no use to anyone holding the
wrong cable.

The lead list exists twice, in `catalogue.py` and in `models.js`, because the
browser has to answer *which cable would this be* during a drag and cannot wait
on the server. That duplication is deliberate and guarded: a test reads the
tables back out of the JavaScript and runs the browser's own `leadTo` over every
connector against every signal — 6400 questions — comparing each with the
server's answer. The connector axis reached its previous state by being recorded
on every socket in the catalogue and checked by nothing.

### Controls turn about their own centre

An indicator is positioned from the middle of whatever carries it, and turns
about the point where it meets that middle. This matters because the same
indicator class is worn by controls whose sizes differ by a factor of four
across the catalogue: a pivot expressed as a fixed distance is correct for
exactly one size and wrong by the difference everywhere else. Measured when it was fixed at 15px, every indicator in the
opening rack was off — by up to 29px on a switch, where the pivot fell outside
the control altogether.

Two consequences for anything new. The indicator's length is a fraction of its
container rather than a number of pixels, and **the element that draws the
visible control has to be positioned**, because an absolutely-positioned child
resolves its percentages against the nearest positioned ancestor — a static one
silently hands the job to something further up, which is its own offset.

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
