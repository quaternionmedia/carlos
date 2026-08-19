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

// Two cable layers, because the rack has two: one over the gear for leads you
// can see the whole of, one under it for leads that disappear round the back.
// Each records what was drawn on it, so "which layer did this land on" is a
// question the model can be asked without a browser.
const svg = makeEl({ id: 'patch-cables' });
svg.appendChild = (child) => { SVG_CHILDREN.push(child); };
svg.replaceChildren = () => { SVG_CHILDREN.length = 0; };
svg.classList = { add() {}, remove() {}, toggle() {}, contains: () => false };

const BEHIND_CHILDREN = [];
const behind = makeEl({ id: 'patch-cables-behind' });
behind.appendChild = (child) => { BEHIND_CHILDREN.push(child); };
behind.replaceChildren = () => { BEHIND_CHILDREN.length = 0; };
behind.classList = { add() {}, remove() {}, toggle() {}, contains: () => false };

const rack = makeEl({ id: 'rack', rect: () => rect(0, 0, 1200, 600) });
const nodes = {
    rack, 'patch-cables': svg, 'patch-cables-behind': behind,
    status: makeEl(), 'view-indicator': makeEl(),
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
    + '\nglobalThis.ModuleFactory = ModuleFactory;' +
    '\nglobalThis.SIDE_ORDER = SIDE_ORDER;'
    + '\nglobalThis.cableSpread = cableSpread;'
);
const devDir = path.join(REPO, 'catalogue/devices');
ModuleFactory.load({
    categories: [],
    devices: fs.readdirSync(devDir).filter(f => f.endsWith('.json'))
        .map(f => JSON.parse(fs.readFileSync(path.join(devDir, f), 'utf8'))),
});
// On the global, not a module-scoped `const`. `models.js` is eval'd into the
// global scope, so the `hostSystem()` its code calls looks for `system` there -
// a local binding here is invisible to it, and anything routed through that
// accessor silently sees no system at all. That is how the lane checks below
// first "passed" against an empty list.
global.system = new EurorackSystem();

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
const cablesIn = (children) => children.filter(
    c => c.tag === 'path' && classesOf(c).includes('cable'));
// Everything drawn, wherever it landed: most of this harness asks whether a
// cable exists at all, and which layer it is on is a separate question.
const paths = () => [...cablesIn(SVG_CHILDREN), ...cablesIn(BEHIND_CHILDREN)];
const frontPaths = () => cablesIn(SVG_CHILDREN);
const behindPaths = () => cablesIn(BEHIND_CHILDREN);
const probes = () => [...SVG_CHILDREN, ...BEHIND_CHILDREN].filter(
    c => c.tag === 'path' && classesOf(c).includes('cable-hit'));
const anchors = () => SVG_CHILDREN.filter(c => c.tag === 'circle');

// ---- a cable between two faces that are not both showing ----
const ko2 = place(system.addModule('teenage-engineering.ep-133')); // front, back, top
const desk = place(system.addModule('allen-heath.qu24'));          // front, back, top

// Both turned to their tops, set here rather than inherited: a Qu-24 has
// sockets on its front lip, so into a rack facing front it arrives facing
// front, and a harness that assumed otherwise would be testing a state it had
// not established.
desk.setView('top');
ko2.setView('top');

// desk.talkback_in is on its FRONT lip and ko2.line_out on its BACK edge, so
// with both showing their tops the cable has two ends on two different faces
// and neither of them visible. That is the case this harness exists for, and
// the one a rack of real gear produces constantly.
system.patchBay.createConnection(
    ko2.jacks.get('line_out'), desk.jacks.get('talkback_in'));
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

// ---- turning one device in reveals one end: half in, half out ----
//
// One lead, drawn in two pieces, because the two ends are in different places
// in the room. The half leaving the socket you can see is in the open and
// solid; the half arriving behind the other device is under it and dashed.
// Drawing all of it on either layer is wrong at one end - entirely in front and
// it lies across the device it disappears into, entirely behind and it vanishes
// at the socket it is plugged into.
desk.setView('front');
system.patchBay.redrawAll();
check('turning one end into view keeps one cable',
    system.patchBay.connections.length, 1);
