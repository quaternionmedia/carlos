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
`patch:export`, `display:irl`, `midi:learn`). The contract permits extension and forbids repurposing, so
nothing standard has been given a Carlos-specific meaning.

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
