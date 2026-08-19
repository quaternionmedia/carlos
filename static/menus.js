// ===================================================================
// CARLOS MENU RESOLVER — a RAD consumer
// ===================================================================
// `resolve(context) -> MenuSpec`, per rad's interaction contract. Menus are
// built by data manipulation — conditional spread — never by post-filtering a
// master list, and every commit produces an Intent that the host routes through
// its own state. This file never touches the DOM and never mutates the rack.
//
// The ring ceiling is 8. Anything that can grow past it is packed into
// continuation submenus here, so the resolver never hands the renderer a ring
// it would have to shrink below the touch-target minimum.

const MENU_MAX = 8;

// Pack an unbounded list into rings of at most MENU_MAX, chaining the overflow
// through "More" submenus. A list that fits is returned untouched.
function packRing(items, moreLabel = 'More') {
    if (items.length <= MENU_MAX) return items;
    const head = items.slice(0, MENU_MAX - 1);
    return [
        ...head,
        {
            id: 'more',
            label: moreLabel,
            action: null,
            children: packRing(items.slice(MENU_MAX - 1), moreLabel),
        },
    ];
}

// `short` is what the wedge says; `label` is what the hub says.
//
// rad-android's surfaces record settles this for arbitrary names: wedges show
// something recognisable, the hub shows the highlighted item's full label, and
// ellipsis is banned by the contract - so truncating on the wedge was never
// available as the fix. It shows icons and reads the name at the hub; this app
// is text, so it shows a short name and reads the full one at the hub. Same
// rule, same reason: symbols are recognised, names are read, and only one
// place ever has to be wide enough to read.
const WEDGE_MAX = 12;

function item(id, label, action, extra = {}) {
    return { id, label, action, enabled: true, destructive: false, ...extra };
}

// What a wedge says, which is never longer than the ring can draw.
function wedgeLabel(menuItem) {
    return menuItem.short || menuItem.label;
}

// The one entry that is never hidden and never moves.
//
// rad-android builds editing additively: the root ring gains exactly one fixed
// `Edit ▸`, nothing about the ordinary commit path changes shape, and nothing
// under it is reachable without committing it first. The same reasoning makes
// it unhideable here - a ring you can arrange has to keep the door you arrange
// it through, or the last thing you hide is the way back.
const EDIT_ID = 'edit';

// Apply a stored arrangement to a ring.
//
// Hidden items are dropped and the rest are put in the stored order; anything
// the store has never heard of keeps its declared place at the end. Absence
// means "as declared", so a rack that has never been edited resolves exactly as
// it did before this existed - the same rule rad-android uses for an
// unassigned wedge.
//
// Pure, and takes the config rather than reading it: the resolver stays a
// function of its arguments, which is what lets the whole ring be tested
// without a rack or a browser behind it.
function arrange(items, config = {}) {
    const hidden = new Set(config.hidden || []);
    const order = config.order || [];

    const kept = items.filter(entry => entry.id === EDIT_ID || !hidden.has(entry.id));
    const placed = order
        .map(id => kept.find(entry => entry.id === id))
        .filter(Boolean);
    const rest = kept.filter(entry => !order.includes(entry.id));
    return [...placed, ...rest];
}

// `Edit ▸` itself: one wedge per family, plus the way back to as it shipped.
//
// Built from the **declared** ring rather than the arranged one, which is the
// whole of what makes hiding reversible. Built from the arranged one first,
// and a hidden family vanished from here too - so the way to bring it back was
// gone the moment you used it. The same trap as an unhideable `Edit`, one
// level down, and found the same way: by asking what happens after.
//
// `showing` is the arranged ring, and only decides whether Move up and Move
// down are offered live. A family that is hidden has no position to move
// within, so both are disabled rather than absent - a menu whose items move
// depending on state is a menu you cannot learn.
function editTree(declared, showing, config = {}) {
    const hidden = new Set(config.hidden || []);
    const order = showing.map(entry => entry.id);

    return packRing([
        ...declared
            .filter(entry => entry.id !== EDIT_ID)
            .map(entry => {
                const at = order.indexOf(entry.id);
                const away = hidden.has(entry.id);
                return item(`edit:${entry.id}`, entry.label, null, {
                    children: [
                        item(`edit:up:${entry.id}`, 'Move up', 'edit:up',
                             { payload: { itemId: entry.id },
                               enabled: !away && at > 0 }),
                        item(`edit:down:${entry.id}`, 'Move down', 'edit:down',
                             { payload: { itemId: entry.id },
                               enabled: !away && at >= 0 && at < order.length - 1 }),
                        item(`edit:hide:${entry.id}`,
                             away ? 'Show' : 'Hide',
                             'edit:hide',
                             { payload: { itemId: entry.id } }),
                    ],
                });
            }),
        item('edit:reset', 'Reset ring', 'edit:reset', { destructive: true }),
    ]);
}

