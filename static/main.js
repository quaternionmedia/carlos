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

    openingRack();

    const count = ModuleFactory.ids.length;
    system.status.update(
        `Carlos ready - ${count} devices. Right-click for the menu, `
        + 'or long-press and release to pick in one gesture.'
    );
}

// ===================================
// THE OPENING RACK
// ===================================
// A grid playing a sampler down one USB lead: the smallest rig that is a rig
// rather than a demonstration of the drawing code. Two devices people own, one
// cable, and four channels going down it.
//
// It replaced a VCO next to a VCF, which showed the patch bay and nothing else
// - two boxes of knobs with nothing running between them. What is worth
// arriving to is a picture with a question in it: four groups are bound to four
// channels, and you can see which.
//
// Guarded on the catalogue rather than assumed: entries are data files, and a
// build without these two should open on an empty rack, not on an exception.
function openingRack() {
    const has = (id) => Boolean(ModuleFactory.definitions[id]);
    if (!has('novation.launchpad-x') || !has('teenage-engineering.ep-133')) {
        // Whatever else is there, so an unfamiliar catalogue still opens on
        // something rather than on nothing.
        if (has('carlos.vco')) system.addModule('carlos.vco');
        if (has('carlos.vcf')) system.addModule('carlos.vcf');
        return;
    }

    // Laid out, because the whole point of naming two real devices is that they
    // look like themselves: 64 pads and a sampler panel, at their real sizes
    // relative to each other.
    system.setMode('irl');

    const grid = system.addModule('novation.launchpad-x');
    const sampler = system.addModule('teenage-engineering.ep-133');

    // Four groups, and the drums on ten. This is what the cable splits into:
    // the bindings are the channel assignments, and the strands are drawn from
    // them, so rebinding a group moves the picture without anything being kept
    // in step by hand.
    //
    // Three melodic groups on 1-3 and the kit on 10, which is where a kit goes
    // by a convention nothing enforces and everything obeys. It is the whole
    // reason the strands are worth telling apart: the question you have when
    // you look at a lead is which of these is the drums, and here it is the
    // thick yellow one.
    const opening = [
        { group: 'A', channel: 1 },
        { group: 'B', channel: 2 },
        { group: 'C', channel: 3 },
        { group: 'D', channel: 10, label: 'Drums' },
    ];
    system.midi = opening.map(({ group, channel, label }) => ({
        id: `opening-${group.toLowerCase()}`,
        source: { type: 'channel', channel },
        module: sampler.id,
        label: label || `Group ${group}`,
    }));

    // Both sockets are round the back, which is where USB lives on both of
    // these. The cable is drawn to the silhouette of each device rather than to
    // a socket you cannot see, and dashed to say part of its run is behind
    // something - which is true of every USB lead on every desk.
    const from = grid.jacks.get('usb');
    const to = sampler.jacks.get('usb_c');
    if (from && to) system.patchBay.createConnection(from, to);

    system.patchBay.redrawAll();
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
// Anything that takes focus in its own right. Escape means "let go", which is
// only meaningful for something that had hold of the focus in the first place.
function isFocusable(node) {
    return Boolean(node?.closest?.(
        'input, select, textarea, button, a[href], [tabindex]:not([tabindex="-1"])'
    ));
}

document.addEventListener('keydown', (event) => {
    // A patch name is a text field; Tab and Escape inside it belong to it.
    if (event.target instanceof HTMLInputElement) return;
    if (event.target instanceof HTMLSelectElement) return;

    // An open menu owns the keyboard. It handles its own keys in the capture
    // phase; anything it does not handle must still not reach the rack, or Tab
    // turns devices while a menu is sitting on top of them.
    if (radMenu.open) return;

    // Escape is "let go": drop the selection and hand focus back, so a knob
    // reached by keyboard is not somewhere you have to click your way out of.
    if (event.key === 'Escape') {
        if (isFocusable(event.target)) event.target.blur?.();
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

    // `t` turns the whole rack, `Shift`+`T` walks the sides backwards — which
    // matters once a device has more than two of them and cycling forward is a
    // long way round.
    //
    // This used to be `Tab`, and `Tab` is focus. The rule that was supposed to
    // reconcile the two — take Tab unless something focusable already has it —
    // could not: at load nothing is focused, so the first Tab turned the rack,
    // and so did every Tab after it. Seventeen focusable controls, none of them
    // reachable, measured in a real browser. A gesture that costs the keyboard
    // the entire interface is not a gesture worth the key it is on.
    if (event.key !== 't' && event.key !== 'T') return;
    if (event.ctrlKey || event.altKey || event.metaKey) return;

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

// A pad on a drawn device sends down the same path a real port uses.
//
// This is the whole point of the grids being controls rather than pictures: a
// press on a Launchpad X's pad reaches `MidiInput` as a note, matches whatever
// binding names it, and lights the device that binding points at. Nothing here
// knows about pads and nothing in `models.js` knows about MIDI ports.
system.onEmit = (detail) => {
    if (detail.emits === 'midi-note') {
        midiInput.setBindings(system.midi);
        const matched = midiInput.simulate({
            channel: detail.channel,
            note: detail.note,
            value: 100,
        });
        if (!matched.length) {
            system.status.update(
                `${detail.legend} - nothing is bound to it. `
                + 'Use MIDI > Bind next message on a device.'
            );
        }
        return matched;
    }

    if (detail.emits === 'midi-cc') {
        midiInput.setBindings(system.midi);
        return midiInput.simulate({
            channel: detail.channel,
            controller: detail.controller,
            value: 100,
        });
    }

    // A named event. It reached the device's own screens on the way here, and
    // the status line has already said what it was; there is nothing further
    // for it to do until something asks for one.
    return null;
};

// What is patched, keyed the way the menu addresses it. Built per open rather
// than kept in step: a cache of this would be a second copy of the patch bay,
// and the resolver is called once per menu, not once per frame.
function cableState() {
    const cables = new Map();
    const cableCounts = new Map();

    system.patchBay.connections.forEach(conn => {
        cables.set(
            PatchBayManager.keyOf(conn.source, conn.target),
            { label: system.patchBay.describe(conn) }
        );
        // A device patched into itself is one cable, not two. The set is what
        // keeps "Unpatch (1)" from reading "Unpatch (2)".
        new Set([conn.source.module?.id, conn.target.module?.id])
            .forEach(id => { if (id) cableCounts.set(id, (cableCounts.get(id) || 0) + 1); });
    });

    return { cables, cableCounts };
}

const radMenu = new RadMenu({
    resolve: (context) => carlosResolve(context, {
        definitions: ModuleFactory.definitions,
        groups: system.groups,
        modules: system.modules,
        ...cableState(),
    }),
    onIntent: (intent) => routeIntent(intent),
});

function routeIntent(intent) {
    const { action, context, payload = {} } = intent;
    const targetId = context.targetIds[0];
    const module = targetId ? system.modules.get(targetId) : null;

    switch (action) {
        case 'add-node':
            // Into the row that was pointed at, when one was. `addModule`
            // already falls back to the selected device's row, so this is the
            // only place that has to know a row can be the target.
            system.addModule(
                payload.deviceId,
                context.type === 'row' ? targetId : null);
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

        case 'row:turn':
            if (targetId) system.turnRow(targetId);
            break;

        case 'row:loosen-all':
            if (targetId) system.emptyRow(targetId);
            break;

        case 'row:delete':
            if (targetId) system.deleteGroup(targetId);
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

        case 'cable:remove':
            system.unpatch(targetId);
            break;

        case 'cable:remove-node':
            if (targetId) system.unpatchModule(targetId);
            break;

        case 'cable:follow': {
            // Selecting the device at the source end is what tracing keys on,
            // so following a lead is selecting the thing it comes from.
            const conn = system.patchBay.find(targetId);
            if (conn) system.selectModule(conn.source.module.id);
            break;
        }

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

        case 'palette:reset':
            palette.reset();
            system.status.update('Palette back to where it starts');
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

// What a point in the rack is pointing at, as rad's MenuContext.
//
// Device, then cable, then the rack itself. A device wins over a cable crossing
// it because that is what you are looking at; cables hang below the gear, so
// the two rarely compete.
//
// The cable is found by asking the geometry, not the event target. The cable
// layer is `pointer-events: none` and stays that way - making cables clickable
// the ordinary way would lay an invisible sheet over every knob a lead runs
// across, and trade one missing gesture for a broken one.
function contextAt(event) {
    const moduleEl = event.target.closest?.('.module');
    const inRack = event.target.closest?.('#rack');
    if (!inRack && !moduleEl) return null;

    const position = { x: event.clientX, y: event.clientY };
    if (moduleEl) {
        return { type: 'node', targetIds: [moduleEl.dataset.moduleId], position };
    }

    const cable = system.patchBay.cableAt(event.clientX, event.clientY);
    if (cable) return { type: 'edge', targetIds: [cable.key], position };

    // A row, if the click landed inside one. After the cable, because a lead
    // crossing a row is still a lead; before the rack, because the rack is
    // what is left when you have pointed at nothing in particular.
    const rowEl = event.target.closest?.('.rack-group');
    if (rowEl) return { type: 'row', targetIds: [rowEl.dataset.groupId], position };

    return { type: 'canvas', targetIds: [], position };
}

// Open the menu: right-click anywhere, or `m` on a selection.
document.addEventListener('contextmenu', (event) => {
    const context = contextAt(event);
    if (!context) return;

    event.preventDefault();
    radMenu.openAt(context, event.clientX, event.clientY, 'tap');
});

// Long-press arms release-select: one gesture from press to commit.
document.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    if (radMenu.open) return;
    if (event.target.closest?.('.knob, .jack, button, input, select')) return;

    const context = contextAt(event);
    if (!context) return;

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
// TOOL PALETTE
// ===================================
// The panel holding what a ring cannot express. It is constructed here rather
// than constructing itself, so the storage it uses is something this file
// chose and the tests can hand it another.
const palette = new Palette({
    element: document.getElementById('tool-palette'),
    grip: document.getElementById('tool-palette-grip'),
    // Reached through a guard: a browser can refuse `localStorage` outright,
    // and reading the property is itself what throws.
    storage: (() => {
        try { return window.localStorage; } catch { return null; }
    })(),
});

// ===================================
// INTERCHANGE
// ===================================
function currentPatchName() {
    const field = document.getElementById('patch-name');
    const value = field?.value.trim();
    return value || 'Untitled Patch';
}

// A device with a `patch` screen is showing the rack's name, so typing in the
// field has to reach it. Cheap enough to do per keystroke: it is a text write
// per screen, and there are single digits of them.
document.getElementById('patch-name')?.addEventListener('input', () => {
    system.name = currentPatchName();
    system.refreshScreens();
});

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
