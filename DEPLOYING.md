# Deploying Carlos

What this needs to run somewhere that is not a workstation, and what it does not
claim.

**Nothing here is a release.** Per `RELEASING.md`, `they`, a pull request and a
local build are all drafts. Deploying a draft is a perfectly reasonable thing to
do; describing what you deployed as a release is not.

## What it is

One process. A FastAPI application serving a browser workspace and a JSON seam,
with a TinyDB file for persistence. No queue, no worker, no cache, no second
service. `DRAFT-build-the-seam-buy-the-engines.md` is why it stays that shape.

## The image

```sh
docker build -t carlos .
docker run --rm -p 8000:8000 -v carlos-data:/app/data carlos
```

Then `http://localhost:8000`.

Two stages: the builder resolves dependencies with the same `uv` and the same
`uv.lock` the tests ran under, and the runtime carries the result and nothing
that made it. `--frozen` refuses to update the lockfile, because a build that
quietly resolves a different dependency set than the tests ran under is a build
nobody validated.

It runs as `carlos`, uid 10001. Not root — nothing here needs to write outside
its own data directory.

`.github/workflows/image.yml` builds it on every pull request and proves it:
that it answers `/healthz`, serves `/rack`, keeps the query on a redirect,
answers `HEAD`, runs as a non-root user, and that its own `HEALTHCHECK` agrees.
A `Dockerfile` nobody has run is a `Dockerfile` that does not work yet.

## Settings

All environment variables, all read per process, none of them committed — a
committed address publishes one workstation as a fact.

| Variable | Default | What it decides |
| --- | --- | --- |
| `CARLOS_HOST` | `0.0.0.0` | Which interfaces to bind. Every one, in the image: the thing reaching a container is outside it. |
| `CARLOS_PORT` | `8000` | The port. Predictable on purpose — this is a thing you open in a browser. |
| `CARLOS_DB` | `data/db.json` | The TinyDB file. `/app/data/db.json` in the image, which is the mounted volume. |
| `CARLOS_FORWARDED_ALLOW_IPS` | `127.0.0.1` | Which proxies are believed about the scheme and host in front of this. |
| `CARLOS_RELOAD` | off | Do not turn this on. See below. |

### Behind a proxy

Set `CARLOS_FORWARDED_ALLOW_IPS` to the proxy's address, or to the network it
sits on. Without it, this build believes only loopback — and Starlette's own
trailing-slash redirect is absolute, so `/rack/` would hand somebody the address
of the container rather than the address they typed.

### Do not turn reload on

`CARLOS_RELOAD=1` exists so the claim below can be checked rather than taken on
trust. It does not reload: uvicorn logs `StatReload detected changes ...
Reloading...` and goes on serving the old code. What it does deliver is a
reloader parent that owns the socket, which means killing the process that
answers leaves a parent to spawn another, and killing the parent leaves a
listening socket with nothing behind it.

## Persistence

**Nothing is persisted, and the database is not yet a database.**
`src/db.py` opens `data/db.json` at startup, declares a `patches` table, and
closes it at shutdown. No route reads or writes it — the file on a machine that
has been serving all day is zero bytes. It is a seam waiting for a feature, not
storage this build uses.

Mounting a volume at `/app/data` therefore preserves nothing today. Do it
anyway if you like: it costs nothing and it is where persistence will land.

**Patch persistence is not built.** Export and import are the current answer,
and they are files a person handles. `/healthz` reports the resolved database
path, which is how two clones are told apart rather than a claim that either
holds anything.

## Health

`GET /healthz` — or `HEAD`, which is what most probes actually send.

```json
{"ok": true, "app": "Carlos", "version": "0.0.0",
 "instance": "8e03b9a7923b", "pid": 16108, "started_at": "...",
 "port": 8000, "host": "0.0.0.0", "database": "/app/data/db.json",
 "generated_at": "..."}
```

`instance` and `started_at` are the useful pair: if the id is not the one you
just started, you are reading a process you thought you had replaced. That is
the fastest way to catch a stale container, and it was written after several
sessions lost to exactly that on a workstation.

The port is observed from the connection rather than read from settings, so it
reports the port that answered and not the port somebody configured.

## What another application should know

`GET /api/cadence` declares what every endpoint costs to call and how often it
is worth asking. Nothing in the seam is a subscription, a webhook or a socket;
a peer polls, and the cadence document is where the polite interval is written
down rather than guessed.

Outbound calls are **planned and never sent**. `/api/peers/.../plan` returns the
request this build would make, for a caller to make or not.

## Scaling, and why not to yet

One process. The database is a file with no locking story across processes, so
a second replica pointed at the same volume is two writers and no answer for
what happens when they disagree.

If this ever needs more than one, the database is the thing to change first, and
that is a decision record rather than a deployment flag.
