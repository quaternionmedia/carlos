"""The device catalogue.

A catalogue entry describes one real piece of gear: what it is, what sockets it
has, and which of those sit on the front and which on the back. Entries are data
files under `catalogue/devices/`, not code, so adding a device is a pull request
containing one JSON file and no Python.

The catalogue is the single source of module definitions. The browser builds its
palette from `/api/catalogue`, so a device added here appears in the rack with
no frontend change — which is the whole reason the definitions do not live in
`static/models.js`.

Every entry is addressable by a stable id of the form `<maker>.<model>`, in
lower kebab: `moog.dfam`, `allen-heath.qu24`. That id is what another
application uses to refer to a device across the seam, so it is treated as
permanent once published.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

CATALOGUE_ROOT = Path(__file__).resolve().parent.parent / "catalogue"

# Sides a device can have. A device declares only the ones it uses: a Scarlett
# has a front and a back, a K.O. II has everything along its top edge, and a
# rack-mounted mixer has a surface and a rear. Order is the order a device
# cycles through when it is turned.
SIDE_ORDER = ("front", "back", "top", "bottom", "left", "right")

Side = Literal["front", "back", "top", "bottom", "left", "right"]
JackType = Literal["input", "output"]

# What a socket carries. Kept deliberately coarse: this is a sketching tool, and
# a taxonomy fine enough to be correct about every device would be too fine to
# be useful about any of them.
Signal = Literal[
    "audio",  # line, mic or instrument level analogue audio
    "cv",     # control voltage
    "gate",   # gates and triggers
    "clock",  # analogue clock and sync pulses
    "midi",   # MIDI, on DIN or TRS
    "usb",    # USB of any shape, host or device
    "network",  # ethernet-carried protocols, including dSNAKE and Dante
    "digital",  # AES, S/PDIF, ADAT
    "power",
]

CATEGORIES: dict[str, str] = {
    "mixer": "Consoles that sum, route and process many inputs",
    "audio-interface": "Boxes that get audio in and out of a computer",
    "sequencer": "Devices whose output is time: notes, gates and clock",
    "keyboard": "Playable instruments with a keybed",
    "sampler": "Devices built around recording and replaying audio",
    "semi-modular": "Fixed-architecture synths with a patch bay over the top",
    "eurorack": "Individual modules in a Eurorack case",
    "controller": "Surfaces that play and steer other gear, and make no sound",
    "drum-machine": "Devices built around percussion voices and their sequencing",
}


class CatalogueError(ValueError):
    """A catalogue file that cannot be read as a device."""


class Jack(BaseModel):
    """One socket on a device."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    type: JackType
    signal: Signal
    side: Side = "front"
    connector: str | None = None
    note: str | None = None


