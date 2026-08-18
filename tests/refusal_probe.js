// Does the browser refuse this document?
//
// Reads a JSON object of {name: document} on argv[2] and prints
// {name: "refused" | "accepted"}. Nothing else: the judgement about which of
// those is correct belongs to the Python test that runs this, because the rule
// being checked is the contract in `docs/patch-format.md` rather than anything
// this file knows.
//
// A file rather than a string embedded in the Python test: the embedded version
// needed a literal backslash-n to join its own lines and kept losing it in
// transit, which is a fragile joint for no benefit.

const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..');

function el() {
    return {
        className: '', dataset: {}, textContent: '',
        style: { setProperty() {}, removeProperty() {} },
        set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
        classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
        appendChild() {}, remove() {}, replaceChildren() {}, replaceWith() {},
        addEventListener() {},
        querySelector: () => null,
        querySelectorAll: () => [],
        getBoundingClientRect: () => ({ left: 0, top: 0, width: 10, height: 10 }),
    };
}

const nodes = {
    rack: el(), status: el(), 'patch-cables': null, 'view-indicator': el(),
};

global.document = {
    body: el(),
    getElementById: (id) => (id in nodes ? nodes[id] : null),
    createElement: el,
    createElementNS: el,
    addEventListener() {},
};
global.window = { addEventListener() {} };
global.anime = () => {};

(0, eval)(
    fs.readFileSync(path.join(REPO, 'static/models.js'), 'utf8')
    + '\nglobalThis.EurorackSystem = EurorackSystem;'
    + '\nglobalThis.ModuleFactory = ModuleFactory;'
);

global.system = new EurorackSystem();

const devices = path.join(REPO, 'catalogue/devices');
ModuleFactory.load({
    categories: [],
    devices: fs.readdirSync(devices).filter(f => f.endsWith('.json'))
        .map(f => JSON.parse(fs.readFileSync(path.join(devices, f), 'utf8'))),
});

const cases = JSON.parse(process.argv[2]);
const outcome = {};

for (const [name, document_] of Object.entries(cases)) {
    try {
        system.importState(document_);
        outcome[name] = 'accepted';
    } catch (error) {
        outcome[name] = 'refused';
    }
    // A refused import leaves the rack alone by contract, but an accepted one
    // does not - and the next case has to start from an empty rack or it is
    // measuring the leftovers of the last.
    system.clearRack();
}

console.log(JSON.stringify(outcome));
