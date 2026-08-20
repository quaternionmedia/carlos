# Releasing Carlos

Carlos adopts `governance/qm/records/DRAFT-version-tags-are-claims.md`. This
file is that record applied to this project — what a tag here asserts, who may
make it, and which half of it a machine can do.

## What a `v*` tag asserts

Three things, all of which must hold at the tagged commit:

1. a human **reviewed** the change set;
2. a human **manually tested** it against its real runtime — for Carlos, a real
   browser, on a real screen, with the rack actually driven;
3. its **automated validation passed and is deterministic**.

**Everything untagged carries no release claim.** `they`, a pull request, and a
local build are drafts. They may be perfectly good; they assert nothing, and
nobody outside the project is entitled to read them as a release. Something that
needs publishing unasserted uses a pre-release identifier — `v0.2.0-rc.1` — which
is a tag that says so.

## Who may cut one

**A human, and only a human.** An assistant prepares a release; it never cuts
the tag. This is the same gate as ratifying a decision record and is drawn for
the same reason: the claim is about diligence, and the only thing that can
perform diligence is the person asserting it.

Nothing in this repository — no command, no workflow, no assistant — can satisfy
clauses 1 and 2. `carlos release-check` says so in its own output rather than
implying otherwise by exiting zero.

## The machine half

```sh
uv run carlos release-check
```

Runs the whole suite — `tests`, `tests/browser`, and all five walkthrough pages
— and **fails on a skip**.

That last part is the point. Per §3, a skipped test is an absent test that has
announced itself: better than silence, and still not evidence. This suite skips
whole classes when `node` is missing and the entire browser suite when no
browser has been provisioned, so a run on a bare machine looks green while
having verified a fraction of what a reader would assume. The release gate
refuses it. Reruns and retries are refused for the same reason — a suite whose
result changes between runs on unchanged input is not evidence of anything.

Provision what the suite needs, then run it again. There is no flag to skip
this; a flag to skip it would be the failure the record describes.

## The tag itself

Annotated, never lightweight, and the annotation records its own basis: **who
reviewed, what was manually tested, and what the automated gate covered —
including what it did not.**

```sh
git tag -s v0.1.0 -F - <<'EOF'
Carlos v0.1.0

Reviewed by: <name>
Manually tested: <what was actually driven, on what, and what was not>
Automated validation: carlos release-check — <N> tests, no skips.
Not covered: <the honest list>
EOF
```

Then check the tag says what it must, and push it:

```sh
uv run carlos release-check --tag v0.1.0
git push origin v0.1.0
```

A tag whose annotation cannot state the manual test performed is a tag that
should not exist yet.

## What is not mechanical here yet

§7 asks for a tag-protection ruleset restricting who may create `v*`, so that
"a human cuts the tag" is enforced rather than customary. That is a repository
setting, and it needs someone with admin on `quaternionmedia/carlos`. Until it
exists, clause 1 of this file is a convention held by the people reading it.

The call is written down so it is one command rather than a form somebody fills
in from memory. The payload is [.github/tag-ruleset.json](.github/tag-ruleset.json),
kept in this repository rather than in the corpus because the bypass actors are
this repository's:

```sh
gh api -X POST repos/quaternionmedia/carlos/rulesets     --input .github/tag-ruleset.json
gh api repos/quaternionmedia/carlos/rulesets --jq '.[] | .name'
```

It restricts creating, moving and deleting `refs/tags/v*` to repository and
organisation admins, so §1 stops being a convention and starts being a
permission. Deleting the ruleset undoes it; nothing about it is one-way.

**Check the state rather than trusting this paragraph.** The second command is
the check, and an empty result means the setting is not there — which is what
it returns today.

`.github/workflows/release-gate.yml` runs on a `v*` tag and re-runs the gate on
a clean machine, which is the other half of §7. It cannot create a tag and does
not try to.

## The current state of this project

The machine half is currently green. At `80c7c5e` on `they`:

```
514 passed, 1449 subtests passed in 159.70s
Deterministic validation passed, with nothing skipped.
```

That is clause 3 and only clause 3. **Carlos has never been tagged, and nothing
here is a release.** The
publish-readiness checklist in `GOVERNANCE.md` has two human items open — the
adoption record is unratified and the outbound licence class is unchosen — and
`reuse-lint` is red on purpose because of the second.

None of that blocks a tag. A `v0.x` tag asserts diligence, not compliance; the
numbers below `1.0.0` promise less and the gate does not change. What blocks a
tag is that nobody has yet done clauses 1 and 2.
