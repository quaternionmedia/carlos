// ===================================
// INITIALIZE SYSTEM
// ===================================
const system = new EurorackSystem();

// ===================================
// BOOTSTRAP: the catalogue is the palette
// ===================================
// Device definitions live in `catalogue/devices/*.json` and arrive over
// /api/catalogue. Nothing is hard-coded here, so adding a device is a data file
// and never a frontend change.
async function bootstrap() {
    let payload;
    try {
        const response = await fetch('/api/catalogue');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        payload = await response.json();
    } catch (error) {
        system.status.update(
            `Could not load the catalogue (${error.message}) - the palette is empty`
        );
        return;
    }

    ModuleFactory.load(payload);

    // A rack to start from, if the catalogue has the generic pair.
    if (ModuleFactory.definitions['carlos.vco']) system.addModule('carlos.vco');
    if (ModuleFactory.definitions['carlos.vcf']) system.addModule('carlos.vcf');

    const count = ModuleFactory.ids.length;
    system.status.update(
        `Carlos ready - ${count} devices. Right-click for the menu, `
        + 'or long-press and release to pick in one gesture.'
    );
}

// ===================================
// EXAMPLES
// ===================================
// Every device ships a simple and a complex example. They are ordinary patch
// documents, so loading one is the same code path as importing a file.
async function loadExample(kind, deviceId) {
    if (!deviceId) {
        system.status.update('Pick a device to load an example for');
        return;
    }

    try {
        const response = await fetch(
            `/api/catalogue/devices/${encodeURIComponent(deviceId)}/examples`
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const { examples } = await response.json();
        const document_ = examples[kind];
        if (!document_) {
            system.status.update(`${deviceId} ships no ${kind} example yet`);
            return;
        }
        system.importState(document_);
        const field = document.getElementById('patch-name');
        if (field) field.value = system.name;
    } catch (error) {
        system.status.update(`Could not load that example: ${error.message}`);
    }
}

// ===================================
// VIEW: Tab turns devices around
// ===================================
// With a device selected, Tab turns that one. With nothing selected it turns
// the whole rack, which is the common case and so the default.
//
// Tab must not also move focus to the next control, or the two meanings
// collide; preventDefault is what keeps them apart.
document.addEventListener('keydown', (event) => {
    // A patch name is a text field; Tab and Escape inside it belong to it.
    if (event.target instanceof HTMLInputElement) return;
    if (event.target instanceof HTMLSelectElement) return;

    // An open menu owns the keyboard. It handles its own keys in the capture
    // phase; anything it does not handle must still not reach the rack, or Tab
    // turns devices while a menu is sitting on top of them.
    if (radMenu.open) return;

    if (event.key === 'Escape') {
        system.deselect();
        return;
    }

    // `m` opens the menu on the current selection, which is the contract's
    // keyboard invoke. Pointer is never required to reach a menu.
    if (event.key === 'm' || event.key === 'M') {
        event.preventDefault();
        const targetIds = system.selected ? [system.selected] : [];
        const rect = (system.selected
            ? system.modules.get(system.selected)?.element
            : system.rackElement)?.getBoundingClientRect();
        const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
        const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;
        radMenu.openAt(
            { type: targetIds.length ? 'node' : 'canvas', targetIds, position: { x, y } },
            x, y, 'tap'
        );
        return;
    }

    if (event.key !== 'Tab' || event.ctrlKey || event.altKey || event.metaKey) return;

    // Shift+Tab walks the sides backwards, which matters once a device has
    // more than two of them and cycling forward is a long way round.
    event.preventDefault();
    system.flipView(event.shiftKey ? -1 : 1);
});

// ===================================
// MENUS — one radial menu, per rad's contract
// ===================================
// There is no other menu in this app. The options drawer, its palette, its
// example picker and its row controls were all replaced by this: menus are a
// resolver plus a ring, and a second menu system would be a second answer to a
// question the contract already settles.
//
// The menu never mutates the rack. It emits an Intent; this router is the only
// place an intent becomes a change, which is what keeps the menu replaceable.
// One MIDI input for the page. Activity goes straight to the rack; the
// bindings live on the rack, because they are its state.
const midiInput = new MidiInput({
    onActivity: (activity) => system.showActivity(activity),
    onMessage: (message) => learnFrom(message),
    onStatus: ({ state, detail }) => system.status.update(`MIDI ${state}: ${detail}`),
});

// Learn binds the *shape* of the message that arrived, not the message itself:
// a C1 on channel 10 becomes "note 36 on channel 10", so the next hit of the
// same pad matches and a different pad does not.
function learnFrom(message) {
    const target = midiLearnTarget;
    midiLearnTarget = null;
    if (!target) return null;

    const source =
        message.type === 'cc'
            ? { type: 'cc', channel: message.channel, controller: message.controller }
            : ['note_on', 'note_off', 'aftertouch'].includes(message.type)
                ? { type: 'note', channel: message.channel, note: message.note }
                : { type: 'transport' };

    const binding = {
        id: `bind-${system.midi.length + 1}`,
        source,
        module: target,
        label: message.type === 'cc'
            ? `CC ${message.controller} ch ${message.channel}`
            : `note ${message.note} ch ${message.channel}`,
    };
    system.midi = [...system.midi, binding];
    midiInput.setBindings(system.midi);
    system.status.update(
        `Bound ${binding.label} to ${system.modules.get(target)?.name ?? 'device'}`
    );
    return binding;
}

// The device waiting to be bound to whatever arrives next, if any.
let midiLearnTarget = null;

const radMenu = new RadMenu({
    resolve: (context) => carlosResolve(context, {
        definitions: ModuleFactory.definitions,
        groups: system.groups,
        modules: system.modules,
    }),
    onIntent: (intent) => routeIntent(intent),
});

function routeIntent(intent) {
    const { action, context, payload = {} } = intent;
    const targetId = context.targetIds[0];
    const module = targetId ? system.modules.get(targetId) : null;

    switch (action) {
        case 'add-node':
            system.addModule(payload.deviceId);
            break;

        case 'example:simple':
        case 'example:complex':
            loadExample(action.endsWith('simple') ? 'simple' : 'complex', payload.deviceId);
            break;

        case 'row:new':
            system.createRow();
            break;

        case 'row:assign':
            if (targetId) system.assignToGroup(targetId, payload.groupId);
            break;

        case 'row:loosen':
            if (targetId) {
                system.removeFromGroup(targetId);
                system.status.update(`${module?.name ?? 'Device'} is loose in the rack`);
            }
            break;

        case 'turn':
            if (targetId) system.turnModule(targetId);
            break;

        case 'turn-all':
            system.flipAll();
            break;

        case 'randomize':
            system.randomizeAll();
            break;

        case 'randomize:node':
            if (module) system.randomizeModule(module.id);
            break;

        case 'delete':
            if (targetId) system.removeModule(targetId);
            break;

        case 'rack:clear':
            system.clearRack();
            break;

        case 'patch:export':
            exportPatch();
            break;

        case 'patch:import':
            triggerImport();
            break;

        case 'display:minimal':
        case 'display:irl':
            system.setMode(action.endsWith('irl') ? 'irl' : 'minimal');
            break;

        case 'midi:connect':
            midiInput.setBindings(system.midi);
            midiInput.connect();
            break;

        case 'midi:status':
            system.status.update(
                `MIDI: ${midiInput.ports.length} port(s), `
                + `${system.midi.length} binding(s), `
                + `${midiInput.received} message(s) in, ${midiInput.matched} matched`
                + (midiInput.available ? '' : ' - no Web MIDI in this browser')
            );
            break;

        case 'midi:test':
            // A rack with nothing plugged in still has to be demonstrable.
            midiInput.setBindings(system.midi);
            if (!midiInput.simulate({ channel: 1, note: 36, value: 100 }).length) {
                system.status.update(
                    'Test note sent, and no binding matched it - bind a device first'
                );
            }
            break;

        case 'midi:learn':
            if (!targetId) break;
            midiLearnTarget = targetId;
            midiInput.setBindings(system.midi);
            system.status.update(
                `${module?.name ?? 'Device'} is listening - send a MIDI message to bind it`
            );
            break;

        case 'midi:clear':
            if (!targetId) break;
            system.midi = system.midi.filter(b => b.module !== targetId);
            midiInput.setBindings(system.midi);
            system.status.update(`Cleared bindings for ${module?.name ?? 'device'}`);
            break;

        default:
            system.status.update(`No handler for intent "${action}"`);
    }
}

// Open the menu: right-click anywhere, or `m` on a selection.
document.addEventListener('contextmenu', (event) => {
    const moduleEl = event.target.closest?.('.module');
    const inRack = event.target.closest?.('#rack');
    if (!inRack && !moduleEl) return;

    event.preventDefault();
    const context = moduleEl
        ? { type: 'node', targetIds: [moduleEl.dataset.moduleId], position: { x: event.clientX, y: event.clientY } }
        : { type: 'canvas', targetIds: [], position: { x: event.clientX, y: event.clientY } };
    radMenu.openAt(context, event.clientX, event.clientY, 'tap');
});

// Long-press arms release-select: one gesture from press to commit.
document.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    if (radMenu.open) return;
    const moduleEl = event.target.closest?.('.module');
    const inRack = event.target.closest?.('#rack');
    if (!inRack && !moduleEl) return;
    if (event.target.closest?.('.knob, .jack, button, input, select')) return;

    const context = moduleEl
        ? { type: 'node', targetIds: [moduleEl.dataset.moduleId], position: { x: event.clientX, y: event.clientY } }
        : { type: 'canvas', targetIds: [], position: { x: event.clientX, y: event.clientY } };
    radMenu.armLongPress(context, event);
});

