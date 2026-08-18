from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

try:
    from .db import DatabaseManager
    from . import catalogue, interop, midi, patch_format
except ImportError:
    from db import DatabaseManager
    import catalogue
    import interop
    import midi
    import patch_format


class Settings(BaseModel):
    """Application settings."""

    app_name: str = "Carlos"
    version: str = "0.1.0"
    db_path: str = "data/db.json"
    template_dir: str = "templates"
    static_dir: str = "static"
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True


settings = Settings()
db_manager: DatabaseManager | None = None


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
async def healthz():
    return {"ok": True, "app": settings.app_name, "version": settings.version}


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
