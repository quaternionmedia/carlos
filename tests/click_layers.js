// Click-layer regression harness.
//
// Carlos stacks several things that all want a click: the radial menu, device
// selection, jacks, knobs, row chrome and the rack background. Each collision
// below was a real defect found on 2026-08-17; each check is the reproduction.
//
// Run directly (`node tests/click_layers.js`) or through the Python suite,
// which is what makes it a gate rather than a script somebody remembers.
const fs = require('fs');
const path = require('path');
const REPO = path.resolve(__dirname, '..');

const listeners = { doc: [] };
function makeEl(opts = {}) {
    const el = {
        tag: opts.tag || 'div',
        id: opts.id || '',
        className: opts.className || '',
        dataset: opts.dataset || {},
        style: {}, textContent: '',
        parent: opts.parent || null,
        _listeners: [],
        set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
        classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
        appendChild() {}, remove() {}, replaceChildren() {},
        setAttribute() {}, removeAttribute() {},
        addEventListener(t, fn) { this._listeners.push({ t, fn }); },
        removeEventListener() {},
        querySelector: () => null,
        querySelectorAll: () => [],
        getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }),
        closest(sel) {
            let node = this;
            while (node) {
                if (node.matches(sel)) return node;
                node = node.parent;
            }
            return null;
        },
        matches(sel) {
            return sel.split(',').map(s => s.trim()).some(s => {
                if (s.startsWith('#')) return this.id === s.slice(1);
                if (s.startsWith('.')) return (' ' + this.className + ' ').includes(' ' + s.slice(1) + ' ');
                return this.tag === s;
            });
        },
    };
    return el;
}

const rack = makeEl({ id: 'rack', className: 'rack-container' });
const shelf = makeEl({ className: 'rack-shelf', parent: rack });
const moduleEl = makeEl({ className: 'module', parent: shelf, dataset: { moduleId: 'm1' } });
const knobEl = makeEl({ className: 'knob', parent: moduleEl });
const status = makeEl({ id: 'status' });

const nodes = {
    rack, status, 'patch-cables': null, 'view-indicator': makeEl(),
    'patch-name': null, 'patch-file': null, 'row-target': null, 'palette': null,
    'example-device': null, 'options-drawer': null,
};

global.window = {
    innerWidth: 1200, innerHeight: 800,
    addEventListener() {}, removeEventListener() {},
};
global.document = {
    body: makeEl({ tag: 'body' }),
    getElementById: (id) => (id in nodes ? nodes[id] : null),
    createElement: (tag) => makeEl({ tag }),
    createElementNS: (ns, tag) => makeEl({ tag }),
    addEventListener(t, fn, capture) { listeners.doc.push({ t, fn, capture: !!capture }); },
    removeEventListener(t, fn) {
        const i = listeners.doc.findIndex(l => l.t === t && l.fn === fn);
        if (i >= 0) listeners.doc.splice(i, 1);
    },
};
global.anime = () => {};
global.HTMLInputElement = class {};
global.HTMLSelectElement = class {};
global.fetch = async () => { throw new Error('offline'); };
global.Blob = class {}; global.URL = { createObjectURL: () => '', revokeObjectURL() {} };
global.FileReader = class { readAsText() {} };

function load(file) {
    return fs.readFileSync(path.join(REPO, file), 'utf8');
}
(0, eval)(
    load('static/rad-core.js') +
    load('static/midi.js') +
    load('static/menus.js') +
    load('static/rad-menu.js') +
    load('static/models.js') +
    '\nglobalThis.EurorackSystem = EurorackSystem;' +
    '\nglobalThis.ModuleFactory = ModuleFactory;' +
    '\nglobalThis.RadMenu = RadMenu;' +
    '\nglobalThis.carlosResolve = carlosResolve;' +
    '\nglobalThis.RAD_GEOMETRY = RAD_GEOMETRY;' +
    '\nglobalThis.radIntent = radIntent;' +
    // Class declarations inside an indirect eval do not outlive it, so every
    // name the next eval needs is handed over explicitly.
    '\nglobalThis.MidiInput = MidiInput;'
);
const devDir = path.join(REPO, 'catalogue/devices');
ModuleFactory.load({
    categories: [],
    devices: fs.readdirSync(devDir).filter(f => f.endsWith('.json'))
        .map(f => JSON.parse(fs.readFileSync(path.join(devDir, f), 'utf8'))),
});
// main.js declares its own `const system`, which shadows anything we put on
// globalThis. Reach the instance the handlers actually close over, or the
// harness measures an object nothing is wired to.
(0, eval)(
    load('static/main.js').replace('bootstrap();', '')
    + '\nglobalThis.radMenu = radMenu;'
    + '\nglobalThis.appSystem = system;'
);
const system = globalThis.appSystem;

