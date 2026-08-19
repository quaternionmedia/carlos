// A DOM small enough to read, real enough to catch what stubs cannot.
//
// The earlier harnesses stub `classList` as no-ops and `querySelectorAll` as
// `[]`. That is fine for testing model state and useless for testing whether
// the model reached the screen — the exact gap that let "devices report turning
// but do not turn" through. This module parses innerHTML into real nodes and
// implements the handful of DOM the app actually uses.
//
// Not a browser. No layout, no CSS cascade, no event capture ordering. It
// answers one question: after the app runs, what does the tree look like?

class ClassList {
    constructor(el) { this.el = el; }
    get _set() {
        return new Set((this.el.getAttribute('class') || '').split(/\s+/).filter(Boolean));
    }
    _write(set) { this.el.setAttribute('class', [...set].join(' ')); }
    add(...names) { const s = this._set; names.forEach(n => s.add(n)); this._write(s); }
    remove(...names) { const s = this._set; names.forEach(n => s.delete(n)); this._write(s); }
    contains(name) { return this._set.has(name); }
    toggle(name, force) {
        const has = this.contains(name);
        const want = force === undefined ? !has : Boolean(force);
        if (want) this.add(name); else this.remove(name);
        return want;
    }
    get length() { return this._set.size; }
    toString() { return [...this._set].join(' '); }
}

class El {
    constructor(tag = 'div') {
        this.tagName = tag.toUpperCase();
        this.attributes = {};
        this.children = [];
        this.parent = null;
        this.listeners = [];
        this._text = '';
        this.classList = new ClassList(this);
        // A style object that remembers. It was two no-ops, which models a DOM
        // that silently forgets rather than a thin one: a custom property set
        // through it could not be read back, so `--panel-width` and `--value`
        // were unassertable and a rule reading them would have failed silently.
        // Plain assignment (`style.transform = ...`) still works and is
        // recorded alongside.
        this.style = {
            _props: {},
            setProperty(name, value) { this._props[name] = String(value); },
            getPropertyValue(name) { return this._props[name] ?? ''; },
            removeProperty(name) { delete this._props[name]; },
        };
        this.dataset = new Proxy({}, {
            get: (_, key) => this.getAttribute(`data-${camelToDash(String(key))}`),
            set: (_, key, value) => {
                this.setAttribute(`data-${camelToDash(String(key))}`, String(value));
                return true;
            },
            has: (_, key) => `data-${camelToDash(String(key))}` in this.attributes,
        });
    }

    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; }
    removeAttribute(name) { delete this.attributes[name]; }

    get className() { return this.getAttribute('class') || ''; }
    set className(v) { this.setAttribute('class', v); }

    get textContent() {
        return this.children.length
            ? this.children.map(c => c.textContent).join('')
            : this._text;
    }
    set textContent(v) { this.children = []; this._text = String(v); }

    set innerHTML(html) { this.children = parse(html, this); }
    get innerHTML() { return this.children.map(serialize).join(''); }

    appendChild(child) {
        if (child.parent) child.parent.children = child.parent.children.filter(c => c !== child);
        child.parent = this;
        this.children.push(child);
        return child;
    }
    replaceChildren(...nodes) {
        this.children = [];
        nodes.forEach(n => this.appendChild(n));
    }
    remove() {
        if (!this.parent) return;
        this.parent.children = this.parent.children.filter(c => c !== this);
        this.parent = null;
    }
    replaceWith(node) {
        if (!this.parent) return;
        const at = this.parent.children.indexOf(this);
        node.parent = this.parent;
        this.parent.children[at] = node;
        this.parent = null;
    }

    addEventListener(type, fn) { this.listeners.push({ type, fn }); }
    removeEventListener(type, fn) {
        this.listeners = this.listeners.filter(l => !(l.type === type && l.fn === fn));
    }

    get descendants() {
        return this.children.flatMap(c => [c, ...c.descendants]);
    }
    querySelectorAll(selector) {
        return this.descendants.filter(node => matches(node, selector));
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    closest(selector) {
        let node = this;
        while (node) {
            if (matches(node, selector)) return node;
            node = node.parent;
        }
        return null;
    }
    matches(selector) { return matches(this, selector); }
    getBoundingClientRect() {
        return { left: 0, top: 0, width: 100, height: 100, right: 100, bottom: 100 };
    }
}

