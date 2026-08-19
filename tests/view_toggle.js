// Does turning a device actually reach the screen?
//
// Every other harness asserts `module.view`, which is the model. This one
// asserts the tree: exactly one face laid out, and it is the face for the side
// the model claims. A device that reports turning and does not turn passes
// every model test there is.

const fs = require('fs');
const path = require('path');
const { El, makeDocument } = require('./dom.js');

const REPO = path.resolve(__dirname, '..');
const load = (f) => fs.readFileSync(path.join(REPO, f), 'utf8');

const document = makeDocument();
const rack = new El('div');
rack.setAttribute('id', 'rack');
document.body.appendChild(rack);
document.register('rack', rack);

const status = new El('div');
status.setAttribute('id', 'status');
document.body.appendChild(status);
document.register('status', status);

const cables = new El('svg');
cables.setAttribute('id', 'patch-cables');
rack.appendChild(cables);
document.register('patch-cables', cables);

global.document = document;
global.window = { innerWidth: 1200, innerHeight: 800, addEventListener() {} };
global.anime = () => {};
global.navigator = {};

(0, eval)(
    load('static/rad-core.js') + load('static/midi.js') + load('static/models.js')
    + '\nglobalThis.EurorackSystem = EurorackSystem;'
    + '\nglobalThis.ModuleFactory = ModuleFactory;'
);

const devDir = path.join(REPO, 'catalogue/devices');
ModuleFactory.load({
    categories: [],
    devices: fs.readdirSync(devDir).filter(f => f.endsWith('.json'))
        .map(f => JSON.parse(fs.readFileSync(path.join(devDir, f), 'utf8'))),
});

// On the global: `models.js` is eval'd into global scope, so the `hostSystem()`
// its code calls looks for `system` there. A module-scoped binding here is
// invisible to it, and every path routed through that accessor quietly sees no
// system at all - which is a harness agreeing with code it never ran.
global.system = new EurorackSystem();

const results = [];
const check = (name, got, want) => results.push({ name, got, want });

// What the tree says is on screen for one device.
function shownSides(module) {
    return module.element.querySelectorAll('.face')
        .filter(face => face.classList.contains('active'))
        .map(face => face.getAttribute('data-side'));
}
function facesOf(module) {
    return module.element.querySelectorAll('.face')
        .map(face => face.getAttribute('data-side'));
}

const vco = system.addModule('carlos.vco');            // front, back
const ko2 = system.addModule('teenage-engineering.ep-133'); // front, back, top

// --- the tree was built at all ---
check('a module renders its faces', facesOf(vco).sort(), ['back', 'front']);

// A face with nothing on it is not drawn. A K.O. II is a slab played from
// above: its surface is the top, its sockets are along the back edge, and its
// front is the thin lip between them. Nothing is on that lip, so it is not a
// side you can turn to - abstract or laid out, because a device has one face
// and the mode it is drawn in is not an opinion about which side that is.
check('a face with nothing on it is not drawn',
    facesOf(ko2).sort(), ['back', 'top']);
check('the model agrees about what it draws',
    ko2.drawnSides(), ['back', 'top']);
check('the side is still one the device has',
    ko2.sides, ['front', 'back', 'top']);

// --- one face laid out, and it is the right one ---
check('exactly one face is active to start', shownSides(vco), ['front']);
check('and it matches the model', shownSides(vco)[0], vco.view);

// --- turning one device ---
system.turnModule(vco.id);
check('the model turned', vco.view, 'back');
check('THE TREE TURNED', shownSides(vco), ['back']);
check('still exactly one face active', shownSides(vco).length, 1);
check('data-view follows too', vco.element.getAttribute('data-view'), 'back');
// Turning the VCO must not move anything else.
check('the other device did not move', shownSides(ko2), ['top']);

// --- turning everything ---
system.turnModule(vco.id); // back to front
system.flipAll();
check('every device turned in the model',
    [vco.view, ko2.view], ['back', 'back']);
check('EVERY DEVICE TURNED ON SCREEN',
    [shownSides(vco)[0], shownSides(ko2)[0]], ['back', 'back']);

