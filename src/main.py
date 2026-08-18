import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

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
    # Read per instance, not once when this class is defined. A bare
    # `os.environ.get(...)` as a default is evaluated at import, so the
    # environment only ever reached these if it was set before the first
    # import — which made "overridable per process" thinner than it sounded,
    # and was invisible until a test set one and watched nothing happen.
    db_path: str = Field(
        default_factory=lambda: os.environ.get("CARLOS_DB", "data/db.json"))
    template_dir: str = "templates"
    static_dir: str = "static"
    host: str = Field(
        default_factory=lambda: os.environ.get("CARLOS_HOST", "0.0.0.0"))
    port: int = Field(
        default_factory=lambda: int(os.environ.get("CARLOS_PORT", "8000")))
    # Off, and opt in with `CARLOS_RELOAD=1`.
    #
    # It does not reload here, and it is not free. Measured: uvicorn logs
    # "StatReload detected changes in 'src\main.py'. Reloading..." and goes on
    # serving the old code — an edit to this very line did not reach `/healthz`.
    # What it does deliver is a second process that owns the socket and hands it
    # to a child, so killing the server that answers leaves the parent to spawn
    # a replacement, and killing the parent leaves a listening socket with no
    # process behind it. That is the whole of this environment's
    # phantom-listener trap: three processes and an orphaned port, bought for a
    # feature that logs a lie.
    reload: bool = Field(
        default_factory=lambda: os.environ.get("CARLOS_RELOAD", "") == "1")

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


@app.get("/")
async def home():
    """The bare port lands on the splash, not in the workspace.

    Opening a rack is a thing you choose. A tool that drops you straight into
    an editable document has decided for you what you came for, and the first
    thing anyone arriving at an unfamiliar address needs is to be told what
    this is.

    A redirect rather than serving the splash here, so the splash has one
    address a reader can link to and come back to.
    """
    return RedirectResponse(url="/splash", status_code=307)


@app.get("/splash", response_class=HTMLResponse)
async def splash(request: Request):
    """What this is, and the way in.

    Every figure is measured here rather than written into the template: a
    device count typed into a page is wrong the first time somebody adds a
    device, and nothing would notice.
    """
    devices = catalogue.load_all()
    return templates.TemplateResponse(
        "splash.html",
        {
            "request": request,
            "title": settings.app_name,
            "version": settings.version,
            "device_count": len(devices),
            "category_count": len(catalogue.CATEGORIES),
            "format_name": patch_format.FORMAT_NAME,
            "format_version": patch_format.FORMAT_VERSION,
        },
    )


@app.get("/rack", response_class=HTMLResponse)
async def rack(request: Request):
    """The patch workspace itself."""
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
        # The process actually serving, which on Windows is the one thing the
        # operating system will not tell you reliably. `netstat` attributes a
        # uvicorn reload socket to the parent that bound it, and that parent is
        # gone - so the port shows a LISTENING owner that `taskkill` reports
        # does not exist, while the reloader's spawned child answers happily.
        # Asking the server which process it is beats inferring it, and it is
        # what `carlos stop` uses.
        "pid": os.getpid(),
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


def lan_address() -> str | None:
    """This machine's address on the network, or `None` if it has none.

    No packet is sent: a UDP socket has no handshake, so connecting one only
    asks the routing table which local address would be used to reach that
    destination. The destination is never contacted and need not exist, which
    is why this answers instantly offline instead of timing out.
    """
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))  # TEST-NET-1: reserved, unroutable.
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def reachable_urls(host: str, port: int) -> list[str]:
    """The addresses a browser can actually open, given what we bound.

    `0.0.0.0` is not one of them. It is a bind address meaning "every
    interface", and it is the address uvicorn prints on startup — so the one
    URL the server offers you is the one Chrome refuses with
    `ERR_ADDRESS_INVALID`. Firefox and curl are more forgiving on some
    platforms, which makes it worse rather than better: it works until the
    person it does not work for is the one you handed the link to.

    Binding every interface stays right, because it is what lets a phone or a
    tablet on the same network reach this. Only the advertisement was wrong.
    """
    if host in ("0.0.0.0", "::", ""):
        urls = [f"http://127.0.0.1:{port}/"]
        lan = lan_address()
        if lan and lan != "127.0.0.1":
            urls.append(f"http://{lan}:{port}/")
        return urls
    return [f"http://{host}:{port}/"]


def port_is_free(host: str, port: int) -> bool:
    """Whether we can take the port, asked by trying to take it.

    Not a guarantee — something can claim it between this and uvicorn's own
    bind — and it is not meant to be one. It exists so the failure has a
    sentence a person can act on instead of one ERROR line among the INFO,
    printed *after* "Application startup complete" and after this program has
    already told you the address to open. That combination is how you end up
    reading an hour-old server and believing it is yours.

    No HTTP client here, deliberately: `src/` is forbidden one, so this cannot
    ask `/healthz` who the occupant is. It says which command will.
    """
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("" if host in ("0.0.0.0", "::") else host, port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def main() -> None:
    import uvicorn

    # `flush=True` on every line, because this is the first thing anybody
    # reads and it is written to a pipe as often as to a terminal. Python
    # block-buffers a pipe, so without the flush the banner sits in the buffer
    # while the server runs — it appeared in a terminal and vanished under
    # `carlos serve`, which is exactly the audience that needs it.
    if not port_is_free(settings.host, settings.port):
        print(flush=True)
        print(f"  :{settings.port} is already taken, so this did not start.",
              flush=True)
        print("  `carlos status` names who has it, `carlos stop` frees it.",
              flush=True)
        print(flush=True)
        raise SystemExit(1)

    urls = reachable_urls(settings.host, settings.port)
    print(flush=True)
    print(f"  {settings.app_name} is at {urls[0]}", flush=True)
    for other in urls[1:]:
        print(f"  and on this network at {other}", flush=True)
    print("  (uvicorn will say 0.0.0.0 below; that is the bind, not a URL)",
          flush=True)
    print(flush=True)

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