class Parameter(BaseModel):
    """One continuous control on a device."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    min: float = 0
    max: float = 127
    default: float | None = None
    unit: str | None = None

    @field_validator("max")
    @classmethod
    def _range_is_real(cls, value: float, info) -> float:
        minimum = info.data.get("min", 0)
        if value <= minimum:
            raise ValueError(f"max {value} is not above min {minimum}")
        return value


# What a parameter-backed control looks like on the panel. A fader is not a
# knob turned sideways, and drawing one as the other is the difference between a
# recognisable device and a grid of circles.
ControlKind = Literal[
    "knob",     # a rotary you turn
    "fader",    # a linear travel, long axis vertical unless said otherwise
    "encoder",  # a rotary with no end stops, drawn with a detent ring
    "switch",   # a two- or three-position throw
    "drawbar",  # an organ drawbar: a fader with a stepped grip
]

# What else is on a panel. None of these carry a value - they are what makes a
# device recognisable rather than what makes it playable in this app. A device
# is not usefully drawn without them: a Stage 3 with its knobs and sockets and
# no keybed is not a Stage 3.
FeatureKind = Literal[
    "keybed",   # a piano keyboard; `keys` long, starting at `from_note`
    "pads",     # a grid of `rows` x `cols` performance pads
    "buttons",  # a grid of `rows` x `cols` small buttons
    "screen",   # a display, showing `text` if it has anything to say
    "wheel",    # pitch or modulation, upright
    "grille",   # a speaker
    "vent",     # a slot or a fan
    "logo",     # the maker's mark, drawn as `text`
    "label",    # a panel legend or a section name
    "plate",    # a section boundary: the thing that makes a panel read as parts
]


# What a screen reads. Every one of these is derived from state the app already
# holds, and none of it is stored: a screen showing a remembered message would
# be a second copy of something, disagreeing with the first the moment anything
# moved. Same reasoning as knob rotation.
ScreenSource = Literal[
    "device",       # the maker and model, which is what an idle panel shows
    "last-event",   # the most recent thing that happened on this device
    "parameter",    # the control being moved, and its value
    "patch",        # the name of the rack being worked on
    "transport",    # tempo and running state, for devices that have them
    "static",       # only ever its own `text`
]

# What pressing a cell sends. A grid on a controller sends MIDI down the same
# path a real port uses, so a device bound to that note lights up - which is the
# difference between a pad that looks like a pad and one that is one.
EmitKind = Literal[
    "midi-note",  # `note` for the first cell, +1 across the grid
    "midi-cc",    # `controller` for the first cell, +1 across the grid
    "event",      # a named device event: no MIDI, but the panel still reacts
]


class Box(BaseModel):
    """A device's real outside dimensions, in millimetres.

    One measurement set, six faces derived from it: front and back are width by
    height, top and bottom are width by depth, left and right are depth by
    height. Declaring the box rather than a per-face aspect is what makes the
    sides agree with each other - two aspects typed by hand can contradict, and
    a device whose top is wider than its front is not a shape.
    """

    model_config = ConfigDict(extra="forbid")

    width: float = Field(gt=0, le=5000)
    height: float = Field(gt=0, le=3000)
    depth: float = Field(gt=0, le=3000)

    def aspect(self, side: str) -> float:
        """Width over height of one face, as that face is seen."""
        if side in ("front", "back"):
            return self.width / self.height
        if side in ("top", "bottom"):
            return self.width / self.depth
        return self.depth / self.height  # left, right


class Feature(BaseModel):
    """One thing on a panel that is not a socket and carries no value.

    Placed by its centre like everything else, but sized too: a keybed and a
    screen are areas, not points, and a vocabulary that could only place points
    would draw every device as scattered dots.
    """

    model_config = ConfigDict(extra="forbid")

    kind: FeatureKind
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)
    side: Side = "front"
    # A keybed's length, and where it starts. 88 keys from A, 61 from C.
    keys: int | None = Field(default=None, ge=1, le=128)
    from_note: Literal["C", "E", "F", "A"] | None = None
    # A grid's shape.
    rows: int | None = Field(default=None, ge=1, le=32)
    cols: int | None = Field(default=None, ge=1, le=32)
    # What a screen shows, or a logo or label reads.
    text: str | None = None
    label: str | None = None
    # A screen reads one source. Required for `screen` and meaningless
    # elsewhere, which the validator enforces rather than trusting.
    source: ScreenSource | None = None
    # What a press sends, for the grids that are controls rather than shape.
    emits: EmitKind | None = None
    channel: int | None = Field(default=None, ge=1, le=16)
    note: int | None = Field(default=None, ge=0, le=127)
    controller: int | None = Field(default=None, ge=0, le=127)

    @model_validator(mode="after")
    def _kind_carries_what_it_needs(self) -> "Feature":
        if self.kind == "keybed" and not self.keys:
            raise ValueError("a keybed needs `keys`")
        if self.kind in ("pads", "buttons") and not (self.rows and self.cols):
            raise ValueError(f"a {self.kind} grid needs `rows` and `cols`")
        if self.kind == "screen" and self.source is None:
            raise ValueError(
                "a screen needs a `source` - what it shows. Use `static` for one "
                "that only ever shows its own `text`"
            )
        if self.source == "static" and not self.text:
            raise ValueError("a static screen needs the `text` it shows")
        if self.emits in ("midi-note", "midi-cc") and self.channel is None:
            raise ValueError(f"{self.emits} needs the `channel` it sends on")
        if self.emits == "midi-note" and self.note is None:
            raise ValueError("midi-note needs the `note` its first cell sends")
        if self.emits == "midi-cc" and self.controller is None:
            raise ValueError("midi-cc needs the `controller` its first cell sends")
        if self.kind == "logo" and not self.text:
            raise ValueError("a logo needs the `text` it reads")
        return self


class Placement(BaseModel):
    """Where one control or socket sits on a face.

    Coordinates are fractions of the panel, 0..1, origin top-left. Fractions
    rather than millimetres because the drawing is abstract: what has to be
    right is the arrangement — which knob is above which socket, what is in a
    row together — not the absolute size of anything.
    """

    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    side: Side = "front"
    size: float = Field(default=1.0, gt=0, le=4)
    kind: ControlKind = "knob"
    # Travel direction, for the kinds that have one. A mixer's channel faders
    # run up and down; a crossfader runs across.
    orient: Literal["vertical", "horizontal"] = "vertical"
    # Long axis as a fraction of the panel, for the kinds that have length.
    # `size` scales the grip; this is how far it slides.
    length: float | None = Field(default=None, gt=0, le=1)


class Layout(BaseModel):
    """A device's panel, for `irl` display.

    Optional throughout. A device with no layout still draws in `irl` — it falls
    back to the same arrangement `minimal` uses — because a catalogue that
    refused a device until someone had measured its front panel would collect
    fewer devices, and the entry is the valuable part.
    """

    model_config = ConfigDict(extra="forbid")

    # Panel proportion, width relative to height. A Eurorack module is tall and
    # narrow; a mixer is wide and shallow. Getting this one number right is most
    # of what makes a rack recognisable at a glance.
    aspect: float = Field(default=1.0, gt=0, le=20)
    # The side you look at first. `front` for almost everything, because almost
    # everything is a box you face. A stage piano is not: its controls and its
    # keybed are on its top, its front is the thin blank lip below the keys, and
    # opening it facing that would show a device with nothing on it. Naming the
    # face is one field; deriving it from whichever side carries the most would
    # silently reface every device nobody has laid out yet.
    face: Side = "front"
    # Real millimetres. When present every face's proportion is derived from it
    # and `aspect` is ignored, because a box knows about six faces and a single
    # number only ever described one of them.
    box: Box | None = None
    controls: dict[str, Placement] = Field(default_factory=dict)
    jacks: dict[str, Placement] = Field(default_factory=dict)
    # Everything on the panel that is not a socket and carries no value.
    features: list[Feature] = Field(default_factory=list)

    def aspect_of(self, side: str) -> float:
        """The proportion of one face. The box if there is one, else `aspect`.

        `aspect` describes the front and was only ever applied to every side
        because nothing else was available; a device with a box gets its top
        drawn as a top.
        """
        return self.box.aspect(side) if self.box else self.aspect

    def sides_used(self) -> set[str]:
        """Sides this layout puts something on."""
        placed = list(self.controls.values()) + list(self.jacks.values())
        return {p.side for p in placed} | {f.side for f in self.features}


class Device(BaseModel):
    """One catalogue entry."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+\.[a-z0-9-]+$")
    maker: str = Field(min_length=1)
    model: str = Field(min_length=1)
    category: str
    summary: str = Field(min_length=1)
    # Where the description stops and the sketch begins. Real devices have more
    # sockets and far more parameters than an entry lists; an entry names the
    # ones worth patching in a sketch.
    fidelity: Literal["sketch", "detailed"] = "sketch"
    jacks: list[Jack] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    layout: Layout | None = None

    @field_validator("category")
    @classmethod
    def _known_category(cls, value: str) -> str:
        if value not in CATEGORIES:
            known = ", ".join(sorted(CATEGORIES))
            raise ValueError(f"unknown category {value!r} (known: {known})")
        return value

    @field_validator("jacks")
    @classmethod
    def _unique_jack_names(cls, jacks: list[Jack]) -> list[Jack]:
        seen: set[str] = set()
        for jack in jacks:
            if jack.name in seen:
                raise ValueError(f"duplicate jack name {jack.name!r}")
            seen.add(jack.name)
        return jacks

    @field_validator("parameters")
    @classmethod
    def _unique_parameter_names(cls, parameters: list[Parameter]) -> list[Parameter]:
        seen: set[str] = set()
        for parameter in parameters:
            if parameter.name in seen:
                raise ValueError(f"duplicate parameter name {parameter.name!r}")
            seen.add(parameter.name)
        return parameters

    @model_validator(mode="after")
    def _layout_places_real_things(self) -> "Device":
        if self.layout is None:
            return self

        jack_names = {j.name for j in self.jacks}
        for name, placement in self.layout.jacks.items():
            if name not in jack_names:
                raise ValueError(f"layout places jack {name!r}, which this device has no")
            declared = self.jack(name)
            if declared and placement.side != declared.side:
                raise ValueError(
                    f"layout puts jack {name!r} on the {placement.side} "
                    f"but it is declared on the {declared.side}"
                )

        parameter_names = {p.name for p in self.parameters}
        for name in self.layout.controls:
            if name not in parameter_names:
                raise ValueError(
                    f"layout places control {name!r}, which this device has no"
                )

        if self.layout.face not in self.sides():
            raise ValueError(
                f"layout faces the {self.layout.face}, which this device has no "
                f"(it has {', '.join(self.sides())})"
            )

        # A feature is checked for fitting on the face it claims. A keybed
        # centred at x=0.5 that is 1.2 panels wide is a typo, and one that runs
        # off the edge draws as a device that is not the shape it says it is.
        for feature in self.layout.features:
            for axis, centre, extent in (("x", feature.x, feature.w),
                                         ("y", feature.y, feature.h)):
                if centre - extent / 2 < -0.001 or centre + extent / 2 > 1.001:
                    raise ValueError(
                        f"{feature.kind} at {axis}={centre} is {extent} wide "
                        f"and runs off the {feature.side}"
                    )
        return self

    def jack(self, name: str) -> Jack | None:
        return next((j for j in self.jacks if j.name == name), None)

    def sides(self) -> list[str]:
        """The sides this device has, in cycling order.

        Derived from what is on them rather than declared, so a device cannot
        claim a side with nothing on it. A side counts if it carries a socket
        or anything the layout places there - a keybed, a screen, a fader.
        Sockets alone was the older rule and it was too narrow: a K.O. II's
        pads and screen are the front of a K.O. II, and under a jacks-only rule
        a device could carry a fully drawn face that officially did not exist.

        `front` is always included even when nothing is on it: every device has
        a face you look at.
        """
        used = {jack.side for jack in self.jacks} | {"front"}
        if self.layout:
            used |= self.layout.sides_used()
        return [side for side in SIDE_ORDER if side in used]


