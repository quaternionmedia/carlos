// Rack behaviour regression harness.
//
// Sides, per-device turning, groups, the interchange round trip, and the
// version upgrades — driven headlessly against a DOM stub. This is the largest
// behavioural suite in the project and it runs from the Python suite, so it is
// a gate rather than a script somebody remembers.
//
// Run directly: `node tests/rack_behaviour.js`
const fs = require('fs');
const path = require('path');

function el() {
    return {
        className: '', dataset: {}, style: {}, textContent: '',
        set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
        classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
        appendChild() {}, remove() {}, replaceChildren() {}, replaceWith() {},
        addEventListener() {},
        querySelector: () => null,
        querySelectorAll: () => [],
        getBoundingClientRect: () => ({ left: 0, top: 0, width: 10, height: 10 }),
    };
}

const nodes = { rack: el(), status: el(), 'patch-cables': null, 'view-indicator': el() };
global.document = {
    body: el(),
    getElementById: (id) => (id in nodes ? nodes[id] : null),
    createElement: el,
    createElementNS: el,
    addEventListener() {},
};
global.window = { addEventListener() {} };
global.anime = () => {};

const src = fs.readFileSync(
    process.argv[2] || path.join(path.resolve(__dirname, '..'), 'static/models.js'),
    'utf8');
// Indirect eval: runs in global scope, so the classes are visible here.
(0, eval)(src + '\nglobalThis.EurorackSystem = EurorackSystem;'
    + '\nglobalThis.ModuleFactory = ModuleFactory;'
    + '\nglobalThis.PATCH_VERSION = PATCH_VERSION;'
    + '\nglobalThis.PatchBayManager = PatchBayManager;');
global.system = new EurorackSystem();

// The palette now comes from the catalogue, so the harness loads it the same
// way the browser does - from the same files, without a server.
const deviceDir = path.join(path.resolve(__dirname, '..'), 'catalogue', 'devices');
const devices = fs.readdirSync(deviceDir)
    .filter(f => f.endsWith('.json'))
    .map(f => JSON.parse(fs.readFileSync(path.join(deviceDir, f), 'utf8')));
ModuleFactory.load({ categories: [], devices });

const results = [];
function check(name, actual, expected) {
    const ok = JSON.stringify(actual) === JSON.stringify(expected);
    results.push({ name, ok, actual, expected });
}

// --- modules and sides ---
const vco = system.addModule('carlos.vco');
const vcf = system.addModule('carlos.vcf');

check('vco has 4 jacks (2 front, 2 back)', vco.jacks.size, 4);
check('vco front jacks', [...vco.jacks.values()].filter(j => j.side === 'front').length, 2);
check('vco back jacks', [...vco.jacks.values()].filter(j => j.side === 'back').length, 2);

// --- connection rules ---
const frontOut = vco.jacks.get('audio_out');
const frontIn = vcf.jacks.get('audio_in');
const backOut = vco.jacks.get('sub_out');
const backIn = vcf.jacks.get('cutoff_cv_in');

check('front out -> front in is legal', frontOut.canConnectTo(frontIn), true);
check('front out -> back in is LEGAL', frontOut.canConnectTo(backIn), true);
check('no side refusal remains', frontOut.refusalReason(backIn), null);
check('two outputs refused', frontOut.canConnectTo(backOut), false);
check('self-patch refused', frontOut.canConnectTo(frontOut), false);
check('back out -> back in is legal', backOut.canConnectTo(backIn), true);

// --- connections across sides ---
system.patchBay.createConnection(frontOut, frontIn);
system.patchBay.createConnection(backOut, backIn);
system.patchBay.createConnection(vco.jacks.get('cv_in'), vcf.jacks.get('env_out'));
check('three cables including one crossing sides', system.patchBay.connections.length, 3);
const crossing = system.patchBay.connections[2];
check('crossing cable has front and back ends',
    [crossing.source.side, crossing.target.side], ['back', 'front']);

// direction is normalized to output -> input even when patched input-first
const vco2 = system.addModule('carlos.vco');
system.patchBay.createConnection(vcf.jacks.get('cutoff_cv_in'), vco2.jacks.get('audio_out'));
const last = system.patchBay.connections[3];
check('direction normalized to output first', last.source.type, 'output');
check('target is the input', last.target.type, 'input');

// --- per-device flipping ---
check('every device starts on front',
    [...system.modules.values()].every(m => m.view === 'front'), true);

check('flip one device', system.turnModule(vco.id), 'back');
check('only that device turned', [...system.modules.values()].map(m => m.view),
    ['back', 'front', 'front']);
check('summary reports the mix', system.viewSummary(), '2 front, 1 back');

