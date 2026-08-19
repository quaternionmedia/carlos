// ===================================================================
// RAD MENU — the DOM half
// ===================================================================
// Renders a ring and adapts pointer and keyboard input into the events
// `rad-core.js` understands. Every decision about *what* a point or a key means
// lives in the core; this file only turns browser events into core events and
// core state into SVG.
//
// Colour never appears here as a literal. The contract requires palette tokens,
// because a hex in a menu cannot survive a theme change and makes two
// implementations that agree on meaning disagree on bytes. Tokens are CSS
// custom properties defined in demo.css.

const RAD_SVG_NS = 'http://www.w3.org/2000/svg';

// How tall the resting bar is, and how far apart two presses can be in time
// and space and still be one double-tap.
//
// The double-tap figures are rad-android's, and so is the gesture: a second
// press that then *holds* is how its overlay handle is moved, chosen so the
// ordinary press-and-drag that works the ring keeps its exact shape and never
// has to know a second gesture exists.
const RAD_BAR_HEIGHT = 30;
const RAD_DOUBLE_TAP_MS = 320;
const RAD_DOUBLE_TAP_SLOP = 24;

// Break a hub label into lines that fit inside the dead zone.
//
// Word boundaries only, and never mid-word: a break falling inside a word reads
// as a truncation, which is the thing the contract's ban on the ellipsis exists
// to avoid. A single word longer than the hub is left whole and allowed to
// overflow - it is still readable, where a cut version would be a lie about
// what the item is called.
//
// Characters rather than measured text, because this runs per frame while a
// finger is moving and the hub is a fixed width in a fixed family. Three lines
// is the ceiling: past that the name is not the problem the hub can solve.
function wrapHubLabel(text, r0, perLine = Math.max(6, Math.floor(r0 / 4.1)),
                      maxLines = 3) {
    const words = String(text || '').split(/\s+/).filter(Boolean);
    if (!words.length) return [''];

    const lines = [];
    let line = '';
    words.forEach(word => {
        const candidate = line ? `${line} ${word}` : word;
        if (candidate.length <= perLine || !line) {
            line = candidate;
        } else {
            lines.push(line);
            line = word;
        }
    });
    if (line) lines.push(line);
    return lines.slice(0, maxLines);
}

class RadMenu {
    constructor({ host, resolve, onIntent, geometry = RAD_GEOMETRY }) {
        this.host = host;
        this.resolve = resolve;
        this.onIntent = onIntent;
        this.geometry = geometry;

        this.layer = null;
        this.machine = null;
        this.spec = null;
        this.context = null;
        this.centre = { x: 0, y: 0 };
        this.stack = [];          // submenu breadcrumbs
        // Pinned: the ring stays open over the rack instead of closing when it
        // has done something. There is no second surface here - a pinned ring
        // *is* what a floating panel was, which is why this is a state of the
        // menu rather than a window beside it. Two menu systems would be two
        // answers to a question rad's contract already settles.
        this.pinned = false;
        this.readout = null;      // what a pinned hub shows, if the host says
        // Where the bar sits, and what it is doing.
        //
        // A pinned ring rests as a bar across the top - a title, saying what
        // the rack is - and blooms into the ring itself only while held. That
        // is what keeps it out of the way: at rest it covers a strip nothing
        // is drawn in, rather than a corner of the rack.
        this.barY = 0;
        this.lastBarTap = 0;
        this.moving = null;
        // What the app last answered, and whether anybody has held the bar yet.
        // The host owns both — it is the thing that knows what was said and
        // what this browser remembers.
        this.saidLately = '';
        this.hintLearned = false;

        // Whether this ring is currently the thing being driven.
        //
        // An unpinned ring always is: it exists for the length of one gesture
        // and that gesture is its own. A pinned one is on screen all the time,
        // and a ring that owned the keyboard and swallowed every click for as
        // long as it was up would take the whole app with it - which is exactly
        // what it did: arrow keys stopped reaching knobs, Enter stopped
        // patching, and every click anywhere was suppressed as the ring's.
        this.engaged = false;
        this.longPressTimer = null;
        this.pressOrigin = null;

        this.onPointerDown = this.onPointerDown.bind(this);
        this.onPointerMove = this.onPointerMove.bind(this);
        this.onPointerUp = this.onPointerUp.bind(this);
        this.onKeyDown = this.onKeyDown.bind(this);
    }

