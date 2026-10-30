"""The performing family's way in: a cue from the hub, held here for every tab.

ShowRunner, the family's hub, fires a cue and delivers each member its part of
the cue's `family` block. Carlos's part is one of two things a person does to
the rack by hand: load an example from the menu, or turn the rack. A third
action is a rig held from outside: another application that knows a rig sends
it whole, and carlos holds it and draws it.

    POST /family/cue    {"cue": {"number": "3", "name": "...", "fired_at": "..."},
                         "action": {"patch": "<device>.<simple|complex>"}
                                or {"turn": "<side>"}
                                or {"hold": {"patch": <carlos.patch>,
                                             "devices": [<device entry>, ...],
                                             "states": {"modules": {<id>: <state>},
                                                        "connections": [<lead state>]}}}}
                        200 {"ok": true, "state": {...}}
                        422 {"ok": false, "error": "..."}  for anything else
    GET  /family/state  200 {"member": "carlos", "cue": {...} | null,
                             "state": {"patch": name | null, "facing": side,
                                       "revision": n, "held": <the hold> | null}}

**The server holds the truth for these two actions**, which is new: the rack
has lived in the tab that draws it. An open tab reads `GET /family/state` and
draws whatever changed since it last looked, in place.

**A held rig is drawn, never judged.** What is in it and what state each part
of it is in are the sender's to know: carlos checks only that it can draw it --
the document reads as a `carlos.patch`, every type it names is a catalogue
device or one of the `devices` sent with it, each lead joins two jacks its
devices have and is a cable the rack can draw (an output into an input, or two
buses of one signal), no lead is sent twice, and each state is a level from
`LEVELS` and the lines that say it. A module's state may name some of its
controls, by parameter, and some of its jacks, by name, each with a state of its
own -- a control the sender could not read, a socket with a plug in it that no
lead names -- and a control or a jack its device does not have is refused. A
lead's state names it as the patch does, once. The devices are held for this rig
and nowhere else: they are not in the palette or the catalogue, so they keep the
vocabulary of whoever sent them. A held rig's cables are drawn as sent. Loading
an example lets go of it; a turn keeps it.

A rig held again with the same devices on the same sides is the same rig at new
values, leads and states, and an open tab turns it in place rather than drawing
it again: a rig followed through a concert is turned frame by frame, and a lead
moved from one socket to another is the one cable taken out and put in, the
devices left where they stand.

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

import re

try:
    from . import catalogue, patch_format
except ImportError:
    import catalogue
    import patch_format

MEMBER = "carlos"

# The sides a device can have, in cycling order. Mirrors `SIDE_ORDER` in
# static/models.js, and tests/test_family.py holds the two together.
SIDES = ("front", "back", "top", "bottom", "left", "right")

# How much a held state asks of a person, least first. The rack colours by it
# and reads nothing else: `says` is shown as it is sent.
LEVELS = ("none", "ok", "warn", "fault")
JACK_TYPES = ("input", "output")
# The carriers that are buses, and what a connector implies. Mirror
# `BUS_CARRIERS` and `carrierOfConnector` in static/models.js, which draws a
# cable only where these say it can.
BUS_CARRIERS = ("usb", "network")
DEVICE_ID = re.compile(r"^[a-z0-9-]+\.[a-z0-9-]+$")


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


def _text_list(value: object, where: str) -> list:
    if not isinstance(value, list) or not all(isinstance(line, str) for line in value):
        raise Refused(f"{where} says what it says as a list of lines, not {_shown(value)}")
    return value


def _state(value: object, where: str) -> dict:
    if not isinstance(value, dict) or value.get("level") not in LEVELS:
        raise Refused(f"{where} is {{level, says}} with a level of {', '.join(LEVELS)}, "
                      f"not {_shown(value)}")
    return {"level": value["level"], "says": _text_list(value.get("says", []), where)}


def _module_state(value: object, where: str, parameters: set[str], jacks: set[str]) -> dict:
    """A module's state, and its controls' states by parameter name and its
    jacks' by jack name, if any."""
    state = _state(value, where)
    for part, names, by in (("controls", parameters, "parameter"), ("jacks", jacks, "jack")):
        named = value.get(part) or {}
        if not isinstance(named, dict):
            raise Refused(f"{where}'s {part} are an object, by {by} name")
        for name in named:
            if name not in names:
                raise Refused(f"{where} names a {part[:-1]} {_shown(name)} "
                              "its device does not have")
        if named:
            state[part] = {name: _state(each, f"{where}'s {part[:-1]} {name}")
                           for name, each in named.items()}
    return state


