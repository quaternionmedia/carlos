# The Carlos Patch Format

**Format name:** `carlos.patch`
**This build writes:** `2`
**This build reads:** `1`, `2`

One JSON document describes the entire state of a rack: which modules are in it,
which way each one is facing, where its knobs are, and which cables run between
them — including the ones running round the back. It is what the browser
exports, what the browser imports, and what `src/patch_format.py` validates.

## Why a format and not just a save button

An interchange format is a seam. The test that matters is the one the QM seams
record states: *could this be replaced by a from-scratch implementation of the
format alone, without changes on our side of the seam?* Plain JSON with a
declared name and version passes — anything that can write JSON can write a
patch, and nothing needs Carlos's source to do it.

That is why the format is not pickled Python, not a TinyDB table dump, and not
"whatever `JSON.stringify` happened to produce this build". Those are all
readable by exactly one implementation.

## The document

```json
{
  "format": "carlos.patch",
  "version": 2,
  "name": "Evening Drone",
  "modules": [
    {
      "id": "module_1755432000000_a1b2c",
      "type": "moog.dfam",
      "view": "back",
      "parameters": { "frequency": 64.0, "fine": 71.5 }
    },
    {
      "id": "module_1755432000001_d3e4f",
      "type": "focusrite.scarlett-2i2",
      "view": "front",
      "parameters": { "cutoff": 40.0, "resonance": 90.0 }
    }
  ],
  "connections": [
    {
      "source": { "module": "module_1755432000000_a1b2c", "jack": "audio_out" },
      "target": { "module": "module_1755432000001_d3e4f", "jack": "audio_in" }
    }
  ],
  "groups": [
    {
      "id": "row-1",
      "kind": "row",
      "label": "Instruments",
      "members": ["module_1755432000000_a1b2c"]
    }
  ]
}
```

That example is a DFAM turned to face its rear, patched into an interface
still facing front, with the DFAM gathered into a row. It is a legal patch.

### Top level

| Field | Type | Rule |
| --- | --- | --- |
| `format` | string | Exactly `carlos.patch`. A reader refuses anything else. |
| `version` | integer | `3` when written by this build; `1` and `2` are read and upgraded. See *Versioning*. |
| `name` | string | Human label. Defaults to `Untitled Patch`. |
| `modules` | array | May be empty — an empty rack is a valid patch. |
| `connections` | array | May be empty. |
| `groups` | array | Groupings. May be empty. |

Unknown top-level fields are **rejected**, not ignored. A document carrying a
field this version does not define is more likely a newer document than a
harmless one, and silently dropping it would import a patch that is not the
patch the file describes.

### `modules[]`

| Field | Type | Rule |
| --- | --- | --- |
| `id` | string | Unique within the document. Connections reference it. |
| `type` | string | A catalogue device id, e.g. `moog.dfam`. See [catalogue.md](catalogue.md). |
| `view` | string | Which side is showing: `front`, `back`, `top`, `bottom`, `left`, `right`. Defaults to `front`. |
| `parameters` | object | Parameter name → **value**. |

**Parameter values are values, never knob rotations.** Rotation is derived from
the value and the parameter's range at render time. Storing both would let them
disagree, and a document carrying a contradiction has no correct reading.

A parameter absent from the object keeps its module's default. A value outside
the parameter's range is clamped on import rather than refused, because a knob
that cannot go that far is a display fact, not a corrupt file.

**`view` is per device, not per patch.** Devices turn independently, so a rack
half turned round is an ordinary state and the document has to be able to say
so. There is no rack-level view field: the rack's apparent facing is just what
its devices happen to be doing.

**Devices are n-sided, and do not share a side list.** Which sides a device has
is derived from where its jacks are, so a K.O. II has a face and a top edge and
no back at all, while a DFAM has a front and a back. `front` is always present,
because every device has a face you look at and it is where the knobs are
drawn. A `view` naming a side the device does not have is coerced to its first
side rather than stored.

### `groups[]`

| Field | Type | Rule |
| --- | --- | --- |
| `id` | string | Unique within the document. |
| `kind` | string | `row`. The only kind today. |
| `label` | string | What to call it. |
| `members` | array | Module ids. May be empty. |

