# Carlos as a RAD Consumer

Carlos gets its menus from [`quaternionmedia/rad`](https://github.com/quaternionmedia/rad),
QM's radial menu. **There is one menu in this application, and it is RAD's.**

## What "consuming RAD" means, and does not

RAD governs a **contract**, not an implementation. Its own record is explicit:

> The cross-platform trap is sharing *code*. The org's doctrine (build the seam,
> buy the engines; replaceability test) points the other way: share a
> **contract**, let each platform implement it natively. The contract — not any
> implementation — is the governed artifact.

So Carlos imports nothing from RAD. There is no package, no submodule, no
vendored source. What is vendored is `vendor/rad/vectors.json` — the executable
half of the contract — and conformance against it is the entire basis for
claiming to be a consumer.

This is worth stating plainly because "consumer" reads like a dependency and is
not one. Two consumers of RAD share no code and are still interoperable, because
what they share is the interaction and the action vocabulary.

## The three governed artifacts, and where each lives

An implementation is conformant iff it satisfies all three. Nothing else about
it is governed.

| Artifact | Where | Conformance |
| --- | --- | --- |
| **Menu model** — items are data, actions are intents | `static/menus.js` | Ring ceiling case |
| **Geometry** — one polar convention | `static/rad-core.js` | `angle-to-index` cases |
| **Interaction** — one state machine, two commit styles | `static/rad-core.js` | 15 trace cases |

### Menu model

`carlosResolve(context, state) → MenuSpec`. Menus are built by conditional
spread, never by post-filtering a master list. Committing emits an `Intent`;
**the menu never mutates the rack.** `routeIntent` in `static/main.js` is the
only place an intent becomes a change, which is what keeps the menu replaceable.

The ring holds at most 8. Overflow is a design error, not a scrolling problem,
so `packRing` groups into continuation submenus and `radAssertRing` raises on a
ninth item rather than rendering wedges below the touch-target minimum.

That guard has already earned itself. Adding Display and MIDI to the canvas ring
took it to nine, and the test failed before the menu ever rendered. The fix was
the one the contract intends — Turn All is a view action, so it moved under
Display — rather than shrinking eight wedges to fit a ninth.

Carlos uses RAD's standard vocabulary where it exists (`add-node`, `delete`) and
extends it where it does not (`turn`, `row:assign`, `example:complex`,
`patch:export`, `display:irl`, `midi:learn`, `cable:remove`). The contract permits extension and forbids repurposing, so
nothing standard has been given a Carlos-specific meaning.

### Contexts

rad's `MenuContext.type` is `node | edge | canvas | selection`. Carlos resolves
all four and adds a fifth, `row`. The contract permits extension and forbids
repurposing, which is the whole reason it is a fifth name rather than a reuse of
`node`: a row has no jacks, no panel and no sides, and calling it a node to stay
inside the list would have been exactly the repurposing the rule forbids.

So there are four things you can point at — **a device, a cable, a row, the rack
itself** — and each resolves to its own ring. A row previously fell through to
the rack menu, which meant the only way to act on one was the small × in its
header: one click target, one action, and no way to turn a row or empty it.

The order is device, cable, row, rack. A device wins over the row it sits in
because that is what you are pointing at; the rack is what is left when you have
pointed at nothing in particular.

`edge` is a patch cable, and resolving it is what made a single lead removable —
before it, the only way out of a patch was `Clear Rack`.

A cable is found by asking the geometry, not the event target. The cable layer
is `pointer-events: none` so it cannot intercept a click meant for a knob
underneath it, and turning that off to make cables clickable would have laid an
invisible sheet over every control a lead runs across. Instead each cable draws
a second, invisible copy of itself at a thickness worth aiming at, and
`cableAt` asks that copy `isPointInStroke`. The probe is never painted and never
interactive; it is geometry, not a control.

An edge is addressed by the two sockets it joins rather than by a stored id —
the same reasoning that keeps a jack's side out of the exported document. A
stored id would be a second answer to "which cable is this".

### Look, and where it comes from

