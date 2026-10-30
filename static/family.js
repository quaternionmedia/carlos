// ===================================
// FOLLOWING THE HUB
// ===================================
// The performing family's hub delivers its cues to this server, and the server
// holds what they did: which example is loaded, and which way the rack faces.
// See src/family.py. An open tab asks for that once a second and draws whatever
// changed since it last looked, in place - no reload.
//
// A tab follows from the moment it opens. One that arrives after a cue keeps
// the rig it opened on until the next cue lands, and then draws all of it:
// what a tab draws is a function of the state, not of the cues it happened to
// see.
//
// A rig held from outside is drawn as it is sent: its devices for that rig
// only, its cables as they are, and each state as its level and its lines. The
// sender knows what is in the rig; this draws it. A held rig is what the rack
// is, so a tab that opens on one draws it at once. The same rig held again -- the
// same devices on the same sides -- at new values, leads and states is turned in
// place, so a rig followed through a concert turns rather than being drawn again
// for every frame: a lead moved to another socket is that one cable taken out
// and put in, and the devices stand where they are.
const HUB_POLL_MS = 1000;

const hub = {
    // The revision this tab last drew, or found when it opened.
    revision: null,
    // The example it last loaded for the hub, and the document the rack was
    // last loaded from: the opening rig until the hub names a patch.
    patch: null,
    document: null,
    // The hold last drawn, as its JSON, so a hold sent again unchanged is not
    // drawn again; and what makes it the rig it is, so one at new values and
    // states only is turned in place.
    held: null,
    rig: null,
};

// What makes a held rig the rig it is, as one string: its devices, the side
// each shows, how it is drawn and the devices sent with it. Two holds that
// agree on it are one rig at two moments, whatever leads each has: a rig's
// leads are what changes most often, a plug at a time.
function rigOf(held) {
    const patch = held.patch || {};
    return JSON.stringify({
        modules: (patch.modules || []).map(m => [m.id, m.type, m.view || 'front']),
        groups: patch.groups || [],
        display: patch.display || null,
        devices: held.devices,
    });
}

// The states a held rig gives its devices and its leads, put where they are
// read as the rack is drawn.
function holdTheStates(held) {
    HELD_MODULE_STATES.clear();
    HELD_LEAD_STATES.clear();
    Object.entries(held.states.modules).forEach(([id, state]) => {
        HELD_MODULE_STATES.set(id, state);
    });
    // By both ways round: the rack draws a cable output first, whichever end
    // the patch names first, and the server lets a lead's state name it only as
    // the patch does, once.
    held.states.connections.forEach(lead => {
        const source = `${lead.source.module}:${lead.source.jack}`;
        const target = `${lead.target.module}:${lead.target.jack}`;
        HELD_LEAD_STATES.set(`${source}->${target}`, lead);
        HELD_LEAD_STATES.set(`${target}->${source}`, lead);
    });
}

// A lead as its two sockets, whichever is named first: what makes it the lead.
function socketsOf(one, other) {
    return [one, other].sort().join(' & ');
}

// The rack's cables made the hold's leads: each one the hold no longer has
// taken out, each new one put in, and the rest left as they are, drawn once at
// the end. What changed, as how many went out and came in.
function repatchTheHeldRig(connections) {
    const bay = system.patchBay;
    const wanted = new Map((connections || []).map(conn => [
        socketsOf(`${conn.source.module}:${conn.source.jack}`,
                  `${conn.target.module}:${conn.target.jack}`),
        conn]));
    const drawn = new Set();
    let out = 0;
    [...bay.connections].forEach(({ source, target }) => {
        const sockets = socketsOf(`${source.module.id}:${source.name}`,
                                  `${target.module.id}:${target.name}`);
        if (wanted.has(sockets)) {
            drawn.add(sockets);
        } else {
            bay.remove(PatchBayManager.keyOf(source, target), { redraw: false });
            out += 1;
        }
    });
    let into = 0;
    wanted.forEach((conn, sockets) => {
        if (drawn.has(sockets)) return;
        const source = system.modules.get(conn.source.module)?.jacks.get(conn.source.jack);
        const target = system.modules.get(conn.target.module)?.jacks.get(conn.target.jack);
        if (source && target && bay.createConnection(source, target, { redraw: false })) {
            into += 1;
        }
    });
    return { out, into };
}

// The held rig drawn: its devices, then its states, then the rack from its
// document, so each device and each cable is drawn with its state.
function drawTheHeldRig(held) {
    ModuleFactory.held = Object.fromEntries(held.devices.map(device => [device.id, device]));
    holdTheStates(held);
    system.importState(held.patch);
    hub.rig = rigOf(held);
}

