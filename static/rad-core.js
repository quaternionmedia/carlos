// ===================================================================
// RAD CORE — platform-free
// ===================================================================
// An implementation of quaternionmedia/rad's interaction contract: the menu
// model, the polar geometry, and the state machine. Carlos is a RAD consumer.
//
// **This file must contain no DOM.** No `document`, no `window`, no
// `navigator`, no `HTMLElement`. That is rad's own conformance clause — a
// conformant implementation keeps state machine and geometry in a platform-free
// core — and here it is enforced by a lint in the test suite rather than by a
// comment banner. rad's `DRAFT-rad-core-extraction` record exists because its
// own reference implementation cannot pass that lint; there is no reason for
// the consumer to inherit the problem.
//
// Nothing is imported from rad. The contract is the seam, not the code: rad's
// doctrine is to share a contract and let each platform implement it natively,
// and `vendor/rad/vectors.json` is how this implementation is held to it.

const RAD_GEOMETRY = {
    startDeg: -90,     // 12 o'clock
    clockwise: true,
    r0: 36,            // dead zone; inside it, cancel
    r1: 108,           // ring outer edge
    longPressMs: 350,
    slop: 10,
    cancelScale: 1.35, // r_cancel = cancelScale * r1; outside it, cancel
    maxItems: 8,
};

const RAD_VECTORS_VERSION = '0.3.0';

function radCancelRadius(geometry = RAD_GEOMETRY) {
    return geometry.cancelScale * geometry.r1;
}

// Normalize to [0, 360).
function radNorm(deg) {
    return ((deg % 360) + 360) % 360;
}

// The contract's shared pure function:
//   angleToIndex(θ, N) = round(norm(θ + 90) / (360/N)) mod N
// Item i is centred at -90 + i*(360/N); its wedge spans ±180/N around that.
function radAngleToIndex(thetaDeg, n) {
    if (!Number.isInteger(n) || n < 1) throw new Error(`ring size must be >= 1, got ${n}`);
    const step = 360 / n;
    return Math.round(radNorm(thetaDeg + 90) / step) % n;
}

// Which wedge a point resolves to, or null for no target. The band is
// identical in both commit styles — that is the contract's own emphasis, and
// it is why this is one function rather than one per style.
function radHitTest(r, thetaDeg, n, geometry = RAD_GEOMETRY) {
    if (r <= geometry.r0) return null;              // dead zone cancels inward
    if (r > radCancelRadius(geometry)) return null; // r_cancel cancels outward
    return radAngleToIndex(thetaDeg, n);
}

// ===================================================================
// MENU MODEL
// ===================================================================
// MenuItem   { id, label, icon?, enabled, destructive, children? }
// MenuContext{ type: node|edge|canvas|selection, targetIds[], position{x,y} }
//              hosts may extend this list; they may not repurpose a name.
// MenuSpec   { items: MenuItem[] (1..8), title? }
// Intent     { action, context, itemId }

// The ring ceiling is enforced here, not by a reviewer. Overflow is a design
// error: the resolver groups into a submenu rather than rendering wedges below
// the touch-target minimum.
function radAssertRing(items, geometry = RAD_GEOMETRY) {
    const n = Array.isArray(items) ? items.length : 0;
    if (n < 1) throw new Error('a ring needs at least one item');
    if (n > geometry.maxItems) {
        throw new Error(
            `a ring holds at most ${geometry.maxItems} items, got ${n} - ` +
            'group them into a submenu rather than shrinking the wedges'
        );
    }
    return items;
}

function radMenuSpec(items, title = null) {
    radAssertRing(items);
    return { items, title };
}

// A commit produces an Intent. The menu never mutates the scene; the host
// routes intents through its own state layer.
function radIntent(action, context, itemId) {
    return { action, context, itemId };
}

