import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

try:
    from .db import DatabaseManager
    from . import cadence, catalogue, interop, midi, patch_format
except ImportError:
    from db import DatabaseManager
    import cadence
    import catalogue
    import interop
    import midi
    import patch_format


class Settings(BaseModel):
    """Application settings.

    The address is deliberately predictable: this is a thing you open in a
    browser, so `localhost:8000` has to mean it every time. The
    monitoring-seam record's answer to instance identity - bind port 0 and
    write a run-file - is declined for that reason in `GOVERNANCE.md`, and
    declining the mechanism is not declining the requirement. `/healthz`
    answers it the other way, by reporting which instance answered.

    Both are overridable per process without editing anything: `CARLOS_HOST`,
    `CARLOS_PORT`, `CARLOS_DB`. An environment variable rather than a committed
    value, because a committed address publishes one workstation as a fact.
    """

    app_name: str = "Carlos"
    version: str = "0.1.0"
    db_path: str = os.environ.get("CARLOS_DB", "data/db.json")
    template_dir: str = "templates"
    static_dir: str = "static"
    host: str = os.environ.get("CARLOS_HOST", "0.0.0.0")
    port: int = int(os.environ.get("CARLOS_PORT", "8000"))
    reload: bool = True

    def resolved_db_path(self) -> str:
        """Where the database actually is, not where it was asked for.

        `data/db.json` resolves against the working directory, so two clones -
        or one clone started from `src/` - have two different databases behind
        identical settings. That is the exact confusion the monitoring-seam
        record was written about, so what is reported is the resolved path.
        """
        return str(Path(self.db_path).resolve())


settings = Settings()
db_manager: DatabaseManager | None = None

# When this process started, and which process it is.
#
# Two clones answer `/healthz` identically without these, and a collector then
# attributes a measurement to whichever it happened to dial. The id is per
# process rather than per machine: two runs of the same clone, one after the
# other, are two instances and a stale answer from the first should not read as
# the second.
STARTED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")
INSTANCE = uuid.uuid4().hex[:12]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global db_manager
    db_manager = DatabaseManager(settings.db_path)
    print(f"Database initialized at {settings.db_path}")
    yield
    if db_manager:
        db_manager.close()
    print("Application shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

static_path = Path(settings.static_dir)
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

templates_path = Path(settings.template_dir)
templates_path.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=settings.template_dir)


def asset(path: str) -> str:
    """A static URL that changes when the file does.

    Without this a browser is free to keep serving the copy it already has, and
    the result is the worst kind of bug report: the server log is clean, the
    status line reports success, and nothing on screen moves - because the page
    is running last week's JavaScript against this week's markup. The mtime is
    enough; the point is only that the URL differs once the bytes do.
    """
    candidate = Path(settings.static_dir) / path.lstrip("/")
    try:
        stamp = int(candidate.stat().st_mtime)
    except OSError:
        stamp = 0
    return f"/static/{path.lstrip('/')}?v={stamp}"


templates.env.globals["asset"] = asset


