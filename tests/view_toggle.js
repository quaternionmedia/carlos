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

const system = new EurorackSystem();

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
const ko2 = system.addModule('teenage-engineering.ep-133'); // front, top

// --- the tree was built at all ---
check('a module renders its faces', facesOf(vco).sort(), ['back', 'front']);
check('a device with a top renders that too', facesOf(ko2).sort(), ['front', 'top']);

// --- one face laid out, and it is the right one ---
check('exactly one face is active to start', shownSides(vco), ['front']);
check('and it matches the model', shownSides(vco)[0], vco.view);

// --- turning one device ---
system.turnModule(vco.id);
check('the model turned', vco.view, 'back');
check('THE TREE TURNED', shownSides(vco), ['back']);
check('still exactly one face active', shownSides(vco).length, 1);
check('data-view follows too', vco.element.getAttribute('data-view'), 'back');
check('the other device did not move', shownSides(ko2), ['front']);

// --- turning everything ---
system.turnModule(vco.id); // back to front
system.flipAll();
check('every device turned in the model',
    [vco.view, ko2.view], ['back', 'top']);
check('EVERY DEVICE TURNED ON SCREEN',
    [shownSides(vco)[0], shownSides(ko2)[0]], ['back', 'top']);

// --- cycling wraps ---
system.flipAll();
check('cycling wraps in the tree',
    [shownSides(vco)[0], shownSides(ko2)[0]], ['front', 'front']);

// --- backwards ---
system.flipAll(-1);
check('shift-tab walks back in the tree',
    [shownSides(vco)[0], shownSides(ko2)[0]], ['back', 'top']);

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

let failed = 0;
for (const r of results) {
    const pass = JSON.stringify(r.got) === JSON.stringify(r.want);
    if (!pass) failed++;
    console.log(`${pass ? 'OK  ' : 'BUG '} ${r.name}`);
    if (!pass) console.log(`       got ${JSON.stringify(r.got)} want ${JSON.stringify(r.want)}`);
}
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
