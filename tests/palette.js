// Tool palette harness.
//
// A floating panel is a small pile of arithmetic wearing a UI, and every piece
// of it is a thing that can be silently wrong: a default corner computed against
// a window nobody measured, a clamp that lets the grip off the screen, a stored
// position that comes back as NaN. None of those throw. They just leave the
// panel somewhere you cannot reach it, and "cannot reach it" looks exactly like
// "did not render".
//
// Run directly (`node tests/palette.js`) or through the Python suite.

const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..');
const { El } = require('./dom.js');

// A window the tests own, so a default position can be asserted rather than
// described. The real one is whatever the browser is.
const VIEW = { width: 1200, height: 800 };
const SIZE = { width: 232, height: 200 };

global.window = {
    get innerWidth() { return VIEW.width; },
    get innerHeight() { return VIEW.height; },
    addEventListener() {},
    removeEventListener() {},
};

(0, eval)(fs.readFileSync(path.join(REPO, 'static/palette.js'), 'utf8')
    + '\nglobalThis.Palette = Palette;'
    + '\nglobalThis.PALETTE_STORE_KEY = PALETTE_STORE_KEY;'
    + '\nglobalThis.PALETTE_KEEP_VISIBLE = PALETTE_KEEP_VISIBLE;'
    + '\nglobalThis.PALETTE_INSET = PALETTE_INSET;'
    + '\nglobalThis.PALETTE_STEP = PALETTE_STEP;'
    + '\nglobalThis.PALETTE_STEP_COARSE = PALETTE_STEP_COARSE;');

// A storage that behaves, and one that refuses everything the way a browser
// with storage disabled does.
function fakeStorage() {
    const store = new Map();
    // Writes are counted, not just kept. "Remembered once at the end of a drag"
    // and "remembered on every frame" leave the same value behind, so a check
    // that reads the value cannot tell them apart - and it did not, until this
    // counter was added and the per-frame version was watched stay green.
    let writes = 0;
    return {
        getItem: (k) => (store.has(k) ? store.get(k) : null),
        setItem: (k, v) => { writes += 1; store.set(k, String(v)); },
        removeItem: (k) => store.delete(k),
        get writes() { return writes; },
        _store: store,
    };
}

const hostileStorage = {
    getItem() { throw new Error('storage is disabled'); },
    setItem() { throw new Error('storage is disabled'); },
    removeItem() { throw new Error('storage is disabled'); },
};

// A palette element that measures like the real one.
function makePalette({ storage = fakeStorage(), corner = 'top-right' } = {}) {
    const element = new El('div');
    element.setAttribute('id', 'tool-palette');
    element.setAttribute('data-default-corner', corner);
    element.getBoundingClientRect = () => ({
        left: 0, top: 0, width: SIZE.width, height: SIZE.height,
    });

    const grip = new El('div');
    grip.setAttribute('id', 'tool-palette-grip');
    element.appendChild(grip);

    const palette = new Palette({ element, grip, storage });
    return { palette, element, grip, storage };
}

// Fire at the element's own listeners, which is where the palette binds.
function fire(node, type, extra = {}) {
    const event = {
        type, button: 0, pointerId: 1,
        clientX: 0, clientY: 0,
        shiftKey: false, ctrlKey: false, altKey: false, metaKey: false,
        defaultPrevented: false, propagationStopped: false,
        preventDefault() { this.defaultPrevented = true; },
        stopPropagation() { this.propagationStopped = true; },
        ...extra,
    };
    node.listeners.filter(l => l.type === type).forEach(l => l.fn(event));
    return event;
}

const results = [];
const check = (name, got, want) => results.push({ name, got, want });

const at = (palette) => ({ x: palette.position.x, y: palette.position.y });
const styleOf = (element) => ({
    left: element.style.getPropertyValue('left'),
    top: element.style.getPropertyValue('top'),
});

