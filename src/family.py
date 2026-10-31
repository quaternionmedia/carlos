"""The performing family's way in: a cue from the hub, held here for every tab.

ShowRunner, the family's hub, fires a cue and delivers each member its part of
the cue's `family` block. Carlos's part is one of two things a person does to
the rack by hand: load an example from the menu, or turn the rack.

    POST /family/cue    {"cue": {"number": "3", "name": "...", "fired_at": "..."},
                         "action": {"patch": "<device>.<simple|complex>"}
                                or {"turn": "<side>"}}
                        200 {"ok": true, "state": {...}}
                        422 {"ok": false, "error": "..."}  for anything else
    GET  /family/state  200 {"member": "carlos", "cue": {...} | null,
                             "state": {"patch": name | null, "facing": side,
                                       "revision": n}}

**The server holds the truth for these two actions**, which is new: the rack
has lived in the tab that draws it. An open tab reads `GET /family/state` and
draws whatever changed since it last looked, in place.

`patch` names an example by its file, `catalogue/examples/<device>.<kind>.json`,
which is the device and the kind the menu loads it by. Loading one faces the
rack the way its document does. `turn` faces the rack to a side: every device
that shows that side turns to it, and one that does not keeps the side its
document gave it. Turning back to the side the document faces restores the
document's own arrangement. So what a tab draws is a function of the state:
a tab that missed a cue draws, at the next one, the same rack as a tab that
saw them all.
"""

from __future__ import annotations

try:
    from . import catalogue
except ImportError:
    import catalogue

MEMBER = "carlos"

# The sides a device can have, in cycling order. Mirrors `SIDE_ORDER` in
# static/models.js, and tests/test_family.py holds the two together.
SIDES = ("front", "back", "top", "bottom", "left", "right")


def examples() -> dict[str, dict]:
    """Every shipped example, by the name a cue gives it: `<device>.<kind>`."""
    return {
        f"{device_id}.{kind}": document
        for device_id in sorted(catalogue.load_all())
        for kind, document in catalogue.examples_for(device_id).items()
    }


def document_facing(document: dict | None) -> str:
    """The side a patch document mostly faces.

    The commonest `view` among its modules, the first one seen breaking a tie,
    and `front` for a document with none - the rule `commonestSide()` applies
    to the rack in static/models.js, applied to the document instead, so the
    tab and this module answer it from the same input.
    """
    counts: dict[str, int] = {}
    for module in (document or {}).get("modules") or []:
        side = module.get("view") or "front"
        counts[side] = counts.get(side, 0) + 1
    best, most = "front", -1
    for side, count in counts.items():
        if count > most:
            best, most = side, count
    return best


class Refused(ValueError):
    """A body this member does not understand: answered with 422, never raised."""


def _shown(value: object) -> str:
    text = repr(value)
    return text if len(text) <= 80 else text[:77] + "..."


class Rack:
    """What the hub talks to: the rack's patch and facing, and the last cue."""

    def __init__(self, opening: dict | None = None) -> None:
        self.cue: dict | None = None
        self.patch: str | None = None
        self.facing = document_facing(opening)
        self.revision = 0

    def state(self) -> dict:
        return {"patch": self.patch, "facing": self.facing, "revision": self.revision}

    def snapshot(self) -> dict:
        return {"member": MEMBER, "cue": self.cue, "state": self.state()}

    def receive(self, body: object) -> tuple[int, dict]:
        """Act on a cue's body. A refused cue changes nothing, its record included."""
        try:
            change = self._understood(body)
        except Refused as refusal:
            return 422, {"ok": False, "error": str(refusal)}
        change()
        self.revision += 1
        self.cue = body["cue"]
        return 200, {"ok": True, "state": self.state()}

    def _understood(self, body: object):
        if not isinstance(body, dict):
            raise Refused("the body must be a JSON object with a cue and an action")
        if not isinstance(body.get("cue"), dict):
            raise Refused("cue must be an object: {number, name, fired_at}")
        action = body.get("action")
        if not isinstance(action, dict) or len(action) != 1 \
                or not set(action) <= {"patch", "turn"}:
            raise Refused('carlos takes {"patch": "<device>.<kind>"} or '
                          f'{{"turn": "<side>"}}, one at a time, not {_shown(action)}')
        (verb, value), = action.items()
        if verb == "patch":
            document = examples().get(value) if isinstance(value, str) else None
            if document is None:
                raise Refused(f"no example is called {_shown(value)}: an example is "
                              "named <device>.<kind>, as in moog.dfam.complex")

            def change():
                self.patch, self.facing = value, document_facing(document)

            return change
        if value not in SIDES:
            raise Refused(f"a rack turns to {', '.join(SIDES)}, not {_shown(value)}")

        def change():
            self.facing = value

        return change