check('drawn as two pieces, one per end', paths().length, 2);
check('the visible half is over the gear and solid',
    [frontPaths().length, classesOf(frontPaths()[0]).includes('is-occluded')],
    [1, false]);
check('the hidden half is under the gear and dashed',
    [behindPaths().length, classesOf(behindPaths()[0]).includes('is-occluded')],
    [1, true]);

// The two halves meet: the end of one is the start of the other, or the lead
// has a gap in it where it crosses from one layer to the other.
const ends = (path) => {
    const m = path.getAttribute('d').match(
        /M ([\d.-]+) ([\d.-]+) Q [\d.-]+ [\d.-]+ ([\d.-]+) ([\d.-]+)/);
    return m && { start: [+m[1], +m[2]], finish: [+m[3], +m[4]] };
};
// Which half is which depends on which end is hidden, so this asks that they
// share a point rather than assuming an order.
const front = ends(frontPaths()[0]);
const back = ends(behindPaths()[0]);
const corners = [front.start, front.finish].map(p => JSON.stringify(p));
const theirs = [back.start, back.finish].map(p => JSON.stringify(p));
check('and the halves meet exactly',
    corners.filter(c => theirs.includes(c)).length, 1);

check('only the still-hidden end keeps an anchor',
    anchors().length, 1);

// ---- both ends visible: a plain cable ----
ko2.setView('back');
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
    Boolean(title && /back/.test(title.textContent)
        && /front/.test(title.textContent)),
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

// ---- a pair turned away is still a pair ----
// Every hidden socket used to anchor to the midpoint of its device's edge, so
// two cables between the same two devices arrived at the same point and left
// from the same point: one visible run standing for two leads, with no way to
// tell which end was which.
system.clearRack();
SVG_CHILDREN.length = 0;

const send = place(system.addModule('nord.stage-3'));
const recv = place(system.addModule('focusrite.scarlett-2i2'));

// The Stage 3's outputs are a pair on its back, adjacent in its layout.
system.patchBay.createConnection(send.jacks.get('out_l'), recv.jacks.get('input_1'));
system.patchBay.createConnection(send.jacks.get('out_r'), recv.jacks.get('input_2'));
check('two cables between the same two devices',
    system.patchBay.connections.length, 2);

// Turn the sending device away from its sockets, so both ends go to silhouette.
send.setView('top');
system.patchBay.redrawAll();

const anchorsOf = (name) => {
    const jack = send.jacks.get(name);
    return system.patchBay.silhouetteAnchor(jack, system.patchBay.rackOrigin());
};
const anchorL = anchorsOf('out_l');
const anchorR = anchorsOf('out_r');

check('a hidden pair anchors at two distinct points',
    Boolean(anchorL && anchorR && anchorL.x !== anchorR.x), true);
check('and in the order they sit on the panel, L before R',
    Boolean(anchorL && anchorR && anchorL.x < anchorR.x), true);
// Measured from the device's own box: `place` steps each device along, so a
// literal here would be asserting where the harness happened to put it.
const sendBox = send.element.getBoundingClientRect();
const rackLeft = system.patchBay.rackOrigin().left;
const boxLeft = sendBox.left - rackLeft;
check('both anchors stay off the corners of the device',
    [anchorL, anchorR].every(
        a => a && a.x > boxLeft && a.x < boxLeft + sendBox.width), true);

// And the two runs are two curves, not one drawn twice. Four pieces, because
// each lead has one end in sight and one out of it.
const drawn = paths().map(p => p.getAttribute('d'));
check('two cables produced two runs', system.patchBay.connections.length, 2);
check('drawn as four pieces, two per lead', drawn.length, 4);
check('and no two pieces are the same curve',
    new Set(drawn).size, drawn.length);

// A device with no layout falls back to socket order, which is still an order.
system.clearRack();
SVG_CHILDREN.length = 0;
const bare = place(system.addModule('squarp.hapax'));
const backJacks = [...bare.jacks.values()].filter(j => j.side === 'back');
const fractions = backJacks.map(j => system.patchBay.edgeFraction(j));
check('an unlaid-out device still spreads its sockets along the edge',
    new Set(fractions).size, fractions.length);
check('and spreads them in the order the entry lists them',
    fractions.every((f, i) => i === 0 || f > fractions[i - 1]), true);