// --- cycling wraps ---
system.flipAll();
check('cycling wraps in the tree',
    [shownSides(vco)[0], shownSides(ko2)[0]], ['front', 'top']);

// --- backwards ---
system.flipAll(-1);
check('shift-tab walks back in the tree',
    [shownSides(vco)[0], shownSides(ko2)[0]], ['back', 'back']);

// --- devices do not share a side list ---
//
// A VCO has a front and a back; a K.O. II has a back and a top and no front
// at all. Two devices whose lists overlap in one side and disagree about the
// rest, which is what makes "turn everything" mean each device advancing its
// own list rather than the rack setting one value on all of them.
system.setMode('irl');
check('laid out, the blank lip is gone', facesOf(ko2).sort(), ['back', 'top']);
// Arrival, not this device: it was left on its back two checks ago and a mode
// switch keeps a side that is still drawn. So ask one that arrives here.
const arriving = system.addModule('teenage-engineering.ep-133');
check('and one arriving opens on the face it is played from',
    shownSides(arriving), ['top']);
check('the face it would open on is its top', ko2.preferredView(), 'top');
system.removeModule(arriving.id);
check('while the VCO still has its front', facesOf(vco).sort(), ['back', 'front']);

vco.setView('front');
ko2.setView('top');
system.flipAll();
check('each device advanced its own list',
    [vco.view, ko2.view], ['back', 'back']);
system.flipAll();
check('and wrapped through lists of its own',
    [vco.view, ko2.view], ['front', 'top']);
check('NO DEVICE EVER SHOWS A BLANK FACE',
    facesOf(ko2).includes('front'), false);

system.setMode('minimal');

// --- a device with one side does not move ---
system.flipAll();  // reset to front

// --- switching display mode keeps the shown side ---
vco.setView('back');
system.setMode('irl');
check('mode switch preserves the side in the model', vco.view, 'back');
check('MODE SWITCH PRESERVES THE SIDE ON SCREEN', shownSides(vco), ['back']);
check('irl draws a panel', vco.element.querySelectorAll('.irl-panel').length > 0, true);

// --- and turning still works after a mode switch ---
system.turnModule(vco.id);
check('turning still reaches the tree after a mode switch',
    shownSides(vco), ['front']);

system.setMode('minimal');
check('back to minimal keeps the side', shownSides(vco), ['front']);
check('minimal draws no panel',
    vco.element.querySelectorAll('.irl-panel').length, 0);

// --- a device added while a mode is set gets that mode ---
const dfam = system.addModule('moog.dfam');
system.setMode('irl');
const added = system.addModule('moog.subharmonicon');
check('a device added under irl draws as irl',
    added.element.querySelectorAll('.irl-panel').length > 0, true);

// ---------------------------------------------------------------
// ONE DEVICE, ONE NODE
// ---------------------------------------------------------------
// A device rendered twice looks like a device that half works: the stale copy
// is on screen and unreactive, the live one is below it. Nothing in the model
// can see this, which is how it reached a person instead of a test.
function moduleNodes() {
    return rack.querySelectorAll('.module');
}
function duplicateIds() {
    const counts = new Map();
    moduleNodes().forEach(node => {
        const id = node.getAttribute('data-module-id');
        counts.set(id, (counts.get(id) || 0) + 1);
    });
    return [...counts.entries()].filter(([, n]) => n > 1).map(([id, n]) => `${id} x${n}`);
}
function strayChildren() {
    // A `.module` parented straight to the rack rather than to a row or the
    // loose container is a node that escaped the rebuild.
    return rack.children.filter(c => c.classList.contains('module')).length;
}

system.clearRack();
system.setMode('minimal');
const a = system.addModule('carlos.vco');
const b = system.addModule('moog.dfam');

check('two devices, two nodes', moduleNodes().length, 2);
check('no duplicates after adding', duplicateIds(), []);
check('nothing parented straight to the rack', strayChildren(), 0);

