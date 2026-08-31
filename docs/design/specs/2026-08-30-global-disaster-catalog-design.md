# Design — a global, cross-region, cross-hazard, multi-source disaster catalog

**Date:** 2026-08-30 · **Status:** approved in brainstorming (positioning and the three
decisions in §5–§7 approved by the owner, 2026-08-30) · **Scope:** documentation only. This
spec fixes the record schema, the vocabularies, and the conflict rule for a catalog layer over
`events/`. No schema file, no `catalog.jsonl`, and no global connector lands with it — §11 says
what the first implementation stage would add, and §13 says how to tell whether it happened.

## 1. Why this is the core of the project, and not a fifth plan

GeoSteward's stated purpose is to tell a person what the evidence about their location actually
supports. Everything built so far serves one geography at a time: four keyless US connectors for
the Tier-1 watch, three deep-case AOIs in California and Florida, and one archived western-Pacific
typhoon. The accountability machinery — the two policy planes, the `verifiability` axis, the
append-only manifests — is general. The **coverage** is not.

A cross-region, cross-hazard, multi-source disaster database is the thing that turns the
machinery into a system: it is what lets the agent answer *"is this place covered, by what
evidence, to what depth, and may I keep it"* for somewhere it has never been asked about before.
Without it, every new region is a bespoke deep case. With it, a region is a set of catalog rows
whose gaps are declared rather than discovered by a user.

So the catalog is not a fifth workstream beside the four planes. It is the **event-level tier of
the same accountability record** the manifests already keep at the artifact level, generalised
from one country to the world.

## 2. What the existing global databases are actually short of

The instinct on hearing "global disaster database" is that the field lacks data. It does not. The
field lacks a machine-readable answer to *what may I conclude from this row*.

| Source | What it gives | What it does not answer |
| --- | --- | --- |
| **EM-DAT** (CRED/UCLouvain) | The canonical global loss record — deaths, affected, damages, at event level, back to 1900 | Nothing about supported claim resolution; core records carry admin names rather than geometry, and entry is threshold-gated, so absence is not evidence of absence |
| **GDACS** (JRC / UN) | Near-real-time global alerting with a severity score and, for some hazards, an event footprint | An alert is a modelled estimate at issue time; nothing distinguishes an estimate from an observation once both are rows |
| **Copernicus EMS Rapid Mapping** | Genuine geospatial delineation and grading products, high quality | Coverage is activation-driven, so the map of what exists is a map of who asked, not of what happened |
| **ReliefWeb** (UN OCHA) | Situation reports and a working GLIDE linkage | Prose. Nothing enumerable, nothing hashed |
| **USGS / national agencies** | Authoritative single-hazard depth (ShakeMap, PAGER, gauge networks) | Single hazard, and each with its own taxonomy, so cross-type comparison is a manual crosswalk somebody has to redo |
| **DesInventar** (UNDRR) | Subnational loss granularity where a country maintains it | Coverage and method vary by country; the variation is documented for humans, not carried in the record |

Every one of these is a good database. What none of them carries in the row itself is the thing
this project already computes for its own artifacts: **at what resolution a statement is
authorised, whether a reader can check the support, and whether the evidence is ours to keep.**

That is the gap this catalog is aimed at. Its differentiator is not volume. It is that a row
knows the limits of what can be said from it.

## 3. Scope

**In scope.** A per-event record schema that is global from the first row; a controlled hazard
vocabulary with declared crosswalks to each source's own taxonomy; region and time conventions
that do not assume the United States; a rule for what happens when sources disagree; and the
wiring by which the catalog becomes a harness-registered, distribution-governed artifact.

**Not in scope, deliberately.** Any new connector. Any change to the Tier-1 watch pipeline, which
stays the four US sources it is today. Any global analysis product — the deep-case AOIs remain
three. Any bulk import of historical events; §11 stages that, and §7 explains why an unstaged bulk
import would be actively harmful. Any change to `policy_v1.yaml`, whose claim plane this design
consumes and does not modify.