// Clicking the rack, rather than a device on it, clears the selection. This
// asks whether the click landed on a device rather than whether it landed on
// #rack exactly: rows and shelves sit between the two, and testing for #rack
// meant clicking row chrome silently kept the old selection.
document.getElementById('rack')?.addEventListener('click', (event) => {
    if (!event.target.closest?.('.module')) system.deselect();
});

// Cable endpoints are measured from laid-out elements, so a resize invalidates
// every path already drawn.
window.addEventListener('resize', () => system.patchBay.redrawAll());

// ===================================
// INTERCHANGE
// ===================================
function currentPatchName() {
    const field = document.getElementById('patch-name');
    const value = field?.value.trim();
    return value || 'Untitled Patch';
}

function exportPatch() {
    system.name = currentPatchName();
    const document_ = system.exportState();
    const json = JSON.stringify(document_, null, 2);

    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${system.name.replace(/[^a-z0-9._-]+/gi, '_')}.carlos.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);

    system.status.update(`Exported "${system.name}"`);
}

function importPatch(file) {
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
        let parsed;
        try {
            parsed = JSON.parse(reader.result);
        } catch (error) {
            system.status.update(`That file is not JSON: ${error.message}`);
            return;
        }

        try {
            system.importState(parsed);
            const field = document.getElementById('patch-name');
            if (field) field.value = system.name;
        } catch (error) {
            // importState checks before it clears, so the rack on screen is
            // still the one that was there.
            system.status.update(`Import refused: ${error.message}`);
        }
    };
    reader.onerror = () => system.status.update('That file could not be read');
    reader.readAsText(file);
}

function triggerImport() {
    document.getElementById('patch-file')?.click();
}

bootstrap();
