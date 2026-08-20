# Carlos Governance

Carlos is becoming a governed Quaternion Media project. The adoption is
underway and not finished, and this page is the honest state of it.

## Local Status

- Repository: `quaternionmedia/carlos`
- Current default branch on GitHub: `they`
- Governance corpus: `quaternionmedia/qm`, vendored at `governance/qm`
- Project branch: `project/carlos` — **pushed** to `quaternionmedia/qm`
- Phase: `v0.0.1` on the corpus's project-phase ladder, which is the rung that
  means "working toward governance adoption"

## Publish-Readiness Checklist

- [x] README describes the current prototype truthfully.
- [x] Project metadata names Carlos and uses the declared package version.
- [x] License file exists.
- [x] Contributing, security, and code-of-conduct files exist.
- [x] Issue and pull request templates exist.
- [x] `governance/qm` submodule is added, pinned to `project/carlos`.
- [x] Seed workflows are copied into `.github/workflows/` — all six.
- [x] The project's own tests run in CI, beside the gates
      (`.github/workflows/tests.yml`). Until that existed nothing ran them, and
      green checks meant six gates about paperwork.
- [x] `AGENTS.md`, `CLAUDE.md`, and `.github/copilot-instructions.md` are wired.
- [x] The adoption record is written —
      `governance/qm/adr/DRAFT-adopt-the-qm-constitution.md`, numberless and
      Proposed. Ratification is a human commit.
- [x] `walkthrough/` exists and runs from the ordinary test command.
- [x] `project/carlos` is pushed to `quaternionmedia/qm`. Done at the handoff;
      `check-submodule-refs` went green on the same push.
- [ ] The adoption record is ratified: status flipped, number assigned by the
      index, index updated. **A human commit naming the record.**
- [ ] Runtime dependency policy is settled — see the conflicts below.
- [ ] Licensing pass done and `reuse-lint` green. **Deliberately not done**:
      it is gated on the outbound licence class, and settling a licence class
      to turn a check green decides the wrong question for the wrong reason.
      Publishing with this red is the accepted state.
- [x] Patch export/import behaviour is implemented and specified.
- [x] Device catalogue, worked examples, and the interop seam are specified.
- [x] Menus adopt the `quaternionmedia/rad` interaction contract, with its
      conformance vectors vendored and passing.

## Gate Status

Run them yourself rather than trusting this table:

```bash
python governance/qm/project-seed/ci/run_workflows_locally.py --base-ref they
```

| Gate | State | Why |
| --- | --- | --- |
| `adr-lint` | pass | |
| `one-pr-check` | pass | |
| `signature-check` | **fail** under the runner, passes locally | The runner uses the CI path, which asks the forge about a commit the forge has never seen and reports `E` — "could not be checked", not "bad signature". With `--source git`, on a machine holding the key, the same commit reports `G` |
| `reuse-lint` | **fail** | The licensing pass has not been done — **three** files carry copyright information and the rest do not (`python -m reuse lint` for the current total, which moves with every file added) and there is no `LICENSES/` directory. The ratio has worsened as the project grew, which is the cost of deferring it |
| `submodule-check` | **fail** | `project/carlos` exists only locally |
| `tag-claims` | skipped | Only fires on a `v*` tag |

All three failures are expected, and two of them are useful rather than
regrettable. The corpus says to start `reuse-lint` in reporting mode precisely
because a project that has not had its licensing pass fails it immediately, and
`submodule-check` is correctly reporting an unpushed branch. `signature-check`
is the odd one out: it is asking the forge about a commit the forge has never
seen, so it is reporting an absence of evidence rather than a defect.

## Known Conflicts With Org Records

These belong in the adoption record as a conflict table, per the fork
procedure's step 6, and they are in it:
`governance/qm/adr/DRAFT-adopt-the-qm-constitution.md`, numberless and Proposed
until a human ratifies. This table stays the working surface; that record is
the decision behind it, and the two are kept in step by hand rather than
generated — if they disagree, the record is the one that was reviewed.

Enumerating a conflict is not waiving it.

