"""Being callable, and being able to call.

Two halves of one seam.

**Inbound** is done: every catalogue and patch route is REST+JSON with an
OpenAPI description FastAPI generates, which is a protocol with many
independent implementations. Another application needs nothing from this
repository to drive it.

**Outbound** is specified here and deliberately has no socket in it yet.
`plan()` returns exactly what a request to a peer *would* be — method, path,
headers, transformed body — without sending it. That makes the outbound seam
reviewable and testable before anything can reach the network, and it is the
honest state of this run: the contract is built, the client is not.

The reason for the split is the org's monitoring-seam record, which says a
committed policy carries no machine literal and that an endpoint allowlist with
a stated side effect per entry is the reviewed artifact. So `catalogue/peers.json`
names peers, their endpoints, and what each one does to the world; the base
address of any peer is resolved from the environment at run time and is never
committed. A peer nobody has configured reports as unresolved rather than being
guessed at.

Transforms are pure functions from a patch document to some other document.
They are named, listed over the API, and applied on the way out, so a peer that
wants a connection list rather than a rack gets one without either side knowing
about the other's internals.
"""

import json
import os
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

try:
    from . import catalogue, patch_format
except ImportError:  # running as a top-level module
    import catalogue
    import patch_format

PEERS_FILE = Path(__file__).resolve().parent.parent / "catalogue" / "peers.json"

# What a call does to the world on the other side. Copied from the org's
# monitoring-seam record, which requires this to be a reviewed fact per
# endpoint rather than a comment in whatever code happens to make the call.
SideEffect = Literal["none", "persists", "creates"]


class InteropError(ValueError):
    """A peer, transform or plan that cannot be built as asked."""


# ===================================================================
# TRANSFORMS
# ===================================================================

TRANSFORMS: dict[str, Callable[[patch_format.Patch], dict]] = {}
TRANSFORM_DOCS: dict[str, str] = {}


def transform(name: str, description: str):
    """Register a transform under a name the API can address."""

    def register(fn: Callable[[patch_format.Patch], dict]):
        TRANSFORMS[name] = fn
        TRANSFORM_DOCS[name] = description
        return fn

    return register


def _device_of(patch: patch_format.Patch, module_id: str):
    module = next((m for m in patch.modules if m.id == module_id), None)
    if module is None:
        return None, None
    return module, catalogue.load_all().get(module.type)


@transform("identity", "The patch unchanged. The default, and the honest one.")
def _identity(patch: patch_format.Patch) -> dict:
    return patch.model_dump()


@transform("summary", "Counts by category and signal, with no topology.")
def _summary(patch: patch_format.Patch) -> dict:
    devices = catalogue.load_all()
    categories = Counter()
    makers = Counter()
    for module in patch.modules:
        device = devices.get(module.type)
        categories[device.category if device else "unknown"] += 1
        makers[device.maker if device else "unknown"] += 1

    signals = Counter()
    for cable in patch.connections:
        _, device = _device_of(patch, cable.source.module)
        jack = device.jack(cable.source.jack) if device else None
        signals[jack.signal if jack else "unknown"] += 1

    return {
        "name": patch.name,
        "modules": len(patch.modules),
        "connections": len(patch.connections),
        "by_category": dict(categories),
        "by_maker": dict(makers),
        "by_signal": dict(signals),
    }


@transform(
    "patchbay",
    "One readable line per cable: what plugs into what, and on which side.",
)
def _patchbay(patch: patch_format.Patch) -> dict:
    lines = []
    for cable in patch.connections:
        src_module, src_device = _device_of(patch, cable.source.module)
        dst_module, dst_device = _device_of(patch, cable.target.module)
        src_jack = src_device.jack(cable.source.jack) if src_device else None
        dst_jack = dst_device.jack(cable.target.jack) if dst_device else None

        def name(module, device):
            if device is None:
                return module.type if module else "?"
            return f"{device.maker} {device.model}"

        lines.append({
            "from": {
                "device": name(src_module, src_device),
                "jack": src_jack.label if src_jack else cable.source.jack,
                "side": src_jack.side if src_jack else "unknown",
                "signal": src_jack.signal if src_jack else "unknown",
            },
            "to": {
                "device": name(dst_module, dst_device),
                "jack": dst_jack.label if dst_jack else cable.target.jack,
                "side": dst_jack.side if dst_jack else "unknown",
                "signal": dst_jack.signal if dst_jack else "unknown",
            },
            "text": (
                f"{name(src_module, src_device)} "
                f"{src_jack.label if src_jack else cable.source.jack} "
                f"-> {name(dst_module, dst_device)} "
                f"{dst_jack.label if dst_jack else cable.target.jack}"
            ),
        })
    return {"name": patch.name, "cables": lines}


@transform(
    "topology",
    "The routing with every parameter value stripped, for sharing a patch "
    "without sharing the sound.",
)
def _topology(patch: patch_format.Patch) -> dict:
    document = patch.model_dump()
    for module in document["modules"]:
        module["parameters"] = {}
    return document