// The rig already drawn, at this hold's values, leads and states: each device
// turned where it stands, its leads re-patched, and the cables drawn again for
// their states. What moved, by device.
function turnTheHeldRig(held) {
    holdTheStates(held);
    const moved = {};
    (held.patch.modules || []).forEach(m => {
        const module = system.modules.get(m.id);
        const turned = module ? module.retouchHeld(m.parameters) : [];
        if (turned.length) moved[m.id] = turned;
    });
    repatchTheHeldRig(held.patch.connections);
    system.patchBay.redrawAll();
    return moved;
}

// Let a held rig go: what loads next is the rack's own.
function letTheHeldRigGo() {
    ModuleFactory.held = {};
    HELD_MODULE_STATES.clear();
    HELD_LEAD_STATES.clear();
    hub.held = null;
    hub.rig = null;
}

// Mirrors `document_facing` in src/family.py: the commonest view among a
// document's modules, the first one seen breaking a tie, and front for none.
// The same rule `commonestSide()` applies to the rack, asked of the document.
function documentFacing(document_) {
    const counts = new Map();
    (document_?.modules || []).forEach(module => {
        const side = module.view || 'front';
        counts.set(side, (counts.get(side) || 0) + 1);
    });
    let best = 'front';
    let most = -1;
    counts.forEach((count, side) => {
        if (count > most) { most = count; best = side; }
    });
    return best;
}

// Face the rack the way the state says. Facing the way its document faces is
// the document's own arrangement; any other side turns every device that shows
// that side to it, and leaves the rest as the document has them.
function faceTheRack(facing, document_) {
    const asWritten = new Map(
        (document_?.modules || []).map(module => [module.id, module.view || 'front']));
    const own = facing === documentFacing(document_);
    system.modules.forEach((module, id) => {
        const written = asWritten.get(id) || module.view;
        const shows = module.drawnSides().includes(facing);
        module.setView(own || !shows ? written : facing);
    });
    system.view = system.commonestSide();
    system.applyView();
}

async function openingDocument() {
    const response = await fetch('/api/opening');
    return response.status === 200 ? response.json() : null;
}

// One look at the server, and whatever it changed drawn.
async function followTheHub() {
    let snapshot;
    try {
        const response = await fetch('/family/state', { cache: 'no-store' });
        if (!response.ok) return;
        snapshot = await response.json();
    } catch {
        // A server between restarts. The next look asks again.
        return;
    }
    const { cue, state } = snapshot;
    if (hub.revision === null && !state.held) {
        hub.revision = state.revision;
        return;
    }
    if (state.revision === hub.revision) return;

    let loaded = null;
    let turned = null;
    if (state.held) {
        const key = JSON.stringify(state.held);
        if (key !== hub.held) {
            if (hub.held && rigOf(state.held) === hub.rig) {
                turned = turnTheHeldRig(state.held);
            } else {
                drawTheHeldRig(state.held);
            }
            hub.held = key;
            hub.patch = null;
            hub.document = state.held.patch;
            loaded = state.held.patch;
        }
    } else if (hub.held) {
        letTheHeldRigGo();
    }
    if (!state.held && state.patch && state.patch !== hub.patch) {
        const cut = state.patch.lastIndexOf('.');
        loaded = await loadExample(state.patch.slice(cut + 1), state.patch.slice(0, cut));
        // `loadExample` has said why on the status line; the next look retries.
        if (!loaded) return;
        hub.patch = state.patch;
        hub.document = loaded;
    }
    if (!hub.document) hub.document = await openingDocument();
    // A rig turned in place already faces the way it did.
    if (!turned) faceTheRack(state.facing, hub.document);
    hub.revision = state.revision;

    const what = loaded ? `"${loaded.name}"` : `facing ${state.facing}`;
    system.status.update(state.held
        ? `Held from ${cue?.name ?? 'outside'}: ${what} - ${system.viewSummary()}`
        : `Cue ${cue?.number ?? '?'} from the hub: ${what} - ${system.viewSummary()}`);
}

// Looks are chained rather than on an interval, so a slow one - an example
// loading - is never overtaken by the next. One that throws still reaches the
// console, and the next look is still taken.
async function keepFollowing() {
    try {
        await followTheHub();
    } finally {
        setTimeout(keepFollowing, HUB_POLL_MS);
    }
}

booted.then(keepFollowing);
