# 03 — A modular drum rig

> **Runtime: hermetic.** Builds and validates patch documents in memory.

A drum machine here is not one box. It is a voice you patch and a surface you
play it from, and the catalogue ships one of each.

```python
>>> from src import catalogue, interop, patch_format
>>> devices = catalogue.load_all()
>>> voice = devices['carlos.drum']
>>> grid = devices['novation.launchpad-x']
>>> (voice.category, grid.category)
('eurorack', 'controller')

```

## The voice

`carlos.drum` is generic, like the VCO and the VCF — not a real product, the
neutral module a rig is built around. One trigger fires it; tone and decay take
control voltage, so a sequencer can move them per step:

```python
>>> for jack in voice.jacks:
...     print(f'{jack.type:6} {jack.signal:5} {jack.side:5} {jack.label}')
input  gate  front TRIG
input  gate  front ACCENT
input  cv    front TONE CV
input  cv    front DECAY CV
output audio front OUT
input  power back  POWER

```

Eight HP of a 3U rack, which is where its shape comes from:

```python
>>> box = voice.layout.box
>>> (box.width, box.height)
(40.3, 128.5)
>>> round(voice.layout.aspect_of('front'), 2)
0.31

```

## The surface

A Launchpad X makes no sound at all. It sends MIDI, which is what makes it the
thing you play a modular drum rig *from* rather than a drum machine itself:

```python
>>> [(j.label, j.signal) for j in grid.jacks]
[('USB-C', 'usb'), ('MIDI OUT', 'midi')]

```

Sixty-four pads, and sixteen more buttons around them:

```python
>>> pads = next(f for f in grid.layout.features if f.kind == 'pads')
>>> pads.rows * pads.cols
64

```

## Putting them together

The shipped example is the pairing. Three voices, tuned apart, each bound to a
pad:

```python
>>> document = catalogue.examples_for('carlos.drum')['complex']
>>> document['name']
'Three drum voices from one grid'
>>> [m['type'] for m in document['modules']]
['novation.launchpad-x', 'carlos.drum', 'carlos.drum', 'carlos.drum',
 'allen-heath.qu24']

```

It is a real patch document, so the server validates it the same way it
validates one you saved yourself:

```python
>>> patch = patch_format.load(document)
>>> len(patch.connections)
3

```

The bindings are what make the grid play the voices. Each is a *shape* of
message rather than a message: note 36 on channel 10, so the next hit of that
pad matches and a different pad does not.

```python
>>> for binding in patch.midi:
...     print(f"{binding.label:16} -> {binding.module}")
note 36 ch 10    -> kick
note 38 ch 10    -> snare
note 42 ch 10    -> hat

```

Channel 10 is where a drum machine has always listened.

## Reading it back as cables

The interop seam reshapes a patch for another application. `patchbay` is the
human-readable one — panel legends rather than raw jack names, and the side
each end sits on:

```python
>>> report = interop.apply_transform('patchbay', patch)
>>> for cable in report['cables']:
...     print(cable['text'])
Carlos Drum OUT -> Allen & Heath Qu-24 MIC 1
Carlos Drum OUT -> Allen & Heath Qu-24 MIC 2
Carlos Drum OUT -> Allen & Heath Qu-24 MIC 3

```

Three voices into three channels of a desk. The line is the readable summary;
each end also carries the face it sits on, which differ here because a Eurorack
module patches on its front and a desk wires from its back:

```python
>>> ends = report['cables'][0]
>>> (ends['from']['side'], ends['to']['side'])
('front', 'back')

```

## The other example

`novation.launchpad-x` ships the same rig from the other end — a Hapax
sequencing the voices while the grid plays them by hand:

```python
>>> other = catalogue.examples_for('novation.launchpad-x')['complex']
>>> other['name']
'A grid playing a modular drum rig'
>>> other['display']['mode']
'irl'

```

`irl` is the display mode that draws each device at its own proportions with
its controls where they sit. Loading that example is how you see the point of
it, which is what `05-in-the-browser.md` does — in a browser, with the pictures
to show for it.

Next: `04-cookbook.md`.
