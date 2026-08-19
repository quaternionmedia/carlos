# Retrospective — the `adopt/qm-governance` cycle

Seventy-one commits, one branch, one workstation. Written at the handoff, from
the log rather than from memory.

This is not a summary of what was built; `HANDOFF.md` and the commit messages
carry that. It is an account of **how the work went wrong and how it was
caught**, because that is the part that does not survive in a diff.

---

## 1. The shape of the cycle

It ran in four movements, and only the first was planned.

1. **Governance adoption** — submodule, gates, the adoption record, the
   walkthrough, the CI that runs the tests. Ended with a publish-readiness
   checklist and three deliberately-red gates.
2. **The device model** — the catalogue gained a box, panel features, control
   kinds; devices became caricatures drawn at their real relative sizes; every
   drawn thing became a thing that does something.
3. **The seam and the ground** — healthz, cadence declarations, a predictable
   port, the splash, the house navy.
4. **rad, properly** — the family's palette and gestures read from
   `rad-android` itself, then the ring absorbing every other menu surface in
   the app until there was one.

Movement 4 was not on any plan. It came out of one instruction — *make the menu
follow the larger rad family* — and it ended with the floating panel, the status
bar and the info dock all deleted, because each of them turned out to be a
second menu surface wearing different clothes.

---

## 2. What actually caught the defects

Nine defects in this cycle were found by something other than a passing test
suite. They are worth listing by **what found them**, because the pattern is the
lesson.

### A real browser, driven like a hand — 3

- **`Tab` made every control unreachable.** Turning was bound to `Tab`, guarded
  by "unless something focusable already has it". At load nothing is focused, so
  the first `Tab` turned the rack and so did every one after it. Seventeen
  focusable controls, none reachable. The stub harness passed because it
  pre-focused a knob and tested only the second half of the rule.
- **A pinned ring owned the whole app.** Twenty browser tests failed the moment
  the ring was pinned by default: arrows stopped reaching knobs, Enter stopped
  patching, Escape stopped deselecting, every click was swallowed.
- **The facing indicator read `EMPTY`** on a rack with two devices in it, for
  two sessions, because it was refreshed only on a path nobody took.

### Measurement, when the story did not add up — 2

- **The reload that never reloaded.** uvicorn logged `StatReload detected
  changes… Reloading…` and went on serving the old code — proven by editing a
  value and watching `/healthz` keep the old one. What it *did* deliver was a
  reloader parent that owned the socket, which was the whole of this
  environment's phantom-listener trap: three processes, an orphaned port, and
  every stale-server hunt in the repo's history.
- **Two sockets sharing an anchor.** Turning the rack put three pairs of
  different leads on the same pixel. An edge has one dimension and a panel has
  two, so projecting one onto the other dropped an axis — and a DFAM puts
  `trigger_in` and `vca_out` at the same `x`.

### Walking the demo against the running app — 2

Both found while writing a demo script by driving the app rather than
remembering it, and neither had a failing test.

- **A rule with no enforcement.** The integration doc claimed wedges stay within
  twelve characters and the hub reads the long name. The mechanism shipped;
  nothing used it. Fourteen labels were over, one at seventeen.
- **The pinned ring was one action stale.** It re-resolved before dispatching,
  so hiding a family left it on the ring until the next commit — at which point
  it vanished and looked like *that* commit had done it.

### A user looking at the screen — 2

- **Cables drawn in front of the gear they ran behind**, and then, after the
  first fix, **not drawn at all**.
- **The bar walling off the rack** once moved.

---

## 3. The mistakes worth naming

### Testing the mechanism instead of the outcome

The worst single failure of the cycle. Cables were given a layer under the
devices; `z-index: -1` put them under the rack's own opaque floor instead, and
**every dashed lead vanished**. Five tests passed against a screen with no
cables on it — right layer, right z-index, right classes, invisible.

Parentage is not visibility. The replacement test asks
`elementsFromPoint` at a point taken off the curve itself and asserts the lead
paints in front of the floor it runs across, and it was **verified in both
directions** — failing against the broken stacking, passing against the fix.

That verification step is now the standard this cycle ends holding: *a new test
that has not been watched fail is a test whose subject is unproven.*

### Believing a log line

The reload lie cost several sessions of chasing stale servers. The log said the
reload happened. It had not. Nothing else in the system contradicted it, so
there was nothing to notice — until the value being served was compared with the
value on disk.

### Fixing a trap and leaving its twin

Twice, a defect was fixed in one place and left in its sibling:

- `Edit ▸` was made unhideable so the ring keeps the door you arrange it
  through — and was then built *from the arranged ring*, so hiding a family
  removed it from `Edit` too. The same trap, one level down.
- The silhouette inset was written so a turned-away stereo pair could be told
  apart, and the same collision came back for grid patch bays.

Both were found by a test asking **what happens after**, not what happens now.

### Two copies of one fact

A recurring smell, caught three times: the patch name in a field *and* on the
system; the readout pushed *and* held; whether the panel was on screen held in a
variable *and* in a class. Each time the fix was the same — read it at the point
of use from the one thing that owns it.

---

## 4. What the tests learned

| Then | Now |
| --- | --- |
| Model harnesses only | Plus 128 browser tests against real Chromium |
| Counting `path.cable` | Counting distinct `data-cable` leads — a cable is drawn in pieces |
| A test written and passing | A test watched fail against the code it names |
| Rules stated in docs | Rules enforced by the resolver: ring ceiling, wedge length, no ellipsis |
| Tests reading the opening rack | Tests building their own rig on a `bench` fixture |

That last one matters more than it looks. Sixteen tests failed when the opening
rack changed, all of them because they treated presentation as a fixture. The
opening rack has changed three times since.

---

## 5. What governance actually bought

Concretely, and only what can be pointed at:

- **`tests.yml` exists because the checklist asked whether the project's own
  tests ran in CI.** They did not. Six green gates were about records,
  signatures and licensing, and a reviewer could reasonably have believed the
  suite had passed.
- **The cadence declaration caught an undeclared endpoint** — `/api/opening` —
  before a human did.
- **The walkthrough is executable**, so five pages of documentation cannot drift
  from the app without going red.
- **The rad contract settled arguments** that would otherwise have been taste:
  the ring ceiling, the ellipsis ban, colour as tokens. Three of this cycle's
  designs are downstream of "the contract already answers this".

And what it cost: three gates stay red, two of them deliberately. The licensing
pass is gated on a licence class nobody has chosen, and choosing one to turn a
check green would decide the wrong question for the wrong reason.

---

## 6. If the next cycle reads one thing

**Drive the app.** Every defect in section 2 that a suite did not catch was
found by someone — or something — actually operating the thing: a real browser,
a measurement, a demo walk-through, or a person looking at the screen. The
suite is what stops those defects coming back. It is not what finds them.
