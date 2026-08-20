# Retrospectives

Two cycles, newest last. Each is an account of **how the work went wrong and how
it was caught**, because that is the part a diff does not carry.

---

# 1. The `adopt/qm-governance` cycle

Seventy-five commits, one branch, and — right at the end — a second machine. Written at the handoff, from
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

Twelve defects in this cycle were found by something other than a passing
test suite. They are worth listing by **what found them**, because the pattern is the
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

### The first CI run — 3

The branch was pushed at the handoff, and the tests ran somewhere other than
this workstation for the first time. All three of these were invisible here by
construction.

- **A right-click opened a ring and shut it in the same gesture.** `contextmenu`
  fires on pointer *down* on Linux and on pointer *up* on Windows, so on Linux
  the ring was still owed a release — which arrived, landed in the dead zone at
  its centre, and cancelled it. Thirty-nine failures and fourteen errors.
- **`data/` does not exist on a fresh checkout.** A cadence guard wrote a marker
  into it to prove the measurement notices a write. Locally the directory was
  always there because the app had run.
- **The screenshot-drift check failed on a font**, which is the failure the
  walkthrough record names in the clause that forbids it. See below.

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

### Deviating from a record and finding out why it says that

`DRAFT-one-executable-walkthrough.md` §4: the artifact is *recorded, never
compared* — "a test that diffs images fails on a font and gets switched off".

CI had a step that diffed `walkthrough/media` against the committed copies. It
was added in good faith, to make drift arrive as a diff nobody can miss, and it
worked for as long as every run happened on one machine. The first run on Linux
failed on exactly the stated grounds: the same DOM, different bytes.

It is removed rather than pinned to a platform, because the record already says
where regression protection belongs — in the assertions, which the runtime-bound
page makes against the real component, and which also assert their own artifacts
exist. The pictures are output and are uploaded.

The lesson is not "follow the record". It is that a record's *reason* is the part
worth reading: the clause predicted the failure mode, the deviation looked
harmless for weeks, and one cross-platform run settled it.

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

---

# 2. The compliance cycle — 2026-08-20

Six pull requests here and two in the corpus, in one day. Written from the log
and the run outputs rather than from memory.

The theme is narrow enough to state in a sentence: **almost every defect this
cycle was a rule that everybody believed was enforced, and nothing enforced.**

---

## 1. Three rules with no detector

| Rule | Who said it was enforced | What actually checked it |
| --- | --- | --- |
| No vendor `noreply@` co-author trailer | the record, the seed `AGENTS.md`, and the corpus's own workflow comment saying it "was already forbidden" | nothing, anywhere in the corpus |
| A branch outside the five namespaces "is a mistake, not a variation" | `docs/ref/namespaces.md`, marked **canonical** | nothing — `check_pr_base.py` reads the base and the head's `project/` prefix, never the namespace |
| Screenshots regenerate with the ordinary test command | the walkthrough record, and the README | the command did, and nothing asserted it would keep doing so |

The first two were found by breaking them. Three commits went through a full set
of green checks carrying the trailer the rule forbids, in a session that had
read the rule. Two branches were pushed outside the namespaces by someone who
had been pointed at the canonical page in `AGENTS.md` item 1 and had not opened
it.

**The agreement between documents is what made them look settled.** Three
sources saying the same thing reads as corroboration, and all three were
restatements of one unenforced sentence.

---

## 2. The gate that asserted determinism contained a flaky test

`carlos release-check` exists to assert one clause of a version tag: automated
validation passed **and is deterministic**. It refuses a run reporting a skip, a
rerun or a retry.

Inside it, a walkthrough example read a CSS class that a 220ms timer takes away,
and one browser test did the same. Both were measuring how busy the machine was.
It passed three times in a row on this workstation and failed once under the
gate runner, which had just executed a three-minute browser suite in the same
job.

A gate that refuses nondeterminism, containing nondeterminism, is worse than no
gate: it is a green check standing exactly where a reader believes something was
proven. The fix records the transition rather than sampling the state, and it
was demonstrated in both directions — disable the lamp and the assertion fails;
shorten the lamp to `0ms`, the worst race available, and it still passes.

---

## 3. Two documents describing one endpoint, both wrong, differently

`DEPLOYING.md` showed eight of `/healthz`'s ten keys, missing `ok` — the field a
health probe is most likely to read — and `app`. `docs/interop.md` showed nine,
missing `pid`. Neither was stale in the ordinary way. Both were hand-written
from a payload that had since grown, and nothing compared either with it.

Found by starting the app and reading what it answers. That is the only way this
class surfaces: every sample was well-formed, plausible, and describing an
endpoint that answers something else.

---

## 4. The mistakes worth naming

**A version was two literals.** `pyproject.toml` and a default on `Settings`,
with nothing comparing them — the one fact a release is named after, stored
twice. It was behind a ticked checklist box, and it was found by auditing the
checklist against the tree instead of reading it. The fix went in backwards
first: installed metadata is a *copy* taken at install time, and preferring the
copy is the same mistake in a smaller place.

**A picture was taken two mutations after the assertions it illustrated.** The
file called `boot` showed twelve devices under a caption saying eleven, and the
README showed it as the homepage. Nothing was individually wrong — the picture
was correct for the state it was taken in, the assertions were true where they
stood, the caption was true of a state the file did not hold. **The defect was
an order, and no test can see an order.**

**A branch name invited the confusion it caused.** `roster/carlos` reads as a
sibling of `project/carlos` and is close to its opposite: one is permanent,
submodule-pinned and may never flow to `main`; the other was org content whose
whole purpose was to flow to `main` and then be deleted.

**I said a rename would carry the pull request across, and it closed it.**
Stated as fact, not measured first. #82 is closed and #83 replaces it.

**Exit codes were read through a pipe.** `pytest ... | tail -4` reports `tail`'s
status. The corpus's own runner header warns about exactly this — "a pipe
replaces the exit code and this corpus has read a failing check as passing twice
that way" — and the numbers reported survived only because pytest prints its
summary as text.

---

## 5. What governance actually caught

Worth recording, because the cycle's other findings are all about governance
that did not fire.

- The **namespace guard** refused org content on a `project/*` branch, correctly,
  and the reason it gave was the real one: propagation is one-directional, so
  what lands there is stranded. That refusal was accepted deliberately and
  recorded in the corpus ledger as `2026-08-20-002`, with its cost written down
  rather than argued away.
- **`check_pr_base.py`** was run before every pull request and was right every
  time about what it does check.
- **The one-PR rule** held across eight pull requests with no overlap, which is
  the only reason the sequencing stayed legible.
- The **uncommitted-diff signal** worked twice without being asked: the
  re-version changed four screenshots because the bar shows the version, and the
  corrected shutter changed one.

---

## 6. If the next cycle reads one thing

**A rule every document agrees about is the one to check has a detector.**
Corroboration between restatements is not enforcement, and it reads exactly like
it. The question worth asking of any rule this corpus states is not "is this
written down" but "what would go red if I broke it, and have I watched it do
that".

---

## Where this belongs, and does not yet

`AGENTS.md` item 7 puts every *why* in `governance/qm/perspectives/`, dated and
attributed, with a `Tools:` row the directory requires. That is this document's
proper home, and it is not there: the corpus's one-PR slot is held by the draft
roster claim, and opening a second would break the rule this cycle is about.
Queued behind it deliberately rather than routed around.