// ===================================================================
// STATE MACHINE
// ===================================================================
// CLOSED -> PENDING -> OPEN -> TRACKING -> COMMITTED | CLOSED
//
// Two commit styles over one band. Release-select: the invoking press
// continues, and release in the band commits. Tap-select: the menu opens idle
// and a tap in the band commits.
class RadMachine {
    constructor(n, { geometry = RAD_GEOMETRY, labels = null } = {}) {
        this.n = n;
        this.geometry = geometry;
        this.labels = labels;
        this.state = 'CLOSED';
        this.style = null;        // 'release' | 'tap'
        this.highlight = null;    // current wedge, or null
        this.highlights = [];     // edge-triggered sequence
        this.effects = [];        // { index, label } per highlight edge
        this.committed = null;
        this.cancelled = false;
        this.opened = false;
        this.downAt = null;       // press origin, for slop
        this.hubLatched = false;  // a press inside r0 suppresses highlighting
    }

    get stillOpen() {
        return this.state === 'OPEN' || this.state === 'TRACKING';
    }

    labelFor(index) {
        if (index === null || index === undefined) return null;
        if (Array.isArray(this.labels) && this.labels[index] !== undefined) {
            return this.labels[index];
        }
        // The contract requires a highlight effect to carry its own label,
        // resolvable without consulting live state.
        return `i${index}`;
    }

    // Edge-triggered: jitter inside one wedge fires once.
    setHighlight(index) {
        if (index === this.highlight) return;
        this.highlight = index;
        this.highlights.push(index);
        this.effects.push({ index, label: this.labelFor(index) });
    }

    open(style = 'tap') {
        this.state = 'OPEN';
        this.style = style;
        this.opened = true;
        return this;
    }

    cancel() {
        this.state = 'CLOSED';
        this.cancelled = true;
        this.hubLatched = false;
        return this;
    }

    commit(index) {
        this.state = 'COMMITTED';
        this.committed = index;
        this.hubLatched = false;
        return this;
    }

    // One event in, state out. Events are the contract's vocabulary:
    // down, move, up, longpress, open, key.
    send(event) {
        const { type } = event;

        if (type === 'open') return this.open('tap');

        if (type === 'longpress') {
            // Long-press fires while the finger is still down: it opens the
            // menu in release-select, where the same press goes on to commit.
            if (this.state === 'PENDING') this.open('release');
            return this;
        }

        if (type === 'down') {
            if (this.state === 'CLOSED') {
                this.state = 'PENDING';
                this.downAt = { r: event.r ?? 0, thetaDeg: event.thetaDeg ?? 0 };
                return this;
            }
            if (this.stillOpen) {
                const r = event.r ?? 0;
                // A press inside the dead zone latches the hub: it arms
                // back/cancel, and dragging out from there must not highlight,
                // because that press can no longer commit.
                if (r <= this.geometry.r0) {
                    this.hubLatched = true;
                    return this;
                }
                if (r > radCancelRadius(this.geometry)) return this.cancel();
                this.state = 'TRACKING';
                this.setHighlight(radHitTest(r, event.thetaDeg, this.n, this.geometry));
                return this;
            }
            return this;
        }

        if (type === 'move') {
            if (!this.stillOpen) return this;
            if (this.hubLatched) return this;
            this.setHighlight(
                radHitTest(event.r, event.thetaDeg, this.n, this.geometry)
            );
            return this;
        }

        if (type === 'up') {
            if (this.state === 'PENDING') {
                // Released before the long-press fired: never opened.
                return this.cancel();
            }
            if (!this.stillOpen) return this;
            if (this.hubLatched) return this.cancel();
            const target = radHitTest(event.r, event.thetaDeg, this.n, this.geometry);
            return target === null ? this.cancel() : this.commit(target);
        }

        if (type === 'key') return this.key(event.key);

        return this;
    }

    key(key) {
        if (!this.stillOpen) return this;

        if (key === 'Escape') return this.cancel();

        if (key === 'Enter' || key === ' ') {
            return this.highlight === null ? this.cancel() : this.commit(this.highlight);
        }

        if (key === 'ArrowRight' || key === 'ArrowDown') {
            const from = this.highlight === null ? -1 : this.highlight;
            this.setHighlight((from + 1 + this.n) % this.n);
            return this;
        }

        if (key === 'ArrowLeft' || key === 'ArrowUp') {
            const from = this.highlight === null ? 0 : this.highlight;
            this.setHighlight((from - 1 + this.n) % this.n);
            return this;
        }

        return this;
    }