check('with nothing landing on a corner',
    fractions.every(f => f > 0 && f < 1), true);

// ---- all six sides anchor on their own edge ----
// `SIDE_ORDER` has had six entries since devices became n-sided, and no real
// device in the catalogue uses left, right or bottom - so three of the six
// anchor cases had never been executed. A synthetic definition covers them
// here rather than a fictional device being added to a catalogue of real gear.
ModuleFactory.definitions['test.six-sided'] = {
    id: 'test.six-sided', maker: 'Test', model: 'Six Sided',
    category: 'eurorack',
    jacks: SIDE_ORDER.flatMap(side => ([
        { name: `${side}_a`, label: `${side} A`, type: 'output', signal: 'audio', side },
        { name: `${side}_b`, label: `${side} B`, type: 'input', signal: 'audio', side },
    ])),
    parameters: [],
    layout: null,
};

system.clearRack();
SVG_CHILDREN.length = 0;
const six = place(system.addModule('test.six-sided'));
check('a device declares every side it has sockets on', six.sides, [...SIDE_ORDER]);

const sixBox = six.element.getBoundingClientRect();
const origin = system.patchBay.rackOrigin();
const edge = {
    left: sixBox.left - origin.left,
    top: sixBox.top - origin.top,
};
edge.right = edge.left + sixBox.width;
edge.bottom = edge.top + sixBox.height;

// Which edge each side leaves by, and which way its sockets spread along it.
const EDGES = {
    front:  { fixed: 'y', at: edge.top,    along: 'x' },
    top:    { fixed: 'y', at: edge.top,    along: 'x' },
    back:   { fixed: 'y', at: edge.bottom, along: 'x' },
    bottom: { fixed: 'y', at: edge.bottom, along: 'x' },
    left:   { fixed: 'x', at: edge.left,   along: 'y' },
    right:  { fixed: 'x', at: edge.right,  along: 'y' },
};

SIDE_ORDER.forEach(side => {
    const spec = EDGES[side];
    const anchors = ['a', 'b'].map(
        suffix => system.patchBay.silhouetteAnchor(six.jacks.get(`${side}_${suffix}`), origin)
    );
    check(`${side}: both sockets anchor on the ${side} edge`,
        anchors.every(a => a && Math.abs(a[spec.fixed] - spec.at) < 0.001), true);
    check(`${side}: the two sockets do not land on the same point`,
        anchors[0][spec.along] !== anchors[1][spec.along], true);
    check(`${side}: they spread in socket order`,
        anchors[0][spec.along] < anchors[1][spec.along], true);
});

// And every side turns, in order, all the way round.
const walked = [six.view];
for (let i = 1; i < SIDE_ORDER.length; i++) walked.push(six.cycle(1));
check('turning walks every side in order', walked, [...SIDE_ORDER]);
check('and wraps back to the first', six.cycle(1), SIDE_ORDER[0]);

delete ModuleFactory.definitions['test.six-sided'];


// ---------------------------------------------------------------------------
// A bus is not a direction, and a lead carrying channels is drawn as them
// ---------------------------------------------------------------------------
// Every USB socket in the catalogue is typed `output`, because the catalogue
// types every jack `input` or `output` and almost everything is one or the
// other. Under the plain rule two of them refused each other - correct for
// audio, wrong for what USB is: a pair of wires carrying messages both ways,
// with host and device a role the two ends negotiate.
system.clearRack();
// `place` gives each device a measurable box: this harness stubs the DOM, and
// a device with no geometry anchors nowhere, so a lead between two of them
// would not be drawn at all.
const pad = place(system.addModule('novation.launchpad-x'));
const box = place(system.addModule('teenage-engineering.ep-133'));

const padUsb = pad.jacks.get('usb');
const boxUsb = box.jacks.get('usb_c');

check('both USB sockets are typed as outputs',
    [padUsb.type, boxUsb.type], ['output', 'output']);
check('and both are bus ports', [padUsb.isBus(), boxUsb.isBus()], [true, true]);
check('two USB ports may be linked anyway', padUsb.canConnectTo(boxUsb), true);
check('and nothing is refused', padUsb.refusalReason(boxUsb), null);

