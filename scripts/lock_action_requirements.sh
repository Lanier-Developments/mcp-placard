#!/usr/bin/env bash
# Regenerate requirements/action.txt: runtime deps only, hashes for every available
# distribution (all platforms), resolved universally for Python >= 3.11.
set -euo pipefail
cd "$(dirname "$0")/.."
uv pip compile pyproject.toml requirements/build.in --generate-hashes --universal \
  --python-version 3.11 --no-header -o requirements/action.txt
sed -i.bak "1i\\
# Runtime dependencies for the GitHub Action (plus the hatchling build backend),\\
# hash-pinned for every platform wheel. Regenerate with\\
# scripts/lock_action_requirements.sh. The action installs these with\\
# `pip install --require-hashes`, then Placard itself from its own checkout with\\
# `--no-deps --no-build-isolation`, so PyPI is never trusted for Placard and nothing\\
# unpinned is fetched for the build (Phase 4 §3, go memo ruling 1).\\
" requirements/action.txt && rm -f requirements/action.txt.bak
# Runtime dependencies for the GitHub Action, hash-pinned for every platform wheel.\
# Regenerate with scripts/lock_action_requirements.sh; the action installs these with\
# `pip install --require-hashes` and then Placard itself from its own checkout with\
# `--no-deps`, so PyPI is never trusted for Placard and every dependency is pinned by\
# hash (Phase 4 §3, go memo ruling 1).\
' requirements/action.txt && rm -f requirements/action.txt.bak
echo "wrote requirements/action.txt"
