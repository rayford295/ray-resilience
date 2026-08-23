"""Check that repository paths cited in documentation actually exist.

The failure this catches: `docs/architecture.md` pointed at
`src/disasterpilot/` for days after the package was renamed `geosteward`, and
nothing caught it because the coupling between prose and code was purely
narrative. This script extracts every path-shaped token cited in an
inline-code span or a Markdown link target, and checks that it resolves on
disk (or is declared absent on purpose — see `DECLARED_ABSENT` below).

Known misses (documented here rather than fixed, because the alternative is
worse):

- Bare (un-backticked) paths in prose are not extracted. The false-positive
  rate over ordinary English text — "and/or", "he/she", version strings —
  is not worth the extra recall.
- A path broken across two lines by hard wrapping is not extracted. For
  example `src/geosteward/harness/policy_v1.yaml` line 115 wraps
  `docs/design/specs/` onto the next line; this script checks each line
  independently and will not join them.
- An anchor that resolves says nothing about whether the behaviour behind it
  still matches the sentence citing it. This script checks that the path
  exists, not that the prose describing it is still true.

`DECLARED_ABSENT` exists because some paths are cited *because* they do not
exist — `events/live_evidence.jsonl` is cited to say no live API call has
ever run. A gate that failed on that citation would make the cheapest fix
deleting the (true) sentence, which is worse than not gating it at all. So
absence is declared explicitly, with a reason, and checked in both
directions: cited-and-absent passes, but if the path comes into existence
the declaration itself is now stale and `stale_absences` reports it — the
same shape as `artifact_classes` in
`src/geosteward/harness/policy_v1.yaml`: declare the exception, then check
the declaration so it cannot silently rot.

Usage:
    python scripts/manual_anchors.py list [ROOT ...]
    python scripts/manual_anchors.py check [ROOT ...]

ROOT defaults to docs/manual. Each ROOT may be a directory (walked for
*.md files) or a single file (read directly, whatever its extension) --
so CI can point this at README.md and at source files that cite docs, not
just at documentation directories.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Rule 3 of "what counts as an anchor": a token must begin with one of these
# to be treated as a path. This is what keeps "H3 r9", "sha256", "EPSG:4326",
# and prose like "and/or" from being mistaken for repository paths.
TOP_LEVEL = ("app/", "docs/", "events/", "gateway/", "scripts/", "src/", "tests/", ".github/")

# Paths cited because they do NOT exist -- the absence is the content being
# asserted. See the module docstring for why this must be checked in both
# directions rather than just skipped.
DECLARED_ABSENT = {
    # No Google Maps Platform key exists, so neither live adapter has ever run.
    # The manual cites this path precisely to say the file is not there.
    # See docs/manual/05-verifiability-and-live.md.
    "events/live_evidence.jsonl": "no GMP key; both adapters are tested against a stub",
    # Created by Task 2 of the bilingual-manual plan. Declared rather than
    # de-formatted on purpose: when the directory appears, stale_absences fails
    # the gate, which is what forces this citation to become a live link
    # instead of quietly staying a bare string.
    "docs/manual/": "created by Task 2 of docs/design/plans/2026-08-23-bilingual-manual.md",
}

# Source-file prefixes whose own anchors are not checked. This is keyed on
# the *citing* file, not the cited path -- these files legitimately cite
# paths that don't resolve, in bulk, for reasons unrelated to staleness.
SKIP_PATHS = (
    # Design records cite paths that are planned, or historical, or cited as
    # counterexamples: this plan cites the thirteen files it is about to create,
    # and the specs cite `src/disasterpilot/` precisely because it no longer
    # exists. 80 correct citations would report as failures.
    "docs/design/",
    # Scheduled for deletion in Task 14. Until then it cites
    # src/disasterpilot/sources/, which is the very staleness this gate exists to
    # catch — but a gate that is red for thirteen tasks is a gate people learn to
    # override. Task 14 deletes the file AND this entry, together.
    "docs/architecture.md",
)

# Inline code span: `like/this`. Deliberately excludes newlines so a span
# can't accidentally swallow the rest of the document if a closing backtick
# is missing.
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
# Markdown link target: [text](like/this). Stops at whitespace so a link
# title ("(path "a title")") doesn't get pulled into the path.
_LINK_TARGET_RE = re.compile(r"\]\(([^)\s]+)\)")
# Trailing `:N` or `:N-M` line reference, e.g. `policy.py:195` or `:10-20`.
_LINE_REF_RE = re.compile(r":(\d+(?:-\d+)?)$")


@dataclass(frozen=True)
class Anchor:
    raw: str
    path: str
    line_ref: str | None
    source: Path
    source_line: int


def _split_line_ref(token: str) -> tuple[str, str | None]:
    """Strip a trailing :N or :N-M line reference, returning (path, ref)."""
    match = _LINE_REF_RE.search(token)
    if match is None:
        return token, None
    return token[: match.start()], match.group(1)


def _looks_like_path(token: str) -> bool:
    """Implements anchor rules 1-3 plus the template/glob/brace exclusions.

    A token is a candidate path only if it contains a slash, has no
    whitespace, and starts with a known top-level directory (rule 3 is what
    rejects "H3 r9", "sha256", "EPSG:4326", and "and/or"). Tokens containing
    <, >, or * describe a shape rather than a concrete path (e.g.
    `events/<event-id>/artifact_manifest.jsonl`) and are not anchors. Tokens
    containing { or } are brace notation for multiple paths (e.g.
    `docs/superpowers/{specs,plans}/`), not a single path, and are also
    rejected.
    """
    if any(ch in token for ch in "<>*{}"):
        return False
    if "/" not in token:
        return False
    if any(ch.isspace() for ch in token):
        return False
    return token.startswith(TOP_LEVEL)


def _anchor_from_token(token: str, source: Path, line_no: int) -> Anchor | None:
    # A `::`-suffixed test node ID (pytest/unittest style) names a file, not
    # a path of its own -- strip it the same way a :N line reference is
    # stripped, then resolve what remains.
    path_part = token.split("::", 1)[0]
    if not _looks_like_path(path_part):
        return None
    path, line_ref = _split_line_ref(path_part)
    return Anchor(raw=token, path=path, line_ref=line_ref, source=source, source_line=line_no)


def extract_anchors(text: str, source: Path) -> list[Anchor]:
    """Find every anchor-shaped token in `text`, attributing it to `source`."""
    found: list[Anchor] = []
    seen: set[tuple[Path, int, str]] = set()
    for line_no, line in enumerate(text.splitlines(), start=1):
        tokens = _CODE_SPAN_RE.findall(line) + _LINK_TARGET_RE.findall(line)
        for token in tokens:
            anchor = _anchor_from_token(token, source, line_no)
            if anchor is None:
                continue
            key = (anchor.source, anchor.source_line, anchor.path)
            if key in seen:
                continue
            seen.add(key)
            found.append(anchor)
    return found


def resolve(anchor: Anchor, repo_root: Path) -> bool:
    """True when the anchor's path exists, or is declared absent on purpose."""
    if anchor.path in DECLARED_ABSENT:
        return True
    return (repo_root / anchor.path).exists()


