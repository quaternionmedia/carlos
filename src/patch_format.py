"""The Carlos patch interchange format.

One versioned JSON document describes the whole state of a rack: its modules,
their parameter values, and the cables between them on either side of the
rack. The same document is what the browser exports, what the browser imports,
and what this module validates.

The format is deliberately plain JSON. Per the seams record, an interchange
format is a seam, and a seam is chosen so that a from-scratch reimplementation
on the other side needs nothing but the format itself.

Parameter values are stored as values, never as knob rotations. Rotation is a
rendering detail derived from the value and the parameter's range; storing both
lets them disagree, and a document that carries a contradiction has no correct
reading.
"""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

try:
    from . import midi as midi_module
except ImportError:  # running as a top-level module
    import midi as midi_module

FORMAT_NAME = "carlos.patch"

# What this build writes.
FORMAT_VERSION = 3

# What this build reads. A reader accepts a version it has an explicit upgrade
# path for and refuses one it does not. That is not "best effort": each older
# version is upgraded by a named function that knows exactly what changed, and
# anything newer or unrecognised is still refused outright, because a document
# from the future cannot be guessed at.
SUPPORTED_VERSIONS = (1, 2, 3)

# A device is not a coin. Sockets appear on whichever face the manufacturer put
# them on, and a sampler with everything along one edge is not describable as a
# front and a back. The order here is the order a device cycles through.
SIDE_ORDER = ("front", "back", "top", "bottom", "left", "right")

Side = Literal["front", "back", "top", "bottom", "left", "right"]

GroupKind = Literal["row"]

# How a rack is drawn. `minimal` is the abstract box every device shares; `irl`
# lays each device out to its own panel proportions and control positions. Both
# are abstract - `irl` is accurate, not photographic.
DisplayMode = Literal["minimal", "irl"]


class PatchFormatError(ValueError):
    """A document that cannot be read as a patch of this format version."""


class Endpoint(BaseModel):
    """One end of a cable: a named jack on a named module."""

    model_config = ConfigDict(extra="forbid")

    module: str = Field(min_length=1)
    jack: str = Field(min_length=1)


class Connection(BaseModel):
    """A cable. `source` is an output; `target` is an input.

    A cable carries no side of its own. Which side each end sits on is fixed by
    the module definition that declares the jack, so a stored copy could only
    ever disagree with it. Cables may run front-to-back; that is a rack you can
    lose track of, which is the point.
    """

    model_config = ConfigDict(extra="forbid")

    source: Endpoint
    target: Endpoint

    @model_validator(mode="after")
    def _reject_self_patch(self) -> "Connection":
        if self.source == self.target:
            raise ValueError("a cable cannot connect a jack to itself")
        return self


class ModuleState(BaseModel):
    """One module: what it is, which way it is facing, and where its knobs are.

    Devices turn independently, so `view` is per module rather than a single
    setting on the patch. A rack half turned round is a state worth keeping.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    view: Side = "front"
    # `allow_inf_nan=False` because `"NaN"` and `"Infinity"` are valid JSON
    # strings that pydantic coerces to floats, and the seam then cannot serialise
    # what it accepted. `/api/patch/validate` exists so a peer can ask "is this
    # readable before I act on it" and it answered yes to a document
    # `/api/transforms/...` chokes on: FastAPI's JSONResponse uses
    # `allow_nan=False`, so the transform raised at serialisation with the
    # validator having passed it. The refusal belongs at the point the question
    # is asked.
    parameters: dict[str, Annotated[float, Field(allow_inf_nan=False)]] = Field(
        default_factory=dict)


class Group(BaseModel):
    """Devices gathered together.

    `kind` is `row` and only `row` today. It is an enum rather than a boolean
    because rows are the first grouping and plainly not the last — a case, a
    channel strip and a stage position are all groupings a rig has — and adding
    a second kind should not be a change to the shape of the document.

    A module belongs to at most one group. Anything in no group is still in the
    rack; it is loose rather than missing.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: GroupKind = "row"
    label: str = ""
    members: list[str] = Field(default_factory=list)


class Display(BaseModel):
    """How the rack is drawn. Presentation, but presentation is state: a rig
    laid out in `irl` and reopened in `minimal` is not the rig you left."""

    model_config = ConfigDict(extra="forbid")

    mode: DisplayMode = "minimal"