    get open() {
        return this.layer !== null;
    }

    // --- geometry helpers -------------------------------------------------
    toPolar(clientX, clientY) {
        const dx = clientX - this.centre.x;
        const dy = clientY - this.centre.y;
        return {
            r: Math.hypot(dx, dy),
            thetaDeg: Math.atan2(dy, dx) * 180 / Math.PI,
        };
    }

    // --- opening ----------------------------------------------------------
    openAt(context, clientX, clientY, style = 'tap') {
        this.close({ silent: true });

        this.context = context;
        this.spec = this.resolve(context);
        this.stack = [];
        this.centre = this.clampToViewport(clientX, clientY);
        this.machine = new RadMachine(this.spec.items.length, {
            geometry: this.geometry,
            labels: this.spec.items.map(i => i.label),
        });
        this.machine.open(style);

        // Summoned rather than rested: a pinned ring opened by pointing at
        // something is being driven, and settles back to its bar afterwards.
        if (this.pinned) this.engaged = true;

        this.render();
        document.addEventListener('pointerdown', this.onPointerDown, true);
        document.addEventListener('pointermove', this.onPointerMove);
        document.addEventListener('pointerup', this.onPointerUp);
        document.addEventListener('keydown', this.onKeyDown, true);
        return this;
    }

    // Whether input belongs to this ring right now.
    //
    // Unpinned, always: the ring is the gesture. Pinned, only once a press has
    // landed inside it - the ring is one thing on a screen full of others, and
    // the rack underneath it is still a rack.
    get owningInput() {
        return !this.pinned || this.engaged;
    }

    // The bar's box, in viewport coordinates.
    barBox() {
        const width = (typeof window !== 'undefined' && window.innerWidth) || 0;
        return { x: 0, y: this.barY, width, height: RAD_BAR_HEIGHT };
    }

    // Is this press on the bar? Asked of the geometry for the same reason the
    // ring is: the layer is `pointer-events: none` so it cannot swallow a click
    // meant for a knob beneath it, which means the DOM cannot answer.
    aimedAtBar(clientX, clientY) {
        if (!this.pinned) return false;
        const box = this.barBox();
        return clientY >= box.y && clientY <= box.y + box.height
            && clientX >= box.x && clientX <= box.x + box.width;
    }

    // Resting: pinned, and not currently bloomed into a ring.
    get resting() {
        return this.pinned && !this.engaged;
    }

    // Is this point inside the ring's own band?
    //
    // Asked of the geometry, not of the element: the layer is
    // `pointer-events: none` so that a ring drawn over a knob cannot swallow a
    // click meant for it, which means the DOM cannot answer this.
    aimedAtRing(clientX, clientY) {
        if (!this.centre) return false;
        const { r } = this.toPolar(clientX, clientY);
        return r <= radCancelRadius(this.geometry);
    }

    // Clamp the ring inside the viewport by shifting the centre inward, never
    // by shrinking below the minimum radii — the contract is explicit that
    // shrinking is the wrong fix.
    clampToViewport(x, y) {
        const pad = this.geometry.r1 * this.geometry.cancelScale;
        return {
            x: Math.min(Math.max(x, pad), window.innerWidth - pad),
            y: Math.min(Math.max(y, pad), window.innerHeight - pad),
        };
    }

    // Closing is not unpinning.
    //
    // It used to clear `pinned` too, which meant `openAt` - which closes first -
    // quietly unpinned the ring every time you summoned one on a device. A
    // pinned ring that is put away by pointing at something else was never
    // pinned. `pin(false)` is the one thing that unpins.
    close({ silent = false } = {}) {
        this.engaged = false;
        this.disarm();
        if (this.layer) {
            this.layer.remove();
            this.layer = null;
        }
        document.removeEventListener('pointerdown', this.onPointerDown, true);
        document.removeEventListener('pointermove', this.onPointerMove);
        document.removeEventListener('pointerup', this.onPointerUp);
        document.removeEventListener('keydown', this.onKeyDown, true);
        this.machine = null;
        this.spec = null;
        if (!silent && this.onClose) this.onClose();
    }