system.setMode('irl');
check('mode switch does not duplicate', moduleNodes().length, 2);
check('and leaves no duplicate ids', duplicateIds(), []);
check('and no strays', strayChildren(), 0);

system.setMode('minimal');
check('switching back does not duplicate', moduleNodes().length, 2);

// Import is where this actually bit: modules were appended straight to the
// rack, then re-rendered, leaving the originals behind.
const imported = JSON.parse(fs.readFileSync(
    path.join(REPO, 'catalogue/examples/moog.dfam.complex.json'), 'utf8'));
system.importState(imported);

check('IMPORT LEAVES ONE NODE PER DEVICE',
    moduleNodes().length, system.modules.size);
check('IMPORT LEAVES NO DUPLICATES', duplicateIds(), []);
check('import leaves no strays', strayChildren(), 0);

// And once more with a mode set, which is the path that first broke.
system.setMode('irl');
system.importState(imported);
check('import under irl leaves one node per device',
    moduleNodes().length, system.modules.size);
check('import under irl leaves no duplicates', duplicateIds(), []);

// Every node on screen belongs to a device the model still has.
const modelIds = new Set([...system.modules.keys()]);
check('every node on screen is a device the model has',
    moduleNodes().every(n => modelIds.has(n.getAttribute('data-module-id'))), true);

// Removing a device removes its node.
const victim = [...system.modules.keys()][0];
const before = moduleNodes().length;
system.removeModule(victim);
check('removing a device removes exactly one node', moduleNodes().length, before - 1);
check('and its node is gone',
    moduleNodes().some(n => n.getAttribute('data-module-id') === victim), false);

// --- controls reach the screen as controls ---
// The model is not the screen, and "a knob exists" is not "a knob can be
// turned". These assert the tree, which is the only thing that caught the
// `irl` knobs being rendered and dead.
system.clearRack();
system.setMode('minimal');
const controlled = system.addModule('carlos.vco');

const knobs = () => controlled.element.querySelectorAll('.knob, .irl-knob');
const jacks = () => controlled.element.querySelectorAll('.jack');

check('minimal draws a knob per parameter',
    knobs().length, controlled.parameters.size);
check('every knob is reachable by keyboard',
    knobs().every(k => k.getAttribute('tabindex') === '0'), true);
check('every knob says what it is and where it stands',
    knobs().every(k => k.getAttribute('role') === 'slider'
        && k.getAttribute('aria-valuenow') !== null
        && k.getAttribute('aria-valuemax') !== null), true);
check('every socket is reachable by keyboard',
    jacks().every(j => j.getAttribute('tabindex') === '0'), true);