// The rule is about the bus, not about giving up on direction.
const audioOut = box.jacks.get('line_out');
check('two audio outputs still refuse each other',
    audioOut.canConnectTo(pad.jacks.get('midi_out')), false);
check('and USB does not go into an audio socket',
    padUsb.canConnectTo(audioOut), false);
check('with a reason that names both signals',
    typeof padUsb.refusalReason(audioOut), 'string');

check('the link is made', system.patchBay.createConnection(padUsb, boxUsb), true);

// --- the split, derived from the bindings ---
//
// No bindings, no channels: a lead nobody has assigned anything to is one
// line, because it is one lead. The strands are the assignments, so they
// cannot be drawn before there are any.
system.midi = [];
system.patchBay.redrawAll();
const link = system.patchBay.connections[0];
check('an unassigned lead is a single strand', link.strands.length, 1);
check('and carries no channels',
    system.patchBay.lanesOf(link.source, link.target).length, 0);

system.midi = ['A', 'B', 'C', 'D'].map((group, index) => ({
    id: `bind-${group}`,
    source: { type: 'channel', channel: index + 1 },
    module: box.id,
    label: `Group ${group}`,
}));
system.patchBay.redrawAll();

const lanes = system.patchBay.lanesOf(link.source, link.target);
check('four bindings on four channels make four lanes', lanes.length, 4);
check('in channel order', lanes.map(l => l.channel), [1, 2, 3, 4]);
check('each named by what is bound to it',
    lanes.map(l => l.label), ['Group A', 'Group B', 'Group C', 'Group D']);
check('and the lead is drawn as four strands',
    system.patchBay.connections[0].strands.length, 4);

// Derived, not stored: rebinding moves the picture with nothing kept in step.
system.midi = system.midi.slice(0, 2);
system.patchBay.redrawAll();
check('unbinding two groups leaves two strands',
    system.patchBay.connections[0].strands.length, 2);

// Several rules on one channel is a distribution, not four captions.
system.midi = [
    { id: 'a', source: { type: 'note', channel: 10, note: 36 }, module: box.id, label: 'kick' },
    { id: 'b', source: { type: 'note', channel: 10, note: 39 }, module: box.id, label: 'clap' },
];
system.patchBay.redrawAll();
const shared = system.patchBay.lanesOf(link.source, link.target);
check('two rules on one channel are one strand', shared.length, 1);
check('named for the count rather than for one of them',
    shared[0].label, '2 bindings');

// A binding for some other device is not on this lead.
system.midi = [
    { id: 'c', source: { type: 'channel', channel: 7 }, module: 'somewhere-else', label: 'x' },
];
system.patchBay.redrawAll();
check('a binding naming another device is not on this lead',
    system.patchBay.lanesOf(link.source, link.target).length, 0);

system.midi = [];
system.clearRack();


// ---------------------------------------------------------------------------
// A lead that goes round the back is drawn round the back
// ---------------------------------------------------------------------------
// The dashes said "part of this run is behind something" while the cable was
// painted over the panel it was meant to be behind - the picture contradicting
// its own annotation. Which layer a lead lands on is the same question as
// whether it is occluded, asked once.
system.clearRack();
const upper = place(system.addModule('carlos.vco'));
const lower = place(system.addModule('carlos.vcf'));

// Both showing their fronts, and a front-to-front lead: nothing is hidden, so
// it runs across the gear in plain sight.
upper.setView('front');
lower.setView('front');
system.patchBay.createConnection(
    upper.jacks.get('audio_out'), lower.jacks.get('audio_in'));
system.patchBay.redrawAll();
check('a lead you can see the whole of is drawn over the gear',
    [frontPaths().length, behindPaths().length], [1, 0]);
check('and it is not marked occluded',
    classesOf(frontPaths()[0]).includes('is-occluded'), false);

// Turn one device away and the same lead now leaves out of sight.
lower.setView('back');
system.patchBay.redrawAll();
// Half in, half out: the end still on a face you can see stays in front.
check('turning a device away puts that half of the lead under the gear',
    [frontPaths().length, behindPaths().length], [1, 1]);
check('the hidden half says so',
    classesOf(behindPaths()[0]).includes('is-occluded'), true);
check('and the visible half does not',
    classesOf(frontPaths()[0]).includes('is-occluded'), false);