function camelToDash(name) {
    return name.replace(/[A-Z]/g, m => `-${m.toLowerCase()}`);
}

// Supports what the app uses: `.class`, `#id`, `tag`, `[attr="v"]`, compounds
// of those, and comma lists. No descendant combinators — the app does not use
// them in querySelectorAll, and a parser that pretends to support them would
// be the harness lying about its own coverage.
function matches(node, selector) {
    return selector.split(',').map(s => s.trim()).filter(Boolean).some(part => {
        const tokens = part.match(/(\[[^\]]+\]|[.#]?[\w-]+)/g) || [];
        return tokens.every(token => {
            if (token.startsWith('.')) return node.classList.contains(token.slice(1));
            if (token.startsWith('#')) return node.getAttribute('id') === token.slice(1);
            if (token.startsWith('[')) {
                const [, name, value] = token.match(/\[([\w-]+)(?:="([^"]*)")?\]/) || [];
                if (value === undefined) return node.getAttribute(name) !== null;
                return node.getAttribute(name) === value;
            }
            return node.tagName === token.toUpperCase();
        });
    });
}

const VOID = new Set(['br', 'hr', 'img', 'input', 'meta', 'link']);

// Good enough for the app's own templates: well-formed tags, quoted attributes,
// no comments, no CDATA.
function parse(html, parent) {
    const tokens = String(html).split(/(<[^>]+>)/).filter(t => t !== '');
    const roots = [];
    const stack = [];

    for (const token of tokens) {
        if (!token.startsWith('<')) {
            const text = token.trim();
            if (text && stack.length) stack[stack.length - 1]._text += text;
            continue;
        }
        if (token.startsWith('</')) {
            stack.pop();
            continue;
        }

        const tag = (token.match(/^<\s*([\w-]+)/) || [])[1];
        if (!tag) continue;

        const node = new El(tag);
        for (const [, name, value] of token.matchAll(/([\w:-]+)\s*=\s*"([^"]*)"/g)) {
            node.setAttribute(name, value);
        }

        const parentNode = stack[stack.length - 1];
        if (parentNode) {
            node.parent = parentNode;
            parentNode.children.push(node);
        } else {
            node.parent = parent;
            roots.push(node);
        }

        if (!VOID.has(tag.toLowerCase()) && !token.endsWith('/>')) stack.push(node);
    }
    return roots;
}

function serialize(node) {
    const attrs = Object.entries(node.attributes)
        .map(([k, v]) => ` ${k}="${v}"`).join('');
    const tag = node.tagName.toLowerCase();
    return `<${tag}${attrs}>${node.textContent}${node.children.map(serialize).join('')}</${tag}>`;
}

function makeDocument() {
    const body = new El('body');
    const registry = new Map();
    const listeners = [];

    const doc = {
        body,
        createElement: (tag) => new El(tag),
        createElementNS: (_ns, tag) => new El(tag),
        addEventListener(type, fn) { listeners.push({ type, fn }); },
        removeEventListener(type, fn) {
            const i = listeners.findIndex(l => l.type === type && l.fn === fn);
            if (i >= 0) listeners.splice(i, 1);
        },
        getElementById(id) {
            if (registry.has(id)) return registry.get(id);
            const found = body.descendants.find(n => n.getAttribute('id') === id);
            return found || null;
        },
        register(id, node) { registry.set(id, node); return node; },
        listeners,
    };
    return doc;
}

module.exports = { El, ClassList, makeDocument, matches, parse };