A module belongs to **at most one** group, and a document putting one in two is
refused. A module in no group is *loose* — still in the rack, just not gathered
with anything. Loose is a state, not an error.

`kind` is an enum rather than a boolean because rows are plainly not the last
grouping a rig wants — a case, a channel strip and a stage position are all
groupings — and adding a second kind should not reshape the document.

Deleting a group never deletes devices: a grouping is a way of reading a rack,
not a container the gear lives inside.

### `connections[]`

| Field | Type | Rule |
| --- | --- | --- |
| `source` | object | `{module, jack}` — always the **output** end. |
| `target` | object | `{module, jack}` — always the **input** end. |

Direction is normalized on export, so a reader never has to work out which end
is which. Both endpoints must name modules present in the same document.

**A cable carries no side of its own.** Which side each end sits on is fixed by
the module definition that declares the jack — `sync_in` is a rear jack on every
VCO there will ever be — so a `side` field on the cable could only ever be a
second copy that disagrees with the first. A document that supplies one is
refused rather than half-honoured, on the same reasoning that keeps knob
rotations out of `parameters`.

**Cables may run front to back.** A lead from a front panel round to a rear
header is a legal patch, and losing track of one is part of the instrument. Only
two rules hold: opposite types, and not a jack into itself.

## Versioning

`version` is a single integer. A reader accepts a version it has an **explicit
upgrade path for**, and refuses one it does not.

That is not a "best effort" read. Each older version is brought forward by a
named function that knows exactly what changed — `_v1_to_v2` in
`src/patch_format.py`, and the matching step in `static/models.js`. A version
newer than this build, or one it does not recognise, is refused outright,
because a document from the future cannot be guessed at. A patch that
half-loads is worse than one that refuses: the failure shows up later as a rack
that is subtly not the one that was saved.

Adding a field, changing a field's meaning, or changing the direction rule are
all version bumps. Adding a new *module type* is not: an unknown `type` is a
per-document error, reported as such.

### Version 2

Version 2 added two things, both additive:

- **`groups`** — rows, absent from v1.
- **Six sides instead of two.** v1 knew `front` and `back`; v2 adds `top`,
  `bottom`, `left` and `right`. Every v1 side is still a v2 side.

Because both changes are additive, the upgrade adds `groups: []` and changes
nothing else — a v1 document and its v2 upgrade describe the same rack. The
upgrade does not mutate the document it was given.

## What is validated where

The two sides check different things, and neither is a superset of the other.

| Check | `src/patch_format.py` | Browser import |
| --- | --- | --- |
| `format` and `version` | yes | yes |
| Unknown fields rejected | yes | no |
| Duplicate module ids | yes | no |
| Connection endpoints name known modules | yes | yes |
| Self-patch refused | yes | yes |
| `view` is a known side | yes | yes |
| Group ids unique, no module in two groups | yes | no |
| `view` is a side *this device* has | no | yes |
| `type` is a module this build can build | no | yes |
| `jack` exists on that module | no | yes |
| Direction legal for those jacks | no | yes |

The server validates what is true of the *document*. The browser additionally
validates what is true of *this build* — which module types and jacks exist is
a property of the running frontend, not of the format. A document that passes
the server and fails the browser is a valid patch this build cannot render, and
that is a real and distinct state.

The browser checks before it clears: a refused import leaves the rack that was
already on screen untouched.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/patch/format` | The format name and version this build reads. |
| `POST /api/patch/validate` | Validate a document. `200` with a summary, or `422` with the reason. |

Validation is stateless — it stores nothing. Persisting named patches is a
separate decision, and it is blocked on the datastore question recorded in
[GOVERNANCE.md](../GOVERNANCE.md).

```sh
curl -s -X POST http://127.0.0.1:4186/api/patch/validate \
  -H 'Content-Type: application/json' \
  -d '{"format":"carlos.patch","version":1,"modules":[],"connections":[]}'
```

## Known limits of version 3

- No module positions within a row. Order inside a group is the order in
  `members`; loose devices import in document order.
- Only one kind of group. Rows today; cases, strips and stage positions are the
  obvious next ones.
- No cable colour, length, or routing.
- No provenance — nothing records which build wrote the document.
