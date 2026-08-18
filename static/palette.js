// ===================================================================
// TOOL PALETTE — a floating panel, not a menu
// ===================================================================
// This holds the things rad's ring cannot express: a patch name is a text
// field, a file input is a file input. It resolves no context and emits no
// intent, which is what makes it a panel rather than a second menu system —
// the thing `docs/rad-integration.md` says this app will not have.
//
// It floats because a rack is the width of the window. The strip this replaces
// was pinned across the bottom and took a slice out of every rack whether or
// not anyone was naming a patch.
//
// No DOM measurement is trusted that has not been taken: every clamp below
// reads the element's real box rather than assuming the width the stylesheet
// asks for, because the two disagree the moment anything inside wraps.

// Where it opens before anyone has moved it, as an inset from a named corner.
// A corner rather than a coordinate, so the default is right on a phone and on
// a wide desktop without a breakpoint.
const PALETTE_DEFAULT_CORNER = 'top-right';
const PALETTE_INSET = { x: 20, y: 68 };

// How much of the palette must stay on screen. Dragging it fully off the edge
// loses it with no way back short of the reset action, so the grip is kept
// reachable at every edge.
const PALETTE_KEEP_VISIBLE = 64;

// Where a moved palette is remembered. Local to the browser and deliberately
// not in the patch document: where someone put a window is not part of a rig,
// and a rack exported on one screen would carry a position meaningless on
// another. See docs/patch-format.md on what the format is for.
const PALETTE_STORE_KEY = 'carlos.palette.position';

// How far an arrow key moves it, and with Shift.
const PALETTE_STEP = 12;
const PALETTE_STEP_COARSE = 60;

class Palette {
    constructor({ element, grip, storage = null, onMove = null } = {}) {
        this.element = element;
        this.grip = grip;
        // Injected so the tests can drive a real one without a browser, and so
        // a browser with storage disabled degrades to "opens at the default
        // every time" rather than throwing on load.
        this.storage = storage;
        this.onMove = onMove;
        this.position = null;

        if (!this.element) return;
        this.restore();
        this.bind();
    }

    // ---- geometry ----

    viewport() {
        return {
            width: window.innerWidth || 0,
            height: window.innerHeight || 0,
        };
    }

    size() {
        const rect = this.element?.getBoundingClientRect?.();
        return { width: rect?.width || 0, height: rect?.height || 0 };
    }

    // The default, resolved against the window it is actually opening in.
    defaultPosition() {
        const view = this.viewport();
        const box = this.size();
        const corner = this.element?.dataset?.defaultCorner || PALETTE_DEFAULT_CORNER;
        const right = view.width - box.width - PALETTE_INSET.x;
        const bottom = view.height - box.height - PALETTE_INSET.y;

        switch (corner) {
            case 'top-left':
                return { x: PALETTE_INSET.x, y: PALETTE_INSET.y };
            case 'bottom-left':
                return { x: PALETTE_INSET.x, y: bottom };
            case 'bottom-right':
                return { x: right, y: bottom };
            case 'top-right':
            default:
                return { x: right, y: PALETTE_INSET.y };
        }
    }

    // Keep at least a grip's worth on screen, at every edge. A palette dragged
    // past the corner is gone, and "gone" is indistinguishable from "broken".
    clamp({ x, y }) {
        const view = this.viewport();
        const box = this.size();
        const keep = Math.min(PALETTE_KEEP_VISIBLE, box.width || PALETTE_KEEP_VISIBLE);

        return {
            x: Math.round(Math.min(
                Math.max(x, keep - box.width),
                Math.max(view.width - keep, 0)
            )),
            y: Math.round(Math.min(
                Math.max(y, 0),                         // never above the top edge
                Math.max(view.height - keep, 0)
            )),
        };
    }

    // ---- placement ----

    moveTo(position, { remember = true } = {}) {
        // A palette with no element is inert, not fatal. `main.js` builds one
        // from `getElementById` before it knows the template rendered, and the
        // reset action would otherwise throw on a page that has no panel.
        if (!this.element) return null;

        const at = this.clamp(position);
        this.position = at;

        this.element.style?.setProperty?.('left', `${at.x}px`);
        this.element.style?.setProperty?.('top', `${at.y}px`);
        // Until this runs the stylesheet is holding it against the right edge.
        // Both would fight the drag, so the class drops `right`.
        this.element.classList?.add?.('is-placed');

        if (remember) this.remember(at);
        this.onMove?.(at);
        return at;
    }

