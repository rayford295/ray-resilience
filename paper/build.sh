#!/bin/sh
# Build the OASIS short paper. TinyTeX is expected at ~/Library/TinyTeX
# (not on PATH); pass TEXBIN to override.
set -e
TEXBIN="${TEXBIN:-$HOME/Library/TinyTeX/bin/universal-darwin}"
cd "$(dirname "$0")"
"$TEXBIN/pdflatex" -interaction=nonstopmode ray-resilience-oasis2026.tex
"$TEXBIN/bibtex" ray-resilience-oasis2026
"$TEXBIN/pdflatex" -interaction=nonstopmode ray-resilience-oasis2026.tex
"$TEXBIN/pdflatex" -interaction=nonstopmode ray-resilience-oasis2026.tex
echo "Built: paper/ray-resilience-oasis2026.pdf"