check('flip it back', system.turnModule(vco.id), 'front');

// Tab with nothing selected turns everything
check('nothing selected', system.selected, null);
system.flipView();
check('all turned', [...system.modules.values()].map(m => m.view),
    ['back', 'back', 'back']);
check('summary says all rear', system.viewSummary(), 'ALL BACK');
system.flipView();
check('all turned back', [...system.modules.values()].every(m => m.view === 'front'), true);

// Tab with a selection turns only that device
system.selectModule(vcf.id);
check('selection recorded', system.selected, vcf.id);
system.flipView();
check('only the selected device turned', [...system.modules.values()].map(m => m.view),
    ['front', 'back', 'front']);

check('selecting the same device again deselects', system.selectModule(vcf.id), null);
system.selectModule(vcf.id);
system.deselect();
check('deselect clears', system.selected, null);

// a new device arrives facing the way the rack is facing
system.flipAll();
const arrived = system.addModule('carlos.vcf');
check('new device matches the rack default', arrived.view, 'back');
system.clearRack();
check('clearing resets selection', system.selected, null);

// rebuild for the round-trip section
system.view = 'front';
const m1 = system.addModule('carlos.vco');
const m2 = system.addModule('carlos.vcf');
m1.setView('back');
system.patchBay.createConnection(m1.jacks.get('sub_out'), m2.jacks.get('audio_in'));
check('cable spans a turned device and a facing one',
    m1.jacks.get('sub_out').isVisible() && !m2.jacks.get('audio_in').isVisible(), false);

// --- export / import round trip ---
system.name = 'Round Trip';
const exported = system.exportState();
check('export format', exported.format, 'carlos.patch');
check('export version', exported.version, PATCH_VERSION);
check('export module count', exported.modules.length, 2);
check('export connection count', exported.connections.length, 1);
check('parameters are values not rotations',
    typeof exported.modules[0].parameters.frequency, 'number');
check('no rotation key leaks',
    Object.keys(exported.modules[0].parameters).includes('rotation'), false);
check('per-device view is exported', exported.modules[0].view, 'back');
check('cables carry no side', 'side' in exported.connections[0], false);

if (process.argv[3]) fs.writeFileSync(process.argv[3], JSON.stringify(exported, null, 2));

const before = JSON.stringify(exported);
system.importState(JSON.parse(before));
const after = JSON.stringify(system.exportState());
check('round trip is byte-identical', after, before);

// --- import refusals ---
function refuses(name, doc, fragment) {
    try {
        system.importState(doc);
        results.push({ name, ok: false, actual: 'accepted', expected: `refused: ${fragment}` });
    } catch (e) {
        results.push({ name, ok: e.message.includes(fragment), actual: e.message, expected: fragment });
    }
}
refuses('foreign format refused', { format: 'ableton.set', version: 1 }, 'Not a carlos.patch');
refuses('future version refused', { format: 'carlos.patch', version: 9 }, 'Version 9');
refuses('unknown module type refused',
    { format: 'carlos.patch', version: 1, modules: [{ id: 'z', type: 'theremin' }] }, 'theremin');
refuses('a list is not a patch', [], 'JSON object');

// a refused import must leave the rack alone
check('rack survived the refusals', system.modules.size, 2);
check('turned device survived the round trip',
    [...system.modules.values()][0].view, 'back');


// --- n-sided devices ---
const ko2 = system.addModule('teenage-engineering.ep-133');
check('K.O. II has a face and a top, no back', ko2.sides, ['front', 'top']);
check('it starts on its first side', ko2.view, 'front');
check('cycling reaches its top', ko2.cycle(), 'top');
check('cycling wraps back to front', ko2.cycle(), 'front');
check('cycling backwards reaches top', ko2.cycle(-1), 'top');
check('K.O. II turns', ko2.turns, true);

const dfam = system.addModule('moog.dfam');
check('DFAM has front and back', dfam.sides, ['front', 'back']);
check('devices do not share a side list',
    JSON.stringify(ko2.sides) !== JSON.stringify(dfam.sides), true);

// turning everything advances each device along its own sides
ko2.setView('front'); dfam.setView('front');
system.selected = null;
system.flipAll();
check('each device advanced on its own list', [ko2.view, dfam.view], ['top', 'back']);

// a view a device does not have is coerced, never stored
check('unknown side coerces to the first', dfam.setView('inside'), 'front');

system.clearRack();

// --- groups ---
system.view = 'front';
const g1 = system.addModule('carlos.vco');
const g2 = system.addModule('carlos.vcf');
const g3 = system.addModule('moog.dfam');

check('no groups to start', system.groups.length, 0);
const row = system.createRow('Synths');
check('a row was made', system.groups.length, 1);
check('row is a row', row.kind, 'row');

