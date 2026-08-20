// Vendor the *authorised* deep-case artifacts into public/ so the PWA is
// self-contained: dev and Pages builds serve the exact committed products.
//
// The set of files copied is not decided here. It is decided by the
// distribution plane in src/geosteward/harness/policy_v1.yaml and written to
// publication_allowlist.json by scripts/publication_boundary.py. This script
// only executes that decision, and refuses to run without it.
//
// It used to copy whole event directories. That is how a parcel-level DINS
// source reached the public site on 2026-08-20 — see
// docs/incidents/2026-08-20-publication-boundary.md. Copying by allowlist
// means a new artifact in events/ is invisible to the site until the policy
// classifies it, rather than public the moment it lands on disk.
//
// The Tier-1 live watch layer is fetched at runtime (live-data branch) and
// degrades to a stale badge when unreachable — never a fabricated layer.

import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");
const publicDir = join(here, "..", "public");
const allowlistPath = join(publicDir, "publication_allowlist.json");

// Absolute paths on the maintainer's workstation are honest provenance inside a
// private repository and needless disclosure on a public site. The sha256 in
// each manifest row is the verifiable anchor; the path is not reproducible by
// anyone else. Keep this pattern in step with WORKSTATION_PATH in
// src/geosteward/harness/publication.py — CI verifies the built output, so a
// drift here fails the deploy rather than shipping quietly.
const WORKSTATION_PATH = /(?:[A-Za-z]:[\\/]Users[\\/][^\\/"]+|\/Users\/[^/"]+|\/home\/[^/"]+)/g;

if (!existsSync(allowlistPath)) {
  console.error(
    `publication allowlist not found at ${allowlistPath}\n` +
      "Run: python scripts/publication_boundary.py plan"
  );
  process.exit(1);
}

const { allowed } = JSON.parse(readFileSync(allowlistPath, "utf8"));
if (!Array.isArray(allowed) || allowed.length === 0) {
  console.error("publication allowlist is empty; refusing to build an eventless app");
  process.exit(1);
}

// Rebuild from scratch so a file dropped from the allowlist also disappears
// from any previously synced tree.
rmSync(join(publicDir, "events"), { recursive: true, force: true });

let redacted = 0;
for (const entry of allowed) {
  const source = join(repoRoot, entry.path);
  if (!existsSync(source)) {
    console.error(`allowlisted artifact missing from the repository: ${entry.path}`);
    process.exit(1);
  }
  const target = join(publicDir, entry.path.replace(/^events\//, "events/"));
  mkdirSync(dirname(target), { recursive: true });
  if (entry.redact_workstation_paths) {
    const original = readFileSync(source, "utf8");
    const clean = original.replace(WORKSTATION_PATH, "<workstation>");
    if (clean !== original) redacted += 1;
    writeFileSync(target, clean, "utf8");
  } else {
    copyFileSync(source, target);
  }
}

console.log(
  `synced ${allowed.length} authorised artifact(s) -> ${join(publicDir, "events")}` +
    (redacted ? ` (${redacted} file(s) redacted)` : "")
);