check('every socket carries a label naming its signal and side',
    jacks().every(j => /\((cv|audio|gate|midi|clock|trigger)/.test(
        j.getAttribute('aria-label') || '')), true);

// The same device drawn the other way. `irl` names its knobs `.irl-knob`, and
// a selector reading only `.knob` left every one of them inert.
system.setMode('irl');
const laidOut = controlled.element.querySelectorAll('.irl-knob');
check('as-laid-out draws its knobs as irl-knobs', laidOut.length > 0, true);
check('and those knobs are reachable too',
    laidOut.every(k => k.getAttribute('tabindex') === '0'), true);
check('and carry the value they are showing',
    laidOut.every(k => k.getAttribute('aria-valuenow') !== null), true);
// The one that matters. Attributes are markup; a handler is what makes a knob
// turn. `irl` knobs were drawn complete and wired to nothing, which no
// attribute assertion would have noticed.
const listenerTypes = (el) => new Set(el.listeners.map(l => l.type));
check('an as-laid-out knob is actually wired to a drag',
    laidOut.every(k => listenerTypes(k).has('pointerdown')), true);
check('and to a wheel and the keyboard',
    laidOut.every(k => listenerTypes(k).has('wheel') && listenerTypes(k).has('keydown')),
    true);
check('a minimal knob is wired the same way',
    controlled.element.querySelectorAll('.knob')
        .every(k => listenerTypes(k).has('pointerdown')), true);
check('a socket answers to the keyboard as well as the pointer',
    jacks().every(j => listenerTypes(j).has('click') && listenerTypes(j).has('keydown')),
    true);

// A value set from anywhere has to reach the attribute a screen reader reads.
system.setMode('minimal');
const param = [...controlled.parameters.values()][0];
param.setValue(param.maxValue);
controlled.paintKnob(param);
check('painting a knob updates the value it announces',
    controlled.element.querySelector(`[data-param="${param.name}"]`)
        .getAttribute('aria-valuenow'),
    String(Math.round(param.maxValue)));

// --- a device drawn as a caricature of itself ---
// `irl` used to draw knobs and sockets and nothing else, so a stage piano came
// out as five circles on an empty rectangle. These assert the tree: the keybed,
// the screens and the section plates are either on it or they are not.
system.clearRack();
system.setMode('irl');
const nord = system.addModule('nord.stage-3');
const drawn = (sel) => nord.element.querySelectorAll(sel);

check('a stage piano opens on the face it is played from', nord.view, 'top');
check('and has the three sides it carries', nord.sides, ['front', 'back', 'top']);

// 88 keys is 52 naturals and 36 sharps. Any other split is a keybed drawn from
// the wrong note, which puts the wrong key under every hand position.
const keys = drawn('.irl-key');
const sharps = drawn('.irl-key.is-sharp');
check('an 88 draws 88 keys', keys.length, 88);
check('52 of them natural', keys.length - sharps.length, 52);
check('36 of them sharp', sharps.length, 36);

check('the three sections read as sections', drawn('.irl-plate').length, 3);
check('each section has a screen, and the programmer has one',
    drawn('.irl-screen').length, 4);
check('pitch and modulation are both there', drawn('.irl-wheel').length, 2);
check('the organ has its nine drawbars', drawn('.irl-drawbar').length, 9);
check('and the drawbars are controls, not decoration',
    drawn('.irl-drawbar').every(d => d.getAttribute('role') === 'slider'), true);

// Decoration is decoration: a keybed this app cannot play, a logo, a plate.
// Announcing 88 keys before the controls would bury the controls.
const decoration = drawn('.irl-feature').filter(f => !f.getAttribute('role'));
check('there is decoration to hide', decoration.length > 0, true);
check('and all of it is hidden from a screen reader',
    decoration.every(f => f.getAttribute('aria-hidden') === 'true'), true);

// A grid that sends is not decoration. It is announced, and so is every cell.
const live = drawn('.irl-feature[role="group"]');
check('a grid that emits is announced rather than hidden',
    live.every(f => f.getAttribute('aria-hidden') === null
        && (f.getAttribute('aria-label') || '').length > 0), true);

// The face's own proportion, and the measurement it was compressed from.
const activePanel = drawn('.irl-panel').find(
    panel => panel.parent?.classList.contains('active'));
const panelStyle = activePanel?.getAttribute('style') || '';
check('the drawn face carries a proportion', /--aspect:[\d.]+/.test(panelStyle), true);
check('and the measurement it came from',
    /--true-aspect:3\.84/.test(panelStyle), true);
check('the top is not drawn at the front’s proportion',
    /--true-aspect:10\.7/.test(panelStyle), false);

// A device drawn as laid out is drawn at something like its real size.
check('a laid-out device carries its own drawn width',
    nord.element.style.getPropertyValue('--panel-width').endsWith('px'), true);

// `minimal` is the abstract box every device shares and makes no such claim.
system.setMode('minimal');
const bare = system.modules.get(nord.id);
check('minimal draws no panel furniture',
    bare.element.querySelectorAll('.irl-feature').length, 0);
check('and claims no proportion',
    bare.element.style.getPropertyValue('--panel-width'), '');

// --- every drawn thing does something ---
// A panel of pictures is a photograph. These assert the tree and the wiring:
// a grid that says it sends is a grid of buttons that are wired to send, and a
// screen shows what its entry says it reads rather than a message baked into
// the markup.
system.clearRack();
system.setMode('irl');
const pad = system.addModule('novation.launchpad-x');
const listeners = (el) => new Set(el.listeners.map(l => l.type));

const cells = pad.element.querySelectorAll('.irl-cell');
check('a controller draws every cell it has', cells.length, 64 + 8 + 8);
check('and every one of them is a button',
    cells.every(c => c.tagName === 'BUTTON'), true);
check('wired to a press and to the keyboard',
    cells.every(c => listeners(c).has('pointerdown') && listeners(c).has('keydown')),
    true);
check('each naming where it is, so they are not 80 identical controls',
    new Set(cells.map(c => c.getAttribute('aria-label'))).size, cells.length);

// The note a cell sends climbs with the grid: an entry declares two numbers
// rather than sixty-four.
const gridCells = pad.element
    .querySelectorAll('.irl-pads')[0].querySelectorAll('.irl-cell');
check('the first pad sends what the entry declares',
    gridCells[0].getAttribute('title'), 'note 36 ch 10');
check('and the last sends sixty-three notes up',
    gridCells[63].getAttribute('title'), 'note 99 ch 10');

// A press reaches the device, and would reach the host if there were one.
let sent = null;
pad.element.querySelectorAll('.irl-pads')[0]
    .querySelectorAll('.irl-cell')[3]
    .listeners.filter(l => l.type === 'pointerdown')
    .forEach(l => l.fn({ preventDefault() {}, stopPropagation() {} }));
check('pressing a pad tells the device what it sent', pad.lastEvent, 'note 39 ch 10');

// Screens read their declared source, and carry no text of their own.
const screenOf = (module) => module.element.querySelectorAll('.irl-screen')[0];
check('a screen names what it reads',
    screenOf(pad).getAttribute('data-source'), 'last-event');
check('and shows the event that just happened',
    screenOf(pad).querySelectorAll('.irl-screen-text')[0].textContent,
    'NOTE 39 CH 10');

// A different source reads something else entirely.
const stage = system.addModule('nord.stage-3');
const sources = stage.element.querySelectorAll('.irl-screen')
    .map(s => s.getAttribute('data-source'));
check('a device may read several different things', new Set(sources).size, 4);
const byId = {};
stage.element.querySelectorAll('.irl-screen').forEach(s => {
    byId[s.getAttribute('data-source')] =
        s.querySelectorAll('.irl-screen-text')[0].textContent;
});
check('the device screen shows the device', byId.device, 'NORD STAGE 3');
check('and none of them is empty',
    Object.values(byId).every(text => text.length > 0), true);

// Moving a control is an event too, and a `parameter` screen is what reads it.
const drawbar = stage.element.querySelectorAll('.irl-drawbar')[0];
const moved = stage.parameters.get(drawbar.getAttribute('data-param'));
drawbar.listeners.filter(l => l.type === 'keydown').forEach(l => l.fn({
    key: 'ArrowUp', shiftKey: false, ctrlKey: false, altKey: false,
    metaKey: false, preventDefault() {}, stopPropagation() {},
}));
const after = {};
stage.element.querySelectorAll('.irl-screen').forEach(s => {
    after[s.getAttribute('data-source')] =
        s.querySelectorAll('.irl-screen-text')[0].textContent;
});
check('moving a control reaches the parameter screen',
    after.parameter.startsWith(moved.label), true);
check('and the device screen is unmoved by it', after.device, 'NORD STAGE 3');

// A desk's faders are controls, not scenery.
const desk = system.addModule('allen-heath.qu24');
check('every channel fader on a desk moves',
    desk.element.querySelectorAll('.irl-fader').length, 25);
check('and each is a slider a screen reader can read',
    desk.element.querySelectorAll('.irl-fader')
        .every(f => f.getAttribute('role') === 'slider'), true);

let failed = 0;
for (const r of results) {
    const pass = JSON.stringify(r.got) === JSON.stringify(r.want);
    if (!pass) failed++;
    console.log(`${pass ? 'OK  ' : 'BUG '} ${r.name}`);
    if (!pass) console.log(`       got ${JSON.stringify(r.got)} want ${JSON.stringify(r.want)}`);
}
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
