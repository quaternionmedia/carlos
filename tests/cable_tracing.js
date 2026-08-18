// Cable tracing regression harness.
//
// Devices turn independently, so a cable's two ends are often on faces that are
// not both showing — and a cable you cannot follow is the one thing a patch
// exists to tell you. Every connection must render as one continuous line in
// every view, including when neither end is visible.
//
// Run directly (`node tests/cable_tracing.js`) or through the Python suite.

const fs = require('fs');
const path = require('path');
const REPO = path.resolve(__dirname, '..');

const SVG_CHILDREN = [];

function rect(x, y, w, h) {
    return { left: x, top: y, width: w, height: h, right: x + w, bottom: y + h };
}

function makeEl(opts = {}) {
    return {
        tag: opts.tag || 'div',
        id: opts.id || '',
        className: opts.className || '',
        dataset: opts.dataset || {},
        style: {}, textContent: '',
        _attrs: {}, _children: [],
        set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
        classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
        appendChild(child) { this._children.push(child); },
        remove() {}, replaceChildren() { this._children.length = 0; },
        setAttribute(k, v) { this._attrs[k] = String(v); },
        getAttribute(k) { return this._attrs[k]; },
        removeAttribute() {},
        addEventListener() {}, removeEventListener() {},
        querySelector: () => null,
        querySelectorAll: () => [],
        getBoundingClientRect: opts.rect || (() => rect(0, 0, 0, 0)),
        closest: () => null,
        matches: () => false,
    };
}

// The cable layer records what was drawn on it.
const svg = makeEl({ id: 'patch-cables' });
svg.appendChild = (child) => { SVG_CHILDREN.push(child); };
svg.replaceChildren = () => { SVG_CHILDREN.length = 0; };
svg.classList = { add() {}, remove() {}, toggle() {}, contains: () => false };

const rack = makeEl({ id: 'rack', rect: () => rect(0, 0, 1200, 600) });
const nodes = {
    rack, 'patch-cables': svg, status: makeEl(), 'view-indicator': makeEl(),
    'patch-name': null, 'patch-file': null,
};

global.window = { innerWidth: 1200, innerHeight: 800, addEventListener() {} };
global.document = {
    body: makeEl({ tag: 'body' }),
    getElementById: (id) => (id in nodes ? nodes[id] : null),
    createElement: (tag) => makeEl({ tag }),
    createElementNS: (ns, tag) => makeEl({ tag }),
    addEventListener() {}, removeEventListener() {},
};
global.anime = () => {};

const load = (f) => fs.readFileSync(path.join(REPO, f), 'utf8');
(0, eval)(
    load('static/rad-core.js') + load('static/models.js')
    + '\nglobalThis.EurorackSystem = EurorackSystem;'
    + '\nglobalThis.ModuleFactory = ModuleFactory;'
);
const devDir = path.join(REPO, 'catalogue/devices');
ModuleFactory.load({
    categories: [],
    devices: fs.readdirSync(devDir).filter(f => f.endsWith('.json'))
        .map(f => JSON.parse(fs.readFileSync(path.join(devDir, f), 'utf8'))),
});
const system = new EurorackSystem();

// Give each device a real box, and each jack an element that measures zero when
// its own face is turned away — which is what `display: none` does in a browser
// and is exactly the case that used to produce an untraceable stub.
let placed = 0;
function place(module) {
    const box = rect(40 + (placed++ * 260), 60, 200, 240);
    module.element = makeEl({ className: 'module', rect: () => box });
    module.jacks.forEach(jack => {
        jack.element = makeEl({
            className: 'jack',
            rect: () => (jack.module.view === jack.side
                ? rect(box.left + 20, box.top + 100, 16, 16)
                : rect(0, 0, 0, 0)),
        });
    });
    return module;
}

const results = [];
const check = (name, ok, detail) => results.push({ name, ok, detail });
// Tolerant of a missing path: a dropped cable should be reported as a
// failed expectation, not crash the run before anything is printed.
const classesOf = (p) => (p && p.getAttribute('class') || '').split(/\s+/);
// The drawn cables, which is what "one connection is one line" is about. Each
// one also lays down a `.cable-hit` probe - invisible, never painted, there so
// a lead can be aimed at - and counting those as cables would say every
// connection drew two.
const paths = () => SVG_CHILDREN.filter(
    c => c.tag === 'path' && classesOf(c).includes('cable'));
