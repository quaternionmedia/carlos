// ===================================================================
// MIDI — in, mapped, and onto the picture
// ===================================================================
// Mirrors src/midi.py. Both sides parse the same bytes and match the same
// bindings, so a mapping behaves identically whether the message arrived from a
// port in this browser or over HTTP from another application.
//
// Nothing here assumes hardware. Web MIDI is asked for and may be refused —
// no browser support, no permission, no devices — and every refusal is reported
// rather than swallowed, because "no activity" and "no connection" look
// identical on screen and only one of them is a problem.

const MIDI_RESERVED_CC = [20, 21, 22, 23]; // rad's speed axes; watch, never reuse

function midiParse(bytes) {
    const data = Array.from(bytes || []);
    if (!data.length) throw new Error('no bytes');

    const status = data[0];
    if (status < 0x80) throw new Error(`0x${status.toString(16)} is a data byte`);

    if (status >= 0xF8) {
        const transport = { 0xF8: 'clock', 0xFA: 'start', 0xFB: 'continue', 0xFC: 'stop' };
        if (!transport[status]) throw new Error(`unsupported system message`);
        return { type: transport[status] };
    }
    if (status >= 0xF0) throw new Error('system common is not mapped');

    const kind = status & 0xF0;
    const channel = (status & 0x0F) + 1;
    const d1 = data[1];
    const d2 = data[2];

    switch (kind) {
        case 0x90:
            // Velocity zero is a note-off. Devices send this, and reading it as
            // a note-on leaves the device lit with nothing playing.
            return { type: d2 ? 'note_on' : 'note_off', channel, note: d1, value: d2 };
        case 0x80:
            return { type: 'note_off', channel, note: d1, value: d2 };
        case 0xA0:
            return { type: 'aftertouch', channel, note: d1, value: d2 };
        case 0xB0:
            return { type: 'cc', channel, controller: d1, value: d2 };
        case 0xC0:
            return { type: 'program', channel, value: d1 };
        case 0xD0:
            return { type: 'aftertouch', channel, value: d1 };
        case 0xE0:
            return { type: 'pitchbend', channel, value: (d2 << 7) | d1 };
        default:
            throw new Error(`unhandled status 0x${status.toString(16)}`);
    }
}

// The inverse of `midiParse`, and the only way anything leaves this app.
//
// Mirrors `encode` in src/midi.py, and `tests/test_midi_and_modes.py` asserts
// the two agree byte for byte - a browser that sends different bytes from the
// seam is two applications wearing one name.
//
// Every send goes through here. A malformed message is refused with the reason
// rather than handed to a device, because MIDI marks a status byte with the
// eighth bit: a data byte of 200 is read as the start of a new message and the
// device then starves for data. One bad value desynchronises the stream rather
// than sounding wrong, which is why a device reports "malformed" and can never
// say which byte.
const MIDI_TRANSPORT = { clock: 0xF8, start: 0xFA, continue: 0xFB, stop: 0xFC };

function midiEncode(message) {
    const kind = message?.type;
    if (!kind) throw new Error('a message needs a type');

    if (kind in MIDI_TRANSPORT) return [MIDI_TRANSPORT[kind]];

    const channel = message.channel;
    if (channel === undefined || channel === null) {
        throw new Error(`a ${kind} message needs a channel`);
    }
    if (!Number.isInteger(channel) || channel < 1 || channel > 16) {
        throw new Error(`channel is ${channel}; MIDI channels are 1-16`);
    }
    const nibble = channel - 1;

    const seven = (name, value, fallback) => {
        const got = (value === undefined || value === null) ? fallback : value;
        if (got === undefined) throw new Error(`a ${kind} message needs ${name}`);
        if (!Number.isInteger(got) || got < 0 || got > 127) {
            throw new Error(
                `${name} is ${got}; MIDI carries 0-127 in a data byte, and `
                + 'anything above it sets the bit that marks a status byte');
        }
        return got;
    };

    if (kind === 'note_on') {
        return [0x90 | nibble, seven('a note', message.note),
                seven('a velocity', message.value, 64)];
    }
    if (kind === 'note_off') {
        return [0x80 | nibble, seven('a note', message.note),
                seven('a velocity', message.value, 0)];
    }
    if (kind === 'cc') {
        return [0xB0 | nibble, seven('a controller', message.controller),
                seven('a value', message.value, 0)];
    }
    if (kind === 'program') {
        return [0xC0 | nibble, seven('a program', message.value)];
    }
    if (kind === 'aftertouch') {
        if (message.note !== undefined && message.note !== null) {
            return [0xA0 | nibble, seven('a note', message.note),
                    seven('a pressure', message.value, 0)];
        }
        return [0xD0 | nibble, seven('a pressure', message.value)];
    }
    if (kind === 'pitchbend') {
        const value = (message.value === undefined || message.value === null)
            ? 8192 : message.value;
        if (!Number.isInteger(value) || value < 0 || value > 16383) {
            throw new Error(
                `a pitch bend is ${value}; it is 14 bits, so 0-16383, `
                + 'sent as two 7-bit bytes');
        }
        return [0xE0 | nibble, value & 0x7F, (value >> 7) & 0x7F];
    }

    throw new Error(`nothing knows how to send a ${kind} message`);
}