// The probe follows its cable, or `cableAt` stops finding leads that moved.
check('the probe went with it', probes().length, 1);
check('the anchor mark stays on top, where it can be seen',
    anchors().length > 0, true);

// Turning it back brings the lead forward again: the layer is read off the
// geometry every redraw rather than decided once when the cable was made.
lower.setView('front');
system.patchBay.redrawAll();
check('and turning it back brings the lead forward',
    [frontPaths().length, behindPaths().length], [1, 0]);

system.clearRack();


// ---------------------------------------------------------------------------
// Two sockets in one column do not share an anchor
// ---------------------------------------------------------------------------
// An edge has one dimension and a panel has two, so projecting one onto the
// other drops an axis - and every pair of sockets that shared the surviving
// one arrived at the same point on the outline. Two leads, one visible end,
// no way to tell which was which: the defect `SILHOUETTE_INSET` was written to
// fix for a stereo pair, back again on any device whose patch bay is a grid.
//
// A DFAM is one: `trigger_in` and `vca_out` sit at the same `x`, one above the
// other. Turning the rack round stacked both leads on one anchor.
system.clearRack();
const bay = place(system.addModule('moog.dfam'));
const stacked = bay.jacks.get('trigger_in');
const below = bay.jacks.get('vca_out');

const laid = ModuleFactory.definitions['moog.dfam'].layout.jacks;
check('the two really are in one column',
    laid.trigger_in.x === laid.vca_out.x, true);
check('and really are different sockets',
    laid.trigger_in.y !== laid.vca_out.y, true);

const bayOf = (jack) => system.patchBay.edgeFraction(jack);
check('they no longer land on the same place along the edge',
    bayOf(stacked) !== bayOf(below), true);
check('but both stay near where they actually are',
    [Math.abs(bayOf(stacked) - laid.trigger_in.x) < 0.06,
     Math.abs(bayOf(below) - laid.vca_out.x) < 0.06], [true, true]);
check('and neither runs off the edge',
    [bayOf(stacked), bayOf(below)].every(f => f >= 0 && f <= 1), true);

// Every socket on that face, all twenty-two of them: no two share a point.
const fronts = [...bay.jacks.values()].filter(j => j.side === 'front');
const spots = fronts.map(j => Math.round(bayOf(j) * 10000));
check('twenty-two sockets, twenty-two places',
    new Set(spots).size, fronts.length);

// A socket with no column-mate keeps its exact declared position: the fan is
// for collisions, and a position is real information otherwise.
const alone = [...bay.jacks.values()].find(j => {
    const x = laid[j.name]?.x;
    return x !== undefined && fronts.filter(
        p => Math.abs((laid[p.name]?.x ?? -9) - x) < 0.02).length === 1;
});
if (alone) {
    check('a socket with no column-mate is left where it is',
        Math.abs(bayOf(alone) - laid[alone.name].x) < 1e-9, true);
}

system.clearRack();


// ---------------------------------------------------------------------------
// The drift goes both ways
// ---------------------------------------------------------------------------
// Each cable hangs a little more or a little less than its neighbour, so two
// leads between the same two devices can be told apart. That used to return 0
// to 1, which only ever *added* sag: every cable drifted the same way, and a
// bundle of them leaned downhill together instead of scattering.
const drifts = [];
for (let i = 0; i < 400; i++) {
    drifts.push(cableSpread(
        { module: { id: `m${i}` }, name: 'out' },
        { module: { id: `n${i}` }, name: 'in' }));
}
const under = drifts.filter(d => d < 0).length;
const over = drifts.filter(d => d > 0).length;
check('cables drift under as often as over', Math.abs(under - over) < 60, true);
check('and none drifts further than the spread allows',
    drifts.every(d => d >= -0.5 && d <= 0.5), true);
check('the drift averages out to nothing',
    Math.abs(drifts.reduce((a, b) => a + b, 0) / drifts.length) < 0.05, true);

// Keyed on the two jacks, so unpatching one lead does not shuffle the others.
check('one cable always drifts the same way',
    cableSpread({ module: { id: 'a' }, name: 'out' }, { module: { id: 'b' }, name: 'in' }),
    cableSpread({ module: { id: 'a' }, name: 'out' }, { module: { id: 'b' }, name: 'in' }));

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