    reset() {
        this.forget();
        return this.moveTo(this.defaultPosition(), { remember: false });
    }

    // The window changed shape under a palette that was placed against the old
    // one. Re-clamping is enough: a palette that was on screen stays where it
    // is, and one that would now be off it comes back to the nearest edge.
    reflow() {
        if (!this.position) return this.moveTo(this.defaultPosition(), { remember: false });
        return this.moveTo(this.position, { remember: false });
    }

    // ---- memory ----

    restore() {
        const saved = this.read();
        return saved
            ? this.moveTo(saved, { remember: false })
            : this.moveTo(this.defaultPosition(), { remember: false });
    }

    read() {
        try {
            const raw = this.storage?.getItem?.(PALETTE_STORE_KEY);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            // Anything could be under that key: another build, a hand edit, a
            // half-written value. A stored position that is not two numbers is
            // no position, and the default is a better answer than NaN.
            if (!Number.isFinite(parsed?.x) || !Number.isFinite(parsed?.y)) return null;
            return { x: parsed.x, y: parsed.y };
        } catch {
            // Storage can be absent, full, or refused outright by the browser's
            // privacy settings. None of those should stop the palette drawing.
            return null;
        }
    }

    remember(at) {
        try {
            this.storage?.setItem?.(PALETTE_STORE_KEY, JSON.stringify(at));
        } catch {
            // See `read`. A palette that cannot be remembered still works.
        }
    }

    forget() {
        try {
            this.storage?.removeItem?.(PALETTE_STORE_KEY);
        } catch {
            // See `read`.
        }
    }

    // ---- input ----

    bind() {
        this.grip?.addEventListener?.('pointerdown', (event) => this.startDrag(event));
        this.grip?.addEventListener?.('keydown', (event) => this.nudge(event));
        window.addEventListener?.('resize', () => this.reflow());
    }

    startDrag(event) {
        if (event.button !== 0) return;
        event.preventDefault();

        // Where in the palette the grab landed, so it does not jump its own
        // corner under the cursor on the first move.
        const from = this.position || this.defaultPosition();
        const offset = { x: event.clientX - from.x, y: event.clientY - from.y };

        this.grip.setPointerCapture?.(event.pointerId);
        this.element.classList?.add?.('is-moving');

        const onMove = (moveEvent) => {
            this.moveTo(
                { x: moveEvent.clientX - offset.x, y: moveEvent.clientY - offset.y },
                { remember: false }
            );
        };

        const onUp = () => {
            this.grip.removeEventListener?.('pointermove', onMove);
            this.grip.removeEventListener?.('pointerup', onUp);
            this.grip.removeEventListener?.('pointercancel', onUp);
            this.element.classList?.remove?.('is-moving');
            // Written once, at the end. Remembering every frame would be a
            // hundred writes per drag for one answer.
            if (this.position) this.remember(this.position);
        };

        this.grip.addEventListener?.('pointermove', onMove);
        this.grip.addEventListener?.('pointerup', onUp);
        this.grip.addEventListener?.('pointercancel', onUp);
    }

    nudge(event) {
        if (event.ctrlKey || event.altKey || event.metaKey) return;

        const step = event.shiftKey ? PALETTE_STEP_COARSE : PALETTE_STEP;
        const by = { ArrowLeft: [-step, 0], ArrowRight: [step, 0],
                     ArrowUp: [0, -step], ArrowDown: [0, step] }[event.key];

        if (by) {
            const from = this.position || this.defaultPosition();
            this.moveTo({ x: from.x + by[0], y: from.y + by[1] });
        } else if (event.key === 'Home') {
            this.reset();
        } else {
            // Everything else still belongs to the rack, `m` and Escape
            // included. Only a key this handled is taken.
            return;
        }

        event.preventDefault();
        event.stopPropagation();
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        Palette,
        PALETTE_DEFAULT_CORNER,
        PALETTE_INSET,
        PALETTE_KEEP_VISIBLE,
        PALETTE_STORE_KEY,
        PALETTE_STEP,
        PALETTE_STEP_COARSE,
    };
}
