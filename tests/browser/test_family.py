"""A cue from the hub, drawn by a rack tab that is already open.

The hub posts to the server, never to the page. So the claim is that a tab
nobody touches redraws from the server on its own, in place: the page's own
`window` survives every cue, which a reload would not leave standing.
"""

from __future__ import annotations

import json
import random
import urllib.error
import urllib.request

from src import catalogue, family
from walkthrough.support import open_rack, until


def deliver(app, number: str, action: dict) -> tuple[int, dict]:
    """POST one cue the way the hub delivers it."""
    body = json.dumps({"cue": {"number": number, "name": f"Cue {number}",
                               "fired_at": "2026-10-10T20:00:00+00:00"},
                       "action": action}).encode()
    request = urllib.request.Request(f"{app.base}/family/cue", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as answer:
            return answer.status, json.load(answer)
    except urllib.error.HTTPError as refused:
        return refused.code, json.load(refused)


def drawn(page, number: str) -> None:
    """Wait for the tab to say it drew this cue."""
    until(page, "() => (document.querySelector('#status')?.textContent || '')"
                f".startsWith('Cue {number} from the hub')")


def following(page) -> None:
    """Wait for the tab's first look at the server, which it draws nothing for."""
    until(page, "() => typeof hub !== 'undefined' && hub.revision !== null")


def views(page) -> dict:
    return page.evaluate(
        "() => Object.fromEntries([...system.modules].map(([id, m]) => [id, m.view]))")


def faces(page, side: str, otherwise: dict) -> None:
    """Every device that shows `side` is turned to it; the rest are as `otherwise`."""
    shows = page.evaluate(
        "(side) => [...system.modules].filter(([, m]) => m.drawnSides().includes(side))"
        ".map(([id]) => id)", side)
    now = views(page)
    assert shows, f"no device here shows a {side}, so this proves nothing"
    assert {id: now[id] for id in shows} == {id: side for id in shows}
    assert {id: v for id, v in now.items() if id not in shows} ==         {id: v for id, v in otherwise.items() if id not in shows}
    assert side in page.locator("#view-indicator").inner_text().lower()


EXAMPLE = "novation.launchpad-x.complex"


def test_a_cue_lands_in_an_open_tab_without_a_reload(app, page):
    document = family.examples()[EXAMPLE]
    following(page)
    page.evaluate("() => { window.stillThisPage = true; }")

    status, answer = deliver(app, "41", {"patch": EXAMPLE})
    assert status == 200 and answer["state"]["patch"] == EXAMPLE
    drawn(page, "41")
    assert page.evaluate("() => system.name") == document["name"]
    assert page.locator(".module").count() == len(document["modules"])
    loaded = views(page)

    status, answer = deliver(app, "42", {"turn": "back"})
    assert status == 200 and answer["state"]["facing"] == "back"
    drawn(page, "42")
    faces(page, "back", otherwise=loaded)

    # Back to the side the document faces is the document's own arrangement.
    deliver(app, "43", {"turn": family.document_facing(document)})
    drawn(page, "43")
    assert views(page) == loaded

    assert page.evaluate("() => window.stillThisPage === true")
    assert page.errors == []


def test_a_cue_it_does_not_understand_leaves_the_tab_alone(app, page):
    following(page)
    before = (page.locator("#status").inner_text(), views(page))

    status, answer = deliver(app, "44", {"turn": "sideways"})
    assert status == 422 and answer["ok"] is False

    # Long enough for two looks at the server.
    page.wait_for_timeout(2500)
    assert (page.locator("#status").inner_text(), views(page)) == before
    assert page.errors == []


def test_a_tab_opened_after_a_cue_draws_the_whole_state_at_the_next(app, browser):
    deliver(app, "45", {"patch": EXAMPLE})
    late = open_rack(app, browser)
    try:
        following(late)
        # Opened after the cue: it keeps the rig it opened on.
        opening = catalogue.opening_rack()
        assert late.locator(".module").count() == len(opening["modules"])

        deliver(app, "46", {"turn": "back"})
        drawn(late, "46")
        # The next cue brings the patch the hub left as well as the turn.
        assert late.evaluate("() => system.name") == family.examples()[EXAMPLE]["name"]
        faces(late, "back", otherwise=views(late))
        assert late.errors == []
    finally:
        late.close()


# A rig held from outside, as a concert's frames arrive: a DFAM and a
# Subharmonicon from the catalogue, the clock between them, drawn as laid out.
CLOCK = {"source": {"module": "sub", "jack": "clock_out"},
         "target": {"module": "dfam", "jack": "adv_clock_in"}}


def a_frame(tempo: float, cutoff: float, *, unread: bool = False, plugged: bool = True) -> dict:
    """One frame's hold: the DFAM's tempo and cutoff where a picture read them."""
    dfam = {"level": "ok", "says": ["read: 24 of 24 controls on its front"]}
    if unread:
        dfam = {"level": "warn", "says": ["read: 23 of 24 controls on its front",
                                          "not read: noise_level, no pointer to see"],
                "controls": {"noise_level": {"level": "warn",
                                             "says": ["not read: no pointer to see"]}}}
    return {
        "patch": {"format": "carlos.patch", "version": 3, "name": "a concert",
                  "modules": [{"id": "sub", "type": "moog.subharmonicon", "view": "front",
                               "parameters": {"tempo": 80}},
                              {"id": "dfam", "type": "moog.dfam", "view": "front",
                               "parameters": {"tempo": tempo, "vcf_cutoff": cutoff}}],
                  "connections": [CLOCK], "display": {"mode": "irl"}},
        "devices": [],
        "states": {"modules": {"sub": {"level": "ok", "says": ["read: 17 of 17"]},
                               "dfam": dfam},
                   "connections": [{**CLOCK, "level": "ok" if plugged else "fault",
                                    "says": ["seen" if plugged else "declared: nothing plugged"]}]},
    }


def held(page, number: str) -> None:
    until(page, "() => (document.querySelector('#status')?.textContent || '')"
                f".startsWith('Held from Cue {number}:')")


def dfam(page, name: str) -> float:
    return page.evaluate(f"() => system.modules.get('dfam').parameters.get('{name}').value")


def test_a_held_rig_at_new_values_is_turned_where_it_stands(app, page):
    following(page)
    try:
        assert deliver(app, "50", {"hold": a_frame(40, 30)})[0] == 200
        held(page, "50")
        assert (dfam(page, "tempo"), dfam(page, "vcf_cutoff")) == (40, 30)
        page.evaluate("() => document.querySelectorAll('.module')"
                      ".forEach(m => { m.drawnAtTheFirstFrame = true; })")

        assert deliver(app, "51", {"hold": a_frame(90, 100, unread=True, plugged=False)})[0] == 200
        held(page, "51")
        # Turned, not drawn again: the devices are the elements the first frame drew.
        assert page.evaluate("() => [...document.querySelectorAll('.module')]"
                             ".every(m => m.drawnAtTheFirstFrame)")
        assert (dfam(page, "tempo"), dfam(page, "vcf_cutoff")) == (90, 100)
        tempo = page.locator('.module[data-module-id="dfam"] [data-param="tempo"]')
        assert tempo.get_attribute("aria-valuenow") == "90"

        # The frame's states are on the elements already there.
        device = page.locator('.module[data-module-id="dfam"]')
        assert device.get_attribute("data-held") == "warn"
        assert device.locator(".face.active .held-says li").all_inner_texts() == [
            "read: 23 of 24 controls on its front", "not read: noise_level, no pointer to see"]
        noise = device.locator('[data-param="noise_level"]')
        assert noise.get_attribute("data-held") == "warn"
        assert noise.get_attribute("title") == "NOISE\nnot read: no pointer to see"
        assert page.locator("path.cable.is-held-fault").count() > 0

        # The next frame reads it again: its state goes, and the lead is back.
        assert deliver(app, "52", {"hold": a_frame(90, 100)})[0] == 200
        held(page, "52")
        assert noise.get_attribute("data-held") is None
        assert noise.get_attribute("title") == "NOISE"
        assert device.get_attribute("data-held") == "ok"
        assert page.locator("path.cable.is-held-fault").count() == 0
        assert page.evaluate("() => [...document.querySelectorAll('.module')]"
                             ".every(m => m.drawnAtTheFirstFrame)")
        assert page.errors == []
    finally:
        deliver(app, "59", {"patch": EXAMPLE})


def test_another_rig_held_is_drawn_afresh(app, page):
    following(page)
    try:
        assert deliver(app, "53", {"hold": a_frame(40, 30)})[0] == 200
        held(page, "53")
        page.evaluate("() => document.querySelectorAll('.module')"
                      ".forEach(m => { m.drawnAtTheFirstFrame = true; })")
        other = a_frame(40, 30)
        other["patch"]["modules"][1]["view"] = "back"  # the DFAM turned round: another rig
        assert deliver(app, "54", {"hold": other})[0] == 200
        held(page, "54")
        assert not page.evaluate("() => [...document.querySelectorAll('.module')]"
                                 ".some(m => m.drawnAtTheFirstFrame)")
        assert page.evaluate("() => system.modules.get('dfam').view") == "back"
        assert page.errors == []
    finally:
        deliver(app, "59", {"patch": EXAMPLE})


# Many small leads that change often: the 3.5mm sockets of the same two devices,
# re-patched frame by frame as a concert's hands re-patch them.
SMALL = "3.5mm"


def small_sockets() -> tuple[list, list]:
    """Every 3.5mm output and input of the Subharmonicon and the DFAM."""
    known = catalogue.load_all()
    jacks = {"sub": known["moog.subharmonicon"].jacks, "dfam": known["moog.dfam"].jacks}
    def of(kind):
        return [(module, jack.name) for module, each in jacks.items() for jack in each
                if jack.type == kind and jack.connector == SMALL]
    return of("output"), of("input")


def a_patching(leads: list, *, number: int) -> dict:
    """A frame's hold with these leads, output first, each seen but every third,
    which is declared with nothing in it."""
    hold = a_frame(40, 30)
    connections = [{"source": {"module": a, "jack": b}, "target": {"module": c, "jack": d}}
                   for (a, b), (c, d) in leads]
    hold["patch"]["connections"] = connections
    hold["states"]["connections"] = [
        {**lead, "level": "fault" if (index + number) % 3 == 0 else "ok", "says": ["frame"]}
        for index, lead in enumerate(connections)]
    return hold


def repatched(rng: random.Random, leads: list, outputs: list, inputs: list) -> list:
    """The leads after a hand has been at them: one to three plugs moved to a
    free socket, pulled, or pushed in with a new lead. One plug to a socket."""
    leads = list(leads)
    for _ in range(rng.randint(1, 3)):
        used = {end for lead in leads for end in lead}
        free_in = [jack for jack in inputs if jack not in used]
        free_out = [jack for jack in outputs if jack not in used]
        what = rng.choice(("move", "pull", "push"))
        if what == "move" and free_in:
            at = rng.randrange(len(leads))
            leads[at] = (leads[at][0], rng.choice(free_in))
        elif what == "pull" and len(leads) > 4:
            leads.pop(rng.randrange(len(leads)))
        elif free_in and free_out:
            leads.append((rng.choice(free_out), rng.choice(free_in)))
    return leads


def drawn_as(page, leads: list, number: int) -> None:
    """The rack's cables are these leads, no more and none left over, each in
    its state, and a socket is lit exactly while a lead is in it."""
    want = {f"{a}:{b}->{c}:{d}" for (a, b), (c, d) in leads}
    rack = page.evaluate("""() => ({
        leads: system.patchBay.connections.map(({ source, target }) =>
            `${source.module.id}:${source.name}->${target.module.id}:${target.name}`),
        cables: [...new Set([...document.querySelectorAll('path.cable')]
            .map(path => path.dataset.cable))],
        faults: [...new Set([...document.querySelectorAll('path.cable.is-held-fault')]
            .map(path => path.dataset.cable))],
        lit: [...system.modules.values()].flatMap(module => [...module.jacks.values()]
            .filter(jack => jack.element?.classList.contains('connected'))
            .map(jack => `${module.id}:${jack.name}`)),
        plugged: [...system.modules.values()].flatMap(module => [...module.jacks.values()]
            .filter(jack => jack.connections.length)
            .map(jack => `${module.id}:${jack.name}`)),
    })""")
    assert sorted(rack["leads"]) == sorted(want), f"frame {number}"
    assert set(rack["cables"]) == want, f"frame {number}"
    assert set(rack["faults"]) == {
        f"{a}:{b}->{c}:{d}" for index, ((a, b), (c, d)) in enumerate(leads)
        if (index + number) % 3 == 0}, f"frame {number}"
    ends = {f"{m}:{j}" for lead in leads for (m, j) in lead}
    assert set(rack["plugged"]) == ends and set(rack["lit"]) == ends, f"frame {number}"


def test_many_small_leads_re_patched_often_are_drawn_where_they_are(app, page):
    """A rig of 3.5mm leads re-patched frame by frame: after each frame the
    rack's cables are the frame's leads, the devices are the elements the first
    frame drew, and a burst of frames faster than the tab looks ends at the last."""
    outputs, inputs = small_sockets()
    rng = random.Random(11)
    frames = [list(zip(rng.sample(outputs, 10), rng.sample(inputs, 10)))]
    for _ in range(13):
        frames.append(repatched(rng, frames[-1], outputs, inputs))
    # The frames do re-patch it: no two in a row have the same leads.
    assert all(set(one) != set(other) for one, other in zip(frames, frames[1:]))

    following(page)
    try:
        for number, leads in enumerate(frames[:8], start=60):
            assert deliver(app, str(number), {"hold": a_patching(leads, number=number)})[0] == 200
            held(page, str(number))
            drawn_as(page, leads, number)
            if number == 60:
                page.evaluate("() => document.querySelectorAll('.module')"
                              ".forEach(m => { m.drawnAtTheFirstFrame = true; })")
            assert page.evaluate("() => [...document.querySelectorAll('.module')]"
                                 ".every(m => m.drawnAtTheFirstFrame)"), f"frame {number}"

        # Six frames in less than one look: the tab draws the last of them.
        last = 60 + len(frames) - 1
        for number, leads in enumerate(frames[8:], start=68):
            assert deliver(app, str(number), {"hold": a_patching(leads, number=number)})[0] == 200
        held(page, str(last))
        drawn_as(page, frames[-1], last)
        assert page.evaluate("() => [...document.querySelectorAll('.module')]"
                             ".every(m => m.drawnAtTheFirstFrame)")
        assert page.errors == []
    finally:
        deliver(app, "79", {"patch": EXAMPLE})


def test_a_held_socket_is_ringed_in_its_state_and_turned_in_place(app, page):
    following(page)
    try:
        first = a_frame(40, 30)
        first["states"]["modules"]["dfam"]["jacks"] = {
            "adv_clock_in": {"level": "ok", "says": ["seen: a plug in it"]},
            "trigger_in": {"level": "warn", "says": ["a plug in it that no lead names"]}}
        assert deliver(app, "80", {"hold": first})[0] == 200
        held(page, "80")
        device = page.locator('.module[data-module-id="dfam"]')
        clock = device.locator('.jack[data-jack="adv_clock_in"]')
        stray = device.locator('.jack[data-jack="trigger_in"]')
        quiet = device.locator('.jack[data-jack="velocity_in"]')
        label = stray.get_attribute("aria-label")
        assert clock.get_attribute("data-held") == "ok"
        assert stray.get_attribute("data-held") == "warn"
        assert stray.get_attribute("title") == f"{label}\na plug in it that no lead names"
        assert quiet.get_attribute("data-held") is None
        # Ringed in its level, which a socket with no state is not.
        ring = "(el) => getComputedStyle(el).outlineStyle"
        assert stray.evaluate(ring) == "solid" and quiet.evaluate(ring) == "none"
        page.evaluate("() => document.querySelectorAll('.module')"
                      ".forEach(m => { m.drawnAtTheFirstFrame = true; })")

        # The next frame: the lead's plug is out, and the stray plug is gone.
        second = a_frame(40, 30, plugged=False)
        second["states"]["modules"]["dfam"]["jacks"] = {
            "adv_clock_in": {"level": "fault", "says": ["declared: nothing plugged in"]}}
        assert deliver(app, "81", {"hold": second})[0] == 200
        held(page, "81")
        assert page.evaluate("() => [...document.querySelectorAll('.module')]"
                             ".every(m => m.drawnAtTheFirstFrame)")
        assert clock.get_attribute("data-held") == "fault"
        assert clock.evaluate(ring) == "dashed"
        assert stray.get_attribute("data-held") is None
        assert stray.get_attribute("title") == label
        assert page.errors == []
    finally:
        deliver(app, "89", {"patch": EXAMPLE})


def test_a_lead_named_input_first_is_drawn_in_its_state(app, page):
    """The rack draws every cable output first; a state sent for a lead the
    patch names input first is still that cable's."""
    following(page)
    try:
        hold = a_frame(40, 30, plugged=False)
        backwards = {"source": CLOCK["target"], "target": CLOCK["source"]}
        hold["patch"]["connections"] = [backwards]
        hold["states"]["connections"] = [{**backwards, "level": "fault", "says": ["pulled"]}]
        assert deliver(app, "90", {"hold": hold})[0] == 200
        held(page, "90")
        cable = page.locator('path.cable[data-cable="sub:clock_out->dfam:adv_clock_in"]')
        assert cable.count() > 0
        assert "is-held-fault" in (cable.first.get_attribute("class") or "")
        assert page.errors == []
    finally:
        deliver(app, "99", {"patch": EXAMPLE})
