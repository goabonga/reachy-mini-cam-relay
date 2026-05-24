#!/usr/bin/env bash

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

set -euo pipefail

changed=$(git show --name-only --pretty='' HEAD)

case "$changed" in
    *.github/workflows/*)
        prefix="ci"
        ;;
    *pyproject.toml* | *uv.lock*)
        prefix="chore(deps)"
        ;;
    *)
        prefix="chore(deps)"
        ;;
esac

original=$(git log -1 --pretty=%B HEAD)

subject=$(printf '%s' "$original" \
    | head -n 1 \
    | sed -E 's/^[a-z-]+(\([^)]+\))?:[[:space:]]*//' \
    | sed 's/^[Bb]ump /bump /')

body=$(printf '%s' "$original" \
    | tail -n +2 \
    | sed '/^Co-Authored-By:/d')

if [ -n "$body" ]; then
    new_msg=$(printf '%s: %s\n\n%s' "$prefix" "$subject" "$body")
else
    new_msg=$(printf '%s: %s' "$prefix" "$subject")
fi

git commit --amend --reset-author -m "$new_msg" --quiet
