# 02 — The catalogue

> **Runtime: hermetic.** Reads JSON files off disk. No port, no browser.

A device is a JSON file. Adding one is a pull request containing that file and
no Python, which is the whole reason the definitions do not live in the
frontend.

```python
>>> from src import catalogue
>>> devices = catalogue.load_all()
>>> len(devices)
11

```

Every entry is addressable by a stable id of the form `<maker>.<model>`, and
that id is the same string in a patch document, in an API route, and to another
application across the seam:

```python
>>> sorted(devices)
['allen-heath.qu24', 'carlos.drum', 'carlos.vcf', 'carlos.vco',
 'focusrite.scarlett-2i2', 'moog.dfam', 'moog.subharmonicon',
 'nord.stage-3', 'novation.launchpad-x', 'squarp.hapax',
 'teenage-engineering.ep-133']

```

## A device is a box with faces

Sockets sit on whichever face they are actually on, and the entry declares the
device's real outside dimensions in millimetres. Every face's proportion is
derived from that one measurement set:

```python
>>> grid = devices['novation.launchpad-x']
>>> box = grid.layout.box
>>> (box.width, box.height, box.depth)
(241.0, 17.4, 241.0)

```

Front and back are width by height; top and bottom are width by depth; left and
right are depth by height. A Launchpad X is a flat square, so:

```python
>>> round(grid.layout.aspect_of('top'), 2)
1.0
>>> round(grid.layout.aspect_of('front'), 2)
13.85

```

That difference is the point. A single per-device aspect number only ever
described the front, and applying it to every side drew a device's top as a
shape it is not.

## The face you look at first

Almost everything is a box you face. A Launchpad X is not: you look down at it,
so its playing surface is its top and its front is a 241mm by 17.4mm lip.

```python
>>> grid.layout.face
'top'
>>> sorted({jack.side for jack in grid.jacks})
['back']

```

The entry says which face it opens on rather than anything counting what is on
each side. An empty face means one of two things and only the entry can tell
them apart: a Launchpad X's front really is blank, while a device nobody has
measured yet has an empty front because nobody has measured it.

```python
>>> [d.layout.face for d in devices.values() if d.layout.face != 'front']
['top', 'top', 'top', 'top', 'top']

```

## A side exists if something is on it

Not "if a socket is on it". A keybed, a screen and a pad grid are things.

```python
>>> grid.sides()
['front', 'back', 'top']

```

`front` is always present — every device has a face you look at, even when it
is a blank lip.

## Panel furniture

What makes a device recognisable is mostly not its sockets. The vocabulary
covers the rest:

```python
>>> from collections import Counter
>>> kinds = Counter(f.kind for d in devices.values() for f in d.layout.features)
>>> sorted(kinds)
['buttons', 'faders', 'grille', 'keybed', 'label', 'logo', 'pads', 'plate',
 'screen', 'vent', 'wheel']

```

A Launchpad X is its grid:

```python
>>> for feature in grid.layout.features:
...     if feature.kind in ('pads', 'buttons'):
...         print(f'{feature.kind:8} {feature.rows} x {feature.cols}  {feature.label}')
buttons  1 x 8  Function
buttons  8 x 1  Scene launch
pads     8 x 8  8x8 RGB velocity pads

```

## Honesty

`fidelity` says how much of the real device an entry claims. A Qu-24 has 24 mic
inputs; the entry has four and says so.

```python
>>> desk = devices['allen-heath.qu24']
>>> desk.fidelity
'sketch'
>>> len([j for j in desk.jacks if j.name.startswith('mic_in')])
4

```

A layout carries the same obligation. The drawing is a caricature: the
arrangement is accurate, the proportions are compressed so extreme shapes stay
legible, and where a count is the arrangement rather than a census the entry's
summary says so.

Next: `03-patch-documents.md`, which is what a rack turns into when you save it.
