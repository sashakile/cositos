#!/usr/bin/env bash
# Vendors front/src/*.js (zero external deps) into docs/vendor/cositos-front/ before every
# Quarto render, so tutorials/web-ojs.qmd can import() the real @cositos/front runtime
# client-side (browsers can't reach outside the served docs/ tree). Regenerated on every
# build — docs/vendor/ is gitignored; never edit its contents by hand.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
mkdir -p vendor/cositos-front
cp ../front/src/*.js vendor/cositos-front/