// Devices grouped by category, as a submenu tree. Used by more than one menu,
// so it is built once and parameterised by the action it commits - and by
// whether committing it costs the caller what is already on screen.
function deviceTree(definitions, action, leaf = {}) {
    const byCategory = new Map();
    Object.values(definitions).forEach(device => {
        if (!byCategory.has(device.category)) byCategory.set(device.category, []);
        byCategory.get(device.category).push(device);
    });

    const categories = [...byCategory.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([category, devices]) => item(
            `cat:${category}`,
            category,
            null,
            {
                children: packRing(
                    devices
                        .sort((a, b) => a.model.localeCompare(b.model))
                        .map(device => item(`dev:${device.id}`, device.model, action, {
                            payload: { deviceId: device.id },
                            ...leaf,
                        }))
                ),
            }
        ));

    return packRing(categories);
}

// Rows as a submenu, plus the two row actions that always apply.
function rowTree(groups, { includeAssign }) {
    const rows = groups.map(group => item(
        `row:${group.id}`,
        `${group.label} (${group.members.length})`,
        'row:assign',
        { payload: { groupId: group.id } }
    ));

    return packRing([
        item('row:new', 'New Row', 'row:new'),
        ...(includeAssign && rows.length ? rows : []),
        ...(includeAssign ? [item('row:loosen', 'Loosen', 'row:loosen')] : []),
    ]);
}

