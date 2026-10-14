#!/usr/bin/env bash
# Regenerate requirements/action.txt: runtime deps only, hashes for every available
# distribution (all platforms), resolved universally for Python >= 3.11.
set -euo pipefail
cd "$(dirname "$0")/.."
# --extra signing: the action must be able to verify signatures (Phase 5), and it
# installs with --require-hashes, so cryptography and its wheels are locked here.
# (cryptography was already in the lock transitively, via pyjwt; the extra makes the
# dependency direct and survives pyjwt ever dropping it.)
uv pip compile pyproject.toml requirements/build.in --extra signing --generate-hashes \
  --universal --python-version 3.11 --no-header -o requirements/action.txt
# Prepend the header with cat, not sed: the text contains backticks, which sed's
# double-quoted replacement would hand to the shell as command substitution — the
# bug that once blanked two lines of this header.
tmp="requirements/.action.txt.tmp"
cat >"$tmp" <<'HEADER'
# Runtime dependencies for the GitHub Action (plus the hatchling build backend),
# hash-pinned for every platform wheel. Regenerate with
# scripts/lock_action_requirements.sh. The action installs these with
# `pip install --require-hashes`, then Placard itself from its own checkout with
# `--no-deps --no-build-isolation`, so PyPI is never trusted for Placard and nothing
# unpinned is fetched for the build (Phase 4 §3, go memo ruling 1).

HEADER
cat requirements/action.txt >>"$tmp"
mv "$tmp" requirements/action.txt
echo "wrote requirements/action.txt"
