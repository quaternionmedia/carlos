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
            this.close();
            return;
        }
        const intent = radIntent(chosen.action, this.context, chosen.id);
        if (chosen.payload) intent.payload = chosen.payload;
        this.close();
        this.onIntent(intent);
    }

    // --- rendering --------------------------------------------------------
    render() {
        if (!this.layer) {
            this.layer = document.createElementNS(RAD_SVG_NS, 'svg');
            this.layer.setAttribute('class', 'rad-layer');
            document.body.appendChild(this.layer);
        }
        this.layer.replaceChildren();

        const { r0, r1 } = this.geometry;
        const { x, y } = this.centre;
        const n = this.spec.items.length;

        const group = document.createElementNS(RAD_SVG_NS, 'g');
        group.setAttribute('transform', `translate(${x} ${y})`);

        this.spec.items.forEach((menuItem, index) => {
            const wedge = document.createElementNS(RAD_SVG_NS, 'path');
            wedge.setAttribute('d', this.wedgePath(index, n, r0, r1));
            const classes = ['rad-wedge'];
            if (index === this.machine.highlight) classes.push('is-highlighted');
            if (menuItem.destructive) classes.push('is-destructive');
            if (menuItem.enabled === false) classes.push('is-disabled');
            if (menuItem.children) classes.push('has-children');
            wedge.setAttribute('class', classes.join(' '));
            group.appendChild(wedge);

            const mid = (-90 + (index + 0) * (360 / n)) * Math.PI / 180;
            const labelRadius = (r0 + r1) / 2;
            const text = document.createElementNS(RAD_SVG_NS, 'text');
            text.setAttribute('x', Math.cos(mid) * labelRadius);
            text.setAttribute('y', Math.sin(mid) * labelRadius);
            text.setAttribute('class', 'rad-label');
            text.textContent = menuItem.children ? `${menuItem.label} ›` : menuItem.label;
            group.appendChild(text);
        });

        const hub = document.createElementNS(RAD_SVG_NS, 'circle');
        hub.setAttribute('r', r0);
        hub.setAttribute('class', 'rad-hub');
        group.appendChild(hub);

        const title = document.createElementNS(RAD_SVG_NS, 'text');
        title.setAttribute('class', 'rad-title');
        title.setAttribute('y', 4);
        title.textContent = this.stack.length
            ? `‹ ${this.spec.title || ''}`
            : (this.spec.title || '');
        group.appendChild(title);

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