class _End:
    """One end of a lead: a jack, as drawing a cable to it needs it."""

    def __init__(self, type_: str, signal: str, carrier: str | None, connector: str) -> None:
        self.type, self.signal = type_, signal
        self.bus = (carrier or catalogue.CARRIER_OF_CONNECTOR.get(connector, "direct")) \
            in BUS_CARRIERS


def _ends(device: object) -> dict[str, _End]:
    """Each jack of a catalogue device, or of one sent with a rig, by name."""
    if isinstance(device, dict):
        return {j["name"]: _End(j["type"], j["signal"], j.get("carrier"), j["connector"])
                for j in device["jacks"]}
    return {j.name: _End(j.type, j.signal, j.carrier, j.connector) for j in device.jacks}


def _lead(ends: tuple, where: str) -> None:
    """Refuse a lead the rack cannot draw as a cable: `Jack.canConnectTo`."""
    one, other = ends
    if one is other:
        raise Refused(f"{where} goes from a jack into itself")
    if one.bus and other.bus:
        if one.signal != other.signal:
            raise Refused(f"{where} joins a {one.signal} bus to a {other.signal} one")
    elif one.type == other.type:
        raise Refused(f"{where} joins two {one.type}s")


def _device(value: object) -> dict:
    """A device sent with a held rig, checked for what drawing it needs."""
    if not isinstance(value, dict) or not isinstance(value.get("id"), str) \
            or not DEVICE_ID.match(value["id"]):
        raise Refused(f"a held device has an id like maker.model, not {_shown(value)}")
    jacks = value.get("jacks")
    if not isinstance(jacks, list):
        raise Refused(f"{value['id']}'s jacks are a list")
    names = set()
    for jack in jacks:
        if not isinstance(jack, dict) or not isinstance(jack.get("name"), str) \
                or jack.get("type") not in JACK_TYPES \
                or jack.get("side", "front") not in SIDES \
                or not isinstance(jack.get("connector"), str) \
                or not isinstance(jack.get("signal"), str):
            raise Refused(f"{value['id']} has a jack carlos cannot draw: {_shown(jack)}")
        if jack["name"] in names:
            raise Refused(f"{value['id']} has two jacks called {jack['name']}")
        names.add(jack["name"])
    return value