The ring is painted from **rad-android**, which is the family's most fully
branded surface. A menu that looks like its host rather than like rad is a menu
somebody has to learn twice, and the gesture is already identical — only the
paint was local.

| | |
|---|---|
| wedge, idle | `#4b3b75` |
| wedge, highlighted | `#b84fff` |
| wedge ink | white, `#241033` on the highlighted one |
| hub | `#241b36`, ringed and lettered in `#2de2e6` |
| push / commit | `#d4ff4f` |
| shadow | mid grey at 55% |

**Red-free on purpose.** Violet carries the wedges, turquoise the hub, lime the
zone that commits. Nothing in the set is red, so red never has to mean two
things — which costs this app the obvious mark for a destructive item, and it
is marked with the lime instead: dashed while idle, solid when pointed at.

**The shadow is mid grey rather than black.** Over a dark field a black shadow
composites to nothing and the depth it exists to give never arrives. That is
rad-android's note and it is true here for the same reason.

**Only the ring.** The rack keeps its green. This is not rad-android; it is an
app with rad's menu in it, and repainting the gear would be claiming otherwise.
The one place the violet leaves the ring is the palette's grip, which is the
other thing you grab.

### `Edit ▸`: the ring is a thing you can arrange

rad-android's §8 builds editing additively — the root ring gains exactly one
fixed `Edit ▸`, nothing about the ordinary commit path changes shape, and
nothing under it is reachable without committing it first. Carlos follows that
exactly: seven wedges now, six families and the door.