@app.middleware("http")
async def no_store_static(request: Request, call_next):
    """Static assets revalidate every time.

    This is a development tool served from disk, and a stale asset costs far
    more than the request it saves. A deployment that wants caching should set
    it deliberately rather than inherit it from a default nobody chose.
    """
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the Carlos patch workspace."""
    return templates.TemplateResponse(
        "demo.html",
        {"request": request, "title": settings.app_name},
    )


@app.get("/healthz")
async def healthz(request: Request):
    """Liveness, and which instance is alive.

    The version alone was a package constant - byte identical across every
    clone and every process on the machine - so two checkouts answered
    identically and nothing obtainable over HTTP told them apart. A collector
    then attributes a measurement to whichever it happened to dial, and the one
    case that matters is a stale process from an earlier session still holding
    the port and answering for the one you meant.

    `governance/qm/records/DRAFT-monitoring-seam-and-instance-identity.md` §5:
    identity is asserted before a measurement is attributed. What a caller
    needs to do that is the three things below, and it can match them against
    the port it dialed.

    **The port is observed, not declared.** It comes off the connection this
    request arrived on rather than off `settings`, because the whole point is
    to describe the socket that answered. A process serving on a port other
    than the one it was configured with is exactly the case worth catching, and
    a handler reading its own settings would report the configured one and hide
    it.
    """
    bound = request.scope.get("server") or (None, None)

    return {
        "ok": True,
        "app": settings.app_name,
        "version": settings.version,
        # Which instance answered.
        "instance": INSTANCE,
        "started_at": STARTED_AT,
        "port": bound[1],
        "host": bound[0],
        "database": settings.resolved_db_path(),
        # A live read that cannot be aged cannot be quoted. See src/cadence.py.
        "generated_at": cadence.stamp(),
    }


@app.get("/api/cadence")
async def cadence_policy():
    """How often another application may ask, and what asking costs it.

    Two questions a peer has before it writes a loop - does calling this change
    anything, and how long is the answer good for - and neither is answerable
    from an OpenAPI description. Declared rather than guessed, because the
    guess is how a peer ends up polling a write endpoint every second.

    See `src/cadence.py`, and the monitoring-seam record behind it.
    """
    return cadence.declaration()


@app.get("/api/catalogue")
async def catalogue_index():
    """Everything another application needs to know what this build can build.

    One call, because the common case is a client wanting the whole palette. The
    per-device routes exist for a client that already knows the id it wants.
    """
    devices = catalogue.load_all()
    return {
        "categories": catalogue.categories(),
        "devices": [
            {
                "id": device.id,
                "maker": device.maker,
                "model": device.model,
                "category": device.category,
                "summary": device.summary,
                "fidelity": device.fidelity,
                "jacks": [j.model_dump(exclude_none=True) for j in device.jacks],
                "parameters": [p.model_dump(exclude_none=True) for p in device.parameters],
                # Optional: `irl` display falls back to the minimal arrangement
                # for a device nobody has laid out yet.
                "layout": (
                    device.layout.model_dump(exclude_none=True)
                    if device.layout else None
                ),
            }
            for device in devices.values()
        ],
    }


@app.get("/api/catalogue/categories")
async def catalogue_categories():
    """The device categories, with how many devices sit in each."""
    return {"categories": catalogue.categories()}


@app.get("/api/catalogue/devices/{device_id}")
async def catalogue_device(device_id: str):
    """One device, addressed by its stable id."""
    device = catalogue.load_all().get(device_id)
    if device is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": f"no device {device_id!r} in this catalogue",
                "known": sorted(catalogue.load_all()),
            },
        )
    return device.model_dump(exclude_none=True)


@app.get("/api/catalogue/devices/{device_id}/examples")
async def catalogue_device_examples(device_id: str):
    """The worked examples shipped for one device.

    `simple` is the smallest thing worth doing with it; `complex` is one that
    earns it. Both are ordinary patch documents, importable as they stand.
    """
    if device_id not in catalogue.load_all():
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": f"no device {device_id!r} in this catalogue"},
        )
    return {"device": device_id, "examples": catalogue.examples_for(device_id)}


@app.get("/api/midi")
async def midi_info():
    """What this build understands of MIDI, and what it will not touch."""
    return {
        "accepts": ["raw bytes", "parsed messages"],
        "sources": ["channel", "note", "cc", "program", "pitchbend", "transport"],
        "reserved_cc": {
            "controllers": list(midi.RAD_RESERVED_CC),
            "why": (
                "rad drives its speed axes from these. A binding may watch them; "
                "giving them a second meaning would repurpose a shared vocabulary."
            ),
        },
    }


@app.post("/api/midi/parse")
async def midi_parse(payload: dict):
    """Turn raw MIDI bytes into a message.

    Takes `{"bytes": [153, 36, 100]}`. Exposed because the parse is the fiddly
    half — running status, note-on-with-velocity-zero, 14-bit pitch bend — and a
    peer should not have to reimplement it to talk to this rack.
    """
    try:
        message = midi.parse(payload.get("bytes", []))
    except midi.MidiError as exc:
        return JSONResponse(status_code=422, content={"ok": False, "error": str(exc)})
    return {"ok": True, "message": message.model_dump(exclude_none=True)}


@app.post("/api/midi/route")
async def midi_route(payload: dict):
    """Given bindings and a message, say which devices light up.

    Stateless: the caller supplies the bindings, so this is the same function
    the browser runs, answering for whatever rack the caller has rather than
    for one this process is holding.
    """
    try:
        bindings = [midi.load_binding(b) for b in payload.get("bindings", [])]
    except midi.MidiError as exc:
        return JSONResponse(status_code=422, content={"ok": False, "error": str(exc)})

    raw = payload.get("bytes")
    try:
        message = (
            midi.parse(raw) if raw is not None
            else midi.MidiMessage.model_validate(payload.get("message", {}))
        )
    except Exception as exc:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": f"not a message: {exc}"},
        )

    activity = midi.route(bindings, message)
    return {
        "ok": True,
        "message": message.model_dump(exclude_none=True),
        "activity": [a.model_dump(exclude_none=True) for a in activity],
    }


@app.get("/api/transforms")
async def list_transforms():
    """The named transforms this build can apply to a patch on the way out."""
    return {"transforms": interop.transforms()}


@app.post("/api/transforms/{name}")
async def apply_transform(name: str, document: dict):
    """Apply one transform to a posted patch and return the result.

    Pure: nothing is stored and nothing is sent. This is the half of the seam
    another application can rely on today.
    """
    try:
        patch = patch_format.load(document)
    except patch_format.PatchFormatError as exc:
        return JSONResponse(status_code=422, content={"ok": False, "error": str(exc)})

    try:
        result = interop.apply_transform(name, patch)
    except interop.InteropError as exc:
        return JSONResponse(status_code=404, content={"ok": False, "error": str(exc)})

    return {"ok": True, "transform": name, "result": result}


@app.get("/api/peers")
async def list_peers():
    """Applications Carlos is willing to call, and whether each is configured.

    A declared peer with no address resolves to `resolved: false` rather than
    being hidden, because "none declared" and "none configured" are different
    answers and only one of them is a problem.
    """
    return {"peers": interop.peer_status()}


@app.post("/api/peers/{peer_id}/{endpoint_name}/plan")
async def plan_outbound(peer_id: str, endpoint_name: str, document: dict):
    """What a call to a peer would be, without making it.

    This build plans outbound calls and does not send them; the response says so
    in its own body. Everything a caller needs to review the request first —
    method, URL, side effect, transformed body — is here.
    """
    try:
        patch = patch_format.load(document)
    except patch_format.PatchFormatError as exc:
        return JSONResponse(status_code=422, content={"ok": False, "error": str(exc)})

    try:
        return interop.plan(peer_id, endpoint_name, patch)
    except interop.InteropError as exc:
        return JSONResponse(status_code=404, content={"ok": False, "error": str(exc)})


@app.get("/api/patch/format")
async def patch_format_info():
    """What interchange format this build reads and writes."""
    return {
        "format": patch_format.FORMAT_NAME,
        "version": patch_format.FORMAT_VERSION,
    }


@app.post("/api/patch/validate")
async def validate_patch(document: dict):
    """Check a patch document against the format, without storing it.

    Stateless on purpose: importing a patch is a browser operation, and this
    endpoint exists so a caller on any side of the seam can ask whether a
    document is readable before acting on it.
    """
    try:
        patch = patch_format.load(document)
    except patch_format.PatchFormatError as exc:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": str(exc)},
        )
    return {
        "ok": True,
        "name": patch.name,
        "modules": len(patch.modules),
        "connections": len(patch.connections),
    }


def main() -> None:
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
