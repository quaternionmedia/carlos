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
        this.longPressTimer = null;
        this.pressOrigin = null;

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

        this.render();
        document.addEventListener('pointermove', this.onPointerMove);
        document.addEventListener('pointerup', this.onPointerUp);
        document.addEventListener('keydown', this.onKeyDown, true);
        return this;
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

    close({ silent = false } = {}) {
        this.pinned = false;
        this.disarm();
        if (this.layer) {
            this.layer.remove();
            this.layer = null;
        }
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

    onPointerMove(event) {
        this.cancelLongPress(event);
        if (!this.open) return;
        const { r, thetaDeg } = this.toPolar(event.clientX, event.clientY);
        this.machine.send({ type: 'move', r, thetaDeg });
        this.afterEvent();
    }

    onPointerUp(event) {
        this.disarm();
        if (!this.open) return;
        const { r, thetaDeg } = this.toPolar(event.clientX, event.clientY);
        this.machine.send({ type: 'up', r, thetaDeg });
        // This release belongs to the menu, so nothing below it should also act
        // on it - neither the rest of this event nor the click that follows.
        event.stopPropagation();
        this.suppressNextClick();
        this.afterEvent();
    }

    onKeyDown(event) {
        if (!this.open) return;
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
        this.layer.replaceChildren();

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

        // A pinned hub is bigger, because it has something to say. Only the
        // *drawn* radius grows: the dead zone the machine cancels inside is
        // `r0` and stays `r0`, so the gesture is identical whether or not the
        // ring is pinned. Same split rad-android makes between the shape a
        // wedge appears to have and the band it answers to.
        const hubR = this.pinned ? r0 * 1.6 : r0;

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
        // A pinned ring is idle most of the time, and an idle hub that only
        // repeats the ring's own name is a hub wasted. It reads the rack
        // instead - what is in it and which way it faces - which is what the
        // panel this replaced was for.
        const highlighted = this.spec.items[this.machine.highlight];
        const idle = this.pinned && this.readout
            ? (this.readout() || this.spec.title || '')
            : (this.spec.title || '');
        const heading = highlighted
            ? highlighted.label
            : (this.stack.length ? `◂ Back  ${this.spec.title || ''}` : idle);

        const title = document.createElementNS(RAD_SVG_NS, 'text');
        title.setAttribute('class', 'rad-title');
        title.setAttribute('id', 'rad-menu-title');
        if (highlighted) title.setAttribute('data-highlighted', 'true');
        if (!highlighted && this.stack.length) {
            title.setAttribute('data-back', 'true');
        }

        // Word boundaries only, and never mid-word: a break that falls inside a
        // word reads as a truncation, which is the thing being avoided.
        // Four lines when pinned: the readout is four facts and dropping one
        // silently would be the truncation this contract bans, wearing a
        // different hat.
        const lines = wrapHubLabel(heading, hubR, undefined, this.pinned ? 4 : 3);
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