    // Replay a whole trace, which is the shape the conformance vectors take.
    static replay(trace, n, options = {}) {
        const machine = new RadMachine(n, options);
        trace.forEach(event => machine.send(event));
        return machine;
    }
}

// ===================================================================
// CONFORMANCE
// ===================================================================
// Replays vendor/rad/vectors.json against this core. Pure: the caller supplies
// the parsed document, so this runs in a browser, in Node, or in a test with no
// difference and no I/O.
function radConformance(vectors) {
    const results = [];
    const record = (name, ok, detail) => results.push({ name, ok, detail });

    (vectors.cases || []).forEach(testCase => {
        const { name, n } = testCase;

        if (testCase.pure) {
            testCase.pure.forEach(({ thetaDeg, expectIndex }) => {
                const got = radAngleToIndex(thetaDeg, n);
                record(
                    `${name} @${thetaDeg}deg`,
                    got === expectIndex,
                    `expected ${expectIndex}, got ${got}`
                );
            });
            return;
        }

        if (testCase.ceiling) {
            testCase.ceiling.forEach(({ n: size, expectThrows }) => {
                let threw = false;
                try {
                    radAssertRing(Array.from({ length: size }, (_, i) => ({ id: `i${i}` })));
                } catch {
                    threw = true;
                }
                record(
                    `${name} n=${size}`,
                    threw === expectThrows,
                    `expected throws=${expectThrows}, got ${threw}`
                );
            });
            return;
        }

        if (testCase.trace) {
            const machine = RadMachine.replay(testCase.trace, n);
            const expect = testCase.expect || {};

            if (testCase.expectHighlights !== undefined) {
                const got = JSON.stringify(machine.highlights);
                const want = JSON.stringify(testCase.expectHighlights);
                record(`${name} :: highlights`, got === want, `expected ${want}, got ${got}`);
            }
            if (testCase.expectLabels !== undefined) {
                const got = JSON.stringify(machine.effects.map(e => e.label));
                const want = JSON.stringify(testCase.expectLabels);
                record(`${name} :: labels`, got === want, `expected ${want}, got ${got}`);
            }
            if ('committed' in expect) {
                record(
                    `${name} :: committed`,
                    machine.committed === expect.committed,
                    `expected ${expect.committed}, got ${machine.committed}`
                );
            }
            if ('cancelled' in expect) {
                record(
                    `${name} :: cancelled`,
                    machine.cancelled === expect.cancelled,
                    `expected ${expect.cancelled}, got ${machine.cancelled}`
                );
            }
            if ('opened' in expect) {
                record(
                    `${name} :: opened`,
                    machine.opened === expect.opened,
                    `expected ${expect.opened}, got ${machine.opened}`
                );
            }
            if ('stillOpen' in expect) {
                record(
                    `${name} :: stillOpen`,
                    machine.stillOpen === expect.stillOpen,
                    `expected ${expect.stillOpen}, got ${machine.stillOpen}`
                );
            }
            return;
        }

        // Suites this consumer does not implement: quantized commit, tempo
        // estimation, chorded input, the speed axes. They belong to rad
        // features beyond the three governed artifacts, and skipping them is
        // reported rather than passed over silently.
        record(`${name} :: skipped`, true, 'out of scope for this consumer');
        results[results.length - 1].skipped = true;
    });

    const ran = results.filter(r => !r.skipped);
    return {
        version: vectors.version,
        results,
        passed: ran.filter(r => r.ok).length,
        failed: ran.filter(r => !r.ok).length,
        skipped: results.filter(r => r.skipped).length,
    };
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        RAD_GEOMETRY, RAD_VECTORS_VERSION, RadMachine,
        radAngleToIndex, radHitTest, radCancelRadius, radNorm,
        radAssertRing, radMenuSpec, radIntent, radConformance,
    };
}
