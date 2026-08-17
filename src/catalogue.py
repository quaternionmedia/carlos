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
    controls: dict[str, Placement] = Field(default_factory=dict)
    jacks: dict[str, Placement] = Field(default_factory=dict)


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
        return self

    def jack(self, name: str) -> Jack | None:
        return next((j for j in self.jacks if j.name == name), None)

    def sides(self) -> list[str]:
        """The sides this device has, in cycling order.

        Derived from the jacks rather than declared, so a device cannot claim a
        side with nothing on it. `front` is always included even when nothing is
        socketed there: every device has a face you look at, and it is where the
        knobs are drawn. A Nord Stage 3 wires entirely from the back and still
        has a front, because that is the side you play.
        """
        used = {jack.side for jack in self.jacks} | {"front"}
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