// ---- the default starting position ----
{
    const { palette, element } = makePalette();
    check('opens at the default corner, inset from both edges', at(palette), {
        x: VIEW.width - SIZE.width - PALETTE_INSET.x,
        y: PALETTE_INSET.y,
    });
    // The model is not the screen: a position nothing wrote to the element is
    // a position nobody can see.
    check('and writes that position onto the element', styleOf(element), {
        left: `${VIEW.width - SIZE.width - PALETTE_INSET.x}px`,
        top: `${PALETTE_INSET.y}px`,
    });
    check('and drops the stylesheet’s right-edge hold, which would fight the drag',
        element.classList.contains('is-placed'), true);
    check('the default is not remembered - only a move is',
        palette.read(), null);
}

// Every corner resolves against the window, not against a guessed one.
{
    const corners = {
        'top-left': { x: PALETTE_INSET.x, y: PALETTE_INSET.y },
        'top-right': { x: VIEW.width - SIZE.width - PALETTE_INSET.x, y: PALETTE_INSET.y },
        'bottom-left': { x: PALETTE_INSET.x, y: VIEW.height - SIZE.height - PALETTE_INSET.y },
        'bottom-right': {
            x: VIEW.width - SIZE.width - PALETTE_INSET.x,
            y: VIEW.height - SIZE.height - PALETTE_INSET.y,
        },
    };
    Object.entries(corners).forEach(([corner, want]) => {
        const { palette } = makePalette({ corner });
        check(`${corner} opens where that corner is`, at(palette), want);
    });
}

// ---- clamping: the grip never leaves the screen ----
{
    const { palette } = makePalette();

    palette.moveTo({ x: -9999, y: -9999 });
    check('dragged off the top-left, the grip is still reachable',
        palette.position.x + SIZE.width >= PALETTE_KEEP_VISIBLE
        && palette.position.y >= 0, true);
    check('and it is never dragged above the top edge, where nothing can grab it',
        palette.position.y, 0);

    palette.moveTo({ x: 9999, y: 9999 });
    check('dragged off the bottom-right, some of it is still on screen',
        palette.position.x <= VIEW.width - PALETTE_KEEP_VISIBLE
        && palette.position.y <= VIEW.height - PALETTE_KEEP_VISIBLE, true);

    palette.moveTo({ x: 400, y: 300 });
    check('a position on screen is left alone', at(palette), { x: 400, y: 300 });
}

// ---- the window changing shape under a placed palette ----
{
    const { palette } = makePalette();
    palette.moveTo({ x: 900, y: 700 });

    VIEW.width = 640;
    VIEW.height = 480;
    palette.reflow();
    check('a window that shrinks brings the palette back on screen',
        palette.position.x <= VIEW.width - PALETTE_KEEP_VISIBLE
        && palette.position.y <= VIEW.height - PALETTE_KEEP_VISIBLE, true);

    // A reflow is not a move: the position someone chose is still the position
    // to come back to when the window is itself again.
    check('and does not overwrite what was remembered',
        JSON.parse(palette.storage.getItem(PALETTE_STORE_KEY)), { x: 900, y: 700 });

    VIEW.width = 1200;
    VIEW.height = 800;
}

// ---- memory ----
{
    const storage = fakeStorage();
    const first = makePalette({ storage }).palette;
    first.moveTo({ x: 300, y: 240 });

    const second = makePalette({ storage }).palette;
    check('a second session opens where the first was left',
        at(second), { x: 300, y: 240 });

    second.reset();
    check('reset puts it back to the default corner', at(second), {
        x: VIEW.width - SIZE.width - PALETTE_INSET.x,
        y: PALETTE_INSET.y,
    });
    check('and forgets, so the next session starts at the default too',
        storage.getItem(PALETTE_STORE_KEY), null);
}

// A stored value can be anything: another build, a hand edit, a half-written
// write. None of it should reach the element as a position.
{
    const rubbish = ['not json at all', '{"x":"left","y":12}', '{"x":null}',
                     'null', '[]', '{"y":40}'];
    rubbish.forEach(value => {
        const storage = fakeStorage();
        storage.setItem(PALETTE_STORE_KEY, value);
        const { palette } = makePalette({ storage });
        check(`a stored ${JSON.stringify(value)} falls back to the default`,
            at(palette), {
                x: VIEW.width - SIZE.width - PALETTE_INSET.x,
                y: PALETTE_INSET.y,
            });
    });
}