**The honest statement of position.** After this spec, the catalog's *structure* is global and its
*coverage* is four events. The README says exactly that. A design document that let a reader infer
otherwise would be the same failure as an uncited claim.

## 4. The record

One JSONL row per event, five field groups. The shape follows `events/*/dossier/event_record.json`,
which already carries identity, hazard, AOI, tier, sources, and declared unknowns — the catalog row
is that record plus the fields a *global* set needs and a single-country set could leave implicit.

**Identity.** `event_id` (repository slug, e.g. `eaton-2025`), `name`, `name_local` (the name in
the language of the affected place, unromanised), `aliases[]`, `glide` (§5), `parent_event_id`
(for an event that is one episode of a longer season).

**Hazard.** `hazard_type` from the controlled vocabulary (§8), `hazard_subtype`,
`hazard_vocabulary_version`, and `source_hazard_labels[]` — each source's own label kept verbatim
alongside the mapped value, so a lossy mapping is inspectable rather than silent.

**Space and time.** `iso3[]` — **an array**, because a flood basin, a cyclone track, and an
earthquake do not respect borders and a single-country field would force a lie on exactly the
events that most need the catalog. Then `admin1[]`, `aoi_bbox_wgs84`, `aoi_geometry_ref` (a path
into `events/`, not inline geometry), `start_utc`, `end_utc`, and `time_precision` — one of
`hour`, `day`, `month`, `unknown`. Slow-onset events (drought, subsidence) have no defensible
start hour, and a schema that demands one manufactures precision.

**Evidence and sources.** `evidence_tier` (1 watch, 2 analysis, 3 cross-view), `verifiability`
(§6), `license`, and `sources[]` where each entry carries its own `source_id`, `provider`,
`access` (`api` / `bulk-download` / `manual` / `restricted`), `license`, `verifiability`,
`retrieved_utc`, `sha256` when retained, and `url` when cited-only. Then `artifacts[]`, pointing
at rows of the event's own `artifact_manifest.jsonl` rather than duplicating them, and
`claims_supported` — the finest `resolution` this event's evidence can carry, in the claim plane's
own vocabulary (`tile`, `event`, `source`), so the row states its ceiling in the same words the
policy engine uses to enforce it.

**Provenance and gaps.** `declared_unknowns[]`, `conflicts[]` (§7), `record_created_utc`,
`record_agent`, and `record_inputs[]`. The row is itself an artifact and is built, hashed, and
audited like one.

## 5. Decision one — identity that joins across databases

A catalog whose event identifiers exist only inside this repository cannot be reconciled with
EM-DAT, ReliefWeb, or a national agency, and reconciliation is the entire point of a multi-source
record. So every row carries **`glide`**, the Global unique disaster IDentifier
(`<hazard>-<year>-<serial>-<ISO3>`), alongside `aliases[]` for the names a source actually used.

The discipline that makes this worth anything: **an event with no GLIDE gets `null`, never a
constructed one.** A fabricated identifier that looks like a join key is worse than an absent one,
because the next system down the line will join on it. `null` is a declared unknown in the
project's existing sense, and the same instinct governs it.

`event_id` stays the repository slug and stays authoritative internally. GLIDE is a foreign key,
not a primary one — it is not universally assigned, and a schema that required it would exclude
precisely the under-documented events a global catalog exists to surface.

## 6. Decision two — `evidence_tier` and `verifiability` are orthogonal

There is a tempting single "quality" score. It collapses two questions that have to stay apart:

- **`evidence_tier`** — *how deep is the evidence?* 1 monitoring, 2 analysis, 3 cross-view. This
  is about what was done.
- **`verifiability`** — *what can a reader do to check it?* `cited-only` < `re-derivable` <
  `retained`, weakest-link across the row's sources. This is about what the reader can do, and it
  is already implemented: `VERIFIABILITY_ORDER` in `harness/policy.py`, matched by the
  `verifiability` and `verifiability_below` keys the claim plane already validates at load time.