function midiIntensity(message) {
    if (message.type === 'note_off' || message.type === 'stop') return 0;
    if (message.type === 'pitchbend') return (message.value || 0) / 16383;
    if (message.value === undefined || message.value === null) return 1;
    return message.value / 127;
}

// A field left out is a wildcard, so a binding survives a machine being moved
// to another channel.
function midiMatches(source, message) {
    if (source.channel != null && message.channel !== source.channel) return false;

    switch (source.type) {
        case 'channel':
            return message.channel != null;
        case 'note':
            if (!['note_on', 'note_off', 'aftertouch'].includes(message.type)) return false;
            return source.note == null || message.note === source.note;
        case 'cc':
            if (message.type !== 'cc') return false;
            return source.controller == null || message.controller === source.controller;
        case 'program':
            return message.type === 'program';
        case 'pitchbend':
            return message.type === 'pitchbend';
        case 'transport':
            return ['clock', 'start', 'stop', 'continue'].includes(message.type);
        default:
            return false;
    }
}

// All matching bindings fire. One message can genuinely concern two devices —
// a clock lights everything following it — and picking one winner would hide
// that.
function midiRoute(bindings, message) {
    return (bindings || [])
        .filter(binding => midiMatches(binding.source, message))
        .map(binding => ({
            binding: binding.id,
            module: binding.module,
            parameter: binding.parameter || null,
            jack: binding.jack || null,
            intensity: midiIntensity(message),
            message,
        }));
}

// ===================================================================
// THE PORT
// ===================================================================
// Where messages go out, and the guard they pass on the way.
//
// Held apart from `MidiInput` because the failure modes do not overlap: an
// input that never fires is usually a permission or a cable, while an output
// that never arrives is usually a message a device refused. `send` returns what
// it sent so a caller can show it, and throws with the reason when it will not.
class MidiOutput {
    constructor({ onStatus = () => {} } = {}) {
        this.onStatus = onStatus;
        this.access = null;
        this.ports = [];
        this.port = null;
        this.sent = 0;
        this.refused = 0;
        this.lastRefusal = null;
    }

    async connect(access = null) {
        this.access = access || this.access;
        if (!this.access) {
            if (typeof navigator === 'undefined' || !navigator.requestMIDIAccess) {
                this.onStatus({ state: 'unsupported', detail: 'no Web MIDI here' });
                return false;
            }
            try {
                this.access = await navigator.requestMIDIAccess({ sysex: false });
            } catch (error) {
                this.onStatus({ state: 'refused', detail: error.message });
                return false;
            }
        }
        this.ports = [...this.access.outputs.values()];
        this.port = this.ports[0] || null;
        this.onStatus({
            state: this.ports.length ? 'connected' : 'no-ports',
            detail: this.ports.length
                ? this.ports.map(p => p.name).join(', ')
                : 'no MIDI outputs are attached',
        });
        return Boolean(this.ports.length);
    }

    choose(id) {
        const found = this.ports.find(p => p.id === id || p.name === id);
        if (found) this.port = found;
        return found || null;
    }

    // Encode, then send. Never the other way round: a device that reports a
    // malformed message cannot say which byte, so the check has to happen on
    // this side while the message is still a message.
    send(message) {
        let bytes;
        try {
            bytes = midiEncode(message);
        } catch (error) {
            this.refused += 1;
            this.lastRefusal = { message, reason: error.message };
            this.onStatus({ state: 'malformed', detail: error.message });
            throw error;
        }
        if (!this.port) {
            this.onStatus({ state: 'no-ports', detail: 'nothing to send to' });
            return { bytes, sent: false };
        }
        this.port.send(bytes);
        this.sent += 1;
        return { bytes, sent: true };
    }
}


class MidiInput {
    constructor({ onActivity, onStatus, onMessage }) {
        this.onActivity = onActivity;
        this.onStatus = onStatus || (() => {});
        // Every message, matched or not. Learn needs the ones nothing matches —
        // that is the whole point of binding something new.
        this.onMessage = onMessage || (() => {});
        this.access = null;
        this.ports = [];
        this.bindings = [];
        this.lastMessage = null;
        // Counted rather than inferred: a rack with no bindings and a rack with
        // no cable both show nothing, and the count tells them apart.
        this.received = 0;
        this.matched = 0;
    }

    setBindings(bindings) {
        this.bindings = bindings || [];
        return this.bindings;
    }

    get available() {
        return typeof navigator !== 'undefined' && Boolean(navigator.requestMIDIAccess);
    }

