// ===================================
// INTERCHANGE FORMAT
// ===================================
// Mirrors src/patch_format.py. Both sides of the seam name the same format and
// the same version; a document this file writes is a document that module reads.
const PATCH_FORMAT = 'carlos.patch';
// What this build writes, and what it can read. An older version is upgraded
// by a named step; anything newer is refused rather than guessed at.
const PATCH_VERSION = 3;
const PATCH_READS = [1, 2, 3];

// The sides a device can have, in the order it cycles through them. A device
// declares only the ones it uses: a Scarlett has a front and a back, a K.O. II
// has a face and a top edge and no back at all.
const SIDE_ORDER = ['front', 'back', 'top', 'bottom', 'left', 'right'];

// How wide a cable is to aim at, as against the 2px it is drawn at. Roughly a
// fingertip, so a cable can be picked on a touchscreen and not only with a
// mouse.
const CABLE_HIT_WIDTH = 16;

// How far a hidden socket's anchor is kept from the corners of its device, as a
// fraction of the edge. Without it the first and last socket on a face anchor
// exactly at the corners, and a lead there reads as leaving the device
// diagonally rather than through its edge.
const SILHOUETTE_INSET = 0.12;

// How far a cable hangs. A longer run hangs further, which is what a cable
// does; the small per-cable term is what keeps a stereo pair between the same
// two devices two followable lines instead of one thick one.
const CABLE_SAG_MIN = 26;
const CABLE_SAG_RATIO = 0.12;
const CABLE_SAG_MAX = 90;
const CABLE_SAG_SPREAD = 14;

