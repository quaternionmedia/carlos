"""A cue from the hub, drawn by a rack tab that is already open.

The hub posts to the server, never to the page. So the claim is that a tab
nobody touches redraws from the server on its own, in place: the page's own
`window` survives every cue, which a reload would not leave standing.
"""

from __future__ import annotations

import json
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
                f".startsWith('Held from Cue {number}')")


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