| Conflict | Record | Note |
| --- | --- | --- |
| Packaging is `uv`, the blessed tool is PDM | house-stack §1 | **Do not write a project exception.** Three QM projects stand on `uv` — carlos, loopwall, sqlmodel-ui — which fires the record's own revision trigger. This is an org-level amendment, not a local waiver |
| Store is TinyDB | house-stack §1, seams | The blessed default is PostgreSQL, or SQLite for single-node tools, reached over SQL. TinyDB has no protocol seam and fails the replaceability test |
| ~~Tests are `unittest`~~ | house-stack §1 | **Closed.** The runner is pytest. The tests themselves are still `unittest.TestCase`, which pytest runs natively, so adopting the blessed tool cost a dependency and no rewrite |
| `static/anime-shim.js` is a local stand-in | house-stack §1 | The set names vendored `anime.js`; a 25-line reimplementation is neither vendored nor anime.js |
| Declared licence is MIT | outbound-licensing §4 | Services and control planes are AGPL-3.0-or-later. The declared licence is a reviewed output, not an inherited default |
| No SPDX headers, no `LICENSES/` | outbound-licensing §12 | What `reuse-lint` is failing on |
| ~~No `walkthrough/`~~ | one-executable-walkthrough §1 | **Closed, including decision 7.** Five pages, four hermetic and one runtime-bound, executed by the ordinary test command. The pages have now run on the default branch: run [32367009542](https://github.com/quaternionmedia/carlos/actions/runs/32367009542) at `80c7c5e`, jobs `96418600755` (hermetic pages) and `96418600498` (the runtime-bound one, in real Chromium). The identifier is the evidence; a workflow file that would have run is not a run |
| Frontend is plain modular JS, no build step | house-stack §1 | The set names mithril with a parcel build for frontend applications. Carlos ships no build step at all, which is neither the blessed answer nor a recorded exception |
| No dependency-manifest licence gate | open-license §4 | Required per package ecosystem shipped |
| No service inventory | open-license §6 | No scanner can produce it, which is why it is written down |
| No control-plane record | build-the-seam §4 | Names what the seam owns and what it refuses to own |
| ~~`/healthz` cannot say which instance answered~~ | monitoring-seam §5 | **Closed.** It reports instance, start time, the port actually bound and the resolved database path. The port is read off the connection rather than off settings, because a process serving somewhere other than where it was configured is the case worth catching |
| Port-0 discovery and a run-file are declined | monitoring-seam §4 | That clause governs services a monitor watches in the internal control plane. Carlos is a browser application whose whole point is a predictable address, and binding port 0 would stop it being a thing you open at `localhost:8000`. §5 is met the other way, by the endpoint saying which instance answered; `CARLOS_HOST`, `CARLOS_PORT` and `CARLOS_DB` move a process without editing anything committed. What is not met is discovery: a collector has to be told where to look |

## What Grew Since Adoption Started

The repository is materially larger than when the checklist above was written,
and two rows are worth stating plainly rather than leaving to be rediscovered:

- **The licensing pass is now a bigger job than it was.** Every file without one needs SPDX
  headers rather than 37. Nothing about it got harder; there is just more of it,
  and there will be more again next time.
- **The frontend is no longer a single prototype file.** `static/` carries the
  rad core, its DOM layer, the menu resolver, the MIDI adapter and the rack
  model, and `tests/` carries a small DOM implementation. None of this is
  governed by a record yet; the house-stack frontend entry names mithril with a
  parcel build, and Carlos is plain modular JS with no build step. That is a
  conflict the adoption record has to name.

## Seam Obligations

The monitoring-seam record governs how a QM service is observed by the family's
harness. Two of its three clauses are met; the third is declined with a reason.

- **§3 — a committed policy carries no machine literal.** *Met.* The address and
  the database path are defaults that `CARLOS_HOST`, `CARLOS_PORT` and
  `CARLOS_DB` override per process, and no address is committed anywhere in the
  peer policy — `tests/test_cadence.py` refuses an IP, a hostname, a URL, a port
  or a Windows path in that file. The per-call timeout is committed, as the
  clause requires.
- **§4 — instances are discovered, never enumerated.** *Declined, deliberately.*
  A monitored service binds port 0 and writes a run-file. Carlos binds a
  predictable port because it is a thing you open in a browser, and a tool whose
  address changes every run is a tool nobody opens. A collector must therefore
  be told where to look rather than enumerating a directory.
- **§5/§6 — identity before attribution.** *Met.* `/healthz` reports the
  instance, its start time, the port actually bound and the resolved database
  path, so two servers running at once are told apart and a measurement can be
  attributed. The port is observed off the connection rather than read back off
  settings, because a process serving somewhere other than where it was
  configured is precisely the case worth catching.

## Publishing

What a publisher does, in order. Everything above the line is done; everything
below needs a person, and two of the three are remote writes.

1. **Push `project/carlos`** to `quaternionmedia/qm`. Closes `submodule-check`,
   and completes fork steps 2 and 3.
2. **Push this branch and open one pull request.** One open pull request per
   contributor, per repository — `one-pr-check` enforces it. Never request a
   review; add the person who asked for the work as assignee. Reviewers are
   named at the version tag, by the human cutting it.
3. **Expect two of the three red gates to go green** on that push.
   `signature-check` passes once the forge can see the commits — every one is
   signed, verifiable now with `carlos signatures`. `submodule-check` passes
   once step 1 lands. `reuse-lint` stays red, by the decision recorded above.
4. ~~**The tests run remotely for the first time.**~~ **Done.** They had only
   ever run on one workstation. Run
   [32367009542](https://github.com/quaternionmedia/carlos/actions/runs/32367009542)
   on `they` is what satisfies the walkthrough record's decision 7, which no
   file can satisfy: a page that ran where nobody merges has not run.
5. **Ratify the adoption record**, or don't. The branch merges either way; the
   record is what lets Carlos be described as carrying governance rather than
   improvising it.

**Merging into the default branch is not a release.** `RELEASING.md` is where
that is written down for this project, with the gate that enforces the half of
it a machine can hold: `carlos release-check`, which runs everything and refuses
a skip.

 Per the version-tags
record, the default branch, a pull request and a local build are all drafts.
The two human gates are ratification, for what a record says, and the version
tag, for what this project ships — a `v*` tag asserts a human reviewed the
change set, a human manually tested it against its real runtime, and
deterministic validation passed.

## Version Tags

`RELEASING.md` is this project's application of
`DRAFT-version-tags-are-claims.md`. The state of its enforcement, which is the
part worth stating here because it is the part that decays:

| §  | What it asks | State |
| -- | --- | --- |
| §1 | a human cuts the tag, never an assistant | **Customary.** The one gap below makes it so |
| §2 | the tag asserts review, manual test, deterministic validation | The third is green at `80c7c5e`: `carlos release-check` — 514 passed, nothing skipped, reran or retried. The first two are unmade; nobody has done them |
| §3 | only deterministic validation counts | **Mechanical.** `carlos release-check` fails the run on a skip, a rerun, a retry, an xfail or an xpass, and this suite really does skip whole classes on a bare machine |
| §6 | annotated tags naming their own basis | **Mechanical.** `tag-claims.yml` fails a pushed `v*` that is lightweight, misnamed, or missing one of the four annotation fields |
| §7 | release automation triggers on the tag, never creates one | **Met.** `release-gate.yml` re-runs the gate on a clean machine and writes a summary saying which of the three claims it did *not* assert |
| §7 | a tag-protection ruleset restricting who may create `v*` | **Missing.** `GET /repos/quaternionmedia/carlos/rulesets` returns an empty list. This is repository settings, not a workflow, and no workflow can substitute — `tag-claims.yml` runs *after* the tag exists. `RELEASING.md` carries the exact call |

**Carlos has never been tagged.** Nothing in the repository is a release, and
the absence is correct rather than an oversight: what blocks a tag is that
nobody has yet reviewed a change set and driven the thing on a real screen.

## Local Rule

Until the checklist is complete, do not describe Carlos as a fully governed QM
project. It carries the governance machinery with open gaps stated — which the
corpus calls instantiated rather than improvised — and that is a different claim
from compliant.