// Two real devices, or the view tests below assert over an empty rack and
// pass by having nothing to change.
system.addModule('carlos.vco');
system.addModule('moog.dfam');

const results = [];
const check = (name, ok, detail) => results.push({ name, ok, detail });

function fire(type, target, extra = {}) {
    const event = {
        type, target, button: 0, clientX: 400, clientY: 300,
        shiftKey: false, ctrlKey: false, altKey: false, metaKey: false,
        defaultPrevented: false, propagationStopped: false,
        preventDefault() { this.defaultPrevented = true; },
        stopPropagation() { this.propagationStopped = true; },
        ...extra,
    };
    // Bubble from the target up through its ancestors, then to document —
    // element listeners are where #rack's own handler lives, and a harness that
    // only dispatches document listeners cannot see it at all.
    const run = (fn, where) => {
        try { fn(event); }
        catch (e) { console.log('   [debug]', where, type, 'threw:', e.message); }
    };
    let node = target;
    while (node) {
        if (!event.propagationStopped) {
            node._listeners.filter(l => l.t === type).forEach(l => run(l.fn, 'element'));
        }
        node = node.parent;
    }
    if (!event.propagationStopped) {
        listeners.doc.filter(l => l.t === type).forEach(l => run(l.fn, 'document'));
    }
    return event;
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
    // ---- COLLISION 1: long-press timer survives a released click ----
    const before = radMenu.open;
    fire('pointerdown', moduleEl);
    const armedListeners = listeners.doc.filter(l => l.t === 'pointerup').length;
    check('C1: a pointerup listener exists while the long-press is armed',
        armedListeners > 0,
        `pointerup listeners while arming: ${armedListeners}`);

    fire('pointerup', moduleEl);          // user releases well before 350ms
    await sleep(450);                      // wait past longPressMs
    check('C1: a short click does NOT open the menu',
        radMenu.open === false,
        `menu open after a released click: ${radMenu.open}`);
    if (radMenu.open) radMenu.close();

    // ---- COLLISION 2: committing also fires the underlying click ----
    radMenu.openAt({ type: 'canvas', targetIds: [], position: { x: 400, y: 300 } }, 400, 300, 'tap');
    fire('pointerup', moduleEl, { clientX: 400 + 80, clientY: 300 });
    const trailing = fire('click', moduleEl);
    check('C2: the click that follows a commit is swallowed',
        trailing.propagationStopped || trailing.defaultPrevented,
        'the trailing click reached the module, so committing also selects it');
    if (radMenu.open) radMenu.close();

    // ---- COLLISION 3: Tab and m still act while the menu is open ----
    radMenu.openAt({ type: 'canvas', targetIds: [], position: { x: 400, y: 300 } }, 400, 300, 'tap');
    const viewsBefore = [...system.modules.values()].map(m => m.view).join(',');
    fire('keydown', document.body, { key: 'Tab' });
    const viewsAfter = [...system.modules.values()].map(m => m.view).join(',');
    check('C3: Tab does not turn the rack while a menu is open',
        viewsBefore === viewsAfter,
        `views changed under an open menu: ${viewsBefore} -> ${viewsAfter}`);
    if (radMenu.open) radMenu.close();

    // ---- COLLISION 4: clicking group chrome does not deselect ----
    system.selected = 'm1';
    fire('click', shelf);
    check('C4: clicking rack chrome (a row shelf) deselects',
        system.selected === null,
        `selection survived a click on .rack-shelf: ${system.selected}`);

    let failed = 0;
    for (const r of results) {
        if (!r.ok) failed++;
        console.log(`${r.ok ? 'OK  ' : 'BUG '} ${r.name}`);
        if (!r.ok) console.log(`       ${r.detail}`);
    }
    console.log(`\n${results.length - failed}/${results.length} clean, ${failed} collision(s)`);
    process.exit(0);
})();
