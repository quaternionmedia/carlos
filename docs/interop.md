# Being Callable, and Being Able to Call

Carlos is meant to sit in a rig of applications the way a device sits in a rig
of gear: addressable by others, and able to address them.

Those are two different pieces of work, and this build has finished one of them.

| Direction | State |
| --- | --- |
| **Inbound** — other applications drive Carlos | Done. REST + JSON + OpenAPI. |
| **Transforms** — reshaping information on the way out | Done. Five, addressable, pure. |
| **Outbound** — Carlos calls other applications | **Contract built, socket absent.** Calls are *planned*, never sent. |

The last row is deliberate and is explained under *Why outbound stops short*.

## Inbound: Carlos is callable

Every route is REST over JSON, described by an OpenAPI document FastAPI
generates at `/openapi.json`. That is a protocol with many independent
implementations, which is what the QM seams record requires of anything a third
party reaches across: a client written from the OpenAPI description alone works,
and needs nothing from this repository.

| Route | Purpose |
| --- | --- |
| `GET /healthz` | Liveness |
| `GET /api/catalogue` | Every device this build knows |
| `GET /api/catalogue/categories` | Categories with counts |
| `GET /api/catalogue/devices/{id}` | One device, by its stable id |
| `GET /api/catalogue/devices/{id}/examples` | Worked examples for that device |
| `GET /api/midi` | What this build understands of MIDI, and what is reserved |
| `POST /api/midi/parse` | Raw MIDI bytes to a message |
| `POST /api/midi/route` | Bindings plus a message to the devices it lights |
| `GET /api/patch/format` | The interchange format name and version |
| `POST /api/patch/validate` | Validate a patch document |
| `GET /api/transforms` | Available transforms |
| `POST /api/transforms/{name}` | Apply one to a posted patch |
| `GET /api/peers` | Peers Carlos would call, and whether each is configured |
| `POST /api/peers/{peer}/{endpoint}/plan` | What a call would be, without making it |

The addressing scheme is the catalogue's: a device is `moog.dfam` everywhere —
in a patch document's `type`, in a route, and in whatever the peer on the other
side stores. See [catalogue.md](catalogue.md).

## Transforms

A transform is a pure function from a patch document to some other document. It
lets a peer receive the shape it wants without either side learning the other's
internals.

| Name | Gives you |
| --- | --- |
| `identity` | The patch unchanged |
| `summary` | Counts by category, maker and signal — no topology |
| `patchbay` | One readable line per cable, with panel legends resolved |
| `topology` | The routing with every parameter stripped |
| `inventory` | The distinct devices called for, by catalogue id |

`patchbay` is the one worth seeing. Given the Hapax complex example:

```
Squarp Instruments Hapax CV 1        -> Moog DFAM VCO 1 CV
Squarp Instruments Hapax GATE 1      -> Moog DFAM TRIGGER
Squarp Instruments Hapax CV 2        -> Moog Subharmonicon VCO 1 CV
Squarp Instruments Hapax MIDI A OUT  -> Moog Subharmonicon MIDI IN
Squarp Instruments Hapax MIDI B OUT  -> Nord Stage 3 MIDI IN
Squarp Instruments Hapax CLOCK OUT   -> Teenage Engineering EP-133 SYNC IN
```

The raw document says `cv_out_1` and `vco1_cv_in`. The transform resolves both
against the catalogue into what is printed on the panels — which is what a
stage-plot tool or a human wants, and what neither would want to derive itself.

`topology` is the other useful one: it strips every parameter value while
keeping the routing, so a patch can be shared as a wiring idea without sharing
the sound. What comes out is still a valid patch document.

```sh
curl -s -X POST http://127.0.0.1:8000/api/transforms/patchbay \
  -H 'Content-Type: application/json' \
  --data-binary @catalogue/examples/squarp.hapax.complex.json
```

Adding one is a decorated function in `src/interop.py`; it is listed over the
API automatically and the test suite runs every registered transform against a
real example.

## Outbound: peers, and planning

`catalogue/peers.json` declares the applications Carlos is willing to call.
Three are described today — a patch archive, a stage-plot renderer, and a gear
inventory — as stubs for real integrations.

Each endpoint states four things:

| Field | Why |
| --- | --- |
| `method`, `path` | The request |
| `side_effect` | `none`, `persists`, or `creates` |
| `transform` | Which shape this peer wants |

**`side_effect` is required and never defaulted.** It comes from the org's
monitoring-seam record, which was written after a service was found expiring the
records it was asked to display — a `GET` that wrote. Which calls change the
world is a reviewed fact stated per endpoint, not something a reader infers from
the verb.

**No addresses are committed.** Each peer names an environment variable holding
its base URL. The file is identical on every machine, and a peer nobody has
configured reports `resolved: false` with the variable to set — rather than
being omitted, because "none declared" and "none configured" are different
answers and only one of them is a problem. A test asserts no URL literal appears
in the file.

### Planning a call

```sh
curl -s -X POST http://127.0.0.1:8000/api/peers/stage-plot/render/plan \
  -H 'Content-Type: application/json' \
  --data-binary @catalogue/examples/allen-heath.qu24.complex.json
```

Returns the method, the path, the resolved URL when the environment supplies
one, the side effect, the transform, and the exact body that transform produced
— with `"sent": false` and a reason saying so in the response itself.

## Why outbound stops short

Three reasons, in order of weight.

**An open outbound POST endpoint is a request-forgery surface.** An endpoint
that takes a destination and a body and sends it is a proxy into whatever
network the server can reach. The allowlist is the mitigation, and an allowlist
is only worth something if it has been reviewed — so the allowlist ships first
and the client comes after somebody has read it.

**It needs a dependency this project does not have.** `httpx` is named by the
QM house-stack record, so adopting it is uncontroversial, but it is not
currently installed — which is also why the test suite avoids
`fastapi.testclient`. Adding it is a deliberate step, not a side effect of
building a feature.

**The contract is the part worth reviewing.** `plan()` makes the whole outbound
seam testable and inspectable with no network at all: the tests assert what
would be sent, to which URL, with which side effect, and a test asserts that no
HTTP client is imported anywhere under `src/`. When the client lands, it will be
a small function that takes a plan and sends it — and everything above it is
already covered.

## What is not here

- No authentication on any route. Carlos is a local development tool and its
  security policy says so; a deployment reachable by anyone else needs this
  answered first.
- No live outbound calls, per the above.
- No streaming or subscription — a peer wanting change notifications has
  nothing to subscribe to.
- No identity endpoint. `/healthz` returns a package constant, so two Carlos
  instances on one machine are indistinguishable over HTTP. The org's
  monitoring-seam record calls this out as a defect worth fixing before
  anything monitors this service; see `GOVERNANCE.md`.