def load_device(path: Path) -> Device:
    """Read one catalogue file, or say why it is not one."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogueError(f"{path.name}: not JSON - {exc}") from exc

    try:
        device = Device.model_validate(raw)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in d['loc'])}: "
            f"{d['msg'].removeprefix('Value error, ')}"
            for d in exc.errors()
        )
        raise CatalogueError(f"{path.name}: {problems}") from exc

    # The filename is part of the addressing scheme, so a file whose name and id
    # disagree is ambiguous rather than merely untidy.
    if path.stem != device.id:
        raise CatalogueError(
            f"{path.name}: declares id {device.id!r}, so the file should be "
            f"named {device.id}.json"
        )
    return device


@lru_cache(maxsize=1)
def load_all(root: Path | None = None) -> dict[str, Device]:
    """Every device in the catalogue, keyed by id.

    Cached: the catalogue is read once per process. Call `load_all.cache_clear()`
    after editing a file in a running server, which is what the reload does for
    free in development.
    """
    directory = (root or CATALOGUE_ROOT) / "devices"
    if not directory.is_dir():
        return {}

    devices: dict[str, Device] = {}
    for path in sorted(directory.glob("*.json")):
        device = load_device(path)
        if device.id in devices:
            raise CatalogueError(f"{path.name}: id {device.id!r} is already used")
        devices[device.id] = device
    return devices


EXAMPLE_KINDS = ("simple", "complex")


def examples_for(device_id: str, root: Path | None = None) -> dict[str, dict]:
    """The worked examples shipped for one device.

    Two per device by convention — `simple` is the smallest thing worth doing
    with it, `complex` is one that earns the device. Each is an ordinary
    `carlos.patch` document, so an example is a file a reader can import and
    take apart rather than a screenshot of one.

    A device with no examples returns an empty mapping. That is a gap worth
    filling rather than an error: the catalogue should accept a device the
    moment someone describes it, and not hold it back for want of a demo.
    """
    directory = (root or CATALOGUE_ROOT) / "examples"
    found: dict[str, dict] = {}
    for kind in EXAMPLE_KINDS:
        path = directory / f"{device_id}.{kind}.json"
        if not path.is_file():
            continue
        try:
            found[kind] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CatalogueError(f"{path.name}: not JSON - {exc}") from exc
    return found


def categories() -> list[dict[str, object]]:
    """The category list, with how many devices sit in each."""
    devices = load_all().values()
    return [
        {
            "id": key,
            "description": description,
            "devices": sum(1 for d in devices if d.category == key),
        }
        for key, description in sorted(CATEGORIES.items())
    ]