system.assignToGroup(g1.id, row.id);
system.assignToGroup(g2.id, row.id);
check('two members', system.groups[0].members.length, 2);
check('third is loose', system.ungrouped(), [g3.id]);
check('groupOf finds the row', system.groupOf(g1.id).id, row.id);

// a device belongs to at most one group
const row2 = system.createRow('Drums');
system.assignToGroup(g1.id, row2.id);
check('moving removes it from the old row', system.groups[0].members, [g2.id]);
check('and adds it to the new one', system.groups[1].members, [g1.id]);

system.removeFromGroup(g1.id);
check('loosening removes it from every row', system.groupOf(g1.id), null);

// deleting a row never deletes devices
const before2 = system.modules.size;
system.deleteGroup(row2.id);
check('devices survive their row', system.modules.size, before2);
check('one row left', system.groups.length, 1);

// groups round-trip
system.assignToGroup(g3.id, system.groups[0].id);
system.name = 'Grouped';
const gexp = system.exportState();
check('groups exported', gexp.groups.length, 1);
check('members exported', gexp.groups[0].members.includes(g3.id), true);
system.importState(JSON.parse(JSON.stringify(gexp)));
check('groups survive a round trip', system.exportState().groups, gexp.groups);

// --- version 1 documents still load ---
const v1 = {
    format: 'carlos.patch', version: 1, name: 'Old',
    modules: [{ id: 'x', type: 'carlos.vco', view: 'back', parameters: { frequency: 90 } }],
    connections: []
};
system.importState(v1);
check('a v1 document loads', system.modules.size, 1);
check('and is re-exported at the current version',
    system.exportState().version, PATCH_VERSION);
check('its view survived', [...system.modules.values()][0].view, 'back');
const future = PATCH_VERSION + 1;
refuses('a future version is refused',
    { format: 'carlos.patch', version: future }, `Version ${future}`);

// --- unpatching ---
// Patching used to be one-way: a lead could be run, and then only ever removed
// by clearing every other lead in the rack with it. These cover the way back.
system.clearRack();
const u1 = system.addModule('carlos.vco');
const u2 = system.addModule('carlos.vcf');
const u3 = system.addModule('carlos.vcf');

// One output feeding two inputs, plus an unrelated cable that must survive.
system.patchBay.createConnection(u1.jacks.get('audio_out'), u2.jacks.get('audio_in'));
system.patchBay.createConnection(u1.jacks.get('audio_out'), u3.jacks.get('audio_in'));
system.patchBay.createConnection(u2.jacks.get('env_out'), u3.jacks.get('cutoff_cv_in'));
check('three cables to unpatch from', system.patchBay.connections.length, 3);

const fanKey = PatchBayManager.keyOf(u1.jacks.get('audio_out'), u2.jacks.get('audio_in'));
check('a cable is found by the sockets it joins',
    system.patchBay.find(fanKey) !== null, true);
check('a key names the two ends and nothing else',
    fanKey, `${u1.id}:audio_out->${u2.id}:audio_in`);

system.unpatch(fanKey);
check('unpatching removes exactly one cable', system.patchBay.connections.length, 2);
check('and that cable specifically', system.patchBay.find(fanKey), null);
// The one that matters: an output feeding two inputs loses one lead, not both.
check('the fan-out keeps its other lead',
    u1.jacks.get('audio_out').connections.length, 1);
check('the far end of the removed cable is free',
    u2.jacks.get('audio_in').connections.length, 0);
check('the unrelated cable is untouched',
    system.patchBay.find(
        PatchBayManager.keyOf(u2.jacks.get('env_out'), u3.jacks.get('cutoff_cv_in'))
    ) !== null, true);

check('unpatching a cable that is not there is not an error',
    system.unpatch('nothing:at->all:here'), null);

check('an unpatched cable is not exported',
    system.exportState().connections.length, 2);

// Every lead on one device, in a single act.
check('cablesOf counts both directions',
    system.patchBay.cablesOf(u3.id).length, 2);
check('unpatching a device reports how many went',
    system.unpatchModule(u3.id), 2);
check('and leaves the rest of the rack patched',
    system.patchBay.connections.length, 0);
check('unpatching a device is not the same as deleting it',
    system.modules.has(u3.id), true);
check('a device with nothing patched to it unpatches to zero',
    system.unpatchModule(u3.id), 0);

let failed = 0;
for (const r of results) {
    if (!r.ok) failed++;
    console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.name}`);
    if (!r.ok) console.log(`        got ${JSON.stringify(r.actual)} want ${JSON.stringify(r.expected)}`);
}
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