    // --- input adapters ---------------------------------------------------
    // A long press on a target arms release-select: the same press goes on to
    // choose and commit, which is the one-gesture path.
    //
    // Arming installs its *own* listeners. It used to rely on the menu's, which
    // only exist while the menu is open — so nothing cancelled the timer for a
    // press that was released early, and every short click on the rack opened a
    // menu 350 ms later.
    armLongPress(context, event) {
        this.disarm();
        this.pressOrigin = { x: event.clientX, y: event.clientY };

        this.armMove = (e) => this.cancelLongPress(e);
        this.armEnd = () => this.disarm();
        document.addEventListener('pointermove', this.armMove);
        document.addEventListener('pointerup', this.armEnd);
        document.addEventListener('pointercancel', this.armEnd);

        this.longPressTimer = setTimeout(() => {
            this.longPressTimer = null;
            this.releaseArmListeners();
            this.openAt(context, this.pressOrigin.x, this.pressOrigin.y, 'release');
            // The press is already down, so the machine must be told the
            // long-press fired rather than waiting for a fresh one.
            this.machine.state = 'PENDING';
            this.machine.send({ type: 'longpress' });
            this.render();
        }, this.geometry.longPressMs);
    }

    releaseArmListeners() {
        if (this.armMove) document.removeEventListener('pointermove', this.armMove);
        if (this.armEnd) {
            document.removeEventListener('pointerup', this.armEnd);
            document.removeEventListener('pointercancel', this.armEnd);
        }
        this.armMove = null;
        this.armEnd = null;
    }

    // Stop arming entirely: no timer, no listeners.
    disarm() {
        if (this.longPressTimer) {
            clearTimeout(this.longPressTimer);
            this.longPressTimer = null;
        }
        this.releaseArmListeners();
    }

    cancelLongPress(event) {
        if (!this.longPressTimer) return;
        if (event && this.pressOrigin) {
            const moved = Math.hypot(
                event.clientX - this.pressOrigin.x,
                event.clientY - this.pressOrigin.y
            );
            if (moved <= this.geometry.slop) return; // within slop, still arming
        }
        this.disarm();
    }

    // A pointer-driven commit or cancel is one physical gesture, but the
    // browser still delivers a `click` afterwards to whatever sits under the
    // cursor. Without this, committing a menu item also selects the device
    // underneath it.
    suppressNextClick() {
        const swallow = (event) => {
            event.stopPropagation();
            event.preventDefault();
            document.removeEventListener('click', swallow, true);
        };
        document.addEventListener('click', swallow, true);
        // If no click follows - a cancel outside any target - the listener must
        // not sit there waiting to eat an unrelated one.
        setTimeout(() => document.removeEventListener('click', swallow, true), 350);
    }

    onPointerDown(event) {
        // Only a pinned ring has to ask. An unpinned one was opened by this
        // very gesture and is already the thing being driven.
        if (!this.open || !this.pinned) return;

        if (!this.resting) {
            this.engaged = this.aimedAtRing(event.clientX, event.clientY);
            return;
        }

        if (!this.aimedAtBar(event.clientX, event.clientY)) return;

        // A press on the bar is one of two things, and which one is decided by
        // what already happened rather than by where it landed.
        const now = event.timeStamp || 0;
        const soon = now - this.lastBarTap < RAD_DOUBLE_TAP_MS;
        const near = this.lastBarAt
            && Math.abs(event.clientX - this.lastBarAt.x) < RAD_DOUBLE_TAP_SLOP
            && Math.abs(event.clientY - this.lastBarAt.y) < RAD_DOUBLE_TAP_SLOP;

        this.lastBarTap = now;
        this.lastBarAt = { x: event.clientX, y: event.clientY };

        if (soon && near) {
            // Second press of a double-tap: this one moves the bar. Deliberate
            // enough that it can never be reached by accident from the press
            // that opens the ring, which is rad-android's whole reason for
            // putting reposition behind this gesture rather than a drag.
            this.moving = { from: event.clientY, at: this.barY };
            this.layer?.classList.add('is-moving');
            event.preventDefault();
            return;
        }

        // Otherwise: hold it and the ring blooms where the press landed.
        this.armBloom(event);
    }

