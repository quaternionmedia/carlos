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

function item(id, label, action, extra = {}) {
    return { id, label, action, enabled: true, destructive: false, ...extra };
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

    if (context.type === 'canvas') {
        return {
            title: 'Rack',
            items: [
                item('add', 'Add Device', null, {
                    children: deviceTree(definitions, 'add-node'),
                }),
                // An example is a whole patch document, so loading one
                // replaces the rack rather than adding to it. That is what it
                // has always done; it had no way of saying so.
                item('examples', 'Examples', null, {
                    destructive: true,
                    children: deviceTree(definitions, 'example:complex',
                                         { destructive: true }),
                }),
                item('rows', 'Rows', null, {
                    children: rowTree(groups, { includeAssign: false }),
                }),
                item('patch', 'Patch', null, {
                    children: [
                        item('patch:export', 'Export', 'patch:export'),
                        item('patch:import', 'Import', 'patch:import',
                             { destructive: true }),
                    ],
                }),
                item('display', 'Display', null, {
                    children: [
                        item('mode:minimal', 'Minimal', 'display:minimal'),
                        item('mode:irl', 'As laid out', 'display:irl'),
                        item('turn-all', 'Turn All', 'turn-all'),
                    ],
                }),
                item('midi', 'MIDI', null, {
                    children: [
                        item('midi:connect', 'Connect', 'midi:connect'),
                        item('midi:status', 'Status', 'midi:status'),
                        item('midi:test', 'Send test note', 'midi:test'),
                    ],
                }),
                item('randomize', 'Randomize', 'randomize'),
                item('clear', 'Clear Rack', 'rack:clear', { destructive: true }),
            ],
        };
    }

    if (context.type === 'node') {
        const moduleId = context.targetIds[0];
        const module = state.modules?.get?.(moduleId);
        const turns = module ? module.sides.length > 1 : false;
        const next = turns ? module.sides[(module.sides.indexOf(module.view) + 1) % module.sides.length] : null;
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
    module.exports = { carlosResolve, packRing, deviceTree, rowTree, MENU_MAX };
}