They are orthogonal, and the useful consequence is that **the pair already expresses "we know this
event happened and we hold nothing about it"** — `evidence_tier: 1`, `verifiability: cited-only`
— without a new field and without a special case. A globally-sourced row that is a bare
registration is honestly typed by the axes that exist.

The reverse combination is equally real and equally important: a Copernicus EMS grading product
is `evidence_tier: 3` under a licence that may not permit redistribution, so it can be `retained`
in method and `cited-only` in what this repository may hold. Two axes catch that; one score buries
it.

The claim plane needs no amendment to consume this. `deny-damage-assessment-without-retained-evidence`
already refuses damage claims below `retained`, so a `cited-only` global row cannot yield a damage
assertion — the refusal comes from the rule that exists, not from one this design invents.

## 7. Decision three — the catalog never merges conflicting values

Sources disagree about the same event, routinely and by large margins. A death toll may be 200 in
EM-DAT, 350 in a GDACS estimate, and 289 from the national authority. Every instinct of database
design says pick one and store a number.

**This catalog stores all three, each with its source and tier**, and then does one of two things:

1. A **policy-selected authoritative value**, with `selected_by` naming the rule that selected it
   — so the choice is inspectable and revisable rather than baked into a build script. (That
   lesson is not hypothetical here: the 2026-08-20 publication-boundary incident happened because
   a governance decision was living as build-script trivia.)
2. A **declared conflict**: `conflicts[]` gains an entry, and any answer resting on the field
   reports the disagreement instead of choosing silently.

This generalises the rule the area query already enforces — *never merge statistics across two
events* — from two events to two sources. The reasoning is the same in both places: a merged
number destroys the information that would let a reader judge it, and it destroys it invisibly.

It is also why §3 refuses a bulk historical import for now. Importing thousands of rows before the
conflict machinery exists would produce a catalog whose *shape* is authoritative and whose
*content* is unreconciled — the precise failure this project's honesty conventions are built to
avoid. Volume first, accountability later, is how the existing global databases arrived at the
gaps in §2.

## 8. Cross-hazard: a controlled vocabulary with declared crosswalks

Each source names hazards its own way. NIFC has fire incident types, NWS has alert event names,
GDACS has six alert types, EM-DAT has a group/subgroup/type/subtype hierarchy. Mapping them is
unavoidable; hiding the mapping is not.

`hazard_type` therefore draws on a small top-level subset of the **UNDRR–ISC Hazard Information
Profiles**, the standing international reference for hazard definitions, and every source's own
label is kept verbatim in `source_hazard_labels[]`. The mapping itself is a **first-class,
hashed artifact** — the same pattern `events/eaton-2025/snapshots/registry/label_crosswalk.json`
already uses for the percent-loss-to-perception mapping, whose approximation the Eaton event
record declares rather than absorbs.

The rule that keeps this honest: **a crosswalk entry that loses information declares it.** A
multi-hazard cascade (an earthquake that causes a tsunami that causes an industrial release) is
not flattened to its most legible component; it is either one row with `hazard_subtype` naming the
cascade or linked rows sharing a `parent_event_id`.

## 9. Cross-region: what stops being assumable outside the United States

Four things that are safe to leave implicit in a US-only system, and are not safe to leave implicit
now:

**Administrative hierarchy.** `state → county → tract` is a US structure. The SVI join that
underpins the deep cases has no global equivalent, and there is no single global vulnerability
index with comparable resolution and method. The catalog therefore stores `admin1[]` as opaque
labels beside ISO3 codes and **makes no claim of cross-country comparability** for any
vulnerability measure. Where a national index exists, it is a source with its own tier — not a
column that pretends to be the same column as SVI.

**Time.** Every timestamp is UTC with an explicit `Z`, as the watch pipeline already writes
(`20260820T015631Z` in the manifests). Local time appears only in rendered prose, never in a
field.

**Language.** `name_local` is stored unromanised, and romanisation is a display concern. An event
that only the affected country reported is exactly the kind of gap a global catalog is supposed to
close, and losing its name in transliteration is how it stays closed.