    // Hold the bar, and the rest of the ring appears.
    //
    // The same `longPressMs` the contract names for summoning a ring anywhere
    // else, because this *is* summoning a ring - the bar is where it rests, not
    // a different control with rules of its own.
    armBloom(event) {
        this.releaseArmListeners();
        const at = { x: event.clientX, y: event.clientY };

        this.armMove = (e) => {
            if (Math.abs(e.clientX - at.x) > this.geometry.slop
                || Math.abs(e.clientY - at.y) > this.geometry.slop) {
                this.cancelBloom();
            }
        };
        this.armEnd = () => this.cancelBloom();
        document.addEventListener('pointermove', this.armMove);
        document.addEventListener('pointerup', this.armEnd);
        document.addEventListener('pointercancel', this.armEnd);

        this.bloomTimer = setTimeout(() => {
            this.bloomTimer = null;
            this.releaseArmListeners();
            this.bloomAt(at.x, at.y);
        }, this.geometry.longPressMs);
    }

    cancelBloom() {
        if (this.bloomTimer) clearTimeout(this.bloomTimer);
        this.bloomTimer = null;
        this.releaseArmListeners();
    }

    // Open the ring out of the bar, below the point that was held.
    //
    // Far enough below that the finger starts *outside* the ring's band, which
    // is the contract's own cancel: let go without moving and nothing is
    // chosen, drag down into a wedge and that wedge is. Blooming closer put the
    // finger on a wedge the moment it appeared, so simply letting go committed
    // whatever happened to be under it - `Add`, every time, because the bar is
    // directly above the centre and north is item zero.
    bloomAt(clientX, clientY) {
        this.engaged = true;
        if (!this.hintLearned) {
            this.hintLearned = true;
            if (this.onHintLearned) this.onHintLearned();
        }
        this.centre = this.clampToViewport(
            clientX, clientY + radCancelRadius(this.geometry) + 8);
        this.spec = this.resolve(this.context);
        this.machine = new RadMachine(this.spec.items.length, {
            geometry: this.geometry,
            labels: this.spec.items.map(i => i.label),
        });
        this.machine.state = 'PENDING';
        this.machine.send({ type: 'longpress' });
        this.render();
        return this;
    }

    onPointerMove(event) {
        if (this.moving) {
            this.barY = Math.max(0, this.moving.at + (event.clientY - this.moving.from));
            this.render();
            return;
        }
        this.cancelLongPress(event);
        if (!this.open || !this.owningInput) return;
        const { r, thetaDeg } = this.toPolar(event.clientX, event.clientY);
        this.machine.send({ type: 'move', r, thetaDeg });
        this.afterEvent();
    }

    onPointerUp(event) {
        if (this.moving) {
            this.moving = null;
            this.layer?.classList.remove('is-moving');
            if (this.onBarMoved) this.onBarMoved(this.barY);
            this.render();
            return;
        }
        this.cancelBloom();
        this.disarm();
        if (!this.open || !this.owningInput) {
            // A press that was not this ring's leaves it as it was: resting if
            // it was resting, and never dragged shut by somebody using the rack
            // underneath it.
            if (this.pinned) this.engaged = false;
            this.render();
            return;
        }
        const { r, thetaDeg } = this.toPolar(event.clientX, event.clientY);
        this.machine.send({ type: 'up', r, thetaDeg });
        // This release belongs to the menu, so nothing below it should also act
        // on it - neither the rest of this event nor the click that follows.
        event.stopPropagation();
        this.suppressNextClick();
        // Engagement is *not* cleared here. `afterEvent` may descend into a
        // submenu, and a pinned ring that stopped being engaged mid-gesture
        // renders as its resting bar - so choosing `View` drew the title bar
        // instead of View's ring. `settle` is the one place a pinned ring goes
        // back to rest, because settling is what finishing means.
        this.afterEvent();
    }

