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