@transform(
    "inventory",
    "Just the gear: the distinct devices a patch calls for, addressable by id.",
)
def _inventory(patch: patch_format.Patch) -> dict:
    devices = catalogue.load_all()
    counts = Counter(m.type for m in patch.modules)
    return {
        "name": patch.name,
        "devices": [
            {
                "id": device_id,
                "count": count,
                "maker": devices[device_id].maker if device_id in devices else None,
                "model": devices[device_id].model if device_id in devices else None,
                "known": device_id in devices,
            }
            for device_id, count in sorted(counts.items())
        ],
    }


def apply_transform(name: str, patch: patch_format.Patch) -> dict:
    if name not in TRANSFORMS:
        known = ", ".join(sorted(TRANSFORMS))
        raise InteropError(f"no transform named {name!r} (known: {known})")
    return TRANSFORMS[name](patch)


def transforms() -> list[dict[str, str]]:
    return [
        {"name": name, "description": TRANSFORM_DOCS[name]}
        for name in sorted(TRANSFORMS)
    ]


# ===================================================================
# PEERS
# ===================================================================


class PeerEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str = Field(pattern=r"^/")
    # Required, never defaulted: the whole point is that somebody stated it.
    side_effect: SideEffect
    transform: str = "identity"
    description: str = ""


class Peer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    description: str = ""
    # The environment variable holding this peer's base address. The address
    # itself is never committed - it differs per machine, and a committed one
    # publishes one workstation's Tuesday as a fact about the org.
    base_url_env: str = Field(min_length=1)
    endpoints: list[PeerEndpoint] = Field(default_factory=list)

    def base_url(self) -> str | None:
        return os.environ.get(self.base_url_env) or None

    def endpoint(self, name: str) -> PeerEndpoint | None:
        return next((e for e in self.endpoints if e.name == name), None)


# How long any one outbound call may take, in seconds.
#
# Committed policy rather than a caller's choice, per the monitoring-seam
# record: a per-call timeout is one of the things that is identical on every
# machine, so two callers cannot disagree about how long is too long. It is
# read from `peers.json` rather than hard-coded here so that the number a
# reviewer sees in the policy is the number a call would use.
DEFAULT_TIMEOUT_SECONDS = 5


@lru_cache(maxsize=1)
def peer_timeout(path: Path | None = None) -> float:
    """The committed per-call timeout."""
    source = path or PEERS_FILE
    if not source.is_file():
        return DEFAULT_TIMEOUT_SECONDS
    raw = json.loads(source.read_text(encoding="utf-8"))
    declared = raw.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if not isinstance(declared, (int, float)) or declared <= 0:
        raise InteropError(
            f"timeout_seconds must be a positive number, got {declared!r}"
        )
    return float(declared)


@lru_cache(maxsize=1)
def load_peers(path: Path | None = None) -> dict[str, Peer]:
    source = path or PEERS_FILE
    if not source.is_file():
        return {}
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InteropError(f"{source.name}: not JSON - {exc}") from exc

    peers: dict[str, Peer] = {}
    for entry in raw.get("peers", []):
        peer = Peer.model_validate(entry)
        if peer.id in peers:
            raise InteropError(f"duplicate peer id {peer.id!r}")
        peers[peer.id] = peer
    return peers


def peer_status() -> list[dict]:
    """Which peers are declared, and which of those are actually reachable.

    A declared peer with no address is reported as unresolved rather than
    omitted. Silence would read as "no peers", which is the wrong answer: the
    difference between nothing declared and nothing configured is the whole
    finding.
    """
    return [
        {
            "id": peer.id,
            "description": peer.description,
            "base_url_env": peer.base_url_env,
            "resolved": peer.base_url() is not None,
            "endpoints": [e.model_dump() for e in peer.endpoints],
        }
        for peer in load_peers().values()
    ]


# ===================================================================
# OUTBOUND: planned, not sent
# ===================================================================


def plan(peer_id: str, endpoint_name: str, patch: patch_format.Patch) -> dict:
    """Exactly what a call to a peer would be, without making it.

    Returns the method, the resolved URL when the environment supplies one, the
    transform that would be applied, and the body that transform produces. A
    caller can diff this against what it expected before anything opens a
    socket, and the tests can assert on it without a network.
    """
    peers = load_peers()
    peer = peers.get(peer_id)
    if peer is None:
        known = ", ".join(sorted(peers)) or "none declared"
        raise InteropError(f"no peer {peer_id!r} (known: {known})")

    endpoint = peer.endpoint(endpoint_name)
    if endpoint is None:
        known = ", ".join(e.name for e in peer.endpoints) or "none declared"
        raise InteropError(
            f"peer {peer_id!r} has no endpoint {endpoint_name!r} (known: {known})"
        )

    base = peer.base_url()
    body = apply_transform(endpoint.transform, patch)

    return {
        "sent": False,
        "reason": "This build plans outbound calls and does not make them.",
        "peer": peer.id,
        "endpoint": endpoint.name,
        "method": endpoint.method,
        "path": endpoint.path,
        "url": f"{base.rstrip('/')}{endpoint.path}" if base else None,
        "resolved": base is not None,
        "unresolved_hint": None if base else f"set {peer.base_url_env}",
        "side_effect": endpoint.side_effect,
        # The timeout a caller would use, reported rather than left to them.
        # A plan that omitted it would be a plan of a different call.
        "timeout_seconds": peer_timeout(),
        "transform": endpoint.transform,
        "headers": {"content-type": "application/json"},
        "body": body,
    }