const probes = () => SVG_CHILDREN.filter(
    c => c.tag === 'path' && classesOf(c).includes('cable-hit'));
const anchors = () => SVG_CHILDREN.filter(c => c.tag === 'circle');

// ---- a cable between two faces that are not both showing ----
const vco = place(system.addModule('carlos.vco'));      // front + back
const ko2 = place(system.addModule('teenage-engineering.ep-133')); // front + top

// vco.sub_out is on its BACK; ko2.line_in is on its TOP. Non-parallel faces,
// and with both devices showing their fronts, neither end is visible.
system.patchBay.createConnection(vco.jacks.get('sub_out'), ko2.jacks.get('line_in'));
system.patchBay.redrawAll();

check('a cable with neither end visible is still drawn',
    paths().length, 1);
check('and it is marked occluded',
    classesOf(paths()[0]).includes('is-occluded'), true);
check('and it is marked as crossing faces',
    classesOf(paths()[0]).includes('crosses-faces'), true);
check('both hidden ends get an anchor',
    anchors().length, 2);
check('the path is a real curve, not a zero-length stub',
    /^M [\d.]+ [\d.]+ Q/.test(paths()[0] ? paths()[0].getAttribute('d') : ''), true);

// The two ends must be at different places, or the "cable" is a dot.
const d = paths()[0] ? paths()[0].getAttribute('d') : '';
const m = d.match(/M ([\d.-]+) ([\d.-]+) Q ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)/);
check('its ends are at different points',
    Boolean(m) && Math.hypot(m[5] - m[1], m[6] - m[2]) > 50, true);

// ---- turning one device in reveals one end, and the cable stays whole ----
vco.setView('back');
system.patchBay.redrawAll();
check('turning one end into view keeps one cable',
    paths().length, 1);
check('still occluded while the other end is away',
    classesOf(paths()[0]).includes('is-occluded'), true);
check('only the still-hidden end keeps an anchor',
    anchors().length, 1);

// ---- both ends visible: a plain cable ----
ko2.setView('top');
system.patchBay.redrawAll();
check('with both faces showing the cable is not occluded',
    classesOf(paths()[0]).includes('is-occluded'), false);
check('and no anchors are drawn',
    anchors().length, 0);
check('a cable across non-parallel faces is still flagged as crossing',
    classesOf(paths()[0]).includes('crosses-faces'), true);

// ---- a cable carries a description of both its ends ----
const title = paths()[0] && paths()[0]._children.find(c => c.tag === 'title');
check('the cable names both ends and their sides',
    Boolean(title && /back/.test(title.textContent) && /top/.test(title.textContent)),
    true);

// ---- tracing ----
const dfam = place(system.addModule('moog.dfam'));
system.patchBay.createConnection(dfam.jacks.get('vca_out'), ko2.jacks.get('line_in'));
system.patchBay.redrawAll();
check('two cables now', paths().length, 2);

system.patchBay.trace(dfam.id);
const traced = paths().filter(p => classesOf(p).includes('is-traced'));
check('tracing marks only cables touching that device', traced.length, 1);

system.patchBay.trace(ko2.id);
check('tracing a device on both cables marks both',
    paths().filter(p => classesOf(p).includes('is-traced')).length, 2);

system.patchBay.trace(null);
check('clearing the trace unmarks everything',
    paths().filter(p => classesOf(p).includes('is-traced')).length, 0);

// ---- nothing is silently dropped ----
check('every connection produced exactly one path',
    paths().length, system.patchBay.connections.length);
check('every drawn cable has one probe to aim at',
    probes().length, paths().length);
check('the probe traces the same curve as the cable it stands for',
    probes().every((probe, i) => probe.getAttribute('d') === paths()[i].getAttribute('d')),
    true);
check('the probe is wider than the line, or it could not be hit',
    probes().every(probe => Number(probe.getAttribute('stroke-width')) > 2), true);
check('the probe strokes transparent, not none - `none` has no area to hit',
    probes().every(probe => probe.getAttribute('stroke') === 'transparent'), true);

let failed = 0;
for (const r of results) {
    const pass = r.detail === undefined
        ? r.ok === true
        : JSON.stringify(r.ok) === JSON.stringify(r.detail);
    if (!pass) failed++;
    console.log(`${pass ? 'OK  ' : 'BUG '} ${r.name}`);
    if (!pass) console.log(`       got ${JSON.stringify(r.ok)} want ${JSON.stringify(r.detail)}`);
}
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
