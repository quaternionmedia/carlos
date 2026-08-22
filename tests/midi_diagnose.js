// Does the MIDI layer name the right cause when it cannot work?
//
// `available` answered one question with two meanings. Web MIDI is only exposed
// in a secure context, so on the LAN address this server prints at startup --
// and which the onboarding page recommends for an on-device test --
// `navigator.requestMIDIAccess` is absent and the app said "this browser has no
// Web MIDI". The browser has it; the page is not a secure context.
//
// Measured in Chromium before this harness was written:
//   http://127.0.0.1:8000      isSecureContext true   requestMIDIAccess present
//   http://192.168.1.151:8000  isSecureContext false  requestMIDIAccess absent

const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(REPO, 'static/midi.js'), 'utf8');

let passed = 0;
let failed = 0;

function check(what, got, want) {
    const ok = got === want;
    if (ok) { passed += 1; console.log(`OK   ${what}`); }
    else { failed += 1; console.log(`BUG  ${what}\n       got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`); }
}

// The module is an ES module served to a browser; load the class out of it by
// evaluating in a scope carrying the globals it reads. Nothing here stubs the
// function under test - only the environment it asks about.
function loadWith({ secure, hasApi, permission }) {
    const navigator = {
        ...(hasApi ? { requestMIDIAccess: async () => ({ inputs: new Map() }) } : {}),
        permissions: permission === undefined ? undefined : {
            query: async () => ({ state: permission }),
        },
    };
    const window = { isSecureContext: secure };
    const location = { origin: 'http://192.168.1.151:8000' };

    const body = source
        .replace(/^export\s+/gm, '')
        .replace(/^import[^\n]*\n/gm, '');
    const make = new Function(
        'navigator', 'window', 'location', 'midiParse',
        `${body}; return MidiInput;`
    );
    const MidiInput = make(navigator, window, location, () => ({ type: 'note_on' }));
    return new MidiInput({});
}

// --- a page that is not a secure context -----------------------------------
const insecure = loadWith({ secure: false, hasApi: false });
const onLan = insecure.diagnose();
check('an insecure page is named as such, not blamed on the browser',
    onLan && onLan.state, 'insecure-context');
check('and it says where to go instead',
    Boolean(onLan && /localhost|HTTPS/i.test(onLan.detail)), true);
check('including the remedy that works over a network',
    Boolean(onLan && /ssh -L/i.test(onLan.detail)), true);
check('it does not claim the browser lacks Web MIDI',
    Boolean(onLan && /no Web MIDI/i.test(onLan.detail)), false);

// --- a secure page in a browser without the API ----------------------------
const noApi = loadWith({ secure: true, hasApi: false });
const missing = noApi.diagnose();
check('a secure page with no API blames the browser', missing && missing.state, 'unsupported');
check('and says the page was not the problem',
    Boolean(missing && /secure context/i.test(missing.detail)), true);

// --- a secure page in a browser that has it --------------------------------
const fine = loadWith({ secure: true, hasApi: true });
check('a secure page with the API has nothing to report', fine.diagnose(), null);

// --- the ALSA hint, which is the Linux and Pi case -------------------------
function platformOf(platform) {
    const body = source
        .replace(/^export\s+/gm, '')
        .replace(/^import[^\n]*\n/gm, '');
    const make = new Function('navigator', 'window', 'location', 'midiParse',
        `${body}; return MidiInput;`);
    const MidiInput = make({ platform, requestMIDIAccess: async () => ({}) },
        { isSecureContext: true }, { origin: 'http://localhost:8000' }, () => ({}));
    return new MidiInput({});
}
check('a Linux browser is told to check ALSA', platformOf('Linux aarch64').onLinux(), true);
check('an ARM platform counts too', platformOf('Linux armv7l').onLinux(), true);
check('Windows is not sent to aconnect', platformOf('Win32').onLinux(), false);
check('macOS is not either', platformOf('MacIntel').onLinux(), false);

// --- the permission probe ---------------------------------------------------
(async () => {
    check('a denied permission is reported',
        await loadWith({ secure: true, hasApi: true, permission: 'denied' }).permissionState(),
        'denied');
    check('a prompt state is reported',
        await loadWith({ secure: true, hasApi: true, permission: 'prompt' }).permissionState(),
        'prompt');
    check('a browser that will not answer is unknown, not denied',
        await loadWith({ secure: true, hasApi: true }).permissionState(),
        'unknown');

    console.log(`\n${passed}/${passed + failed} passed`);
    process.exit(failed ? 1 : 0);
})();