    onKeyDown(event) {
        // A pinned ring does not own the keyboard. Arrow keys belong to
        // whatever knob has focus, Enter to whatever socket does, and Escape to
        // the selection - all of which a permanently-open ring took, leaving a
        // keyboard user with a rack they could look at and not touch.
        //
        // Summoning an unpinned ring with `m` is how the keyboard drives a ring,
        // and that one owns these keys for as long as it is up.
        if (!this.open || !this.owningInput) return;
        const keys = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
                      'Enter', ' ', 'Escape'];
        if (!keys.includes(event.key)) return;
        // The menu owns these keys while it is open, or Tab-to-turn and
        // Escape-to-deselect fire underneath it.
        event.preventDefault();
        event.stopPropagation();
        this.machine.send({ type: 'key', key: event.key });
        this.afterEvent();
    }

    // One place where a finished machine turns into an intent or a close.
    afterEvent() {
        if (!this.machine) return;

        if (this.machine.state === 'COMMITTED') {
            const chosen = this.spec.items[this.machine.committed];
            if (chosen?.children) return this.descend(chosen);
            this.emit(chosen);
            return;
        }

        if (this.machine.state === 'CLOSED') {
            // Backing out of a submenu returns to its parent rather than
            // closing the whole menu.
            if (this.stack.length) return this.ascend();
            // A pinned ring at its root has nowhere to back out to, and taking
            // it away would make every stray release a dismissal.
            if (this.pinned) return this.settle();
            this.close();
            return;
        }

        this.render();
    }

    // Submenus replace the ring in place; no nested popovers.
    descend(parent) {
        this.stack.push({ spec: this.spec, label: parent.label });
        this.spec = { title: parent.label, items: parent.children };
        this.machine = new RadMachine(this.spec.items.length, {
            geometry: this.geometry,
            labels: this.spec.items.map(i => i.label),
        });
        this.machine.open('tap');
        this.render();
    }

    ascend() {
        const previous = this.stack.pop();
        this.spec = previous.spec;
        this.machine = new RadMachine(this.spec.items.length, {
            geometry: this.geometry,
            labels: this.spec.items.map(i => i.label),
        });
        this.machine.open('tap');
        this.render();
    }

    emit(chosen) {
        if (!chosen || chosen.enabled === false) {
            this.settle();
            return;
        }
        const intent = radIntent(chosen.action, this.context, chosen.id);
        if (chosen.payload) intent.payload = chosen.payload;

        // Order matters, and only when pinned.
        //
        // Unpinned the ring closes and then dispatches, which is right: the
        // gesture is over, and the handler is free to open a prompt or a file
        // dialog without a ring hanging behind it.
        //
        // Pinned it has to dispatch *first*. A pinned ring is drawn from state
        // the intent is about to change, so settling before dispatch redraws it
        // from the world as it was - and it showed the previous answer to
        // everything. Hiding a family left it on the ring until the next
        // commit, at which point it vanished and looked like that commit had
        // done it.
        if (this.pinned) {
            this.onIntent(intent);
            this.settle();
            return;
        }

        this.close();
        this.onIntent(intent);
    }

    // What happens after the ring has done something.
    //
    // Unpinned it closes, which is the ordinary atomic gesture: press, choose,
    // release, gone. Pinned it goes back to its root and stays, because the
    // whole point of pinning is that the next thing you want is usually also on
    // it - and a ring that vanished after every commit would be a panel that
    // closed itself whenever you used it.
    settle() {
        if (!this.pinned) {
            this.close();
            return;
        }

        // Back to the bar. The ring is what you asked for by holding, and it
        // has now done the thing you asked for - leaving it open would put it
        // back over the rack, which is the whole reason it rests as a bar.
        this.engaged = false;
        this.stack = [];
        this.spec = this.resolve(this.context);
        this.machine = new RadMachine(this.spec.items.length, {
            geometry: this.geometry,
            labels: this.spec.items.map(i => i.label),
        });
        this.machine.open('tap');
        this.render();
    }

    // Pin the ring open, or let it go.
    //
    // Pinning re-resolves rather than freezing what is on screen: a pinned ring
    // is a live thing, and the rack it describes goes on changing underneath
    // it.
    pin(on = true) {
        if (!on) {
            if (this.open) this.close();
            this.pinned = false;
            document.body?.removeAttribute?.('data-ring');
            return false;
        }

        // Pinning happens from inside the ring it pins, so by the time this
        // runs the commit has already closed it. Reopening where it stood is
        // the honest reading of "leave this one up" - it is the same ring in
        // the same place, in its other state.
        if (!this.open) {
            const where = this.centre || { x: 0, y: 0 };
            const context = this.context
                || { type: 'canvas', targetIds: [], position: where };
            this.openAt(context, where.x, where.y, 'tap');
        }
        this.pinned = true;
        if (this.layer) this.layer.classList.add('is-pinned');
        // The rack makes room for the bar. It is the one thing that gets any of
        // the navy the rack floats in.
        document.body?.setAttribute?.('data-ring', 'pinned');
        // Resolve *after* the flag, not before. `openAt` resolves as it opens,
        // and at that moment this ring was still unpinned - so the menu it
        // built offered to pin a ring that already was, and there was no way
        // back off it. Settling re-asks with the flag set.
        this.settle();
        return true;
    }

    // What the hub says when a pinned ring is idle. Set by the host, read at
    // render time: the ring holds no copy of the rack's state, it asks.
    showsReadout(fn) {
        this.readout = fn;
        return this;
    }

    // --- rendering --------------------------------------------------------
    render() {
        if (this.resting) return this.renderBar();
        return this.renderRing();
    }

    // The pinned ring at rest: a strip across the top saying what the rack is.
    //
    // A title rather than a control. It answers to exactly two gestures - hold
    // it and the ring blooms, double-tap and drag it and it moves - and to
    // nothing else, so the rack underneath keeps every click and key it had.
    renderBar() {
        this.mountLayer();
        this.layer.replaceChildren();
        this.layer.classList.add('is-resting');
        this.layer.setAttribute('aria-label', 'Rack');

        const box = this.barBox();
        const bar = document.createElementNS(RAD_SVG_NS, 'rect');
        bar.setAttribute('x', box.x);
        bar.setAttribute('y', box.y);
        bar.setAttribute('width', box.width);
        bar.setAttribute('height', box.height);
        bar.setAttribute('class', 'rad-bar');
        this.layer.appendChild(bar);

        // Two things, and a rule between them.
        //
        // The standing description of the rack does not stop being true when
        // the app answers something, and the answer does not stop mattering
        // when you look away - so neither replaces the other. One drawn rule
        // separates them, and the facts inside the left half are separated by
        // dim dots rather than more rules, because four rules in a strip is a
        // strip nobody reads.
        const middle = box.y + box.height / 2;
        const facts = this.readout ? this.readout() : '';
        const said = this.saidLately || '';

        const text = document.createElementNS(RAD_SVG_NS, 'text');
        text.setAttribute('x', 16);
        text.setAttribute('y', middle);
        text.setAttribute('class', 'rad-bar-text');
        text.setAttribute('id', 'rad-bar-text');
        // Drawn, never announced: `#status` is the live region that carries
        // this to a screen reader, and announcing it twice would be two voices
        // saying one thing.
        text.setAttribute('aria-hidden', 'true');

        facts.split('|').forEach((fact, index) => {
            if (index) {
                const dot = document.createElementNS(RAD_SVG_NS, 'tspan');
                dot.setAttribute('class', 'rad-bar-dot');
                dot.textContent = ' · ';
                text.appendChild(dot);
            }
            const run = document.createElementNS(RAD_SVG_NS, 'tspan');
            run.textContent = fact.trim();
            text.appendChild(run);
        });
        this.layer.appendChild(text);

        // Where the left half ends. Measured rather than assumed, because the
        // figures change width with the rack.
        const measured = typeof text.getComputedTextLength === 'function'
            ? text.getComputedTextLength()
            : 0;
        let next = 16 + (measured || 300) + 18;

        if (said) {
            const rule = document.createElementNS(RAD_SVG_NS, 'line');
            rule.setAttribute('x1', next);
            rule.setAttribute('x2', next);
            rule.setAttribute('y1', box.y + 7);
            rule.setAttribute('y2', box.y + box.height - 7);
            rule.setAttribute('class', 'rad-bar-rule');
            this.layer.appendChild(rule);

            const answer = document.createElementNS(RAD_SVG_NS, 'text');
            answer.setAttribute('x', next + 14);
            answer.setAttribute('y', middle);
            answer.setAttribute('class', 'rad-bar-said');
            answer.setAttribute('id', 'rad-bar-said');
            answer.setAttribute('aria-hidden', 'true');
            answer.textContent = said;
            this.layer.appendChild(answer);
        }

        // The hint retires itself. It is worth a strip of the bar exactly until
        // somebody has held it once, and after that it is a label on a door
        // they already know how to open.
        if (!this.hintLearned) {
            const hint = document.createElementNS(RAD_SVG_NS, 'text');
            hint.setAttribute('x', box.width - 16);
            hint.setAttribute('y', middle);
            hint.setAttribute('class', 'rad-bar-hint');
            hint.setAttribute('id', 'rad-bar-hint');
            hint.setAttribute('aria-hidden', 'true');
            hint.textContent = 'hold for the menu';
            this.layer.appendChild(hint);
        }
        return this.layer;
    }

    mountLayer() {
        if (!this.layer) {
            this.layer = document.createElementNS(RAD_SVG_NS, 'svg');
            this.layer.setAttribute('class', 'rad-layer');
            // A ring is a menu. It handles its own keys and has always been
            // operable without a pointer; it was never *announced*, so a
            // screen reader met eight unlabelled shapes. The roles say what
            // the geometry already meant.
            this.layer.setAttribute('role', 'menu');
            document.body.appendChild(this.layer);
        }
        return this.layer;
    }

    renderRing() {
        this.mountLayer();
        this.layer.replaceChildren();
        this.layer.classList.remove('is-resting');

        const { r0, r1 } = this.geometry;
        const { x, y } = this.centre;
        const n = this.spec.items.length;

        const group = document.createElementNS(RAD_SVG_NS, 'g');
        group.setAttribute('transform', `translate(${x} ${y})`);

        // The board the wedges sit on.
        //
        // rad-android draws one soft, low-alpha blob behind its nodes - the
        // literal painter's palette the paint daubs are arranged on, which is
        // where `palette` as a word for a ring comes from in the first place.
        // Purely decorative: it carries no state, answers to no gesture, and a
        // renderer that dropped it would lose nothing a person needs to read.
        // It is here because a ring floating on the bare rack reads as pasted
        // over the rack, and this gives it something to be on.
        const backing = document.createElementNS(RAD_SVG_NS, 'circle');
        backing.setAttribute('r', r1 * 1.08);
        backing.setAttribute('class', 'rad-backing');
        backing.setAttribute('aria-hidden', 'true');
        group.appendChild(backing);

        this.spec.items.forEach((menuItem, index) => {
            const wedge = document.createElementNS(RAD_SVG_NS, 'path');
            wedge.setAttribute('d', this.wedgePath(index, n, r0, r1));
            const classes = ['rad-wedge'];
            if (index === this.machine.highlight) classes.push('is-highlighted');
            if (menuItem.destructive) classes.push('is-destructive');
            if (menuItem.enabled === false) classes.push('is-disabled');
            if (menuItem.children) classes.push('has-children');
            wedge.setAttribute('class', classes.join(' '));

            // Each wedge is an item, and says which one it is, whether it
            // opens a submenu, whether it can be chosen, and whether it is the
            // one under the pointer. Without the last of those a reader
            // following the ring by ear has no idea where they are.
            wedge.setAttribute('role', 'menuitem');
            wedge.setAttribute('aria-label', menuItem.label);
            wedge.setAttribute('aria-setsize', String(n));
            wedge.setAttribute('aria-posinset', String(index + 1));
            if (menuItem.children) wedge.setAttribute('aria-haspopup', 'menu');
            if (menuItem.enabled === false) wedge.setAttribute('aria-disabled', 'true');
            if (index === this.machine.highlight) {
                wedge.setAttribute('aria-current', 'true');
            }

            group.appendChild(wedge);

            const mid = (-90 + (index + 0) * (360 / n)) * Math.PI / 180;
            const labelRadius = (r0 + r1) / 2;
            const text = document.createElementNS(RAD_SVG_NS, 'text');
            text.setAttribute('x', Math.cos(mid) * labelRadius);
            text.setAttribute('y', Math.sin(mid) * labelRadius);
            text.setAttribute('class', 'rad-label');
            // The wedge carries the label already, so the text is decoration
            // to a reader and would otherwise be announced a second time.
            text.setAttribute('aria-hidden', 'true');
            // `▸`, the mark rad-android uses on a synthetic verb that opens
            // something (`Edit ▸`). A plain dingbat rather than an emoji, so a
            // high-contrast or monochrome rendering stays exactly as legible.
            const shown = menuItem.short || menuItem.label;
            text.textContent = menuItem.children ? `${shown} ▸` : shown;
            group.appendChild(text);
        });

        const hubR = r0;

        const hub = document.createElementNS(RAD_SVG_NS, 'circle');
        hub.setAttribute('r', hubR);
        hub.setAttribute('class', 'rad-hub');
        group.appendChild(hub);

        hub.setAttribute('aria-hidden', 'true');

        // The hub reads the highlighted item's full name, wrapped across lines
        // rather than cut.
        //
        // rad-android's rule, and the reason its wedges can be icons: the hub
        // is the one place any full name ever appears, so a wedge only ever has
        // to be recognised and never read. Here it means a wedge can say
        // `Subharmonic` while the hub says `Subharmonicon` - and nothing is
        // ever truncated, because the contract bans the ellipsis that would
        // make truncation look deliberate.
        //
        // With nothing highlighted it falls back to what the ring is *of*,
        // which is the question you have before you have aimed at anything.
        // `◂ Back` whenever a tap on the hub would step back rather than
        // commit forward.
        //
        // rad-android found this by using the thing: back already worked and
        // had no affordance at all, so the way out of a submenu was something
        // you knew or did not. Here it is the same gesture - release on the
        // hub inside a submenu ascends - and it was equally unmarked. The
        // ring's own title moves into the line below it, so nothing is lost.
        // The hub names the ring, or whatever is being pointed at. It briefly
        // carried the rack's readout as well, back when a pinned ring was the
        // only place that could live; the bar carries it now, and a hub saying
        // the same thing was two answers to one question.
        const highlighted = this.spec.items[this.machine.highlight];
        const heading = highlighted
            ? highlighted.label
            : (this.stack.length
                ? `◂ Back  ${this.spec.title || ''}`
                : (this.spec.title || ''));

        const title = document.createElementNS(RAD_SVG_NS, 'text');
        title.setAttribute('class', 'rad-title');
        title.setAttribute('id', 'rad-menu-title');
        if (highlighted) title.setAttribute('data-highlighted', 'true');
        if (!highlighted && this.stack.length) {
            title.setAttribute('data-back', 'true');
        }

        // Word boundaries only, and never mid-word: a break that falls inside a
        // word reads as a truncation, which is the thing being avoided.
        const lines = wrapHubLabel(heading, hubR);
        const first = 4 - ((lines.length - 1) * 7);
        lines.forEach((line, index) => {
            const span = document.createElementNS(RAD_SVG_NS, 'tspan');
            span.setAttribute('x', 0);
            span.setAttribute('y', first + index * 14);
            span.textContent = line;
            title.appendChild(span);
        });
        group.appendChild(title);

        // What this ring is *of* — the device, the cable, the rack.
        this.layer.setAttribute('aria-label', this.spec.title || 'Menu');
        this.layer.appendChild(group);
    }

    // Wedge i is centred at -90 + i*(360/n) and spans +/- 180/n around it.
    wedgePath(index, n, r0, r1) {
        const step = 360 / n;
        const centre = -90 + index * step;
        const from = (centre - step / 2) * Math.PI / 180;
        const to = (centre + step / 2) * Math.PI / 180;
        const large = step > 180 ? 1 : 0;

        const p = (radius, angle) => `${Math.cos(angle) * radius} ${Math.sin(angle) * radius}`;
        return [
            `M ${p(r0, from)}`,
            `L ${p(r1, from)}`,
            `A ${r1} ${r1} 0 ${large} 1 ${p(r1, to)}`,
            `L ${p(r0, to)}`,
            `A ${r0} ${r0} 0 ${large} 0 ${p(r0, from)}`,
            'Z',
        ].join(' ');
    }
}