**Coverage.** Absence of a row means the catalog has not registered the event — not that nothing
happened. Every existing global database is threshold-gated, activation-driven, or capacity-limited,
so under-reporting correlates with vulnerability. A catalog silent about that would systematically
mislead in one direction. Coverage is therefore declared **per region**, as a first-class statement,
in the same way the app declares an address outside the evaluated AOIs rather than extrapolating.

## 10. How it wires into what already exists

The catalog is a **derived artifact**, built from the per-event `event_record.json` files and
manifests, registered through the harness, hashed, and audited like every other product. Three
consequences follow without new mechanism:

- **Distribution.** `policy_v1.yaml`'s `artifact_classes` table denies publication to any kind not
  listed in it. A new `event_catalog` class — `{resolution_cap: event, audience: public, license:
  project}`, sitting beside `event_record` and `artifact_manifest` — is what would let it ship.
  Until that entry exists, the catalog cannot reach the site, which is the fail-closed behaviour to
  want.
- **Claims.** `claims_supported` speaks the claim plane's `resolution` vocabulary, so a row's
  ceiling and the policy engine's enforcement are stated in one language. No new match key;
  `_KNOWN_MATCH_KEYS` is untouched.
- **The agent.** The coverage question — *is this place covered, by what, to what depth* — becomes
  a catalog lookup instead of a hard-coded AOI list. That is the change that makes "outside the
  evaluated areas" a computed answer rather than a maintained constant.

## 11. Stages

| Stage | What it adds | Coverage after it |
| --- | --- | --- |
| **S0** | JSON Schema, `scripts/build_catalog.py`, `events/catalog.jsonl` generated from the existing event records, harness registration, the `event_catalog` distribution class, tests | 4 events: 3 US deep cases + the archived non-US Bavi case |
| **S1** | Global event registration from keyless sources (GDACS, USGS global seismicity, ReliefWeb), each row `evidence_tier: 1`, `verifiability` set by licence rather than assumed | Global event registration; no analysis products outside the AOIs |
| **S2** | Conflict reconciliation across sources; the first analysis product outside the United States | Analysis in more than one country |
| **S3** | Contribution path — an external party registering an event, with the same hashing, tier, and licence discipline | Community-extensible |

Each licence in S1 is **verified before use, not assumed from reputation**. `license` is a field
whose wrong value is a redistribution problem, and none of the licences named in §2 have been
checked against their current terms for this purpose.

## 12. Risks

| Risk | Mitigation |
| --- | --- |
| The catalog reads as global capability when coverage is four events | §3 states the position; the README table carries the same statement in the row a reader checks first |
| A bulk import produces authoritative-looking, unreconciled rows | §7 sequences conflict machinery before volume; S1 registers events at tier 1 only |
| A hazard crosswalk silently loses a cascade | §8 keeps source labels verbatim and makes lossy entries declare themselves; the crosswalk is hashed |
| Under-reporting is read as absence of events | §9 makes coverage a per-region declaration, not an inference from row count |
| A third-party licence is assumed rather than checked | §11 requires verification per source; `deny-publish-third-party-restricted` denies the artifact even if a row is wrong |
| The catalog becomes a second source of truth beside the manifests | It is derived and regenerable; manifests stay authoritative for artifacts |

## 13. Definition of done

For this spec:

- The record schema, the three decisions, and the vocabularies are fixed here in enough detail
  that S0 is implementation rather than further design.
- The README states the position of §3 — structure global, coverage four events — in the same
  table a reader uses to find out what works today.
- `docs/STATUS.md` points at this spec so the roadmap and the design record agree.

For S0, when it is taken up: `events/catalog.jsonl` exists and is generated, not hand-written;
every existing event has a row; the `event_catalog` class is in `policy_v1.yaml`; and a test
asserts that a row's `claims_supported` never exceeds what its `evidence_tier` and `verifiability`
permit under the claim plane.
