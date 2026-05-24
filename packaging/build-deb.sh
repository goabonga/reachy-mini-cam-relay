#!/usr/bin/env bash

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

# Build the reachy-mini-cam-relay .deb with debhelper + dh-virtualenv.
#
# Steps:
#   1. Export the pinned runtime dependencies from uv.lock into
#      debian/requirements.txt (the single source of truth is uv.lock).
#   2. Optionally set the package version (VERSION env) into the Debian
#      changelog so the .deb version matches the multicz release.
#   3. Run dpkg-buildpackage to produce ../reachy-mini-cam-relay_*.deb.
#
# The bundled virtualenv is tied to the build host's Python minor version,
# so build inside a debian:12 container to target Raspberry Pi OS / Debian
# 12 (python3.11). See .github/workflows/ci.yml.

set -euo pipefail

cd "$(dirname "$0")/.."

# 1. Pinned runtime requirements from uv.lock.
uv export --frozen --no-dev --no-annotate --no-hashes \
    --no-emit-project -o debian/requirements.txt

# 2. Stamp the release version into debian/changelog when provided.
if [ -n "${VERSION:-}" ]; then
    export DEBFULLNAME="${DEBFULLNAME:-Chris}"
    export DEBEMAIL="${DEBEMAIL:-goabonga@pm.me}"
    export EDITOR=/bin/true  # never open an editor in CI
    dch --newversion "$VERSION" --distribution unstable --force-bad-version \
        "Release $VERSION"
    dch --release --distribution unstable ""
fi

# 3. Build a binary-only package (no source upload signing).
dpkg-buildpackage -us -uc -b
