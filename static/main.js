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

    // Awaited, and the ready line goes last on purpose. `importState` writes
    // its own status naming what it loaded; leaving that up would mean the
    // line saying the app is ready arrives before the rack does, or not at all.
    await openingRack();

    const count = ModuleFactory.ids.length;
    // Shorter than it was. It used to explain where the menu is, which was
    // worth a sentence when the menu was invisible until you asked for it and
    // is noise now that it is the first thing on screen.
    system.status.update(`Carlos ready - ${count} devices in the catalogue`);

    openTheRing();
}

// Where the ring sits when nobody has moved it.
//
// Top left, and low enough that its first node fits above it. That node is
// drawn `2.3` rings out, so a centre at the clamp's own minimum would put the
// readout off the top of the window - the clamp keeps the *ring* on screen and
// knows nothing about a node that reaches past it.
const PINNED_AT = { x: 152, y: 292 };

// The bar reads the live region, so it has to be redrawn when the live region
// changes. Watched rather than hooked into `status.update`: that keeps the
// status line the one thing that knows how to say something, and the bar a
// thing that reads it - the same direction the readout already ran.
function watchTheStatus() {
    const said = document.getElementById('status');
    if (!said || typeof MutationObserver === 'undefined') return;
    new MutationObserver(() => {
        // Installed after boot has had its say, so the first thing this sees is
        // the app answering something somebody did - which is the only kind of
        // message the bar's right half is for.
        radMenu.saidLately = said.textContent.trim();
        if (radMenu.resting) radMenu.render();
    }).observe(said, { childList: true, characterData: true, subtree: true });
}

// The ring is up when you arrive.
//
// It carries the readout, so a rack with no ring on it is a rack that cannot
// tell you anything - which is what the dock used to be for. Unpin it and the
// app is what it was: a rack, and a menu you summon.
function openTheRing() {
    watchTheStatus();
    radMenu.openAt(
        { type: 'canvas', targetIds: [], position: { ...PINNED_AT } },
        PINNED_AT.x, PINNED_AT.y, 'tap');
    radMenu.pin(true);
}

// ===================================
// THE OPENING RACK
// ===================================
// A rig rather than a demonstration of the drawing code: every device in the
// catalogue, in three rows, patched the way they would be on a desk - control
// into voices, voices into the desk, desk into the interface.
//
// It is fetched, not built. `catalogue/opening.json` is an ordinary
// `carlos.patch` document, so the first thing anyone sees is a file they can
// export, edit and import again rather than a rack assembled by frontend code
// that nothing else can reach. It used to be two `addModule` calls here, which
// made the opening picture the one thing in the app that could not be copied.
async function openingRack() {
    let document_;
    try {
        const response = await fetch('/api/opening');
        // 204 is a build that ships none, which is an empty workspace rather
        // than a failure.
        if (response.status === 204) return null;
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        document_ = await response.json();
    } catch (error) {
        system.status.update(
            `Could not load the opening rack (${error.message}) - starting empty`
        );
        return null;
    }

    const { skipped } = system.importState(document_);
    // `importState` writes its own status line naming what it loaded, which is
    // the honest one to leave up: it counts what arrived rather than what was
    // asked for.
    if (skipped?.length) {
        system.status.update(
            `Opened with ${skipped.length} item(s) this build could not place`
        );
    }
    return document_;
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
    } catch (error) {
        system.status.update(`Could not load that example: ${error.message}`);
    }
}

// ===================================
// VIEW: `t` turns devices around
// ===================================
// With a device selected, `t` turns that one. With nothing selected it turns
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
    // A resting bar is not a menu in the way: it is where the menu
    // lives. Only a bloomed ring owns the next press.
    if (radMenu.open && !radMenu.resting) return;

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

// ===================================
// HOW THIS RING IS ARRANGED
// ===================================
// One small store, on this browser, holding what somebody has done to their
// own ring: which families are hidden and what order the rest are in.
//
// rad-android keeps the same thing keyed per palette, and the same rule
// governs it: absence means "as declared". A ring nobody has edited has no
// entry here at all and resolves exactly as it did before this existed, so
// the feature costs nothing to anyone who never opens it.
//
// Local, and deliberately: an arrangement is a fact about this person at this
// screen. Sending it anywhere would make it a fact about an account.
const RING_STORE = 'carlos.ring';

function ringConfig() {
    try {
        return JSON.parse(localStorage.getItem(RING_STORE) || '{}') || {};
    } catch {
        // A corrupt entry is not worth a broken menu. As declared, then.
        return {};
    }
}

function saveRing(config) {
    try {
        const empty = !(config.hidden || []).length && !(config.order || []).length;
        // Nothing to say is said by saying nothing, so a reset leaves no
        // residue behind to be read back as an arrangement.
        if (empty) localStorage.removeItem(RING_STORE);
        else localStorage.setItem(RING_STORE, JSON.stringify(config));
    } catch {
        // Private mode, a full quota: the ring still works, it just forgets.
        system.status.update('This browser will not store the arrangement');
    }
}

// The order the ring is in right now, named rather than implied: moving an
// item needs a list to move it within, and an unedited ring has never written
// one down.
function ringOrder() {
    const spec = carlosResolve(
        { type: 'canvas', targetIds: [], position: { x: 0, y: 0 } },
        radState()
    );
    return spec.items.map(entry => entry.id).filter(id => id !== 'edit');
}

function moveInRing(itemId, step) {
    const order = ringOrder();
    const at = order.indexOf(itemId);
    if (at < 0) return null;
    const to = at + step;
    if (to < 0 || to >= order.length) return null;

    order.splice(to, 0, ...order.splice(at, 1));
    const config = { ...ringConfig(), order };
    saveRing(config);
    return order;
}

