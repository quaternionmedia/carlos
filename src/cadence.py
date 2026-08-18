"""What a caller may expect from each endpoint, and how often to ask.

Another application on the other side of this seam has two questions before it
writes a loop: **does calling this change anything**, and **how long is an
answer good for**. Neither is answerable by reading an OpenAPI description, and
guessing at both is how a peer ends up polling a write endpoint every second.

`governance/qm/records/DRAFT-monitoring-seam-and-instance-identity.md` is the
record behind this file, and two of its clauses shape it directly.

**Which reads are writes is a reviewed fact, not a comment in a collector.**
That record exists because `qmcp`'s detail endpoint expired the request it was
asked about — reading the queue wrote to it — so a dashboard that polled detail
URLs destroyed the decisions it was displaying. `side_effect` is declared per
endpoint here for the same reason it is declared per endpoint in
`catalogue/peers.json`, and `tests/test_cadence.py` calls every endpoint
declared `none` twice and asserts the world did not move.

**A staleness budget stays in the tool.** The record is explicit that budgets
do not go in a committed policy file, so that two machines cannot disagree
about when a figure stops being quotable. That is why this is a Python module
rather than another JSON file beside `peers.json` — the allowlist and the
per-call timeout are committed policy, and the budget is not.

The endpoint list here is checked against the application's real routes in both
directions: an endpoint that exists and is not declared fails, and an endpoint
declared here that no longer exists fails. A cadence document that quietly
stopped covering half the API would be worse than none, because a caller would
read it and believe it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The same vocabulary the outbound policy uses, deliberately: a peer reading
# both should not have to learn two words for one idea.
SideEffect = Literal["none", "persists", "creates"]

# How long an answer stays quotable, in seconds. `None` means the question has
# no shelf life - a validator's verdict on a document is true whenever it is
# asked, because the document is the input.
Budget = int | None


class EndpointCadence(BaseModel):
    """What one endpoint costs a caller, and how often it is worth asking."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(pattern=r"^/")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    # Required and never defaulted. A default would be a guess wearing the
    # costume of a decision, and the guess a caller needs is the one about
    # whether their poll loop writes to somebody's database.
    side_effect: SideEffect
    # How long the answer stays quotable. None for answers with no shelf life.
    staleness_budget_seconds: Budget
    # The shortest interval worth calling at. Never below the budget, because
    # asking faster than the answer changes only costs both sides.
    min_interval_seconds: int | None
    why: str = Field(min_length=1)


# The catalogue changes when somebody commits a JSON file, which is to say on
# the cadence of a deploy rather than of a rig. A peer that mirrors it hourly
# is early rather than late.
_DEPLOY = 24 * 60 * 60

CADENCE: tuple[EndpointCadence, ...] = (
    EndpointCadence(
        path="/healthz",
        method="GET",
        side_effect="none",
        staleness_budget_seconds=0,
        min_interval_seconds=15,
        why=(
            "Liveness, and it is only ever true right now - a cached liveness "
            "answer is the thing liveness exists to avoid. It also names which "
            "instance answered: id, start time, the port actually bound and "
            "the resolved database path, so a measurement can be attributed."
        ),
    ),
    EndpointCadence(
        path="/api/catalogue",
        method="GET",
        side_effect="none",
        staleness_budget_seconds=_DEPLOY,
        min_interval_seconds=3600,
        why="Device definitions change when a file is committed, not while a rig is played.",
    ),
    EndpointCadence(
        path="/api/catalogue/categories",
        method="GET",
        side_effect="none",
        staleness_budget_seconds=_DEPLOY,
        min_interval_seconds=3600,
        why="A view of the same files the catalogue is built from.",
    ),
    EndpointCadence(
        path="/api/catalogue/devices/{device_id}",
        method="GET",
        side_effect="none",
        staleness_budget_seconds=_DEPLOY,
        min_interval_seconds=3600,
        why="One device out of the same set.",
    ),
    EndpointCadence(
        path="/api/catalogue/devices/{device_id}/examples",
        method="GET",
        side_effect="none",
        staleness_budget_seconds=_DEPLOY,
        min_interval_seconds=3600,
        why="Worked examples ship with the device that owns them.",
    ),
    EndpointCadence(
        path="/api/patch/format",
        method="GET",
        side_effect="none",
        staleness_budget_seconds=_DEPLOY,
        min_interval_seconds=3600,
        why="The format name and version this build writes. It changes on release.",
    ),
    EndpointCadence(
        path="/api/patch/validate",
        method="POST",
        side_effect="none",
        staleness_budget_seconds=None,
        min_interval_seconds=None,
        why=(
            "A verdict on the document the caller supplied, so it has no shelf "
            "life and no useful interval - ask whenever there is a document. "
            "Validation stores nothing."
        ),
    ),
    EndpointCadence(
        path="/api/transforms",
        method="GET",
        side_effect="none",
        staleness_budget_seconds=_DEPLOY,
        min_interval_seconds=3600,
        why="The named reshapings this build offers. A build-time fact.",
    ),
    EndpointCadence(
        path="/api/transforms/{name}",
        method="POST",
        side_effect="none",
        staleness_budget_seconds=None,
        min_interval_seconds=None,
        why="A reshaping of the caller's own document. Nothing is kept.",
    ),
    EndpointCadence(
        path="/api/peers",
        method="GET",
        side_effect="none",
        staleness_budget_seconds=_DEPLOY,
        min_interval_seconds=3600,
        why="The committed peer policy, plus whether this machine resolved each address.",
    ),
    EndpointCadence(
        path="/api/peers/{peer_id}/{endpoint_name}/plan",
        method="POST",
        side_effect="none",
        staleness_budget_seconds=None,
        min_interval_seconds=None,
        why=(
            "Says what a call would be without making it. Planning is free and "
            "sends nothing, which is the whole point of it existing."
        ),
    ),
    EndpointCadence(
        path="/api/midi",
        method="GET",
        side_effect="none",
        staleness_budget_seconds=_DEPLOY,
        min_interval_seconds=3600,
        why="The MIDI vocabulary this build understands. A build-time fact.",
    ),
    EndpointCadence(
        path="/api/midi/parse",
        method="POST",
        side_effect="none",
        staleness_budget_seconds=None,
        min_interval_seconds=None,
        why="Reads the caller's own bytes. Nothing is kept.",
    ),
    EndpointCadence(
        path="/api/midi/route",
        method="POST",
        side_effect="none",
        staleness_budget_seconds=None,
        min_interval_seconds=None,
        why="Answers which bindings a message would match, against the caller's own rack.",
    ),
)


def stamp() -> str:
    """When this answer was produced.

    On every response a peer might quote. The record's own words: a live read
    that has no `generated_at` cannot be stamped, budgeted or quoted, and a
    view that looks live and is an hour old is worse than one that admits its
    age, because the first stops people checking.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def declaration() -> dict:
    """The whole cadence policy, as a peer reads it."""
    return {
        "generated_at": stamp(),
        "vocabulary": {
            "side_effect": {
                "none": "a read: calling it changes nothing",
                "persists": "writes to state that already exists",
                "creates": "makes something that was not there",
            },
            "staleness_budget_seconds":
                "how long an answer stays quotable; null means it has no shelf life",
            "min_interval_seconds":
                "the shortest interval worth calling at; null means ask when you have "
                "a document to ask about",
        },
        "endpoints": [entry.model_dump() for entry in CADENCE],
    }


def for_path(path: str) -> EndpointCadence | None:
    return next((entry for entry in CADENCE if entry.path == path), None)