// Device text comes from `catalogue/devices/*.json` and is interpolated into
// attributes. A label holding a quote would otherwise end the attribute early
// and swallow the rest of the tag - a rendering bug that would look like a
// broken device rather than a broken string.
function attr(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
        .replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ===================================
// CORE COMPONENT: Parameter
// ===================================
class Parameter {
    constructor(name, label, minValue = 0, maxValue = 127, defaultValue = null) {
        this.name = name;
        this.label = label;
        this.minValue = minValue;
        this.maxValue = maxValue;
        this.value = defaultValue !== null ? defaultValue : (minValue + maxValue) / 2;
        // Kept so a knob can be put back. Not exported: the catalogue is where
        // a device's defaults live, and a document carrying its own copy could
        // only ever disagree with the definition it was built from.
        this.defaultValue = this.value;
        this.rotation = this.valueToRotation(this.value);
    }

    // Where this stands in its own range, 0..1. A knob turns and a fader
    // slides; both are this one number, drawn differently.
    get fraction() {
        return (this.value - this.minValue) / (this.maxValue - this.minValue);
    }

    valueToRotation(value) {
        const normalized = (value - this.minValue) / (this.maxValue - this.minValue);
        return normalized * 270 - 135; // Map to -135° to +135°
    }

    rotationToValue(rotation) {
        const normalized = (rotation + 135) / 270;
        return normalized * (this.maxValue - this.minValue) + this.minValue;
    }

    setValue(value) {
        this.value = Math.max(this.minValue, Math.min(this.maxValue, value));
        this.rotation = this.valueToRotation(this.value);
    }

    setRotation(rotation) {
        this.rotation = Math.max(-135, Math.min(135, rotation));
        this.value = this.rotationToValue(this.rotation);
    }

    // Rotation is derived from value, so it is never exported. See
    // src/patch_format.py for why storing both is a contradiction waiting.
    getState() {
        return { value: this.value };
    }

    setState(state) {
        this.setValue(state.value);
    }
}

// A socket is a button: press one, press its partner, and a cable exists. Says
// which side it is on, because with devices turning independently that is the
// difference between a lead you can see and one that runs round the back.
function jackAria(jack, side) {
    const label = `${jack.label || jack.name} (${jack.signal} ${jack.type}, ${side})`;
    return `tabindex="0" role="button" title="${attr(label)}" aria-label="${attr(label)}"`;
}

// Every side a layout puts something on. Mirrors `Layout.sides_used()`.
function sidesUsedByLayout(layout) {
    if (!layout) return [];
    const placed = [
        ...Object.values(layout.controls || {}),
        ...Object.values(layout.jacks || {}),
        ...(layout.features || []),
    ];
    return placed.map(p => p.side || 'front');
}

// The proportion of one face. Mirrors `Layout.aspect_of()` and `Box.aspect()`
// in src/catalogue.py; `tests/test_catalogue.py` checks the two agree over
// every device in the catalogue rather than trusting that they do.
//
// One box, six faces: front and back are width by height, top and bottom are
// width by depth, left and right are depth by height. A single per-device
// aspect only ever described the front, and was applied to every side because
// nothing else was there to apply.
function aspectOf(layout, side) {
    if (!layout) return 1;
    const box = layout.box;
    if (!box) return layout.aspect || 1;
    if (side === 'front' || side === 'back') return box.width / box.height;
    if (side === 'top' || side === 'bottom') return box.width / box.depth;
    return box.depth / box.height;
}

// How flat a face may be drawn before its proportion is compressed.
//
// A Stage 3's front is 1284mm by 120mm - an aspect of 10.7. Drawn true at any
// usable width it is about fifty pixels tall, which is not enough to draw the
// keybed, three screens and the drawbars that are the reason to draw it at all.
// So extremes are pulled toward square by a fixed exponent: the ordering and
// the sense of "very wide and shallow" survive, the detail becomes legible, and
// the compression is one documented function rather than a per-device fudge.
//
// The measured aspect is kept on the element as `--true-aspect`, so what was
// measured is still readable off the panel that was drawn.
const ASPECT_COMPRESSION = 0.6;

function drawnAspect(aspect) {
    if (!(aspect > 0)) return 1;
    return aspect >= 1
        ? Math.pow(aspect, ASPECT_COMPRESSION)
        : 1 / Math.pow(1 / aspect, ASPECT_COMPRESSION);
}

// A device's drawn width, from its real one. Sub-linear for the same reason the
// aspect is: a Eurorack module beside an 88-key stage piano is a twentieth of
// its width, and drawn to scale either the piano does not fit or the module is
// a sliver. The square root keeps the ordering and the obviousness of the
// difference while leaving the small device usable.
const PANEL_REFERENCE_MM = 300;   // about a DFAM: the middle of the catalogue
const PANEL_REFERENCE_PX = 300;
const PANEL_MIN_PX = 150;
const PANEL_MAX_PX = 680;

function drawnWidth(layout) {
    const mm = layout?.box?.width;
    if (!mm) return null;
    const scaled = PANEL_REFERENCE_PX * Math.sqrt(mm / PANEL_REFERENCE_MM);
    return Math.round(Math.min(PANEL_MAX_PX, Math.max(PANEL_MIN_PX, scaled)));
}

// A number in 0..1 that belongs to one cable and does not change.
//
// Derived from the sockets it joins, which is the same thing that identifies
// it, so a cable keeps its own hang however many others are added or removed
// around it. An index into the connection list would have made every cable
// move whenever any cable was unpatched.
function cableSpread(source, target) {
    const key = PatchBayManager.keyOf(source, target);
    let hash = 0;
    for (let i = 0; i < key.length; i++) {
        hash = (hash * 31 + key.charCodeAt(i)) | 0;
    }
    return ((hash >>> 0) % 1000) / 1000;
}

// A keyboard, as a run of white keys with the blacks sitting between them.
//
// Drawn from the note it starts on rather than always from C, because an 88 is
// an A-to-C instrument and one drawn from C has the wrong key under every hand
// position. The pattern is the octave's semitone map; a black key follows a
// white one wherever the map says the next semitone is black.
const WHITE_STEPS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const BLACK_AFTER = new Set([0, 2, 5, 7, 9]);   // C D F G A carry a sharp

function keybed(keys, from = 'C') {
    const total = Math.max(1, Math.min(128, Number(keys) || 1));
    const start = WHITE_STEPS[from] ?? 0;

    // Which of the `total` semitones are white, so the whites can be laid out
    // evenly and the blacks hung off them.
    const naturals = [];
    for (let i = 0; i < total; i++) {
        const semitone = (start + i) % 12;
        if (SEMITONE_IS_WHITE[semitone]) naturals.push({ index: i, semitone });
    }
    if (!naturals.length) return '';

    const width = 100 / naturals.length;
    const whites = naturals.map((n, at) =>
        `<span class="irl-key" style="left:${at * width}%; width:${width}%"></span>`
    ).join('');

    // A black key sits on the boundary between its white and the next one, and
    // only if that next semitone is actually in range.
    const blacks = naturals.map((n, at) => {
        if (!BLACK_AFTER.has(n.semitone)) return '';
        if (n.index + 1 >= total) return '';
        return `<span class="irl-key is-sharp"
                      style="left:${(at + 1) * width - width * 0.3}%;
                             width:${width * 0.6}%"></span>`;
    }).join('');

    return whites + blacks;
}

const SEMITONE_IS_WHITE = {
    0: true, 1: false, 2: true, 3: false, 4: true, 5: true,
    6: false, 7: true, 8: false, 9: true, 10: false, 11: true,
};

// A grid of pads or buttons.
//
// A cell that emits is a real button: focusable, pressable by pointer or key,
// and named for where it is. A grid that emits nothing is still drawn, because
// the shape of a device is worth drawing - it just answers to nobody.
//
// Cells are numbered across then down, and the note or controller they send
// climbs with them: the first cell sends what the entry declares and each one
// after it sends the next. That is how a grid controller is laid out, and it
// means an entry declares two numbers rather than sixty-four.
function grid(feature) {
    const rows = Math.max(1, Math.min(32, Number(feature.rows) || 1));
    const cols = Math.max(1, Math.min(32, Number(feature.cols) || 1));
    const cells = [];

    for (let index = 0; index < rows * cols; index++) {
        const row = Math.floor(index / cols) + 1;
        const column = (index % cols) + 1;
        const where = rows > 1 && cols > 1
            ? `row ${row}, column ${column}`
            : `${index + 1}`;

        if (!feature.emits) {
            cells.push('<span class="irl-cell" aria-hidden="true"></span>');
            continue;
        }

        cells.push(
            `<button type="button" class="irl-cell" data-cell="${index}"`
            + ` aria-label="${attr(`${feature.label || 'Pad'} ${where}`)}"`
            + ` title="${attr(cellLegend(feature, index))}"></button>`
        );
    }

    return `<div class="irl-grid" style="--rows:${rows}; --cols:${cols}">`
        + cells.join('') + '</div>';
}

// What one cell sends, in words. Shown on hover and used by the status line, so
// the answer to "what did that do" is the same in both places.
function cellLegend(feature, index) {
    if (feature.emits === 'midi-note') {
        return `note ${feature.note + index} ch ${feature.channel}`;
    }
    if (feature.emits === 'midi-cc') {
        return `CC ${feature.controller + index} ch ${feature.channel}`;
    }
    return `${feature.label || 'button'} ${index + 1}`;
}

// The host, if there is one yet.
//
// `main.js` declares `const system` and this file is loaded before it, so a
// screen filled during the very first render runs while that binding does not
// exist. An undeclared identifier throws on read - optional chaining guards a
// null value, not a missing name - so every reach for the host goes through
// here.
function hostSystem() {
    return typeof system === 'undefined' ? null : system;
}

// A knob is a slider that happens to be round. Saying so is what makes it
// reachable by keyboard and legible to a screen reader; the two arrangements
// draw it differently and mean exactly the same control.
function knobAria(param) {
    return `tabindex="0" role="slider" title="${attr(param.label)}"`
        + ` aria-label="${attr(param.label)}"`
        + ` aria-valuemin="${attr(param.minValue)}"`
        + ` aria-valuemax="${attr(param.maxValue)}"`
        + ` aria-valuenow="${attr(Math.round(param.value))}"`;
}

// ===================================
// CORE COMPONENT: Jack
// ===================================
class Jack {
    constructor(name, type, signal, side = 'front', label = null, element = null) {
        this.name = name;
        this.label = label || name;
        this.type = type; // 'input' or 'output'
        this.signal = signal; // 'audio', 'cv', 'gate', etc.
        this.side = side; // 'front' or 'back'
        this.element = element;
        this.connections = [];
        this.module = null; // set by EurorackModule.addJack
    }

    // Reachable only when its own module is showing the side it sits on.
    // Each module turns independently, so this is a per-jack question.
    isVisible() {
        return this.module?.view === this.side;
    }

    // A cable needs opposite types. Sides are deliberately not checked: running
    // a lead from the front panel round to a rear header is legal, and being
    // able to lose track of one is part of the instrument.
    canConnectTo(otherJack) {
        return this.type !== otherJack.type && this !== otherJack;
    }

    // Why a connection was refused, for the status line. Null when it is legal.
    refusalReason(otherJack) {
        if (this === otherJack) return 'A jack cannot patch into itself';
        if (this.type === otherJack.type) return `Two ${this.type}s cannot be patched together`;
        return null;
    }

    connect(otherJack) {
        if (this.canConnectTo(otherJack)) {
            this.connections.push(otherJack);
            otherJack.connections.push(this);
            this.element?.classList.add('connected');
            otherJack.element?.classList.add('connected');
            return true;
        }
        return false;
    }

    disconnect() {
        this.connections.forEach(jack => {
            jack.connections = jack.connections.filter(conn => conn !== this);
            if (jack.connections.length === 0) {
                jack.element?.classList.remove('connected');
            }
        });
        this.connections = [];
        this.element?.classList.remove('connected');
    }
}

// ===================================
// CORE COMPONENT: EurorackModule
// ===================================
class EurorackModule {
    constructor(type, name) {
        this.type = type;
        this.name = name;
        this.id = `module_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
        this.parameters = new Map();
        this.jacks = new Map();
        this.element = null;
        // The sides this device actually has, in cycling order. Set from the
        // catalogue entry; `front` is always among them, because every device
        // has a face you look at and it is where the knobs are drawn.
        this.sides = ['front'];
        // Panel layout for `irl` display, if the catalogue carries one.
        this.layout = null;
        this.mode = 'minimal';
        // Each device faces whichever way it was last turned. A module turns in
        // place: turning one is not the rack moving.
        this.view = 'front';
    }

    setSides(sides) {
        const used = new Set([...(sides || []), 'front']);
        this.sides = SIDE_ORDER.filter(side => used.has(side));
        if (!this.sides.includes(this.view)) this.view = this.sides[0];
        return this.sides;
    }

    // Is there anything on this side? A device can have a side that carries
    // nothing - a stage piano's front is the blank lip under its keys - and
    // turning a device to a face with nothing on it is a thing you might do
    // deliberately but never a thing it should arrive doing.
    hasContentOn(side) {
        for (const jack of this.jacks.values()) {
            if (jack.side === side) return true;
        }

        // Asked of the mode, not of the device, because the two modes draw
        // different things in different places. `irl` lays out a measured
        // panel; `minimal` puts every parameter on the front and nothing on
        // any other face. So a Stage 3's front is a blank lip when laid out
        // and fifteen knobs when abstract, and both answers are right.
        //
        // A device with no measured layout falls back to the minimal
        // arrangement even in `irl`, so it is asked the minimal question.
        if (this.mode === 'irl' && this.layout) {
            return sidesUsedByLayout(this.layout).includes(side);
        }
        return side === this.face && this.parameters.size > 0;
    }

    // The side this device is looked at from, whichever way it is drawn.
    //
    // The catalogue's `layout.face`, defaulting to `front`. It used to mean
    // something only to `irl`, while `minimal` drew every parameter on the
    // front regardless - so a Launchpad X was played from its top when laid
    // out and from its front when abstract, and its blank lip was empty in one
    // mode and covered in knobs in the other. A device has one face. Which
    // mode you are drawing it in is not an opinion about which side that is.
    get face() {
        return this.layout?.face || 'front';
    }

    // The sides this device actually shows, which is not every side it has.
    //
    // Four devices in the catalogue have a front with nothing on it - the
    // blank lip under a stage piano's keys, under a Launchpad's pads - and
    // turning one used to walk you through that lip on the way to the back.
    // A blank rectangle is not a view of anything, so it is not offered.
    //
    // The fallback matters more than it looks: a device nobody has laid out,
    // with no parameters and no jacks yet, has nothing anywhere. Hiding every
    // face would draw a device with no faces at all, so it keeps them.
    drawnSides() {
        const drawn = this.sides.filter(side => this.hasContentOn(side));
        return drawn.length ? drawn : this.sides;
    }

    // The side to open this device on.
    //
    // A device arrives facing the way the rack is facing - unless that would be
    // a face with nothing on it that the device does not call its own. An empty
    // face means one of two things and only the catalogue can tell them apart:
    // a Stage 3's front really is the blank lip under its keys, while a K.O.
    // II's front is its pads and its screen and nobody has measured them yet.
    // The layout's `face` is that statement, and it defaults to `front`, so
    // every device nobody has laid out behaves exactly as it did.
    preferredView() {
        const drawn = this.drawnSides();

        // The face the catalogue names, when this mode draws it. That entry is
        // the device's own statement about which side you look at: a Qu-24
        // says `top` and means the desk, not the two sockets on its front lip.
        if (drawn.includes(this.face)) return this.face;

        // Otherwise the front, then the top. A device arrives facing the way
        // you would face it, which is not the way the rack happens to be
        // turned - that followed the rack, so a rack turned round to patch its
        // backs handed you the back of every device added after. Turning the
        // rack is a thing you did to look at something; it is not a statement
        // about how the next device should arrive.
        //
        // The declared face is `front` or `top` for every device here, so this
        // is reached only when that face draws nothing in this mode: a Stage 3
        // in `minimal` has no laid-out top, and its fifteen knobs are on the
        // front.
        if (drawn.includes('front')) return 'front';
        if (drawn.includes('top')) return 'top';
        return drawn[0];
    }

    setView(view) {
        // A side that is not drawn cannot be shown. Asking for one is not an
        // error - a saved patch carries the side it was left on, and a device
        // laid out since then may no longer draw it - so it lands on the face
        // this device would have opened on.
        const drawn = this.drawnSides();
        this.view = drawn.includes(view) ? view : this.preferredView();
        if (this.element) {
            this.element.dataset.view = this.view;
            this.element.querySelectorAll('.face').forEach(face => {
                face.classList.toggle('active', face.dataset.side === this.view);
            });
        }
        return this.view;
    }

    // Advance to the next side this device has. A device with one side does not
    // move, which is the right answer rather than a case to guard.
    cycle(step = 1) {
        const drawn = this.drawnSides();
        const at = drawn.indexOf(this.view);
        const next = (at + step + drawn.length) % drawn.length;
        return this.setView(drawn[next]);
    }

    get turns() {
        return this.drawnSides().length > 1;
    }

    // Add a parameter to this module
    addParameter(name, label, min = 0, max = 127, defaultValue = null) {
        this.parameters.set(name, new Parameter(name, label, min, max, defaultValue));
        return this; // For chaining
    }

    // Add a jack to this module
    addJack(name, type, signal, side = 'front', label = null) {
        const jack = new Jack(name, type, signal, side, label);
        jack.module = this;
        this.jacks.set(name, jack);
        return this; // For chaining
    }

    // Render the module HTML: both faces, with only the visible one laid out.
    render() {
        // Which sides are drawn depends on the mode, so a device showing its
        // laid-out top may have no top to show once it is abstract. Settled
        // here, before the markup is built, because every path that changes a
        // mode renders afterwards - reconciling later would name a face active
        // that this mode does not draw.
        if (!this.drawnSides().includes(this.view)) this.view = this.preferredView();

        const moduleEl = document.createElement('div');
        moduleEl.className = 'module';
        moduleEl.dataset.moduleId = this.id;
        moduleEl.dataset.view = this.view;

        // A device drawn as laid out is drawn at something like its real size
        // relative to its neighbours - that comparison is most of what `irl`
        // is for. `minimal` gets no width: it is the abstract box every device
        // shares and fills to fit, and a proportion there would be a claim it
        // does not make.
        const width = this.mode === 'irl' ? drawnWidth(this.layout) : null;
        if (width) moduleEl.style?.setProperty?.('--panel-width', `${width}px`);

        // One face per side the device has, only the active one laid out.
        moduleEl.innerHTML = this.drawnSides().map(side => `
            <div class="face ${side === this.view ? 'active' : ''}" data-side="${side}">
                <div class="module-title">
                    ${this.maker ? `<span class="module-maker">${this.maker}</span>` : ''}
                    ${this.name}
                    ${side === 'front' ? '' : `<span class="side-tag">${side}</span>`}
                </div>
                ${this.faceBody(side)}
            </div>
        `).join('') + `
            <button type="button" class="module-flip"
                    title="${this.turns
                        ? `Turn this device (${this.drawnSides().join(' → ')})`
                        : 'This device has only one side'}"
                    ${this.turns ? '' : 'disabled'}>⇄</button>
        `;

        this.element = moduleEl;
        this.setupInteractions();
        return moduleEl;
    }

    // Which arrangement this face uses. `irl` falls back to `minimal` for a
    // device the catalogue has not laid out, rather than drawing nothing.
    faceBody(side) {
        if (this.mode === 'irl') {
            const panel = this.renderIrlFace(side);
            if (panel) return panel;
        }
        // Parameters go on the face, not on the front. For most devices those
        // are the same side; for the four played from above they are not, and
        // drawing knobs on the blank lip under a stage piano's keys was the
        // abstract mode contradicting the laid-out one about the same device.
        return (side === this.face
                ? `<div class="controls">${this.renderParameters()}</div>`
                : '')
            + this.renderPatchBay(side);
    }

    renderParameters() {
        return Array.from(this.parameters.entries()).map(([name, param]) => `
            <div class="knob" data-param="${attr(name)}" ${knobAria(param)}>
                <div class="knob-base">
                    <div class="knob-indicator"></div>
                </div>
                <div class="knob-label">${param.label}</div>
            </div>
        `).join('');
    }

    // ===============================
    // IRL FACE
    // ===============================
    // The same device, drawn to its own panel proportions with its controls and
    // sockets where they actually sit. Abstract - rings and circles, not a
    // photograph - but arranged accurately, which is what makes a rack
    // recognisable at a glance rather than a row of identical boxes.
    //
    // A device with no layout falls back to the minimal arrangement. The
    // catalogue accepts a device the moment someone describes it, so most of
    // them will have no panel measured for a while, and refusing to draw those
    // would make the mode useless exactly when it is newest.
    renderIrlFace(side) {
        const layout = this.layout;
        if (!layout) return null;

        const on = (place) => (place.side || 'front') === side;
        const controls = Object.entries(layout.controls || {}).filter(([, p]) => on(p));
        const jacks = Object.entries(layout.jacks || {}).filter(([, p]) => on(p));
        const features = (layout.features || []).filter(on);

        const aspect = aspectOf(layout, side);
        // The true proportion is kept on the element even when the drawn one is
        // compressed, so a reader can see what was measured rather than only
        // what was drawn. See `drawnAspect`.
        const style = `--aspect:${drawnAspect(aspect)}; --true-aspect:${aspect}`;

        if (!controls.length && !jacks.length && !features.length) {
            return `<div class="irl-panel is-bare" style="${style}">
                        <span class="irl-empty">Nothing on the ${side}</span>
                    </div>`;
        }

        // Features first: they are the panel a device's controls sit on, and a
        // keybed drawn over its own screen is the wrong way round.
        const panel = features.map(f => this.renderFeature(f)).join('');

        const knobs = controls.map(([name, place]) => {
            const parameter = this.parameters.get(name);
            if (!parameter) return '';
            return this.renderControl(name, place, parameter);
        }).join('');

        const sockets = jacks.map(([name, place]) => {
            const jack = this.jacks.get(name);
            if (!jack) return '';
            return `
                <div class="irl-jack-slot"
                     style="left:${place.x * 100}%; top:${place.y * 100}%;
                            --size:${place.size || 1}">
                    <div class="jack" data-jack="${attr(name)}" data-type="${attr(jack.type)}"
                         data-signal="${attr(jack.signal)}" data-side="${attr(side)}"
                         ${jackAria(jack, side)}></div>
                </div>`;
        }).join('');

        return `<div class="irl-panel" style="${style}">${panel}${knobs}${sockets}</div>`;
    }

    // Which layout feature a rendered group came from. Matched on the label,
    // which is what the markup carries and what the entry names it by.
    featureFor(group) {
        const label = group.getAttribute?.('aria-label');
        return (this.layout?.features || []).find(
            feature => (feature.label || feature.kind) === label
        ) || null;
    }

    // A cell was pressed. The device says what it sent; the system decides what
    // that means, which is what keeps a pad from knowing about MIDI ports.
    press(feature, index, cell) {
        const legend = cellLegend(feature, index);
        cell?.classList?.add('is-struck');
        setTimeout(() => cell?.classList?.remove('is-struck'), 160);

        this.note(legend);
        return hostSystem()?.emit?.(this, feature, index, legend) ?? null;
    }

    // One parameter-backed control, drawn as whatever it actually is. A fader
    // is not a knob turned sideways: a mixer drawn as a field of circles is
    // recognisable as nothing, and the arrangement is the whole point of this
    // mode.
    renderControl(name, place, parameter) {
        const kind = place.kind || 'knob';
        const seat = `left:${place.x * 100}%; top:${place.y * 100}%;`
            + ` --size:${place.size || 1}`;

        if (kind === 'fader' || kind === 'drawbar') {
            const travel = place.length || 0.2;
            const across = (place.orient || 'vertical') === 'vertical';
            return `
                <div class="irl-fader irl-${attr(kind)}" data-param="${attr(name)}"
                     data-orient="${attr(place.orient || 'vertical')}"
                     style="${seat};
                            --travel:${travel * 100}%;
                            ${across ? 'height' : 'width'}:${travel * 100}%"
                     ${knobAria(parameter)}>
                    <div class="irl-fader-slot"></div>
                    <div class="irl-fader-cap"></div>
                </div>`;
        }

        if (kind === 'switch') {
            return `
                <div class="irl-switch" data-param="${attr(name)}" style="${seat}"
                     ${knobAria(parameter)}>
                    <div class="irl-switch-body"><div class="knob-indicator"></div></div>
                </div>`;
        }

        // knob and encoder differ by their ring, which is CSS, not markup.
        return `
            <div class="irl-knob irl-${attr(kind)}" data-param="${attr(name)}"
                 style="${seat}" ${knobAria(parameter)}>
                <div class="knob-base"><div class="knob-indicator"></div></div>
                <span class="irl-knob-label">${parameter.label}</span>
            </div>`;
    }

    // One thing on the panel that carries no value. These are what make a
    // device recognisable: a Stage 3 with its knobs and sockets and no keybed
    // is not a Stage 3, and this mode exists to be recognisable at a glance.
    //
    // What is decoration stays hidden from a screen reader: a keybed this app
    // cannot play, a grille, a logo. What is a control is not decoration - a
    // grid of pads that sends MIDI is announced and reachable, and each cell
    // says which one it is.
    renderFeature(feature) {
        const seat = `left:${feature.x * 100}%; top:${feature.y * 100}%;`
            + ` width:${feature.w * 100}%; height:${feature.h * 100}%`;
        const interactive = Boolean(feature.emits);
        const open = `<div class="irl-feature irl-${attr(feature.kind)}"`
            + ` style="${seat}"`
            + (interactive
                ? ` role="group" aria-label="${attr(feature.label || feature.kind)}"`
                : ' aria-hidden="true"')
            + (feature.source ? ` data-source="${attr(feature.source)}"` : '')
            + (feature.label ? ` title="${attr(feature.label)}"` : '')
            + '>';

        switch (feature.kind) {
            case 'keybed':
                return `${open}${keybed(feature.keys, feature.from_note || 'C')}</div>`;
            case 'pads':
            case 'buttons':
                return `${open}${grid(feature)}</div>`;
            case 'screen':
                // Filled by `refreshScreens`, from the source the entry names.
                // The markup carries no text: a screen with a message baked
                // into it is a screen that is wrong the moment anything moves.
                return `${open}<span class="irl-screen-text"></span></div>`;
            case 'logo':
            case 'label':
                return `${open}<span class="irl-legend">${feature.text || feature.label || ''}</span></div>`;
            default:
                // wheel, grille, vent, plate: shape and shading only, which is
                // CSS keyed on the kind class.
                return `${open}</div>`;
        }
    }

    renderPatchBay(side) {
        const inputs = this.renderJacks('input', side);
        const outputs = this.renderJacks('output', side);

        if (!inputs && !outputs) {
            return `<div class="patch-bay empty-bay">Nothing on the ${side}</div>`;
        }

        return `
            <div class="patch-bay">
                <div class="jack-section">
                    <h4>IN</h4>
                    ${inputs}
                </div>
                <div class="jack-section">
                    <h4>OUT</h4>
                    ${outputs}
                </div>
            </div>
        `;
    }

    renderJacks(type, side) {
        return Array.from(this.jacks.entries())
            .filter(([_, jack]) => jack.type === type && jack.side === side)
            .map(([name, jack]) => `
                <div class="jack-slot">
                    <div class="jack" data-jack="${attr(name)}" data-type="${attr(type)}"
                         data-signal="${attr(jack.signal)}" data-side="${attr(side)}"
                         ${jackAria(jack, side)}></div>
                    <span class="jack-label">${jack.label || name}</span>
                </div>
            `).join('');
    }

    setupInteractions() {
        // Setup parameter knobs. Both classes: `irl` draws a knob as
        // `.irl-knob` at its measured position, and a selector naming only
        // `.knob` left every knob in that mode rendered and dead.
        this.element
            .querySelectorAll('.knob, .irl-knob, .irl-fader, .irl-switch')
            .forEach(knobEl => {
            const paramName = knobEl.dataset.param;
            const parameter = this.parameters.get(paramName);
            if (parameter) {
                this.setupKnob(knobEl, parameter);
            }
        });

        // Setup jacks. Each jack has exactly one element, on its own face.
        this.element.querySelectorAll('.jack').forEach(jackEl => {
            const jackName = jackEl.dataset.jack;
            const jack = this.jacks.get(jackName);
            if (jack && jack.side === jackEl.dataset.side) {
                jack.element = jackEl;
                jackEl.addEventListener('click', (event) => {
                    event.stopPropagation(); // patching a jack is not selecting the module
                    hostSystem()?.patchBay.handleJackClick(jack);
                });
                // Enter and Space are what a button answers to. Patching was
                // pointer-only, which made the whole point of the app so.
                jackEl.addEventListener('keydown', (event) => {
                    if (event.key !== 'Enter' && event.key !== ' ') return;
                    event.preventDefault();
                    event.stopPropagation();
                    hostSystem()?.patchBay.handleJackClick(jack);
                });
            }
        });

        // Turn just this device to its next side.
        this.element.querySelector('.module-flip')?.addEventListener('click', (event) => {
            event.stopPropagation();
            hostSystem()?.turnModule(this.id);
        });

        // Grids that emit. A cell is a button, so it already answers to Enter
        // and Space; the pointer path is separate only because a press should
        // fire on the way down, the way a pad does, rather than on release.
        this.element.querySelectorAll('.irl-feature[role="group"]').forEach(group => {
            const feature = this.featureFor(group);
            if (!feature) return;
            group.querySelectorAll('.irl-cell').forEach(cell => {
                const index = Number(cell.dataset.cell);
                const fire = (event) => {
                    event.stopPropagation();
                    this.press(feature, index, cell);
                };
                cell.addEventListener('pointerdown', (event) => {
                    event.preventDefault();
                    fire(event);
                });
                // The click that follows the press has to be swallowed too.
                // Stopping the pointerdown does not stop it, and the module's
                // own click handler selects the device - which overwrote the
                // status line naming what the pad had just sent, one frame
                // after it appeared.
                cell.addEventListener('click', (event) => event.stopPropagation());
                cell.addEventListener('keydown', (event) => {
                    if (event.key !== 'Enter' && event.key !== ' ') return;
                    event.preventDefault();
                    fire(event);
                });
            });
        });

        this.refreshScreens();

        // Clicking anywhere else on the module selects it, so Tab can act on
        // one device instead of the whole rack.
        this.element.addEventListener('click', () => hostSystem()?.selectModule(this.id));
    }

    // A knob answers to a drag, a wheel and the keyboard. It was a mouse drag
    // and nothing else, which left it unusable by touch and unreachable without
    // a pointer - on a control that is most of what this app is for.
    setupKnob(knobEl, parameter) {
        // A fader has no indicator to turn - it is positioned from `--value`
        // instead. Requiring one here is what would leave every fader on a
        // mixer drawn and dead, which is the same defect `irl` knobs had.
        const indicator = knobEl.querySelector('.knob-indicator');
        if (indicator) {
            indicator.style.transform =
                `translateX(-50%) rotate(${parameter.rotation}deg)`;
        }
        knobEl.style?.setProperty?.('--value', String(parameter.fraction));

        // A step is a fraction of the range, not a constant: a 0..1 parameter
        // and a 0..127 one are the same gesture at different scales.
        const span = parameter.maxValue - parameter.minValue;
        const step = (fine) => span / (fine ? 1000 : 100);

        const paint = (announce = true) => {
            if (indicator) {
                anime({
                    targets: indicator,
                    rotate: parameter.rotation,
                    duration: 50,
                    easing: 'linear',
                });
            }
            knobEl.style?.setProperty?.('--value', String(parameter.fraction));
            // The value a screen reader reads has to be the value on screen.
            knobEl.setAttribute('aria-valuenow', String(Math.round(parameter.value)));
            // What a `parameter` screen shows, and what a `last-event` screen
            // shows when a control rather than a pad was the last thing to
            // move. Set here because this is the one path every kind of
            // control's movement goes through.
            this.lastParameter = `${parameter.label} ${Math.round(parameter.value)}`;
            this.note(this.lastParameter);
            if (announce) {
                hostSystem()?.status.update(`${parameter.label}: ${Math.round(parameter.value)}`);
            }
        };

        const nudge = (delta) => {
            parameter.setValue(parameter.value + delta);
            paint();
        };

        // ---- drag ----
        // Pointer events rather than mouse events, so a finger and a pen turn
        // knobs too. Capture keeps the drag attached to this knob once the
        // cursor leaves it, which is most of a 40px target's life.
        knobEl.addEventListener('pointerdown', (event) => {
            if (event.button !== 0) return;
            event.preventDefault();
            knobEl.focus?.();
            knobEl.setPointerCapture?.(event.pointerId);

            // Measured from the last position rather than from the first, so
            // Shift can be pressed and released mid-drag and mean fine from
            // that moment on rather than rescaling the whole gesture.
            let lastY = event.clientY;

            const onMove = (moveEvent) => {
                const deltaY = lastY - moveEvent.clientY;
                lastY = moveEvent.clientY;
                parameter.setRotation(
                    parameter.rotation + deltaY * (moveEvent.shiftKey ? 0.5 : 2)
                );
                paint();
            };

            const onUp = () => {
                knobEl.removeEventListener('pointermove', onMove);
                knobEl.removeEventListener('pointerup', onUp);
                knobEl.removeEventListener('pointercancel', onUp);
                hostSystem()?.status.update('Ready');
            };

            knobEl.addEventListener('pointermove', onMove);
            knobEl.addEventListener('pointerup', onUp);
            knobEl.addEventListener('pointercancel', onUp);
        });

        // ---- wheel ----
        // Passive is off deliberately: without preventDefault the page scrolls
        // out from under the knob being turned.
        knobEl.addEventListener('wheel', (event) => {
            event.preventDefault();
            const direction = event.deltaY < 0 ? 1 : -1;
            nudge(direction * step(event.shiftKey));
        }, { passive: false });

        // ---- keyboard ----
        knobEl.addEventListener('keydown', (event) => {
            if (event.ctrlKey || event.altKey || event.metaKey) return;
            const fine = event.shiftKey;

            switch (event.key) {
                case 'ArrowUp':
                case 'ArrowRight':
                    nudge(step(fine));
                    break;
                case 'ArrowDown':
                case 'ArrowLeft':
                    nudge(-step(fine));
                    break;
                case 'PageUp':
                    nudge(span / 10);
                    break;
                case 'PageDown':
                    nudge(-span / 10);
                    break;
                case 'Home':
                    parameter.setValue(parameter.minValue);
                    paint();
                    break;
                case 'End':
                    parameter.setValue(parameter.maxValue);
                    paint();
                    break;
                default:
                    return;
            }
            // Only once a key has been handled, so Tab, Escape and `m` still
            // reach the rack from a focused knob.
            event.preventDefault();
            event.stopPropagation();
        });

        // ---- reset ----
        // Double-click puts a knob back where the catalogue had it. Undo is a
        // larger question; putting one control back is not.
        knobEl.addEventListener('dblclick', (event) => {
            event.preventDefault();
            event.stopPropagation();
            parameter.setValue(parameter.defaultValue);
            paint(false);
            hostSystem()?.status.update(
                `${parameter.label} back to ${Math.round(parameter.value)}`
            );
        });
    }

    // ===============================
    // WHAT JUST HAPPENED
    // ===============================
    // Screens read this. It is not stored and never exported: a message a
    // document remembered would disagree with the panel the moment anything
    // moved, which is the same reason knob rotation is derived.
    note(message) {
        this.lastEvent = message;
        this.refreshScreens();
        return message;
    }

    // Every screen on this device, filled from the source its entry names.
    refreshScreens() {
        const screens = this.element?.querySelectorAll?.('.irl-screen') || [];
        screens.forEach(screen => {
            const text = screen.querySelector('.irl-screen-text');
            if (text) text.textContent = this.screenText(screen.dataset.source);
        });
        return screens.length;
    }

    screenText(source) {
        switch (source) {
            case 'device':
                return `${this.maker || ''} ${this.name}`.trim().toUpperCase();
            case 'patch':
                return (hostSystem()?.name || 'UNTITLED').toUpperCase();
            case 'parameter':
                return this.lastParameter || this.name.toUpperCase();
            case 'transport': {
                // Whatever this device calls tempo, if it has one at all.
                const tempo = this.parameters.get('tempo');
                return tempo
                    ? `${Math.round(tempo.value)} BPM`
                    : this.name.toUpperCase();
            }
            case 'static':
                return this.staticText || '';
            case 'last-event':
            default:
                return (this.lastEvent || this.name).toUpperCase();
        }
    }

    // Move a knob to whatever its parameter now says. Three callers used to
    // each find the element and animate the indicator themselves, and none of
    // them updated `aria-valuenow` - so an imported or randomized rack was
    // announced at its old values while showing its new ones.
    paintKnob(param, { duration = 500, easing = 'easeOutCubic', delay = 0 } = {}) {
        const knobEl = this.element?.querySelector(`[data-param="${param.name}"]`);
        if (!knobEl) return null;

        knobEl.setAttribute?.('aria-valuenow', String(Math.round(param.value)));
        // Where it stands, for the controls CSS positions rather than turns. A
        // fader has no indicator to rotate, so this is the only thing that
        // moves it; a knob has both and only uses the rotation.
        knobEl.style?.setProperty?.('--value', String(param.fraction));

        const indicator = knobEl.querySelector('.knob-indicator');
        if (indicator) {
            anime({ targets: indicator, rotate: param.rotation, duration, easing, delay });
        }
        return knobEl;
    }

    // State management
    getState() {
        const parameters = {};
        this.parameters.forEach((param, name) => {
            parameters[name] = param.getState().value;
        });

        return {
            id: this.id,
            type: this.type,
            view: this.view,
            parameters
        };
    }

    setState(state) {
        this.setView(state.view || 'front');
        Object.entries(state.parameters || {}).forEach(([name, value]) => {
            const parameter = this.parameters.get(name);
            if (!parameter) return;
            parameter.setState({ value });
            this.paintKnob(parameter);
        });
    }
}

// ===================================
// SIMPLE COMPONENT: ModuleFactory
// ===================================
class ModuleFactory {
    // Populated from GET /api/catalogue at startup. The catalogue is the single
    // source of device definitions: adding `catalogue/devices/<id>.json` puts a
    // device in the palette with no change to this file. Definitions used to be
    // hard-coded here, and keeping a second copy in JavaScript is exactly the
    // drift the frontend contract tests were invented to chase.
    static definitions = {};
    static categories = [];

    static load(payload) {
        this.categories = payload.categories || [];
        this.definitions = {};
        (payload.devices || []).forEach(device => {
            this.definitions[device.id] = device;
        });
        return this.definitions;
    }

    static get ids() {
        return Object.keys(this.definitions).sort();
    }

    static byCategory() {
        const grouped = new Map();
        this.ids.forEach(id => {
            const device = this.definitions[id];
            if (!grouped.has(device.category)) grouped.set(device.category, []);
            grouped.get(device.category).push(device);
        });
        return grouped;
    }

    static create(type) {
        const def = this.definitions[type];
        if (!def) throw new Error(`Unknown device: ${type}`);

        const module = new EurorackModule(type, def.model || def.id);
        module.maker = def.maker;
        module.category = def.category;

        (def.parameters || []).forEach(p => {
            const fallback = p.default !== undefined && p.default !== null
                ? p.default
                : null;
            module.addParameter(p.name, p.label, p.min, p.max, fallback);
        });

        (def.jacks || []).forEach(j => {
            module.addJack(j.name, j.type, j.signal, j.side, j.label);
        });

        // Sides come from what is on them, so a device cannot claim a face
        // with nothing on it - and cannot be denied one that carries a keybed
        // and a screen just because nothing is socketed there. Mirrors
        // `Device.sides()` in src/catalogue.py.
        module.layout = def.layout || null;
        module.setSides([
            ...(def.jacks || []).map(j => j.side),
            ...sidesUsedByLayout(module.layout),
        ]);

        return module;
    }
}

// ===================================
// SIMPLE COMPONENT: PatchBayManager
// ===================================
class PatchBayManager {
    constructor() {
        this.connections = [];
        this.activeJack = null;
        this.svg = document.getElementById('patch-cables');
        // Held here rather than read off the global: this manager is built
        // during EurorackSystem's constructor, before that global is bound.
        this.view = 'front';
        // The device whose cables are being followed, if any.
        this.tracing = null;
    }

    handleJackClick(jack) {
        if (!this.activeJack) {
            this.startConnection(jack);
        } else if (this.activeJack === jack) {
            this.cancelConnection();
        } else {
            this.completeConnection(jack);
        }
    }

    startConnection(jack) {
        this.activeJack = jack;
        jack.element?.classList.add('arming');
        hostSystem()?.status.update(
            `${jack.name} armed - click any ${jack.type === 'output' ? 'input' : 'output'}, `
            + 'on either side of the rack'
        );
    }

    cancelConnection() {
        this.cancelPending();
        hostSystem()?.status.update('Connection cancelled');
    }

    // Disarm without narrating it, for callers that set their own status.
    cancelPending() {
        this.activeJack?.element?.classList.remove('arming');
        this.activeJack = null;
    }

    completeConnection(jack) {
        const refusal = this.activeJack.refusalReason(jack);
        if (refusal) {
            hostSystem()?.status.update(refusal);
        } else {
            this.createConnection(this.activeJack, jack);
            hostSystem()?.status.update('Connected!');
        }
        this.activeJack?.element?.classList.remove('arming');
        this.activeJack = null;
    }

    // A cable is identified by the two sockets it joins, computed rather than
    // stored - the same reasoning that keeps a jack's side out of the exported
    // document. A stored id would be a second answer to "which cable is this",
    // and the two could disagree the moment a device were renamed.
    static keyOf(source, target) {
        return `${source.module.id}:${source.name}->${target.module.id}:${target.name}`;
    }

    // The connection a key names, or null. Callers get the record, not an index,
    // because an index goes stale the moment anything else is unpatched.
    find(key) {
        return this.connections.find(
            conn => PatchBayManager.keyOf(conn.source, conn.target) === key
        ) || null;
    }

    // Pull one lead out. The jacks either end keep whatever else is plugged
    // into them: an output feeding three inputs loses one cable, not three.
    remove(key) {
        const conn = this.find(key);
        if (!conn) return null;

        const { source, target } = conn;
        source.connections = source.connections.filter(j => j !== target);
        target.connections = target.connections.filter(j => j !== source);
        this.connections = this.connections.filter(c => c !== conn);

        // `connected` and `through` describe a jack's remaining cables, so both
        // are recomputed from what is left rather than simply cleared.
        [source, target].forEach(jack => {
            jack.element?.classList.toggle('connected', jack.connections.length > 0);
            jack.element?.classList.toggle(
                'through', jack.connections.some(other => other.side !== jack.side)
            );
        });

        this.redrawAll();
        return conn;
    }

    // Every cable running to one device, for unpatching it in a single act.
    cablesOf(moduleId) {
        return this.connections.filter(
            ({ source, target }) =>
                source.module?.id === moduleId || target.module?.id === moduleId
        );
    }

    createConnection(jack1, jack2) {
        if (jack1.connect(jack2)) {
            // Normalize so the record always reads output -> input, which is
            // what the interchange format stores. A cable's sides are read off
            // its jacks rather than stored: a jack's side is fixed by its
            // module definition, so a stored copy could only ever disagree.
            const source = jack1.type === 'output' ? jack1 : jack2;
            const target = jack1.type === 'output' ? jack2 : jack1;
            this.connections.push({ source, target, cable: null });
            this.markThrough(source, target);
            this.redrawAll();
            return true;
        }
        return false;
    }

    // A jack whose cable disappears round the back is worth seeing as such.
    markThrough(source, target) {
        const spans = source.side !== target.side;
        [source, target].forEach(jack => {
            jack.element?.classList.toggle('through', spans);
        });
    }

    clear() {
        this.connections.forEach(({ source }) => source.disconnect());
        this.connections = [];
        this.activeJack = null;
        this.redrawAll();
    }

    // Cables are redrawn rather than moved, because a hidden face has no layout
    // box and an endpoint's position is only measurable while its own module is
    // showing that side.
    //
    // **Every cable is drawn, in every view.** An endpoint whose face is turned
    // away is anchored to its device's silhouette instead of to the socket, so
    // the cable stays continuous and can be followed to both of its devices.
    // Previously such a cable became a stub that trailed off, which said a
    // cable existed and refused to say where it went - the one thing you look
    // at a patch to find out.
    redrawAll() {
        if (!this.svg) return;
        this.svg.replaceChildren();

        this.connections.forEach(conn => {
            const drawn = this.createCable(conn.source, conn.target);
            conn.cable = drawn?.path || null;
            conn.hit = drawn?.hit || null;
        });
    }

    rackOrigin() {
        return document.getElementById('rack')?.getBoundingClientRect() || null;
    }

    // Where a cable end is drawn, and whether that is the socket itself.
    endpointOf(jack) {
        const rackRect = this.rackOrigin();
        if (!rackRect) return null;

        if (jack.isVisible()) {
            const rect = jack.element?.getBoundingClientRect();
            // A zero box means the face is laid out but not painted; fall
            // through to the silhouette rather than drawing to the corner.
            if (rect && (rect.width || rect.height)) {
                return {
                    x: rect.left + rect.width / 2 - rackRect.left,
                    y: rect.top + rect.height / 2 - rackRect.top,
                    hidden: false,
                };
            }
        }

        const anchor = this.silhouetteAnchor(jack, rackRect);
        return anchor && { ...anchor, hidden: true };
    }

    // A face that is turned away still has a position: the edge of the device
    // it belongs to. Anchoring there is what a lead round the back actually
    // looks like - it disappears at the device's outline, not in mid-air.
    silhouetteAnchor(jack, rackRect) {
        const rect = jack.module?.element?.getBoundingClientRect();
        if (!rect || (!rect.width && !rect.height)) return null;

        const left = rect.left - rackRect.left;
        const top = rect.top - rackRect.top;

        // Where along the edge. Every hidden socket used to anchor to the
        // midpoint of its device's edge, so a stereo pair turned away became
        // one line: two cables, one visible run, and no way to tell which end
        // was which. Each socket keeps its own place instead, inset from the
        // corners so a lead never appears to leave the device diagonally.
        const t = SILHOUETTE_INSET
            + this.edgeFraction(jack) * (1 - 2 * SILHOUETTE_INSET);
        const alongX = left + t * rect.width;
        const alongY = top + t * rect.height;

        switch (jack.side) {
            case 'top':
            case 'front':
                return { x: alongX, y: top };
            case 'bottom':
            case 'back':
                return { x: alongX, y: top + rect.height };
            case 'left':
                return { x: left, y: alongY };
            case 'right':
                return { x: left + rect.width, y: alongY };
            default:
                return { x: left + rect.width / 2, y: top + rect.height / 2 };
        }
    }

    // Where along its own face a socket sits, 0..1.
    //
    // The measured layout if the device has one, so a turned-away face keeps
    // the real arrangement - an output pair stays a pair, in the order it is on
    // the panel. Otherwise the order the sockets are drawn in, which is the
    // order the entry lists them and the order they appear in minimal mode. The
    // point either way is that two sockets next to each other stay next to each
    // other when you cannot see them.
    edgeFraction(jack) {
        const module = jack.module;
        if (!module) return 0.5;

        const runsAcross = ['front', 'back', 'top', 'bottom'].includes(jack.side);
        const place = module.layout?.jacks?.[jack.name];
        if (place && (place.side || 'front') === jack.side) {
            const along = runsAcross ? place.x : place.y;
            if (typeof along === 'number') return along;
        }

        const peers = [...module.jacks.values()].filter(j => j.side === jack.side);
        const at = peers.indexOf(jack);
        if (at < 0 || peers.length < 2) return 0.5;
        // Spread inside the edge rather than onto its ends: `n` sockets get
        // `n` interior positions, so the first and last are not at the corners.
        return (at + 1) / (peers.length + 1);
    }

    // A small ring where a cable meets a device it enters out of sight, so the
    // hidden end reads as an endpoint rather than as the line stopping.
    createAnchorMark(at, side) {
        const mark = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        mark.setAttribute('cx', at.x);
        mark.setAttribute('cy', at.y);
        mark.setAttribute('r', 3.5);
        mark.setAttribute('class', 'cable-anchor');
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = `continues on the ${side}`;
        mark.appendChild(title);
        this.svg.appendChild(mark);
        return mark;
    }

    createCable(source, target) {
        const from = this.endpointOf(source);
        const to = this.endpointOf(target);
        if (!from || !to) return null;

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const midX = (from.x + to.x) / 2;
        // Cables hang below, under gravity: further for a longer run, and each
        // by its own small amount so two cables between the same two devices
        // can be told apart. Keyed on the cable rather than on its position in
        // the list, so unpatching one does not move the others.
        const reach = Math.abs(to.x - from.x);
        const sag = CABLE_SAG_MIN
            + Math.min(CABLE_SAG_MAX, reach * CABLE_SAG_RATIO)
            + cableSpread(source, target) * CABLE_SAG_SPREAD;
        const midY = Math.max(from.y, to.y) + sag;

        const curve = `M ${from.x} ${from.y} Q ${midX} ${midY} ${to.x} ${to.y}`;
        path.setAttribute('d', curve);
        // Rear wiring reads as rear wiring wherever the device is pointing.
        path.setAttribute('stroke', source.side === 'back' ? '#ff9f43' : '#00ff88');
        path.setAttribute('stroke-width', '2');
        path.setAttribute('fill', 'none');

        const classes = ['cable'];
        // A cable with an end out of sight is dashed: it is still one line you
        // can follow, and the dashes say part of its run is behind something.
        if (from.hidden || to.hidden) classes.push('is-occluded');
        if (source.side !== target.side) classes.push('crosses-faces');
        if (this.tracing && (source.module.id === this.tracing || target.module.id === this.tracing)) {
            classes.push('is-traced');
        }
        path.setAttribute('class', classes.join(' '));

        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent =
            `${source.module.name} ${source.label} (${source.side})`
            + ` -> ${target.module.name} ${target.label} (${target.side})`;
        path.appendChild(title);

        // A 2px curve is not something anyone can hit. This is the same curve
        // at a thickness you can aim at, invisible and never painted; it exists
        // only so `cableAt` has something to ask `isPointInStroke`. It stays
        // `pointer-events: none` like everything else on this layer, so it
        // cannot swallow a click meant for a knob the cable happens to cross.
        const hit = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        hit.setAttribute('d', curve);
        hit.setAttribute('class', 'cable-hit');
        hit.setAttribute('fill', 'none');
        // Transparent, not `none`: `isPointInStroke` answers about the stroke's
        // painting area, and a stroke set to `none` has no painting area to be
        // inside. Transparent paints nothing and still has geometry.
        hit.setAttribute('stroke', 'transparent');
        hit.setAttribute('stroke-width', String(CABLE_HIT_WIDTH));

        this.svg.appendChild(path);
        this.svg.appendChild(hit);
        if (from.hidden) this.createAnchorMark(from, source.side);
        if (to.hidden) this.createAnchorMark(to, target.side);
        return { path, hit };
    }

    // Which cable, if any, is under a viewport point. Asked of the geometry
    // rather than of the event target: the cable layer is `pointer-events:
    // none` on purpose, and turning that off to make cables clickable would put
    // an invisible sheet over every knob a cable runs across.
    //
    // Nearest wins, not first, so where two cables cross you get the one you
    // aimed at rather than the one drawn earliest.
    cableAt(clientX, clientY) {
        const rackRect = this.rackOrigin();
        if (!rackRect || !this.svg) return null;

        const x = clientX - rackRect.left;
        const y = clientY - rackRect.top;

        let best = null;
        this.connections.forEach(conn => {
            const hit = conn.hit;
            // Absent in a harness that stubs SVG, and absent in a browser too
            // old for it. Either way the answer is "no cable here", never a
            // thrown error over a right-click.
            if (typeof hit?.isPointInStroke !== 'function') return;
            let point;
            try {
                point = this.svg.createSVGPoint
                    ? Object.assign(this.svg.createSVGPoint(), { x, y })
                    : new DOMPoint(x, y);
                if (!hit.isPointInStroke(point)) return;
            } catch {
                return;
            }
            const distance = this.distanceToEnds(conn, x, y);
            if (!best || distance < best.distance) {
                best = { key: PatchBayManager.keyOf(conn.source, conn.target), conn, distance };
            }
        });
        return best;
    }

    // A tie-break, not a measurement: how far the point is from the cable's
    // nearer end. Two cables can both contain a point and only one of them is
    // the one being aimed at.
    distanceToEnds(conn, x, y) {
        const ends = [this.endpointOf(conn.source), this.endpointOf(conn.target)]
            .filter(Boolean)
            .map(end => Math.hypot(end.x - x, end.y - y));
        return ends.length ? Math.min(...ends) : Infinity;
    }

    // What a cable is, in words, for a menu title and a status line.
    describe(conn) {
        return `${conn.source.module.name} ${conn.source.label}`
            + ` -> ${conn.target.module.name} ${conn.target.label}`;
    }

    // Follow one device's cables: everything touching it is emphasised and the
    // rest recedes, which is the only way to read a rack once the count is up.
    trace(moduleId) {
        this.tracing = moduleId || null;
        this.svg?.classList.toggle('is-tracing', Boolean(this.tracing));
        this.redrawAll();
        return this.tracing;
    }
}

// ===================================
// SIMPLE COMPONENT: StatusManager
// ===================================
class StatusManager {
    constructor() {
        this.element = document.getElementById('status');
    }

    update(message) {
        this.element.textContent = message;
    }
}

// ===================================
// MAIN SYSTEM
// ===================================
class EurorackSystem {
    constructor() {
        this.modules = new Map();
        this.patchBay = new PatchBayManager();
        this.status = new StatusManager();
        this.rackElement = document.getElementById('rack');
        // The rack-wide default. Individual devices may differ from it once
        // they have been turned on their own.
        this.view = 'front';
        this.selected = null;
        this.name = 'Untitled Patch';
        // Groupings, in display order. `row` is the only kind today; the kind
        // is recorded rather than assumed so a second one is not a reshape.
        this.groups = [];
        this.nextGroupNumber = 1;
        // How the rack is drawn, and which MIDI belongs to which device.
        this.mode = 'minimal';
        this.midi = [];
        this.applyView();
    }

    // ===============================
    // DISPLAY MODE
    // ===============================
    // `minimal` is the abstract box every device shares. `irl` draws each to its
    // own panel proportions with its controls where they sit. Switching rebuilds
    // every face, because the two are different arrangements of the same device
    // rather than a stylesheet apart.
    setMode(mode) {
        this.mode = mode === 'irl' ? 'irl' : 'minimal';
        document.body.dataset.displayMode = this.mode;

        this.modules.forEach(module => {
            module.mode = this.mode;
            if (!module.element) return;
            // Hold the node being replaced *before* rendering. `render()`
            // assigns `this.element` as it goes, so reading `module.element`
            // afterwards returns the new node - and asking a detached node to
            // replace itself does nothing, which left the original in the tree
            // and the replacement appended below it.
            const previous = module.element;
            const replacement = module.render();
            previous.replaceWith(replacement);
            module.element = replacement;
        });

        this.renderRack();
        this.applyView();
        this.status.update(
            this.mode === 'irl'
                ? 'Showing devices as they are laid out'
                : 'Showing devices minimally'
        );
        return this.mode;
    }

    toggleMode() {
        return this.setMode(this.mode === 'irl' ? 'minimal' : 'irl');
    }

    // ===============================
    // MIDI ACTIVITY
    // ===============================
    // A mapped message lights the device it belongs to. Activity is transient
    // and is never exported: the binding is the state, the flash is not.
    showActivity(activity) {
        const module = this.modules.get(activity.module);
        if (!module?.element) return null;

        const intensity = Math.max(0, Math.min(1, activity.intensity));
        module.element.style.setProperty('--activity', intensity.toFixed(3));
        module.element.classList.add('is-active');

        // A note-off is an instruction to stop showing, not a fainter flash.
        if (intensity === 0) {
            module.element.classList.remove('is-active');
        } else {
            clearTimeout(module._activityTimer);
            module._activityTimer = setTimeout(() => {
                module.element?.classList.remove('is-active');
            }, 220);
        }

        if (activity.parameter) {
            const parameter = module.parameters.get(activity.parameter);
            if (parameter) {
                parameter.setValue(
                    parameter.minValue + intensity * (parameter.maxValue - parameter.minValue)
                );
                const knob = module.element.querySelector(`[data-param="${activity.parameter}"]`);
                const indicator = knob?.querySelector('.knob-indicator');
                if (indicator) {
                    indicator.style.transform =
                        `translateX(-50%) rotate(${parameter.rotation}deg)`;
                }
            }
        }

        if (activity.jack) {
            const socket = module.element.querySelector(`[data-jack="${activity.jack}"]`);
            socket?.classList.add('is-active');
            setTimeout(() => socket?.classList.remove('is-active'), 220);
        }

        return module;
    }

    // ===============================
    // GROUPS
    // ===============================
    // A device belongs to at most one group. Anything in no group is loose: it
    // is still in the rack, and renders after the groups.
    createRow(label = null) {
        const id = `row-${this.nextGroupNumber++}`;
        const group = {
            id,
            kind: 'row',
            label: label || `Row ${this.groups.length + 1}`,
            members: []
        };
        this.groups.push(group);
        this.renderRack();
        this.status.update(`Added ${group.label}`);
        return group;
    }

    groupOf(moduleId) {
        return this.groups.find(g => g.members.includes(moduleId)) || null;
    }

    assignToGroup(moduleId, groupId) {
        if (!this.modules.has(moduleId)) return null;
        const group = this.groups.find(g => g.id === groupId);
        if (!group) return null;

        this.removeFromGroup(moduleId, { rerender: false });
        group.members.push(moduleId);
        this.renderRack();
        return group;
    }

    removeFromGroup(moduleId, { rerender = true } = {}) {
        this.groups.forEach(group => {
            group.members = group.members.filter(id => id !== moduleId);
        });
        if (rerender) this.renderRack();
    }

    // Deleting a row never deletes devices. They come loose instead, because a
    // grouping is a way of looking at a rack rather than a container the gear
    // lives inside.
    deleteGroup(groupId) {
        const group = this.groups.find(g => g.id === groupId);
        if (!group) return null;
        this.groups = this.groups.filter(g => g.id !== groupId);
        this.renderRack();
        this.status.update(`Removed ${group.label}; its devices are loose`);
        return group;
    }

    ungrouped() {
        const claimed = new Set(this.groups.flatMap(g => g.members));
        return Array.from(this.modules.keys()).filter(id => !claimed.has(id));
    }

    // Rebuilds the row containers and moves existing module elements into them.
    // Elements are moved rather than recreated, so knob handlers and jack
    // references survive a regrouping.
    renderRack() {
        if (!this.rackElement) return;

        // Detach everything but the cable layer, then rebuild. Removing only
        // the containers left any `.module` appended straight to the rack
        // sitting there — a second, stale copy above the working one. Making
        // this authoritative means a stray node cannot survive a redraw however
        // it got there, rather than only the ways thought of so far.
        this.rackElement.querySelectorAll('.rack-group, .rack-loose').forEach(el => el.remove());
        this.rackElement.querySelectorAll('.module').forEach(el => el.remove());

        this.groups.forEach(group => {
            const container = document.createElement('div');
            container.className = 'rack-group';
            container.dataset.groupId = group.id;

            const header = document.createElement('div');
            header.className = 'rack-group-header';
            header.innerHTML = `
                <span class="rack-group-label">${group.label}</span>
                <span class="rack-group-count">${group.members.length}</span>
            `;
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'rack-group-remove';
            remove.textContent = '×';
            remove.title = 'Remove this row; its devices stay in the rack';
            remove.addEventListener('click', () => this.deleteGroup(group.id));
            header.appendChild(remove);
            container.appendChild(header);

            const shelf = document.createElement('div');
            shelf.className = 'rack-shelf';
            group.members.forEach(id => {
                const module = this.modules.get(id);
                if (module?.element) shelf.appendChild(module.element);
            });
            container.appendChild(shelf);
            this.rackElement.appendChild(container);
        });

        const loose = this.ungrouped();
        if (loose.length) {
            const container = document.createElement('div');
            container.className = 'rack-loose';
            loose.forEach(id => {
                const module = this.modules.get(id);
                if (module?.element) container.appendChild(module.element);
            });
            this.rackElement.appendChild(container);
        }

        this.patchBay.redrawAll();
        this.refreshViewIndicator();
        this.refreshScreens();
    }

    addModule(type, groupId = null) {
        const module = ModuleFactory.create(type);
        // A device arriving into an `irl` rack draws as `irl`. Without this it
        // renders minimal while everything around it is laid out.
        module.mode = this.mode;
        // A device arrives on the face you look at - its front, or its top
        // where the catalogue says so. Not the way the rack happens to be
        // turned: that meant a rack turned round to patch its backs handed you
        // the back of everything added afterwards.
        module.setView(module.preferredView());
        this.modules.set(module.id, module);

        const moduleElement = module.render();
        this.rackElement.appendChild(moduleElement);

        const target = groupId
            || (this.selected ? this.groupOf(this.selected)?.id : null);
        if (target) this.assignToGroup(module.id, target);
        else this.renderRack();

        // Animate appearance
        anime({
            targets: moduleElement,
            translateY: [50, 0],
            opacity: [0, 1],
            duration: 800,
            easing: 'easeOutCubic'
        });

        this.status.update(`Added ${module.name}`);
        this.patchBay.redrawAll();
        return module;
    }

    // ===============================
    // VIEW
    // ===============================
    // Tab acts on the selection if there is one, and on the whole rack if there
    // is not. Turning every device is the common case, so it is the default.
    flipView(step = 1) {
        if (this.selected && this.modules.has(this.selected)) {
            return this.turnModule(this.selected, step);
        }
        return this.flipAll(step);
    }

    // Every device advances one side of its own. Devices do not share a side
    // list, so this is "turn everything", not "set everything to X" — a K.O. II
    // with a front and a top goes to its top while a DFAM goes to its back.
    flipAll(step = 1) {
        this.modules.forEach(module => module.cycle(step));
        // The rack default follows the commonest side, so a device added next
        // arrives facing the way the rack mostly is.
        this.view = this.commonestSide();
        this.applyView();
        this.status.update(`Turned every device - ${this.viewSummary()}`);
        return this.view;
    }

    turnModule(id, step = 1) {
        const module = this.modules.get(id);
        if (!module) return null;

        if (!module.turns) {
            this.status.update(`${module.name} has only one side`);
            return module.view;
        }

        const view = module.cycle(step);
        this.applyView();
        this.status.update(`${module.name} now showing its ${view}`);
        return view;
    }

    commonestSide() {
        const counts = new Map();
        this.modules.forEach(m => counts.set(m.view, (counts.get(m.view) || 0) + 1));
        let best = 'front';
        let most = -1;
        counts.forEach((count, side) => {
            if (count > most) { most = count; best = side; }
        });
        return best;
    }

    selectModule(id) {
        this.selected = this.selected === id ? null : id;
        this.applyView();
        const module = this.modules.get(this.selected);
        this.status.update(
            module
                ? `${module.name} selected - Tab turns just this one, Escape deselects`
                : 'Nothing selected - Tab turns the whole rack'
        );
        return this.selected;
    }

    deselect() {
        if (!this.selected) return;
        this.selected = null;
        this.applyView();
        this.status.update('Nothing selected - Tab turns the whole rack');
    }

    applyView() {
        this.modules.forEach(module => {
            if (!module.element) return;
            module.element.dataset.view = module.view;
            module.element.classList.toggle('selected', module.id === this.selected);
        });

        this.refreshViewIndicator();

        // A jack armed before a flip may no longer be on screen.
        this.patchBay.cancelPending();
        // Selecting a device traces its cables. This is the one place the two
        // pieces of state meet, so it is where they are kept in step.
        this.patchBay.trace(this.selected);
    }

    // The one persistent answer to "which way is this rack facing", written
    // wherever the set of modules or the sides they show can have changed.
    //
    // It used to be written only by `applyView`, which nothing calls when a
    // device is added or removed - so a freshly booted rack with two devices in
    // it read EMPTY until you happened to turn something. Caught by the first
    // run of `walkthrough/05-in-the-browser.md`, in a real browser, after two
    // sessions of asserting the model and never the screen.
    refreshViewIndicator() {
        const indicator = document.getElementById('view-indicator');
        if (indicator) indicator.textContent = this.viewSummary();
        return indicator;
    }

    // What the rack is actually showing, which is not one value once devices
    // turn independently and do not share a side list.
    viewSummary() {
        const views = Array.from(this.modules.values(), m => m.view);
        if (!views.length) return 'EMPTY';

        const counts = new Map();
        views.forEach(v => counts.set(v, (counts.get(v) || 0) + 1));
        if (counts.size === 1) return `ALL ${views[0].toUpperCase()}`;

        return SIDE_ORDER
            .filter(side => counts.has(side))
            .map(side => `${counts.get(side)} ${side}`)
            .join(', ');
    }

    // Remove one device, and every cable that ran to it. A dangling cable is
    // worse than a missing one: it would export as a connection naming a module
    // the document no longer carries.
    removeModule(id) {
        const module = this.modules.get(id);
        if (!module) return null;

        module.jacks.forEach(jack => jack.disconnect());
        this.patchBay.connections = this.patchBay.connections.filter(
            conn => conn.source.module !== module && conn.target.module !== module
        );

        this.removeFromGroup(id, { rerender: false });
        this.modules.delete(id);
        if (this.selected === id) this.selected = null;
        module.element?.remove();

        this.renderRack();
        this.status.update(`Removed ${module.name}`);
        return module;
    }

    // ===============================
    // WHAT A PRESS MEANS
    // ===============================
    // A pad knows what it sends; it does not know there is a MIDI layer. This
    // is the one place that joins them, which is what lets a grid be drawn by
    // a catalogue entry and still reach a real port's code path.
    //
    // `onEmit` is handed in by main.js. Without it a press still lights the
    // cell, still reaches the device's own screens and still reports itself -
    // it just has nowhere to send.
    emit(module, feature, index, legend) {
        const detail = {
            module: module.id,
            emits: feature.emits,
            index,
            legend,
            channel: feature.channel ?? null,
            note: feature.emits === 'midi-note' ? feature.note + index : null,
            controller: feature.emits === 'midi-cc' ? feature.controller + index : null,
        };

        this.status.update(`${module.name}: ${legend}`);
        this.onEmit?.(detail);
        return detail;
    }

    // Every screen in the rack. Called where the thing a screen reads can have
    // changed but the screen's own device did nothing - a renamed patch, a
    // different selection.
    refreshScreens() {
        this.modules.forEach(module => module.refreshScreens());
    }

    // ===============================
    // CABLES
    // ===============================
    // Patching was one-way: a lead could be run and then only ever cleared with
    // every other lead in the rack. These are the other direction.

    unpatch(key) {
        const conn = this.patchBay.find(key);
        if (!conn) {
            this.status.update('That cable is no longer patched');
            return null;
        }
        const description = this.patchBay.describe(conn);
        this.patchBay.remove(key);
        this.status.update(`Unpatched ${description}`);
        return conn;
    }

    unpatchModule(id) {
        const module = this.modules.get(id);
        if (!module) return 0;

        const cables = this.patchBay.cablesOf(id);
        cables.forEach(conn => this.patchBay.remove(
            PatchBayManager.keyOf(conn.source, conn.target)
        ));
        this.status.update(
            cables.length
                ? `Unpatched ${cables.length} cable(s) from ${module.name}`
                : `${module.name} has nothing patched to it`
        );
        return cables.length;
    }

    randomizeModule(id) {
        const module = this.modules.get(id);
        if (!module) return null;

        module.parameters.forEach(param => {
            param.setValue(Math.random() * (param.maxValue - param.minValue) + param.minValue);
            module.paintKnob(param, { duration: 600, easing: 'easeOutElastic(1, .8)' });
        });

        this.status.update(`Randomized ${module.name}`);
        return module;
    }

    randomizeAll() {
        this.modules.forEach(module => {
            module.parameters.forEach(param => {
                param.setValue(
                    Math.random() * (param.maxValue - param.minValue) + param.minValue
                );
                module.paintKnob(param, {
                    duration: 1000 + Math.random() * 500,
                    easing: 'easeOutElastic(1, .8)',
                    delay: Math.random() * 300,
                });
            });
        });

        this.status.update('Randomized all parameters!');
    }

    clearRack() {
        this.patchBay.clear();
        this.modules.clear();
        this.selected = null;
        this.groups = [];
        this.nextGroupNumber = 1;
        this.rackElement.querySelectorAll('.module').forEach(el => el.remove());
        this.renderRack();
        this.status.update('Rack cleared');
    }

    // ===============================
    // INTERCHANGE
    // ===============================
    // Writes the document described by src/patch_format.py.
    exportState() {
        return {
            format: PATCH_FORMAT,
            version: PATCH_VERSION,
            name: this.name,
            modules: Array.from(this.modules.values()).map(m => m.getState()),
            // No side field: a jack's side is fixed by its module definition,
            // so the document derives it rather than storing a second copy.
            connections: this.patchBay.connections.map(({ source, target }) => ({
                source: { module: source.module.id, jack: source.name },
                target: { module: target.module.id, jack: target.name }
            })),
            groups: this.groups.map(({ id, kind, label, members }) => ({
                id, kind, label, members: [...members]
            })),
            display: { mode: this.mode },
            midi: this.midi.map(binding => ({ ...binding }))
        };
    }

    // Reads one. Throws with a reason the holder of the file can act on; the
    // rack is only cleared once the document has been checked, so a failed
    // import leaves what was already patched alone.
    importState(document) {
        if (!document || typeof document !== 'object' || Array.isArray(document)) {
            throw new Error('A patch is a JSON object');
        }
        if (document.format !== PATCH_FORMAT) {
            throw new Error(`Not a ${PATCH_FORMAT} document (got ${document.format})`);
        }
        if (!PATCH_READS.includes(document.version)) {
            throw new Error(
                `Version ${document.version} cannot be read by this build ` +
                `(this build reads ${PATCH_READS.join(' and ')}, writes ${PATCH_VERSION})`
            );
        }
        // An older version is upgraded by a step that knows what changed, never
        // read hopefully. Version 1 had no groups and only a front and a back;
        // both changes are additive, so the upgrade adds the missing field.
        if (document.version === 1) {
            document = { ...document, version: 2, groups: document.groups || [] };
        }
        // Version 2 had no MIDI bindings and no display mode. Both default to
        // what version 2 implied: no mapping, and the only drawing it could do.
        if (document.version === 2) {
            document = {
                ...document, version: 3,
                midi: document.midi || [],
                display: document.display || { mode: 'minimal' },
            };
        }

        const modules = document.modules || [];
        modules.forEach(m => {
            if (!ModuleFactory.definitions[m.type]) {
                throw new Error(`Unknown module type: ${m.type}`);
            }
        });

        // The internal-consistency rules `docs/patch-format.md` states, checked
        // here because they are the contract rather than the server's opinion.
        // `src/patch_format.py` refuses all of these; this side used to accept
        // them, so a document the API would reject loaded in the browser into a
        // rack quietly missing a device - the worst kind of import, because it
        // reports success.
        const declared = new Set();
        modules.forEach(m => {
            if (declared.has(m.id)) throw new Error(`Duplicate module id: ${m.id}`);
            declared.add(m.id);
        });

        (document.connections || []).forEach((conn, index) => {
            [['source', conn.source], ['target', conn.target]].forEach(([role, end]) => {
                if (!declared.has(end?.module)) {
                    throw new Error(
                        `Connection ${index} ${role} names module `
                        + `"${end?.module}", which is not in this patch`
                    );
                }
            });
        });

        const groupIds = new Set();
        (document.groups || []).forEach(group => {
            if (groupIds.has(group.id)) {
                throw new Error(`Duplicate group id: ${group.id}`);
            }
            groupIds.add(group.id);

            (group.members || []).forEach(member => {
                if (!declared.has(member)) {
                    throw new Error(
                        `Group "${group.id}" names module "${member}", `
                        + 'which is not in this patch'
                    );
                }
            });
        });

        this.clearRack();
        this.name = document.name || 'Untitled Patch';

        const byId = new Map();
        modules.forEach(state => {
            const module = ModuleFactory.create(state.type);
            module.id = state.id;
            this.modules.set(module.id, module);

            const el = module.render();
            el.dataset.moduleId = module.id;
            this.rackElement.appendChild(el);
            module.setState(state);
            byId.set(module.id, module);
        });

        // A group naming a module this document does not carry is refused
        // above, so anything left here names something real. The filter stays
        // as the last line of defence, not as a policy.
        this.groups = (document.groups || []).map(group => ({
            id: group.id,
            kind: group.kind || 'row',
            label: group.label || group.id,
            members: (group.members || []).filter(id => byId.has(id))
        }));
        this.nextGroupNumber = this.groups.length + 1;

        // Bindings naming a device this document does not carry are dropped
        // rather than left pointing at nothing.
        this.midi = (document.midi || []).filter(b => byId.has(b.module));
        this.setMode(document.display?.mode || 'minimal');

        const skipped = [];
        (document.connections || []).forEach((conn, index) => {
            const source = byId.get(conn.source?.module)?.jacks.get(conn.source?.jack);
            const target = byId.get(conn.target?.module)?.jacks.get(conn.target?.jack);
            if (!source || !target) {
                skipped.push(`connection ${index} names a jack this build does not have`);
                return;
            }
            if (!this.patchBay.createConnection(source, target)) {
                skipped.push(`connection ${index} is not a legal cable`);
            }
        });

        this.renderRack();

        const summary = `Imported "${this.name}": ${modules.length} module(s), `
            + `${this.patchBay.connections.length} cable(s), `
            + `${this.groups.length} group(s)`;
        this.status.update(skipped.length ? `${summary}; ${skipped.length} skipped` : summary);
        return { skipped };
    }
}