// A browser can refuse storage outright, and reading the property is what
// throws. The palette still has to draw.
{
    let built = null;
    let threw = null;
    try {
        built = makePalette({ storage: hostileStorage }).palette;
        built.moveTo({ x: 200, y: 200 });
    } catch (error) {
        threw = error.message;
    }
    check('storage that throws on every call does not stop the palette', threw, null);
    check('and it still moves', built && at(built), { x: 200, y: 200 });
}

// ---- dragging ----
{
    const { palette, element, grip } = makePalette();
    palette.moveTo({ x: 400, y: 300 });

    // Grab 30px into the panel and move 100 right, 50 down. The panel must move
    // by the same amount, not jump its own corner to the cursor.
    const writesBefore = palette.storage.writes;

    fire(grip, 'pointerdown', { clientX: 430, clientY: 330 });
    check('the grip says it is being moved',
        element.classList.contains('is-moving'), true);

    // Several frames, as a real drag produces.
    fire(grip, 'pointermove', { clientX: 460, clientY: 340 });
    fire(grip, 'pointermove', { clientX: 500, clientY: 360 });
    fire(grip, 'pointermove', { clientX: 530, clientY: 380 });
    check('the panel moves with the cursor, keeping the grab offset',
        at(palette), { x: 500, y: 350 });
    check('and nothing is written while it is still moving',
        palette.storage.writes - writesBefore, 0);

    fire(grip, 'pointerup', {});
    check('and stops being moved when released',
        element.classList.contains('is-moving'), false);
    check('the position is written once, at the end of the drag',
        palette.storage.writes - writesBefore, 1);
    check('and it is the position it ended at',
        JSON.parse(palette.storage.getItem(PALETTE_STORE_KEY)), { x: 500, y: 350 });

    // A released drag leaves nothing behind to move the panel later.
    const before = at(palette);
    fire(grip, 'pointermove', { clientX: 900, clientY: 900 });
    check('a move after release does nothing', at(palette), before);
}

// Only the primary button drags. A right-click on the grip belongs to whatever
// else wants it, not to a drag nobody asked for.
{
    const { palette, element, grip } = makePalette();
    palette.moveTo({ x: 400, y: 300 });
    fire(grip, 'pointerdown', { button: 2, clientX: 430, clientY: 330 });
    check('a right-press on the grip starts no drag',
        element.classList.contains('is-moving'), false);
}

// ---- the keyboard ----
{
    const { palette, grip } = makePalette();
    palette.moveTo({ x: 400, y: 300 });

    fire(grip, 'keydown', { key: 'ArrowRight' });
    check('arrow right moves it right', at(palette), { x: 400 + PALETTE_STEP, y: 300 });

    fire(grip, 'keydown', { key: 'ArrowUp', shiftKey: true });
    check('shift moves it further',
        at(palette), { x: 400 + PALETTE_STEP, y: 300 - PALETTE_STEP_COARSE });

    const moved = fire(grip, 'keydown', { key: 'ArrowDown' });
    check('a key it handled does not also reach the rack',
        moved.defaultPrevented && moved.propagationStopped, true);

    fire(grip, 'keydown', { key: 'Home' });
    check('Home puts it back to the default corner', at(palette), {
        x: VIEW.width - SIZE.width - PALETTE_INSET.x,
        y: PALETTE_INSET.y,
    });

    // Everything else still belongs to the rack. `m` opens the menu and Escape
    // deselects, from here as from anywhere.
    const passed = fire(grip, 'keydown', { key: 'm' });
    check('a key it did not handle is left for the rack',
        passed.defaultPrevented || passed.propagationStopped, false);
}

// A palette handed nothing does not throw. main.js builds one before it knows
// the template rendered.
{
    let threw = null;
    try {
        const empty = new Palette({});
        empty.reset?.();
    } catch (error) {
        threw = error.message;
    }
    check('a palette with no element is inert rather than fatal', threw, null);
}

let failed = 0;
for (const r of results) {
    const pass = JSON.stringify(r.got) === JSON.stringify(r.want);
    if (!pass) failed++;
    console.log(`${pass ? 'OK  ' : 'BUG '} ${r.name}`);
    if (!pass) console.log(`       got ${JSON.stringify(r.got)} want ${JSON.stringify(r.want)}`);
}
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
