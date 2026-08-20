// Vendor the versioned deep-case artifacts into public/ so the PWA is
// self-contained: dev and Pages builds serve the exact committed products.
// The live Tier-1 watch layer is fetched at runtime (live-data branch) and
// degrades to a stale badge when unreachable — never a fabricated layer.

import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");
const src = join(repoRoot, "events");
const dest = join(here, "..", "public", "events");

if (!existsSync(src)) {
  console.error(`events/ not found at ${src}`);
  process.exit(1);
}
rmSync(dest, { recursive: true, force: true });
mkdirSync(dest, { recursive: true });
for (const event of ["eaton-2025", "milton-2024", "ian-2022"]) {
  cpSync(join(src, event), join(dest, event), { recursive: true });
}
console.log(`synced deep-case artifacts -> ${dest}`);