// ===================================================================
// resolve(context) -> MenuSpec
// ===================================================================
// `context` is rad's MenuContext: { type, targetIds, position }.
// `state` is the host's read-only view of itself — the resolver reads, never
// writes, which is what keeps it pure and testable without a rack.
function carlosResolve(context, state) {
    const definitions = state.definitions || {};
    const groups = state.groups || [];

    // Six families, and always the same six.
    //
    // The ring used to be eight items of two kinds: four families that opened
    // submenus and four actions that fired. Which was which you learned by
    // trying, and the mix moved as items were added - `Randomize` and `Clear
    // Rack` were on the ring because there was room, not because they belong
    // beside `Add Device`.
    //
    // Every one of these opens something, none of them fires, and the set does
    // not change. A ring you can learn is a ring whose north is always the
    // same thing, and that is worth more than saving one press on whichever
    // action seemed important the week it was added.
    //
    // Six rather than eight because the ceiling is eight: a family at the
    // ceiling has nowhere to grow, and the next good idea would have to
    // displace one of these rather than join it.
    if (context.type === 'canvas') {
        const config = state.ringConfig || {};
        const declared = [
                // What is in the rack.
                item('add', 'Add', null, {
                    children: deviceTree(definitions, 'add-node'),
                }),
                // How it is arranged.
                item('rows', 'Rows', null, {
                    children: rowTree(groups, { includeAssign: false }),
                }),
                // How it is drawn. Nothing here changes the rig.
                item('view', 'View', null, {
                    children: [
                        item('mode:irl', 'As laid out', 'display:irl'),
                        item('mode:minimal', 'Minimal', 'display:minimal'),
                        item('turn-all', 'Turn All', 'turn-all'),
                        // Pinning is the panel. A ring left open over the rack
                        // is the same object in its other state, which is why
                        // there is no second surface to reset or restore.
                        item('pin', state.pinned ? 'Unpin ring' : 'Pin ring',
                             'ring:pin'),
                        // The overlay's own exit. rad-android gives its
                        // floating window a deliberate way out because a
                        // surface that cannot be dismissed is one you are
                        // stuck with; the way back is this same ring, which
                        // is reachable from the rack whether or not the panel
                        // is on screen.

                    ],
                }),
                // The rack as a document: whole-rig operations, all of which
                // replace what is there.
                item('patch', 'Patch', null, {
                    children: [
                        item('patch:name', 'Name', 'patch:name'),
                        item('patch:export', 'Export', 'patch:export'),
                        item('patch:import', 'Import', 'patch:import',
                             { destructive: true }),
                        // An example is a whole patch document, so loading one
                        // replaces the rack rather than adding to it.
                        item('patch:examples', 'Examples', null, {
                            destructive: true,
                            children: deviceTree(definitions, 'example:complex',
                                                 { destructive: true }),
                        }),
                    ],
                }),
                // What is coming in and going out.
                item('midi', 'MIDI', null, {
                    children: [
                        item('midi:connect', 'Connect', 'midi:connect'),
                        item('midi:status', 'Status', 'midi:status'),
                        item('midi:test', 'Send test note', 'midi:test'),
                        item('midi:learn', 'Learn', 'midi:learn'),
                        item('midi:clear', 'Clear bindings', 'midi:clear',
                             { destructive: true }),
                    ],
                }),
                // Things that act on everything at once. Kept together and one
                // press further away than the rest, because that is what they
                // have in common: none of them can be aimed.
                item('all', 'All Devices', null, {
                    children: [
                        item('turn-all:sweep', 'Turn All', 'turn-all'),
                        item('randomize', 'Randomize', 'randomize'),
                        item('clear', 'Clear Rack', 'rack:clear',
                             { destructive: true }),
                    ],
                }),
        ];
        const showing = arrange(declared, config);

        return {
            title: 'Rack',
            // `Edit ▸` last and always present. Hiding every other family is
            // allowed - the ring is yours - and this is what you get back to.
            items: [
                ...showing,
                item(EDIT_ID, 'Edit', null, {
                    children: editTree(declared, showing, config),
                }),
            ],
        };
    }

    if (context.type === 'node') {
        const moduleId = context.targetIds[0];
        const module = state.modules?.get?.(moduleId);
        // The sides it *draws*, not the sides it has. A device with a blank
        // face has that side and never shows it, so asking `sides` would offer
        // to turn a device that cannot turn and name a next face it will never
        // reach. `drawnSides` is the same list `cycle` walks, which is the
        // point: the menu should promise what the gesture does.
        //
        // Tolerant of a plain object, because this resolver is pure and gets
        // exercised without a rack behind it.
        const drawn = module?.drawnSides?.() || module?.sides || [];
        const turns = drawn.length > 1;
        const next = turns
            ? drawn[(drawn.indexOf(module.view) + 1) % drawn.length]
            : null;
        const cables = state.cableCounts?.get?.(moduleId) || 0;

        return {
            title: module ? module.name : 'Device',
            items: [
                item('turn', turns ? `Turn to ${next}` : 'One side only', 'turn', {
                    enabled: turns,
                }),
                // Reached from a device, and still a whole-rack replacement -
                // the reading most likely to surprise someone, so it is the
                // one most worth marking.
                item('example', 'Example', null, {
                    destructive: true,
                    children: [
                        item('example:simple', 'Simple', 'example:simple',
                             { payload: { deviceId: module?.type }, destructive: true }),
                        item('example:complex', 'Complex', 'example:complex',
                             { payload: { deviceId: module?.type }, destructive: true }),
                    ],
                }),
                item('rows', 'Row', null, {
                    children: rowTree(groups, { includeAssign: true }),
                }),
                item('midi', 'MIDI', null, {
                    children: [
                        item('midi:learn', 'Bind next message', 'midi:learn'),
                        item('midi:clear', 'Clear bindings', 'midi:clear'),
                    ],
                }),
                item('unpatch', cables ? `Unpatch (${cables})` : 'Nothing patched',
                     'cable:remove-node', { enabled: cables > 0, destructive: true }),
                item('randomize', 'Randomize', 'randomize:node'),
                item('delete', 'Delete', 'delete', { destructive: true }),
            ],
        };
    }

    // A cable is an edge, which is a context type rad's contract already names
    // and this app had never resolved. Reaching a lead through the same menu as
    // everything else is what makes unpatching one cable possible at all -
    // before it, the only way out of a patch was to clear the whole rack.
    if (context.type === 'edge') {
        const cable = state.cables?.get?.(context.targetIds[0]);
        return {
            title: cable ? cable.label : 'Cable',
            items: [
                item('cable:follow', 'Follow', 'cable:follow'),
                item('cable:remove', 'Unpatch', 'cable:remove', { destructive: true }),
            ],
        };
    }

    // A row is a context of its own, and the fourth thing you can point at.
    //
    // rad names four types and this is a fifth, which the contract allows:
    // extension is permitted, repurposing is not. A row is not a node - it has
    // no jacks, no panel and no sides - and calling it one to stay inside the
    // list would have been exactly the repurposing the rule forbids.
    //
    // Right-clicking a row used to fall through to the rack menu, so the only
    // way to act on one was the small x in its header: a single click target,
    // one action, and no way to turn a row or empty it.
    if (context.type === 'row') {
        const group = groups.find(g => g.id === context.targetIds[0]);
        const members = group?.members.length || 0;
        return {
            title: group ? `${group.label} (${members})` : 'Row',
            items: [
                item('add', 'Add Device', null, {
                    children: deviceTree(definitions, 'add-node'),
                }),
                item('row:turn', 'Turn Row', 'row:turn', { enabled: members > 0 }),
                item('row:loosen-all', 'Empty Row', 'row:loosen-all',
                     { enabled: members > 0 }),
                // The row goes; its devices stay in the rack. Destructive
                // because it removes something, not because it loses anything.
                item('row:delete', 'Delete Row', 'row:delete', { destructive: true }),
            ],
        };
    }

    if (context.type === 'selection') {
        return {
            title: `${context.targetIds.length} selected`,
            items: [
                item('turn', 'Turn', 'turn'),
                item('rows', 'Row', null, {
                    children: rowTree(groups, { includeAssign: true }),
                }),
                item('delete', 'Delete', 'delete', { destructive: true }),
            ],
        };
    }

    throw new Error(`no menu for context type ${context.type}`);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        carlosResolve, packRing, deviceTree, rowTree, editTree, arrange,
        MENU_MAX, WEDGE_MAX, EDIT_ID,
    };
}