def _held(value: object) -> dict:
    """A rig sent whole, checked for what drawing it needs and nothing else."""
    if not isinstance(value, dict) or set(value) - {"patch", "devices", "states"}:
        raise Refused("a hold is {patch, devices, states}")
    try:
        document = patch_format.load(value.get("patch")).model_dump()
    except patch_format.PatchFormatError as error:
        raise Refused(f"the held patch is not a carlos.patch: {error}") from None
    devices = [_device(d) for d in value.get("devices") or []]
    by_id = {d["id"]: d for d in devices}
    if len(by_id) != len(devices):
        raise Refused("two held devices share an id")
    known = catalogue.load_all()
    for module in document["modules"]:
        if module["type"] not in by_id and module["type"] not in known:
            raise Refused(f"module {module['id']} is a {module['type']}, which is neither "
                          "in the catalogue nor sent with the rig")
    modules = {m["id"] for m in document["modules"]}
    parameters = {
        m["id"]: ({p.get("name") for p in by_id[m["type"]].get("parameters") or []
                   if isinstance(p, dict)}
                  if m["type"] in by_id
                  else {p.name for p in known[m["type"]].parameters})
        for m in document["modules"]
    }
    jacks = {m["id"]: _ends(by_id.get(m["type"]) or known[m["type"]])
             for m in document["modules"]}
    # Each lead joins two jacks its devices have, as a cable the rack can draw,
    # and is sent once: the two sockets are the lead, whichever is named first.
    joined = set()
    for index, connection in enumerate(document["connections"]):
        where = f"lead {index}"
        ends = []
        for role in ("source", "target"):
            end = connection[role]
            found = jacks[end["module"]].get(end["jack"])
            if found is None:
                raise Refused(f"{where}'s {role} is {_shown(end['jack'])} on "
                              f"{end['module']}, which its device does not have")
            ends.append(found)
        _lead(tuple(ends), where)
        sockets = frozenset({(connection["source"]["module"], connection["source"]["jack"]),
                             (connection["target"]["module"], connection["target"]["jack"])})
        if sockets in joined:
            raise Refused(f"{where} joins two jacks an earlier lead already joins")
        joined.add(sockets)
    states = value.get("states") or {}
    if not isinstance(states, dict):
        raise Refused("states are {modules, connections}")
    module_states = states.get("modules") or {}
    if not isinstance(module_states, dict):
        raise Refused("states.modules is an object, by module id")
    for module_id in module_states:
        if module_id not in modules:
            raise Refused(f"states.modules names {_shown(module_id)}, not in the patch")
    lead_states = states.get("connections") or []
    if not isinstance(lead_states, list):
        raise Refused("states.connections is a list")
    leads = {(c["source"]["module"], c["source"]["jack"], c["target"]["module"],
              c["target"]["jack"]) for c in document["connections"]}
    checked_leads, stated = [], set()
    for lead in lead_states:
        try:
            key = (lead["source"]["module"], lead["source"]["jack"],
                   lead["target"]["module"], lead["target"]["jack"])
        except (TypeError, KeyError):
            raise Refused(f"a lead's state names its source and target: {_shown(lead)}") from None
        if key not in leads:
            raise Refused(f"states.connections names a lead not in the patch: {_shown(lead)}")
        if key in stated:
            raise Refused(f"states.connections names one lead twice: {_shown(lead)}")
        stated.add(key)
        checked_leads.append({"source": lead["source"], "target": lead["target"],
                              **_state(lead, "a lead's state")})
    return {
        "patch": value["patch"],
        "devices": devices,
        "states": {
            "modules": {k: _module_state(v, f"module {k}'s state", parameters[k],
                                         set(jacks[k]))
                        for k, v in module_states.items()},
            "connections": checked_leads,
        },
    }


class Rack:
    """What the hub talks to: the rack's patch and facing, the rig held from
    outside, and the last cue."""

    def __init__(self, opening: dict | None = None) -> None:
        self.cue: dict | None = None
        self.patch: str | None = None
        self.facing = document_facing(opening)
        self.held: dict | None = None
        self.revision = 0

    def state(self) -> dict:
        return {"patch": self.patch, "facing": self.facing, "revision": self.revision,
                "held": self.held}

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
                or not set(action) <= {"patch", "turn", "hold"}:
            raise Refused('carlos takes {"patch": "<device>.<kind>"}, '
                          '{"turn": "<side>"} or {"hold": {patch, devices, states}}, '
                          f'one at a time, not {_shown(action)}')
        (verb, value), = action.items()
        if verb == "hold":
            held = _held(value)

            def change():
                self.patch, self.held = None, held
                self.facing = document_facing(held["patch"])

            return change
        if verb == "patch":
            document = examples().get(value) if isinstance(value, str) else None
            if document is None:
                raise Refused(f"no example is called {_shown(value)}: an example is "
                              "named <device>.<kind>, as in moog.dfam.complex")

            def change():
                self.patch, self.facing = value, document_facing(document)
                self.held = None

            return change
        if value not in SIDES:
            raise Refused(f"a rack turns to {', '.join(SIDES)}, not {_shown(value)}")

        def change():
            self.facing = value

        return change
