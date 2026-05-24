#!/usr/bin/env bash

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

# Build the reachy-mini-cam-relay .deb with debhelper + dh-virtualenv.
#
# Steps:
#   1. Export the pinned runtime dependencies from uv.lock into
#      debian/requirements.txt (the single source of truth is uv.lock).
#   2. Run dpkg-buildpackage to produce ../reachy-mini-cam-relay_*.deb.
#
# The package version comes from debian/changelog, which multicz maintains
# natively via its debian-changelog writer (a fresh stanza is prepended and
# committed on every release). The bundled virtualenv is tied to the build
# host's Python minor version, so build inside a debian:12 container to
# target Raspberry Pi OS / Debian 12 (python3.11). See ci.yml.

set -euo pipefail

cd "$(dirname "$0")/.."

# 1. Pinned runtime requirements from uv.lock.
uv export --frozen --no-dev --no-annotate --no-hashes \
    --no-emit-project -o debian/requirements.txt

# 2. Build a binary-only package (no source build, so a "3.0 (quilt)"
#    source needs no orig tarball; no signing).
dpkg-buildpackage -us -uc -b
