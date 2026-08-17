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
        this.rotation = this.valueToRotation(this.value);
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

    setView(view) {
        this.view = this.sides.includes(view) ? view : this.sides[0];
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
        const at = this.sides.indexOf(this.view);
        const next = (at + step + this.sides.length) % this.sides.length;
        return this.setView(this.sides[next]);
    }

    get turns() {
        return this.sides.length > 1;
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
        const moduleEl = document.createElement('div');
        moduleEl.className = 'module';
        moduleEl.dataset.moduleId = this.id;
        moduleEl.dataset.view = this.view;

        // One face per side the device has, only the active one laid out.
        moduleEl.innerHTML = this.sides.map(side => `
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
                        ? `Turn this device (${this.sides.join(' → ')})`
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
        return (side === 'front'
                ? `<div class="controls">${this.renderParameters()}</div>`
                : '')
            + this.renderPatchBay(side);
    }

    renderParameters() {
        return Array.from(this.parameters.entries()).map(([name, param]) => `
            <div class="knob" data-param="${name}">
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

        const controls = Object.entries(layout.controls || {})
            .filter(([, place]) => (place.side || 'front') === side);
        const jacks = Object.entries(layout.jacks || {})
            .filter(([, place]) => (place.side || 'front') === side);

        if (!controls.length && !jacks.length) {
            return `<div class="irl-panel is-bare" style="--aspect:${layout.aspect}">
                        <span class="irl-empty">Nothing on the ${side}</span>
                    </div>`;
        }

        const knobs = controls.map(([name, place]) => {
            const parameter = this.parameters.get(name);
            if (!parameter) return '';
            return `
                <div class="irl-knob" data-param="${name}"
                     style="left:${place.x * 100}%; top:${place.y * 100}%;
                            --size:${place.size || 1}"
                     title="${parameter.label}">
                    <div class="knob-base"><div class="knob-indicator"></div></div>
                    <span class="irl-knob-label">${parameter.label}</span>
                </div>`;
        }).join('');

        const sockets = jacks.map(([name, place]) => {
            const jack = this.jacks.get(name);
            if (!jack) return '';
            return `
                <div class="irl-jack-slot"
                     style="left:${place.x * 100}%; top:${place.y * 100}%;
                            --size:${place.size || 1}">
                    <div class="jack" data-jack="${name}" data-type="${jack.type}"
                         data-signal="${jack.signal}" data-side="${side}"
                         title="${jack.label} (${jack.signal})"></div>
                </div>`;
        }).join('');

        return `<div class="irl-panel" style="--aspect:${layout.aspect}">${knobs}${sockets}</div>`;
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
                    <div class="jack" data-jack="${name}" data-type="${type}"
                         data-signal="${jack.signal}" data-side="${side}"
                         title="${jack.label || name} (${jack.signal})"></div>
                    <span class="jack-label">${jack.label || name}</span>
                </div>
            `).join('');
    }

    setupInteractions() {
        // Setup parameter knobs
        this.element.querySelectorAll('.knob').forEach(knobEl => {
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
                    system.patchBay.handleJackClick(jack);
                });
            }
        });

        // Turn just this device to its next side.
        this.element.querySelector('.module-flip')?.addEventListener('click', (event) => {
            event.stopPropagation();
            system.turnModule(this.id);
        });

        // Clicking anywhere else on the module selects it, so Tab can act on
        // one device instead of the whole rack.
        this.element.addEventListener('click', () => system.selectModule(this.id));
    }

    setupKnob(knobEl, parameter) {
        const indicator = knobEl.querySelector('.knob-indicator');
        indicator.style.transform = `translateX(-50%) rotate(${parameter.rotation}deg)`;

        knobEl.addEventListener('mousedown', (e) => {
            e.preventDefault();
            const startY = e.clientY;
            const startRotation = parameter.rotation;

            const onMouseMove = (e) => {
                const deltaY = startY - e.clientY;
                parameter.setRotation(startRotation + deltaY * 2);

                anime({
                    targets: indicator,
                    rotate: parameter.rotation,
                    duration: 50,
                    easing: 'linear'
                });

                system.status.update(`${parameter.label}: ${Math.round(parameter.value)}`);
            };

            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                system.status.update('Ready');
            };

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
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
            if (parameter) {
                parameter.setState({ value });
                const knobEl = this.element.querySelector(`[data-param="${name}"]`);
                const indicator = knobEl?.querySelector('.knob-indicator');
                if (indicator) {
                    anime({
                        targets: indicator,
                        rotate: parameter.rotation,
                        duration: 500,
                        easing: 'easeOutCubic'
                    });
                }
            }
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

        // Sides come from where the jacks actually are, so a device cannot
        // claim a face with nothing on it.
        module.setSides((def.jacks || []).map(j => j.side));
        module.layout = def.layout || null;

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
        system.status.update(
            `${jack.name} armed - click any ${jack.type === 'output' ? 'input' : 'output'}, `
            + 'on either side of the rack'
        );
    }

    cancelConnection() {
        this.cancelPending();
        system.status.update('Connection cancelled');
    }

    // Disarm without narrating it, for callers that set their own status.
    cancelPending() {
        this.activeJack?.element?.classList.remove('arming');
        this.activeJack = null;
    }

    completeConnection(jack) {
        const refusal = this.activeJack.refusalReason(jack);
        if (refusal) {
            system.status.update(refusal);
        } else {
            this.createConnection(this.activeJack, jack);
            system.status.update('Connected!');
        }
        this.activeJack?.element?.classList.remove('arming');
        this.activeJack = null;
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
            conn.cable = this.createCable(conn.source, conn.target);
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
        const midX = left + rect.width / 2;
        const midY = top + rect.height / 2;

        switch (jack.side) {
            case 'top':
            case 'front':
                return { x: midX, y: top };
            case 'bottom':
            case 'back':
                return { x: midX, y: top + rect.height };
            case 'left':
                return { x: left, y: midY };
            case 'right':
                return { x: left + rect.width, y: midY };
            default:
                return { x: midX, y: midY };
        }
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
        const midY = Math.max(from.y, to.y) + 40; // cables hang below, under gravity

        path.setAttribute('d', `M ${from.x} ${from.y} Q ${midX} ${midY} ${to.x} ${to.y}`);
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

        this.svg.appendChild(path);
        if (from.hidden) this.createAnchorMark(from, source.side);
        if (to.hidden) this.createAnchorMark(to, target.side);
        return path;
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
        this.drawerOpen = true;
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
    }

    // ===============================
    // OPTIONS DRAWER
    // ===============================
    // Slides down rather than unmounting: the handle stays reachable, and the
    // patch name field keeps whatever was typed into it.
    toggleDrawer(open = !this.drawerOpen) {
        this.drawerOpen = open;
        const drawer = document.getElementById('options-drawer');
        if (drawer) drawer.dataset.open = String(open);
        // Cable geometry is measured against the viewport, and the drawer
        // changes how much of it the rack has.
        this.patchBay.redrawAll();
        return this.drawerOpen;
    }

    addModule(type, groupId = null) {
        const module = ModuleFactory.create(type);
        // A device arriving into an `irl` rack draws as `irl`. Without this it
        // renders minimal while everything around it is laid out.
        module.mode = this.mode;
        // A device arrives facing the way the rack is facing, if it has that
        // side. A K.O. II in a rack showing its backs shows its face instead,
        // because it has no back to show.
        module.setView(this.view);
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

        const indicator = document.getElementById('view-indicator');
        if (indicator) indicator.textContent = this.viewSummary();

        // A jack armed before a flip may no longer be on screen.
        this.patchBay.cancelPending();
        // Selecting a device traces its cables. This is the one place the two
        // pieces of state meet, so it is where they are kept in step.
        this.patchBay.trace(this.selected);
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

    randomizeModule(id) {
        const module = this.modules.get(id);
        if (!module) return null;

        module.parameters.forEach(param => {
            param.setValue(Math.random() * (param.maxValue - param.minValue) + param.minValue);
            const knobEl = module.element?.querySelector(`[data-param="${param.name}"]`);
            const indicator = knobEl?.querySelector('.knob-indicator');
            if (indicator) {
                anime({
                    targets: indicator,
                    rotate: param.rotation,
                    duration: 600,
                    easing: 'easeOutElastic(1, .8)'
                });
            }
        });

        this.status.update(`Randomized ${module.name}`);
        return module;
    }

    randomizeAll() {
        this.modules.forEach(module => {
            module.parameters.forEach(param => {
                const randomValue = Math.random() * (param.maxValue - param.minValue) + param.minValue;
                param.setValue(randomValue);

                const knobEl = module.element.querySelector(`[data-param="${param.name}"]`);
                const indicator = knobEl?.querySelector('.knob-indicator');
                if (indicator) {
                    anime({
                        targets: indicator,
                        rotate: param.rotation,
                        duration: 1000 + Math.random() * 500,
                        easing: 'easeOutElastic(1, .8)',
                        delay: Math.random() * 300
                    });
                }
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

        // Groups naming a device this document does not carry are dropped
        // rather than left dangling.
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