class Patch(BaseModel):
    """A whole rack, as an interchange document."""

    model_config = ConfigDict(extra="forbid")

    format: str
    version: int
    name: str = "Untitled Patch"
    modules: list[ModuleState] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)
    groups: list[Group] = Field(default_factory=list)
    display: Display = Field(default_factory=Display)
    # Which MIDI belongs to which device. Bindings are rack state, not runtime:
    # the activity they produce is transient, the mapping is not.
    midi: list[midi_module.MidiBinding] = Field(default_factory=list)

    @field_validator("format")
    @classmethod
    def _known_format(cls, value: str) -> str:
        if value != FORMAT_NAME:
            raise ValueError(f"not a {FORMAT_NAME} document (got {value!r})")
        return value

    @field_validator("version")
    @classmethod
    def _readable_version(cls, value: int) -> int:
        if value not in SUPPORTED_VERSIONS:
            readable = ", ".join(str(v) for v in SUPPORTED_VERSIONS)
            raise ValueError(
                f"version {value} cannot be read by this build "
                f"(this build reads {readable} and writes {FORMAT_VERSION})"
            )
        return value

    @model_validator(mode="after")
    def _check_references(self) -> "Patch":
        seen: set[str] = set()
        for module in self.modules:
            if module.id in seen:
                raise ValueError(f"duplicate module id {module.id!r}")
            seen.add(module.id)

        for index, connection in enumerate(self.connections):
            for role, endpoint in (
                ("source", connection.source),
                ("target", connection.target),
            ):
                if endpoint.module not in seen:
                    raise ValueError(
                        f"connection {index} {role} names module "
                        f"{endpoint.module!r}, which is not in this patch"
                    )

        group_ids: set[str] = set()
        claimed: dict[str, str] = {}
        for group in self.groups:
            if group.id in group_ids:
                raise ValueError(f"duplicate group id {group.id!r}")
            group_ids.add(group.id)

            for member in group.members:
                if member not in seen:
                    raise ValueError(
                        f"group {group.id!r} names module {member!r}, "
                        "which is not in this patch"
                    )
                if member in claimed:
                    raise ValueError(
                        f"module {member!r} is in two groups "
                        f"({claimed[member]!r} and {group.id!r})"
                    )
                claimed[member] = group.id

        binding_ids: set[str] = set()
        for binding in self.midi:
            if binding.id in binding_ids:
                raise ValueError(f"duplicate midi binding id {binding.id!r}")
            binding_ids.add(binding.id)
            if binding.module not in seen:
                raise ValueError(
                    f"midi binding {binding.id!r} names module "
                    f"{binding.module!r}, which is not in this patch"
                )
        return self


def load(document: object) -> Patch:
    """Read an untrusted document, or raise `PatchFormatError` explaining why not.

    Every rejection names the document's problem rather than reporting that
    validation failed, because the reader of the message is the person holding
    a file that did not import.
    """
    if not isinstance(document, dict):
        raise PatchFormatError(
            f"a patch is a JSON object, not {type(document).__name__}"
        )
    try:
        return Patch.model_validate(upgrade(document))
    except ValidationError as exc:
        raise PatchFormatError(_explain(exc)) from exc


def upgrade(document: dict) -> dict:
    """Bring an older document up to the current version.

    Each step is named and knows exactly what changed, so an upgrade is a
    defined transformation rather than a hopeful read. A version this build does
    not recognise is left alone and refused by validation, which is where the
    refusal belongs.
    """
    if document.get("version") == 1:
        document = _v1_to_v2(document)
    if document.get("version") == 2:
        document = _v2_to_v3(document)
    return document


def _v2_to_v3(document: dict) -> dict:
    """Version 2 had no MIDI bindings and no display mode.

    Both are additive, and both default to what version 2 implied: no mapping,
    and the minimal drawing that was the only one it could do.
    """
    upgraded = dict(document)
    upgraded["version"] = 3
    upgraded.setdefault("midi", [])
    upgraded.setdefault("display", {"mode": "minimal"})
    return upgraded


def _v1_to_v2(document: dict) -> dict:
    """Version 1 had no groups, and only a front and a back.

    Both changes are additive — v1 named no grouping, and every v1 side is still
    a v2 side — so the upgrade adds the missing field and changes nothing else.
    A v1 document and its v2 upgrade describe the same rack.
    """
    upgraded = dict(document)
    upgraded["version"] = 2
    upgraded.setdefault("groups", [])
    return upgraded


def _explain(error: "ValidationError") -> str:
    """Turn a validation error into something a person can act on.

    Pydantic's own string carries model names, input echoes and a docs URL,
    none of which help someone holding a file that did not import.
    """
    problems = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"])
        message = detail["msg"].removeprefix("Value error, ")
        problems.append(f"{location}: {message}" if location else message)
    return "; ".join(problems)


def empty(name: str = "Untitled Patch") -> Patch:
    """The document an empty rack exports."""
    return Patch(format=FORMAT_NAME, version=FORMAT_VERSION, name=name)
