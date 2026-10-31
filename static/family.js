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
const HUB_POLL_MS = 1000;

const hub = {
    // The revision this tab last drew, or found when it opened.
    revision: null,
    // The example it last loaded for the hub, and the document the rack was
    // last loaded from: the opening rig until the hub names a patch.
    patch: null,
    document: null,
};

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
    if (hub.revision === null) {
        hub.revision = state.revision;
        return;
    }
    if (state.revision === hub.revision) return;

    let loaded = null;
    if (state.patch && state.patch !== hub.patch) {
        const cut = state.patch.lastIndexOf('.');
        loaded = await loadExample(state.patch.slice(cut + 1), state.patch.slice(0, cut));
        // `loadExample` has said why on the status line; the next look retries.
        if (!loaded) return;
        hub.patch = state.patch;
        hub.document = loaded;
    }
    if (!hub.document) hub.document = await openingDocument();
    faceTheRack(state.facing, hub.document);
    hub.revision = state.revision;

    const what = loaded ? `"${loaded.name}"` : `facing ${state.facing}`;
    system.status.update(
        `Cue ${cue?.number ?? '?'} from the hub: ${what} - ${system.viewSummary()}`);
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
