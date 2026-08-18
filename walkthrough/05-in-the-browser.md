# 05 — In the browser

> **Runtime-bound: a server and a browser.** This page starts the real
> application on a port of its own and drives it in real Chromium. It does not
> skip when either is missing — it fails. A skip is not a pass, and a
> demonstration nobody can run is a claim.

Everything before this page asserts the model. This one asserts the screen, and
the pictures below it are byproducts of the same run: **taken from the render
those assertions were made against, recorded and never compared.** A test that
diffs images fails on a font and gets switched off, taking the assertions
sitting beside it. The regression protection is the assertions.

## Provisioning

```python
>>> from walkthrough.support import LiveApp, Shots, chromium, open_rack
>>> from walkthrough.support import open_menu, pick, until
>>> app = LiveApp().start()
>>> shots = Shots('05-in-the-browser')
>>> browser = chromium()

```

`LiveApp.start()` polls `/healthz` and raises `Unreachable` if it never
answers. A port of its own, not 8000: a developer's own server is usually up,
and measuring that one would test whatever code happened to be running.

Both the server and the browser register their own shutdown as they start.
doctest stops at the first failing example, so a page that dies half way
through never reaches the teardown at the bottom of it — and a server that
outlives its run holds a port until somebody notices. One session left seven of
them.

## Boot

```python
>>> page = open_rack(app, browser)
>>> page.title()
'Carlos - Synth Patch Workspace'

```

The catalogue is fetched at startup, and the rack begins with the generic pair:

```python
>>> page.locator('.module').count()
2

```

**A browser JS error never reaches the server log.** The log is identical
whether the page works perfectly or throws on every keypress, which is why this
project could not previously claim the page worked at all. The console is
captured, and here it is:

```python
>>> page.errors
[]

```

The palette opens at its default corner, which is the top right — the first
thing here ever to check that against a real viewport rather than arithmetic:

```python
>>> palette = page.locator('#tool-palette').bounding_box()
>>> viewport = page.viewport_size
>>> round(viewport['width'] - (palette['x'] + palette['width']))
20
>>> round(palette['y'])
68

```

And the facing indicator reports the rack it is actually looking at:

```python
>>> page.locator('#view-indicator').inner_text()
'ALL FRONT'

```

> That assertion is why this page exists. It read `EMPTY` on a rack with two
> devices in it, for two sessions, because nothing refreshed it when a device
> was added — and every model-level test agreed with the model. The first run
> of this page found it.

```python
>>> shots.take(page, 'boot')
'05-in-the-browser-boot.png'

```

![The rack on boot](media/05-in-the-browser-boot.png)

## The menu is a ring

Right-click anywhere on the rack. The ring holds at most eight, which the
resolver enforces rather than a reviewer:

```python
>>> rack = page.locator('#rack').bounding_box()
>>> spot = (int(rack['x'] + rack['width'] - 120), int(rack['y'] + rack['height'] - 40))
>>> open_menu(page, *spot)
>>> page.locator('.rad-wedge').count()
8

```

```python
>>> shots.take(page, 'menu')
'05-in-the-browser-menu.png'

```

![The radial menu](media/05-in-the-browser-menu.png)

`pick` moves the real pointer onto a wedge and releases, which is the gesture —
the menu resolves a position into a wedge and knows nothing about which element
was under the cursor.

```python
>>> pick(page, 'Examples')
>>> page.locator('.rad-wedge').count()
8

```

Eight categories, one ring. Devices are grouped by category and the overflow
would become a continuation submenu rather than a ninth wedge.

## Loading the drum rig

```python
>>> pick(page, 'controller')
>>> pick(page, 'Launchpad X')
>>> until(page, "document.querySelector('#status').textContent.includes('Imported')")
>>> page.locator('#status').inner_text()
'Imported "A grid playing a modular drum rig": 4 module(s), 4 cable(s), 1 group(s)'

```

Four devices, four cables, and the example asked for `irl`, so the rack is
drawn as laid out:

```python
>>> page.locator('body').get_attribute('data-display-mode')
'irl'
>>> page.locator('path.cable').count()
4

```

## The panels are drawn

This is the claim two sessions of work could not check: that the panel
vocabulary renders as panels rather than as a row of grey boxes.