def stale_absences(repo_root: Path) -> list[str]:
    """DECLARED_ABSENT paths that now exist -- the declaration itself is stale.

    Without this check, DECLARED_ABSENT could silently stop checking a path
    that later comes into existence (and might later go stale again without
    anyone noticing, since it's exempted).
    """
    return [path for path in DECLARED_ABSENT if (repo_root / path).exists()]


def stale_skips(repo_root: Path) -> list[str]:
    """SKIP_PATHS entries whose subject no longer exists on disk.

    A skip that outlives its subject is a silent hole: nobody is checking
    that file's anchors, and nobody notices because the file is gone anyway.
    This is what forces a SKIP_PATHS entry to be removed in the same change
    that removes (or renames) the file it names.
    """
    return [prefix for prefix in SKIP_PATHS if not (repo_root / prefix.rstrip("/")).exists()]


def _is_skipped(source: Path) -> bool:
    as_posix = source.as_posix()
    return any(as_posix.startswith(prefix) for prefix in SKIP_PATHS)


def collect(roots: list[Path], repo_root: Path) -> list[Anchor]:
    """Extract anchors from every root, skipping SKIP_PATHS sources.

    Each root may be a directory (walked recursively for *.md files) or a
    single file (read directly regardless of extension), so callers can
    point this at both documentation directories and individual source
    files that cite documentation paths.
    """
    anchors: list[Anchor] = []
    for root in roots:
        abs_root = root if root.is_absolute() else repo_root / root
        if not abs_root.exists():
            # An absent root contributes no anchors. docs/manual/ does not
            # exist yet at the time this script lands; that is not an error.
            continue
        if abs_root.is_file():
            files = [abs_root]
        else:
            files = sorted(abs_root.rglob("*.md"))
        for file_path in files:
            try:
                rel_source = file_path.relative_to(repo_root)
            except ValueError:
                rel_source = file_path
            if _is_skipped(rel_source):
                continue
            text = file_path.read_text(encoding="utf-8")
            anchors.extend(extract_anchors(text, rel_source))
    return anchors


def _run_list(roots: list[Path]) -> int:
    anchors = collect(roots, REPO_ROOT)
    for anchor in anchors:
        print(f"{anchor.source}:{anchor.source_line}  {anchor.path}")
    return 0


def _run_check(roots: list[Path]) -> int:
    anchors = collect(roots, REPO_ROOT)
    failures = 0

    for anchor in anchors:
        if not resolve(anchor, REPO_ROOT):
            print(f"{anchor.source}:{anchor.source_line}  unresolved: {anchor.path}")
            failures += 1

    # These run on every check regardless of which roots were passed: they
    # guard the exception lists themselves, not the anchors just collected.
    # An exemption that outlives its subject is a silent hole, which is
    # worse than no exemption -- so it must be caught no matter what a
    # caller happened to point this script at.
    for path in stale_absences(REPO_ROOT):
        print(f"declared absent but now exists: {path} — update DECLARED_ABSENT")
        failures += 1
    for prefix in stale_skips(REPO_ROOT):
        print(f"SKIP_PATHS entry no longer exists: {prefix} — remove it")
        failures += 1

    print(f"\n{len(anchors)} anchor(s) checked, {failures} failure(s)")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="print every anchor found under ROOT")
    list_parser.add_argument("roots", nargs="*", default=["docs/manual"], metavar="ROOT")

    check_parser = sub.add_parser("check", help="fail if any anchor under ROOT does not resolve")
    check_parser.add_argument("roots", nargs="*", default=["docs/manual"], metavar="ROOT")

    args = parser.parse_args(argv)
    roots = [Path(r) for r in args.roots]
    if args.command == "list":
        return _run_list(roots)
    return _run_check(roots)


if __name__ == "__main__":
    raise SystemExit(main())
