#!/usr/bin/env python
"""Single-column Word draft of the paper, for co-author editing.

Reads the acmart source, drops the acmart-only plumbing (CCS concepts,
\\maketitle, bibliography commands), turns the author block into metadata,
inserts the concept figures from figures/ with captions, and converts with
pandoc (bundled via pypandoc_binary) using the ACM SIG proceedings CSL for
the reference list. The LaTeX source stays the source of truth; this is a
view of it.

    python paper/build_docx.py            # writes paper/ray-resilience-oasis2026-draft.docx
"""

from __future__ import annotations

import re
from pathlib import Path

import pypandoc

HERE = Path(__file__).resolve().parent
TEX = HERE / "ray-resilience-oasis2026.tex"
OUT = HERE / "ray-resilience-oasis2026-draft.docx"
CSL = HERE / "figures" / "acm-sig-proceedings.csl"

#: (section title the figure follows, figure file, caption). The figure is
#: placed after the first paragraph of that section.
FIGURES = [
    ("The Steward Harness", "figures/fig1_architecture.png",
     "RAY is three loosely coupled planes on top of one harness. The Steward Harness sits between "
     "every pipeline stage and between the model and every sentence it emits, enforcing outcome, "
     "process, and institutional validity, plus a per-claim verifiability axis. The distribution "
     "plane is verified by a CI gate that fails the deploy on violation."),
    ("Citation by default.", "figures/fig2_lifecycle.png",
     "One question through the agent gateway. Two deterministic gates bracket the model: the "
     "claim-plane pre-check decides whether this role may ask this of this place at this resolution "
     "before any model call, and the citation post-check refuses any factual sentence without an "
     "artifact identifier. The audit stores the H3 cell, not the point, and the question as a digest."),
    ("Verifiability.", "figures/fig3_verifiability.png",
     "The verifiability axis states what a reader can do to check a claim, with weakest-link "
     "aggregation across an answer's citations. Re-derivable evidence covers the case where license "
     "terms forbid retention: the harness attests to the request plus a response digest, a record "
     "that is publishable precisely because it holds no content. The license attribute gates "
     "redistribution by rule."),
    ("System and Deep Cases", "figures/fig4_cases.png",
     "Three deep cases across two hazard types, behind a nationwide hourly watch. Every number is a "
     "committed, hashed artifact; every card carries a declared unknown alongside its findings."),
]


def parse_authors(tex: str) -> list[str]:
    """`\\author{Name}` ... `\\institution{Dept, Univ}` ... `\\email{x}` -> 'Name (Dept, Univ) — x'."""
    out = []
    for m in re.finditer(r"\\author\{([^}]*)\}(.*?)(?=\\author\{|\\begin\{abstract\})", tex, re.S):
        name, block = m.group(1), m.group(2)
        inst = re.search(r"\\institution\{([^}]*)\}", block)
        mail = re.search(r"\\email\{([^}]*)\}", block)
        parts = [name]
        if inst:
            parts.append(inst.group(1).replace("\\&", "&"))
        if mail:
            parts.append(mail.group(1))
        out.append(" — ".join(parts))
    return out


def body_from(tex: str) -> str:
    start = tex.index("\\begin{abstract}")
    end = tex.index("\\end{document}")
    body = tex[start:end]
    body = re.sub(r"\\begin\{CCSXML\}.*?\\end\{CCSXML\}", "", body, flags=re.S)
    body = re.sub(r"\\ccsdesc(\[[^\]]*\])?\{[^}]*\}\n?", "", body)
    body = re.sub(r"\\keywords\{([^}]*)\}", lambda m: "\n\\textbf{Keywords:} " + " ".join(m.group(1).split()) + "\n", body)
    body = body.replace("\\maketitle", "")
    body = re.sub(r"\\begin\{acks\}(.*?)\\end\{acks\}", r"\\section*{Acknowledgments}\1", body, flags=re.S)
    body = re.sub(r"\\bibliographystyle\{[^}]*\}\n?", "", body)
    body = re.sub(r"\\bibliography\{[^}]*\}\n?", "", body)
    # \label after \section confuses nothing, but the docx has no cross-refs: spell them out.
    body = body.replace("Section~\\ref{sec:vlm}", "Section 4")
    body = body.replace("Section~\\ref{sec:incidents}", "Section 5")
    body = body.replace("Table~\\ref{tab:vlm}", "Table 1")
    return body


def insert_figures(body: str) -> str:
    for number, (anchor, path, caption) in enumerate(FIGURES, start=1):
        caption = f"Figure {number}. {caption}"  # pandoc's docx captions carry no automatic number
        # find the anchor (a \section{...} title or a \textbf{...} lead-in), then the end of its first paragraph
        m = re.search(r"\\section\{" + re.escape(anchor) + r"\}[^\n]*\n(?:\\label\{[^}]*\}\n)?", body) \
            or re.search(r"\\textbf\{" + re.escape(anchor) + r"\}", body)
        if not m:
            raise SystemExit(f"figure anchor not found: {anchor}")
        para_end = body.find("\n\n", m.end())
        fig = (
            "\n\n\\begin{figure}[h]\n\\centering\n"
            f"\\includegraphics[width=\\linewidth]{{{path}}}\n"
            f"\\caption{{{caption}}}\n\\end{{figure}}\n"
        )
        body = body[:para_end] + fig + body[para_end:]
    return body


def main() -> int:
    tex = TEX.read_text(encoding="utf-8")
    title = re.search(r"\\title\{([^}]*)\}", tex).group(1)
    subtitle = re.search(r"\\subtitle\{([^}]*)\}", tex).group(1)
    authors = parse_authors(tex)
    body = insert_figures(body_from(tex))

    args = [
        "--citeproc",
        f"--bibliography={HERE / 'references.bib'}",
        f"--csl={CSL}",
        f"--resource-path={HERE}",
        "-M", f"title={title}",
        "-M", f"subtitle={subtitle}",
        "-M", "reference-section-title=References",
        "-M", "link-citations=true",
        "-M", "date=Draft for co-author editing — single column; the LaTeX source remains the submission format",
    ]
    for a in authors:
        args += ["-M", f"author={a}"]
    pypandoc.convert_text(body, "docx", format="latex", outputfile=str(OUT), extra_args=args)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB); authors: {len(authors)}; figures: {len(FIGURES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