    // Why MIDI will not work here, in words that name the actual cause.
    //
    // `available` was answering one question with two meanings. Web MIDI is only
    // exposed in a secure context, so on `http://192.168.1.151:8000` -- the LAN
    // address this server prints at startup, and the one the onboarding page
    // recommends for an on-device test -- `navigator.requestMIDIAccess` is
    // simply absent, and the app said "this browser has no Web MIDI". The
    // browser has it. The page is not a secure context. Measured in Chromium:
    // loopback reports `isSecureContext: true` and the API present; the LAN
    // address reports false and absent.
    diagnose() {
        if (typeof navigator === 'undefined') {
            return { state: 'unsupported', detail: 'no navigator in this runtime' };
        }
        if (typeof window !== 'undefined' && window.isSecureContext === false) {
            const here = (typeof location !== 'undefined' && location.origin) || 'this address';
            return {
                state: 'insecure-context',
                detail: `Web MIDI needs a secure context and ${here} is not one. `
                    + 'Open the rack on localhost, put it behind HTTPS, or '
                    + 'forward the port so it arrives as localhost: '
                    + '`ssh -L 8000:localhost:8000 <host>`. The LAN address '
                    + 'this server prints will not do on its own.',
            };
        }
        if (!navigator.requestMIDIAccess) {
            return {
                state: 'unsupported',
                detail: 'this browser exposes no Web MIDI, and the page is a '
                    + 'secure context - so it is the browser or its settings',
            };
        }
        return null;
    }

    // Whether the remedy is likely to be an ALSA one.
    //
    // Deliberately a hint rather than a branch in the logic: the browser cannot
    // see ALSA, so all this does is name the next command instead of leaving
    // "no inputs are attached" as a dead end.
    onLinux() {
        const platform = (typeof navigator !== 'undefined'
            && (navigator.userAgentData?.platform || navigator.platform)) || '';
        return /linux|arm/i.test(platform);
    }

    // granted | denied | prompt | unknown.
    //
    // Worth asking separately, because a browser that blocks MIDI by policy or
    // by a shield reports `denied` without ever prompting, and that is
    // indistinguishable from a dismissed prompt in the failure alone.
    async permissionState() {
        if (typeof navigator === 'undefined' || !navigator.permissions?.query) {
            return 'unknown';
        }
        try {
            const status = await navigator.permissions.query(
                { name: 'midi', sysex: false });
            return status.state;
        } catch {
            // Some browsers refuse to answer for `midi` at all, which is not
            // the same as refusing MIDI.
            return 'unknown';
        }
    }

    async connect() {
        const wrong = this.diagnose();
        if (wrong) {
            this.onStatus(wrong);
            return false;
        }
        try {
            this.access = await navigator.requestMIDIAccess({ sysex: false });
        } catch (error) {
            const permission = await this.permissionState();
            this.onStatus({
                state: 'refused',
                detail: permission === 'denied'
                    ? 'permission is denied for this site - check the browser\'s '
                      + 'MIDI site setting, and any shield or extension that '
                      + 'blocks device access'
                    : `${error.message} (permission: ${permission})`,
            });
            return false;
        }

        this.ports = [...this.access.inputs.values()];
        this.ports.forEach(port => {
            port.onmidimessage = (event) => this.receive(event.data, port.name);
        });
        this.access.onstatechange = () => this.rescan();

        this.onStatus({
            state: this.ports.length ? 'connected' : 'no-ports',
            detail: this.ports.length
                ? this.ports.map(p => p.name).join(', ')
                : 'Web MIDI is available and no inputs are attached'
                  + (this.onLinux()
                     ? ' - on Linux the browser reaches MIDI through ALSA, so '
                       + 'check `aconnect -l` first: a port ALSA cannot see is '
                       + 'invisible to every browser on the machine'
                     : ''),
        });
        return true;
    }

    rescan() {
        if (!this.access) return;
        const seen = new Set(this.ports.map(p => p.id));
        [...this.access.inputs.values()].forEach(port => {
            if (seen.has(port.id)) return;
            port.onmidimessage = (event) => this.receive(event.data, port.name);
            this.ports.push(port);
        });
    }

    // The one path every message takes, whichever side it came from. The
    // synthetic source below calls this too, so nothing is exercised only by
    // hardware nobody has plugged in.
    receive(bytes, from = 'synthetic') {
        let message;
        try {
            message = midiParse(bytes);
        } catch (error) {
            this.onStatus({ state: 'bad-message', detail: error.message });
            return [];
        }

        this.received += 1;
        this.lastMessage = { ...message, from };
        this.onMessage(message);
        const activity = midiRoute(this.bindings, message);
        this.matched += activity.length;
        activity.forEach(item => this.onActivity(item));
        return activity;
    }

    // A rack with no hardware attached still has to be demonstrable, and a
    // feature that can only be seen with a keyboard plugged in is a feature
    // nobody reviews.
    simulate({ channel = 1, note = 36, controller = null, value = 100 } = {}) {
        const bytes = controller === null
            ? [0x90 | (channel - 1), note, value]
            : [0xB0 | (channel - 1), controller, value];
        return this.receive(bytes, 'simulated');
    }
}
