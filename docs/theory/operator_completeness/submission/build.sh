#!/bin/bash
# Build the submission PDF. Requires: brew install tectonic (already done).
export PATH=/opt/homebrew/bin:$PATH
cd "$(dirname "$0")"
tectonic -X compile paper_lncs.tex && echo "OK -> paper_lncs.pdf"