The Launchpad X's grid, and the Hapax's two pad blocks, are real elements with
real boxes:

```python
>>> page.locator('.irl-pads .irl-cell').count()
112

```

Sixty-four of them are the Launchpad's, and the modules are addressed by the
ids the example gave them:

```python
>>> launchpad = page.locator('[data-module-id="grid"]')
>>> launchpad.locator('.irl-pads .irl-cell').count()
64

```

A device draws every side it has and lays out only the one it is showing, so
the panel to measure is the active face. A Launchpad X is 241mm square and the
face it opens on is its top — width by depth — so that panel is square too. That is the box doing its job: a
single per-device aspect would have drawn this face at 241 by 17.4.

```python
>>> panel = launchpad.locator('.face.active .irl-panel').bounding_box()
>>> round(panel['width'] / panel['height'], 1)
1.0

```

A device drawn as laid out is drawn near its real size relative to its
neighbours. A Launchpad X is 241mm across and a drum module is 40mm, so the
grid is the wider of the two on screen — by a compressed ratio, which is what
makes this a caricature rather than a scale drawing:

```python
>>> wide = launchpad.bounding_box()['width']
>>> narrow = page.locator('[data-module-id="kick"]').bounding_box()['width']
>>> wide > narrow
True
>>> 1 < wide / narrow < 6      # not to scale: really it is six times wider
True

```

```python
>>> shots.take(page, 'irl-drum-rig')
'05-in-the-browser-irl-drum-rig.png'

```

![The drum rig, drawn as laid out](media/05-in-the-browser-irl-drum-rig.png)

## Pressing a pad does something

The rig loaded above binds three pads to three drum voices on channel 10. The
grid on screen is not a picture of a grid: each cell is a button, and pressing
one sends a note down the same path a real MIDI port uses.

```python
>>> pads = launchpad.locator('.irl-pads button.irl-cell')
>>> pads.count()
64
>>> pads.first.get_attribute('title')
'note 36 ch 10'

```

Note 36 on channel 10 is what `kick` is bound to. Press it:

```python
>>> pads.first.click()
>>> until(page, "document.querySelector('#status').textContent.includes('note 36')")
>>> page.locator('#status').inner_text()
'Launchpad X: note 36 ch 10'

```

The binding matched, so the device it points at is lit — `is-active` is the
class the MIDI layer adds, and nothing here reached for it directly:

```python
>>> page.locator('[data-module-id="kick"]').get_attribute('class')
'module is-active'

```

That is the whole chain: a button in the browser, through the catalogue's
declared note, into `MidiInput`, matched against a binding, out to a device's
class. The drum voice that is *not* bound to that note stays dark:

```python
>>> page.locator('[data-module-id="clap"]').get_attribute('class')
'module'

```

A press is momentary, so the light goes out on its own:

```python
>>> until(page, '''!document.querySelector('[data-module-id="kick"]')
...                  .classList.contains('is-active')''')
>>> page.locator('[data-module-id="kick"]').get_attribute('class')
'module'

```

## Screens say what is happening

A screen shows what its catalogue entry says it reads. The Launchpad's reads
the last event, so it is showing the note that was just sent:

```python
>>> screen = launchpad.locator('.face.active .irl-screen')
>>> screen.get_attribute('data-source')
'last-event'
>>> screen.locator('.irl-screen-text').inner_text()
'NOTE 36 CH 10'

```

Move a control and the same screen follows, because moving a control is an
event too:

```python
>>> knob = launchpad.locator('.irl-knob').first
>>> knob.click()
>>> page.keyboard.press('ArrowUp')
>>> until(page, '''document.querySelector('.face.active .irl-screen .irl-screen-text')
...                  .textContent.startsWith('BRIGHT')''')
>>> screen.locator('.irl-screen-text').inner_text().startswith('BRIGHT')
True

```

## The two panels with the most on them

A keybed and a fader bank are the two things the vocabulary was extended for,
and neither is in the rig above. Add them the way anyone would:

```python
>>> open_menu(page, *spot)
>>> pick(page, 'Add Device')
>>> pick(page, 'keyboard')
>>> pick(page, 'Stage 3')
>>> open_menu(page, *spot)
>>> pick(page, 'Add Device')
>>> pick(page, 'mixer')
>>> pick(page, 'Qu-24')
>>> until(page, "document.querySelectorAll('.irl-key').length === 88")

```

