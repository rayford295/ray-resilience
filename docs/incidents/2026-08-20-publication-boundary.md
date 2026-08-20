# Incident — parcel-level data served from the public site

**Date found:** 2026-08-20 · **Severity:** disclosure of parcel-level damage data
· **Exposure window:** 2026-08-20, from the first Pages deploy (`65fbcc8`) to the
fix (`7135f04`) — under one day · **Status:** closed and gated

## What was exposed

```
GET https://rayford295.github.io/GeoSteward/app/events/eaton-2025/exposure/dins_points_restricted.csv.gz
200 · 355,597 bytes · application/gzip
```

18,428 rows of CAL FIRE DINS structure assessments:

```
objectid,lat,lon,severity,structure_type
3,34.18569683413362,-118.11356006485147,minor,Single Family Residence Single Story
```

Individual residential coordinates to full float precision, each with a damage
severity and a structure type.

**Scope limit, stated precisely.** The repository is private, so
`raw.githubusercontent.com` returned 404 throughout; GitHub Pages serves publicly
from a private repository, and that was the only exposure path. The file was never
in a public git history, so closing the boundary closed the disclosure — no
history rewrite was required. `events/gateway_audit.jsonl`, which records question
text and exact coordinates, was outside the three synced event directories and was
never served (verified 404).

DINS damage data is published by CAL FIRE, so the underlying records are not
secret. That is not the finding. The finding is that this project stated a
constraint on its own handling of them and then broke it, in the one place a
reader would check.

## What the project had said

Three places, all correct, none consulted by any code:

| Where | Text |
|---|---|
| `src/geosteward/deepcase/dins.py:7` | "restricted-resolution artifact, never shipped to the resident-facing app" |
| `docs/STATUS.md:45` | "parcel-level source registered as a resolution-capped lineage artifact, never served to residents" |
| `events/eaton-2025/artifact_manifest.jsonl` | `"kind": "damage_points_restricted"`, `"notes": "parcel-level DINS source; resolution_cap=parcel, planner lineage only"` |

The deploy workflow had even written down the reasoning:

> `.github/workflows/pages.yml` — "Pages stays public even while the repo is
> private, so only reviewed, committed products belong in the site tree."

The intent was documented four times over. The enforcement was documented zero
times, because it did not exist.

## Root cause

Not the build script. `app/scripts/sync-artifacts.mjs` copied whole directories:

```js
for (const event of ["eaton-2025", "milton-2024", "ian-2022"]) {
  cpSync(join(src, event), join(dest, event), { recursive: true });
}
```

That is how the file travelled, but it is not why it was allowed to. The harness
governed **claims** and not **distribution**.

`policy_v1.yaml` contained `deny-parcel-any-role`, which forbids parcel-level
*claims* at every role and tier. The restricted CSV satisfied it perfectly: no
agent ever claimed it. It was not asserted, it was copied. Every outcome check
passed, every manifest row was written, every hash matched, and the audit log was
complete — the harness worked exactly as designed, over the wrong surface.

**One institutional constraint, two enforcement surfaces, one implemented.**

A second instance of the same category sat next to it: which events form the
public surface was a JavaScript array literal inside the build script. A
governance decision expressed as build-script trivia is a governance decision
nobody reviews.

## Fix

A distribution plane, in the same file and the same grammar as the claim plane,
so the two cannot drift apart.

1. **`artifact_classes`** — every artifact kind declares `resolution_cap` and
   `audience`. **A kind absent from this table is denied.** A new product cannot
   widen the public surface until somebody classifies it, which inverts the
   default that caused the incident.
2. **`distribution`** — ordered rules over those attributes, first match wins,
   fail-closed default. `deny-publish-parcel-resolution` is the rule this file
   exists for.
3. **`published_events`** — the event list, moved out of the build script.
4. **`scripts/publication_boundary.py plan`** — asks the policy about every file
   under `events/` and writes `app/public/publication_allowlist.json`. It
   enumerates what is *on disk*, not what the manifests promise, so a file nobody
   recorded is denied rather than overlooked.
5. **`verify`** — checks an assembled site tree against the allowlist by **set
   difference**. Nothing recognises "dangerous" files; a pattern match would be a
   blocklist, permanently one artifact behind. An unrecognised file under an
   `events/` tree is a violation because it was not authorised.
6. **CI gates, both directions** — `test.yml` regenerates the allowlist and fails
   on drift, so a hand edit cannot widen the surface behind the policy's back;
   `pages.yml` runs `verify _site` before `upload-pages-artifact`, so a violation
   fails the build and the deploy never runs. The second gate inspects the
   artifact about to be served rather than the intent that produced it.

Also fixed while in there: 18 manifest rows disclosed `C:/Users/<user>/…` paths
from the maintainer's workstation. The published copies redact them to
`<workstation>`; the repository copies keep full lineage. The sha256 is the
verifiable anchor — an absolute path on someone else's machine is not
reproducible by anyone.

## Verification

- The live URL returns **404**; a public grid still returns 200; snapshots return 404.
- The live manifest contains **0** workstation paths and 5 `<workstation>` markers.
- Public surface: **30 files → 16**, exactly the set the PWA fetches.
- Negative test: replanting the file into a built site makes `verify` exit 1 and
  name it. This is a test, not a one-off check —
  `tests/test_harness_publication.py::test_planted_restricted_artifact_is_reported`
  fails if the gate ever stops catching it.

## What this changes about the argument

The harness caught a real error during the Eaton build: an over-strict join
assertion was rejected, and both the rejection and the correction are in
`events/eaton-2025/audit_log.jsonl`. That is the harness working *inside* its
coverage.

This incident is the other half, and the more useful one. The constraint was
articulated in prose, encoded in a manifest field, and reasoned about in a
workflow comment — and none of that stopped it, because the enforcement lived on
a surface the harness did not model. A constraint that is written down but not
executed is not a constraint; it is an intention, and intentions do not survive
`cpSync`.

The general claim: **computable institutional constraints have to be enforced at
every surface where the constraint can be violated, and the surfaces are not
obvious in advance.** We found the missing one by violating it. The distribution
plane closes this one. It is not evidence that no others remain — the honest
version of that sentence is that we now check the artifact we serve, not only the
intent that produced it, which is the property that would have caught this on
day one.

## Timeline

| UTC | Event |
|---|---|
| 2026-08-20 ~02:00 | `events/eaton-2025/` built; restricted CSV registered with `resolution_cap=parcel` |
| 2026-08-20 (`65fbcc8`) | Pages deploy ships `/app/` built by whole-directory copy; file becomes public |
| 2026-08-20 (`346553e`) | Latest commit before review; file still live |
| 2026-08-20 | External review flags it; confirmed 200 / 355,597 bytes |
| 2026-08-20 | Repository confirmed private; `raw.githubusercontent.com` 404 — Pages is the only path |
| 2026-08-20 (`7135f04`) | Distribution plane, allowlist, and both CI gates land; redeployed |
| 2026-08-20 | Live URL 404; public surface 16 files; manifests redacted |

Found by external review of the deployed site, not by the test suite. Worth
recording: the tests checked what the code did, and the deployment was the thing
that was wrong.