function radState() {
    return {
        definitions: ModuleFactory.definitions,
        groups: system.groups,
        modules: system.modules,
        ringConfig: ringConfig(),
        // Read at resolve time rather than held: the menu's own flag is the one
        // copy of whether it is pinned, and a second would be a second answer
        // to the same question.
        pinned: Boolean(radMenu?.pinned),
        // What the first node says when the ring is pinned: whatever this app
        // last answered back, falling through to the rack's own figures when it
        // has not said anything yet. Read off the live region rather than kept
        // beside it, so there is one copy of the message and the screen-reader
        // channel and the drawn one cannot disagree.

        ...cableState(),
    };
}

const radMenu = new RadMenu({
    resolve: (context) => carlosResolve(context, radState()),
    onIntent: (intent) => routeIntent(intent),
});

// The rack in four short facts. Short words rather than a sentence, because
// both the places this goes wrap at word boundaries and a long word is what
// makes a readout read as a paragraph that happens to be round.
// What build this is, from the page rather than from a constant here. There
// was a splash saying it; the bar says it now, which is one fact in a line that
// already existed rather than a page somebody clicks through to reach the thing
// they came for.
function buildName() {
    const said = document.querySelector('meta[name="carlos-build"]')?.content;
    return said ? `Carlos ${said}` : 'Carlos';
}

function rackReadout() {
    const leads = system.patchBay.connections.length;
    return `${buildName()} | ${system.modules.size} devices | ${leads} leads | `
        + `${system.groups.length} rows | ${system.viewSummary().toLowerCase()}`;
}

// What the bar says. Asked at render time rather than pushed, so the ring holds
// no copy of a rack that goes on changing underneath it.
//
// Whatever this app last answered back, falling through to the rack's own
// figures when it has not said anything worth keeping. Read off the live region
// rather than kept beside it: `#status` is the channel a screen reader is told
// about, and a second copy would be two answers to one question.
// The bar's left half: the rack, always. It stopped being conditional once the
// bar gained a right half - the figures do not stop being true when the app
// answers something, so nothing has to choose between them any more.
radMenu.showsReadout(rackReadout);

// Whether this browser has been shown how to open the ring. Remembered beside
// the ring's arrangement, because it is the same kind of fact: something about
// this person at this screen, and no use to anybody else.
const HINT_STORE = 'carlos.barHint';

radMenu.hintLearned = (() => {
    try { return localStorage.getItem(HINT_STORE) === 'learned'; } catch { return false; }
})();

radMenu.onHintLearned = () => {
    try { localStorage.setItem(HINT_STORE, 'learned'); } catch { /* it just asks again */ }
};

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

        case 'patch:name': {
            // A ring has no text entry, and rad-android's answer to that is to
            // scope down rather than grow a dialog inside the menu. The
            // browser already has one prompt that works everywhere, including
            // for a screen reader, so this uses it rather than building a
            // second.
            const named = window.prompt('Name this patch', system.name || '');
            if (named === null) break;
            system.name = named.trim() || 'Untitled Patch';
            system.status.update(`Patch is "${system.name}"`);
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

        case 'edit:up':
        case 'edit:down': {
            const moved = moveInRing(payload.itemId, action === 'edit:up' ? -1 : 1);
            system.status.update(
                moved ? `Moved ${payload.itemId} in the ring` : 'It is already there');
            break;
        }

        case 'edit:hide': {
            const config = ringConfig();
            const hidden = new Set(config.hidden || []);
            if (hidden.has(payload.itemId)) hidden.delete(payload.itemId);
            else hidden.add(payload.itemId);
            saveRing({ ...config, hidden: [...hidden] });
            system.status.update(
                hidden.has(payload.itemId)
                    ? `${payload.itemId} hidden - Edit brings it back`
                    : `${payload.itemId} is back on the ring`);
            break;
        }

        case 'edit:reset':
            saveRing({});
            system.status.update('Ring back to how it ships');
            break;

        case 'ring:pin':
            // Pinned from inside the ring it pins, so this runs as the menu is
            // settling. Deferred by a frame for that reason: pinning during
            // its own commit would re-render the thing mid-dispatch.
            requestAnimationFrame(() => {
                const on = radMenu.pin(!radMenu.pinned);
                system.status.update(
                    on
                        ? 'Ring pinned - it stays until you unpin it'
                        : 'Ring let go');
            });
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

    // The panel is a surface the ring can be summoned from, which is what
    // rad-android's overlay is: a floating window whose whole job is to be
    // somewhere you can always reach the menu, even when what is under your
    // hand is not the thing you want to act on. Summoning from it opens the
    // rack's ring - the panel is about the rack, so that is what it offers.
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
    // The release that goes with this right-click has not necessarily happened
    // yet - `contextmenu` fires on down on Linux and on up on Windows - and a
    // release reaching a ring that has just opened lands in its dead zone and
    // cancels it.
    radMenu.openAt(context, event.clientX, event.clientY, 'tap',
                   { ignoreNextUp: true });
});

// Long-press arms release-select: one gesture from press to commit.
document.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    // A resting bar is not a menu in the way: it is where the menu
    // lives. Only a bloomed ring owns the next press.
    if (radMenu.open && !radMenu.resting) return;
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
// INTERCHANGE
// ===================================
// The rack's own name, which is where it lives now. It used to be read out of
// a text field in the floating panel; the panel is gone and `Patch ▸ Name` sets
// it directly, so there is one copy of it rather than two that had to be kept
// in step on every import.
function currentPatchName() {
    return (system.name || '').trim() || 'Untitled Patch';
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