An 88 is 52 naturals and 36 sharps, drawn from A. Any other split is a keybed
drawn from the wrong note, which puts the wrong key under every hand position:

```python
>>> keys = page.locator('.irl-key')
>>> (keys.count(), page.locator('.irl-key.is-sharp').count())
(88, 36)

```

A desk is its fader bank, and every one of the twenty-four channel faders moves
— plus the master. They were drawn as the shape of the device once; a desk you
cannot move a fader on is a photograph.

```python
>>> page.locator('.irl-fader:not(.irl-drawbar)').count()
25
>>> page.locator('.irl-fader[role="slider"]').count()
34

```

The organ's nine drawbars are faders too, and they are real controls — a
drawbar is a fader with a grip you can see, which is what tells an organ
section from a mixer strip at a glance:

```python
>>> page.locator('.irl-drawbar').count()
9
>>> page.locator('.irl-drawbar[role="slider"]').count()
9

```

Both devices are played from their tops, so that is the face each opens on:

```python
>>> for model in ('Stage 3', 'Qu-24'):
...     card = page.locator('.module').filter(has_text=model).first
...     print(model, '->', card.locator('.face.active').get_attribute('data-side'))
Stage 3 -> top
Qu-24 -> top

```

```python
>>> shots.take(page, 'keybed-and-desk')
'05-in-the-browser-keybed-and-desk.png'

```

![A stage piano and a desk, drawn as laid out](media/05-in-the-browser-keybed-and-desk.png)

## Turning a device

`Tab` turns the whole rack; the indicator follows what is actually showing.

```python
>>> page.keyboard.press('Tab')
>>> until(page, "document.querySelector('#view-indicator').textContent !== 'ALL FRONT'")
>>> page.locator('#view-indicator').inner_text() != 'ALL FRONT'
True

```

Every cable is still drawn, with the ends that went out of sight anchored to
their device's outline rather than dropped:

```python
>>> page.locator('path.cable').count()
4

```

```python
>>> shots.take(page, 'turned')
'05-in-the-browser-turned.png'

```

![The rack turned](media/05-in-the-browser-turned.png)

## The palette moves

Drag it by its grip and it goes where you put it.

```python
>>> before = page.locator('#tool-palette').bounding_box()
>>> grip = page.locator('#tool-palette-grip').bounding_box()
>>> grab_x, grab_y = grip['x'] + 40, grip['y'] + 10
>>> page.mouse.move(grab_x, grab_y)
>>> page.mouse.down()
>>> page.mouse.move(grab_x - 260, grab_y + 220, steps=12)
>>> page.mouse.up()

```

It moves by what the hand moved, not to where the hand is — the grab offset is
kept, so the panel does not jump its own corner under the cursor:

```python
>>> after = page.locator('#tool-palette').bounding_box()
>>> round(before['x'] - after['x'])
260
>>> round(after['y'] - before['y'])
220

```

And it is remembered, so a reload brings it back where it was left:

```python
>>> _ = page.reload(wait_until='networkidle')
>>> _ = page.wait_for_selector('#tool-palette')
>>> reloaded = page.locator('#tool-palette').bounding_box()
>>> (round(reloaded['x']), round(reloaded['y'])) == (round(after['x']), round(after['y']))
True

```

## What was recorded

```python
>>> shots.recorded()
['05-in-the-browser-boot.png', '05-in-the-browser-menu.png',
 '05-in-the-browser-irl-drum-rig.png', '05-in-the-browser-keybed-and-desk.png',
 '05-in-the-browser-turned.png']

```

Each of those was written by `Shots.take`, which asserts the file exists and is
not empty before returning its name. Fifteen lines that turn "somebody forgot"
into a red build.

## Nothing threw, the whole way through

```python
>>> page.errors
[]

```

```python
>>> app.stop()

```

The browser needs no line here: it shut itself down when it started.

## What this page does not cover

Real MIDI hardware. The bindings are exercised through the synthetic source in
`02`-level tests and by the menu's own test-note action; a real port needs a
real device, and pretending otherwise would make the automated half less
credible rather than more.