Under it, one wedge per family offering **Move up**, **Move down** and
**Hide**/**Show**, plus **Reset ring**. The arrangement lives in `localStorage`
under `carlos.ring`, and **absence means "as declared"** — a ring nobody has
edited has no entry at all and resolves exactly as it did before this existed,
so the feature costs nothing to anyone who never opens it. That is rad-android's
rule for an unassigned wedge, applied to a whole ring.

Two things cannot happen, both for the same reason: `Edit` is never hidden, and
`Edit` is built from the **declared** ring rather than the arranged one. The
first was obvious. The second was not, and it shipped broken for one commit:
building `Edit` from the arranged ring meant a hidden family vanished from
`Edit` too, so the way to bring it back disappeared the moment you used it. A
ring you can arrange has to keep the door you arrange it through — at every
level, not just the top one.

Local, and deliberately: an arrangement is a fact about this person at this
screen, and sending it anywhere would make it a fact about an account.

**Not ported:** rad-android's `Assign function…`, which rebinds what committing
a wedge *does*. Its verbs are Android intents; Carlos's are its own actions and
are not user-composable, so there is nothing here to offer.

### A pinned ring is the bar

There is one menu surface. A pinned ring **rests as a strip across the top** —
a title saying what the rack is and what the app last answered — and blooms into
the ring itself only while held. Everything that used to float over the rack or
pin itself across the bottom is that bar now.

It takes the navy above the rack rather than the rack: that strip is background
nothing was ever drawn in, so a title can have it without costing the gear
anything, and the body reserves it while the bar is up.

Three gestures, and nothing else:

- **Hold it** and the ring blooms below the point held — far enough below that
  the finger starts *outside* the band, which is the contract's own cancel. Let
  go without moving and nothing is chosen; drag down into a wedge and that wedge
  is. Blooming closer put the finger on a wedge the moment it appeared, so
  letting go committed `Add` every time.
- **Double-tap and drag** moves it. rad-android's own reposition gesture, behind
  a deliberate second press so the press that works the ring keeps its exact
  shape and never has to know this exists. Moving it detaches it: docked it
  spans the window, floating it is a panel the width of what it says, and
  dragging it back to the top docks it again.

  The two shapes are not cosmetic. A bar is hit-tested by geometry rather than
  by what is under the pointer, so a full-width strip claims every press at its
  own height. Along the top that costs nothing; anywhere else it was a wall
  across the rack, taking knobs and sockets with it.
- **Everything else belongs to the rack.** A ring that simply stayed open owned
  the keyboard and swallowed every click for as long as it was up: arrows
  stopped reaching knobs, Enter stopped patching, Escape stopped deselecting. A
  pinned ring takes input only once a press has landed inside it.

### A pinned ring was, briefly, the panel

There is one menu surface, and it is the ring. A ring left open over the rack is
what a floating panel was, which is why pinning is a **state of the menu** rather
than a window beside it — two menu systems would be two answers to a question
rad's contract already settles.

`View ▸ Pin ring` leaves it up. Pinned it does not close when it has done
something; it returns to its root and stays, because the next thing you want is
usually also on it, and a ring that vanished after every commit would be a panel
that closed itself whenever you used it. `Unpin ring` lets it go.

Its idle hub reads the rack — devices, leads, rows, which way it faces — asked at
render time rather than pushed, so the ring holds no copy of a rack that changes
underneath it. The hub is drawn larger when pinned, and **only drawn** larger:
the dead zone the machine cancels inside is the contract's `r0` and stays `r0`,
so the gesture is identical either way. Same split rad-android makes between the
shape a wedge appears to have and the band it answers to.

One ordering trap, found by the tests: `openAt` resolves as it opens, so pinning
resolved the ring while it was still unpinned and built a menu offering to pin a
ring that already was — with no way back off it. Pinning sets the flag and then
re-asks.

### Getting back out

rad-android's §9 records two failures real-device use found, neither of them in
the ported reducer and both in what the host does around it. Carlos is a host,
so both were worth checking here.

**A working back was invisible.** Releasing on the hub inside a submenu ascends,
and always did, with nothing on screen saying so — the way out was something you
knew or you did not. The hub now reads `◂ Back` whenever a tap there would step
back rather than commit forward, and stops saying so the moment you aim at a
wedge, because then a release commits that wedge instead.

Their other affordance — a lighter arc marking where the push-past-the-edge
drill threshold sits — is **not** ported, because this app has no such gesture.
Carlos drills by committing a wedge that has children. An arc marking a
threshold nothing here responds to would be decoration pretending to be a
control.

**Closing never reset the navigation stack**, so drilling into a deep ring and
closing left every future summon opening there — a dead end with no memory of
how it happened. Carlos resets on *open* rather than on close and so never had
it. Two tests assert it anyway, because "never had it" and "cannot grow it" are
different claims.

### High contrast

rad-android holds its high-contrast mode as a correctness contract rather than a
theme: colour comes out of every signal without the signal coming out with it.
Idle and highlighted become black-fill and white-fill, the text inverts to match,
the hub does the same swap, and the decorative board goes entirely — that mode is
for the things a person has to read, and the board carries nothing.

Carlos resolves it from `prefers-contrast`, which is this platform's version of
the device setting rad-android reads, and answers `forced-colors: active` from
the same block. There is no in-app toggle: a preference the browser already knows
is not one this app should ask for a second time.

Destructive is the interesting case. Normally it is the push-zone lime; here the
dashes that accompany it become the whole signal rather than half of it, because
a mark that survives the loss of colour is the only kind this mode can use.

### Wedges are short; the hub reads the name

rad-android's surfaces record settles what to do about names of arbitrary
length: wedges show an **icon**, the hub shows the **highlighted item's full
label**, and the accessibility label always carries the full name. Ellipsis is
banned by the contract, so truncating was never available as the fix.

Carlos is text rather than icons, so it takes the same rule one step over: the
wedge carries a short name, the hub spells out the full one, wrapped at word
boundaries and never cut. `▸` marks a wedge that opens a ring rather than
committing — the same plain dingbat rad-android uses on `Edit ▸`, chosen over
an emoji so a monochrome or high-contrast rendering stays exactly as legible.

A wedge with nothing aimed at it leaves the hub naming what the ring is *of*,
which is the question you have before you have aimed at anything.

### Geometry

Angle origin −90° (12 o'clock), clockwise. Item *i* is centred at
`−90° + i·(360/N)`, its wedge spanning ±180/N. Dead zone `r₀ = 36` cancels
inward; `r_cancel = 1.35 · r₁` cancels outward. **The band is identical in both
commit styles** — one `radHitTest`, not one per style, because the contract's
point is that the same `(r, θ)` resolves the same way regardless of how the menu
was opened.

### Interaction

`CLOSED → PENDING → OPEN → TRACKING → COMMITTED | CLOSED`.

- **Release-select**: long-press (350 ms, ≤10 slop) opens under the finger; the
  same press moves to highlight and releases to commit. One gesture.
- **Tap-select**: right-click or `m` opens idle; move highlights, click commits.
- **Keyboard**: arrows rotate, Enter commits, Escape backs out. Pointer is never
  required — the contract treats that as foundational, not as an add-on.
- Highlights are **edge-triggered**: jitter inside one wedge fires once.
- A **latched hub press** suppresses highlighting, because a press that can no
  longer commit must not show a highlight that implies it can.

### Which presses the ring declines

Long-press summons a ring, and long-press is also how a knob is turned slowly.
The two are told apart at the single `pointerdown` gate in `main.js`: a press
that lands on something announcing itself as a control never arms the menu.

The gate asks by **role**, not by class name. It used to read
`.knob, .jack, button, input, select`, which was true of the compact rack and
false of the one the app opens in — an `irl` knob is `.irl-knob` and matched
none of it. Measured: eight of the ten things a finger can land on were
unguarded, and a 700 ms turn both turned the knob and bloomed a ring over the
top of it. Under 350 ms nothing collided, which is why it read as intermittent
rather than as a rule that had stopped applying.

A role is the durable question because a control has to announce itself anyway:
the attribute a screen reader reads is the same one that says *this handles its
own press*, so a control cannot arrive correctly announced and still be missed
here. The class names went stale precisely because nothing else depended on
them.

Widget roles only — `slider`, `button`, `switch`, `checkbox`, `spinbutton`.
`closest` walks ancestors, so a bare `[role]` test finds the `role="group"` a
pad grid wears and swallows the menu everywhere inside it. Two consequences
worth knowing before adding a control: a label **inside** a control is declined
too, on purpose, because pressing a knob's label is pressing the knob; and
decorative parts that are not announced — a drawn keybed, the trim around a
socket — still summon the ring, which is correct, as they are backdrop.

## Conformance

```bash
uv run python -m unittest tests.test_rad
```

Replays `vendor/rad/vectors.json` against `static/rad-core.js` in Node, with no
browser.

**66 assertions pass, 0 fail, 16 skipped.** The skips are honest and reported
rather than passed over: they are RAD's `quant`, `tempo`, `chord`, `split`,
`vocab`, `aps`, `cc`, `ccdiv` and `grid` suites, which belong to RAD features
Carlos does not carry — quantized commit, tempo estimation, chorded input, the
three speed axes. Those sit outside the three governed artifacts, so skipping
them is not a conformance gap; **claiming them would be a false report.**

### The platform-free core, enforced

RAD's contract requires state machine and geometry to live in a core with no
platform imports, "*enforced by a grep lint in CI*". `static/rad-core.js` is that
core and `tests/test_rad.py` is that lint: no `document`, `window`, `navigator`,
`HTMLElement` or `localStorage`. All DOM lives in `static/rad-menu.js`, so the
boundary is a file boundary rather than a line range.

This matters because **RAD's own reference implementation cannot pass this
lint** — see below.

### Colour is a token

`color:*` intents name palette tokens, never literals. A hex in an intent cannot
survive a theme change and makes two implementations that agree on meaning
disagree on bytes. Tokens are CSS custom properties (`--rad-signal`,
`--rad-danger`) in `demo.css`; a test asserts no `color:#` appears in any intent
path.

## Vendoring and drift

`vendor/rad/vectors.json` is pinned with `PROVENANCE.json` recording the upstream
commit and vectors version. Vendored rather than fetched so the suite has no
network dependency and an upstream change arrives as a reviewed diff rather than
a silent behaviour change.

To refresh: re-copy, re-run the suite, and update the provenance. A version bump
is a deliberate act, and the tests assert the provenance and the file agree.

## What RAD still owes a consumer

Findings from building this integration. They belong upstream — under the audit
queue's rule, a defect two consumers could share is fixed at the source.

**1. There is no consumable core, and its own record says so.**
`DRAFT-rad-core-extraction` is *Proposed*, pending a human decision on whether
`index.html` becomes a build output. Today the core is delimited by a comment
banner inside a ~1,500-line file containing several hundred DOM references, so
RAD cannot run the grep lint its own contract mandates. Its record states this
plainly: *"a project whose central thesis is govern the seam, not the artifact
currently cannot enforce its own seam."* Carlos did not inherit the problem — the
lint runs here — but every consumer will re-solve it independently until §3 is
decided.

**2. "RAD consumer" is not defined anywhere.** The corpus roster records
`codecartographer` as having "named itself a v0.0.2 RAD consumer", and the phase
ladder makes every rung above `v0.0.1` project-defined. But nothing states what
a consumer must do. This document is Carlos's answer; it would be more useful as
RAD's, so that two consumers make the same claim. A minimum worth proposing:
conformance run against a pinned vectors version, the platform-free lint
enforced, the action vocabulary extended rather than repurposed, and skipped
suites reported.

**3. The vectors carry no scope metadata.** A consumer implementing only the
three governed artifacts must hand-classify 34 cases into in-scope and
out-of-scope. A `suite` or `artifact` field per case would make "conformant to
the contract" mechanically distinguishable from "implements every RAD feature",
which is the distinction the contract itself draws.

**4. RAD has no `project/rad` branch in the corpus.** Its ADRs live in its own
`adr/` directory rather than on a branch of `quaternionmedia/qm`, which is not
the branch-per-project model the constitution describes. `harness-status.json`
reports it as `"unknown": "no project/<name> branch in the corpus, so there is
nothing to read"`. Worth reconciling — either RAD adopts the model or the model
gains a stated exception.

## What was deprecated

The options drawer, its device palette, its example picker, its row controls and
its `~` toggle are **gone**, not hidden. Menus are the radial menu; a second menu
system would be a second answer to a question the contract already settles.

What survives is not a menu: the patch-name field and the file input, which are
not expressible as a ring, and two direct affordances — the per-device turn
button and the row remove button. A single-purpose button is not a menu, and
routing one-click actions through a ring would be the deprecation eating
something it was not meant to.

## The tool palette

Those survivors live in a floating panel, `static/palette.js`. **It is not the
device palette that was deleted**, which is worth stating plainly because it
carries the same word.

The test is what a thing does, not what it is called. A menu resolves a context
into a `MenuSpec` and commits an `Intent`. The panel does neither: it holds a
text field and a file input, it names no device, and `tests/test_rad.py` asserts
it contains no button, no `select`, no `onclick`, and no device id from the
catalogue. That guard used to forbid the string `palette` outright; it cannot
now, and asserting the shape is the stronger version anyway — a rename routes
around a forbidden string and cannot route around this.

`static/palette.js` is also held away from the rack: it may not name `system`,
`ModuleFactory`, `radMenu`, `carlosResolve` or `patchBay`. A panel that starts
reaching into the rack is on its way to being the second menu system.

`palette` is rad's own word for a set of colour tokens, and that is what the
panel is drawn from — no colour in its stylesheet is a literal.

It floats because a rack is the width of the window, and the strip it replaces
was pinned across the bottom taking a slice out of every rack whether or not
anyone was naming a patch. It opens at a default corner, is dragged by its grip
or moved with the arrow keys, and is clamped so a grip's width always stays on
screen — a panel dragged past the corner is gone, and gone is indistinguishable
from broken. `Home` on the grip, or **View ▸ Reset panel**, puts it back. **View ▸ Hide
panel** dismisses it entirely — rad-android gives its overlay a deliberate way
out, because a floating surface you cannot dismiss is one you are stuck with.
The way back is the same ring, which the rack always answers to.

Where someone left it is remembered in `localStorage`, and deliberately not in
the patch document: a window position is not part of a rig, and a rack exported
on one screen would carry a position meaningless on another.
