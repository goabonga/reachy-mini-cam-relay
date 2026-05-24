# Contributing

Thanks for your interest in contributing to **reachy-mini-cam-relay**!

By participating in this project you agree to abide by the [Code of Conduct](https://github.com/goabonga/reachy-mini-cam-relay/blob/main/CODE_OF_CONDUCT.md).

## Prerequisites

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) (recommended for speed and reproducibility)
- A reachable Reachy Mini on the local network for end-to-end testing
- `gh` CLI (used by the prebuilt-plugin install path)
- System packages: `v4l2loopback-dkms`, `pulseaudio-utils`, `gstreamer1.0-plugins-bad`, `gstreamer1.0-nice`, `python3-gi`, `gir1.2-gst-plugins-bad-1.0`

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:

   ```bash
   git clone git@github.com:<your-username>/reachy-mini-cam-relay.git
   cd reachy-mini-cam-relay
   ```

3. **Install** the project and its dev tools:

   ```bash
   uv sync                       # base install
   # or, on the head-tracking branch:
   uv sync --extra head-tracking
   uv run pre-commit install     # install the pre-commit + commit-msg hooks
   ```

4. **One-time system setup** (required to actually run the relay):

   ```bash
   ./scripts/install-gst-webrtc-plugin.sh
   sudo ./scripts/setup-v4l2loopback.sh
   ./scripts/setup-virtual-audio.sh
   ```

## Available commands

```console
uv sync                                    # install / re-sync from uv.lock
uv sync --frozen                           # install strictly from the lock (CI mode)
uv sync --extra head-tracking              # add the optional MediaPipe extras (on that branch)
uv lock                                    # refresh uv.lock after editing pyproject.toml
./packaging/build-deb.sh                   # build the Debian package (.deb)
uv run reachy-mini-cam-relay --help        # run the CLI from the project venv
uv run ruff check src/ tests/              # lint
uv run mypy src/                           # static type check
uv run pytest                              # unit tests + coverage gate
uv run pytest --cov-report=html            # generate htmlcov/ for browsing
uv run pre-commit run --all-files          # run the local hooks (lint, headers, commit-msg)
uv tool run multicz validate --strict      # validate Conventional Commits + config
uv tool run multicz plan                   # preview the next release version
```

## Branch naming

Branches must be created off `main` using one of the following prefixes:

| Prefix      | Usage                  | Example                              |
|-------------|------------------------|--------------------------------------|
| `feat/`     | New feature            | `feat/head-tracking`                 |
| `fix/`      | Bug fix                | `fix/reconnect-on-stale-frame`       |
| `docs/`     | Documentation          | `docs/clarify-systemd-instructions`  |
| `refactor/` | Code refactoring       | `refactor/extract-session-class`     |
| `test/`     | Adding/updating tests  | `test/add-cli-arg-coverage`          |
| `chore/`    | Maintenance            | `chore/bump-mediapipe`               |

```bash
git checkout -b feat/my-feature
```

## Commits

This project follows [Conventional Commits](https://www.conventionalcommits.org/). Every commit message must follow this format:

```
<type>(<optional scope>): <description>
```

Write the commit message directly:

```bash
git commit -m "feat: support multiple Reachy hosts"
git commit -m "fix(reconnect): widen exponential backoff cap to 60s"
git commit -m "docs: add troubleshooting note for Chrome on Wayland"
```

Valid types: `feat`, `fix`, `perf`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`. Use the optional scope to point at a subsystem (e.g. `feat(head-tracking): …`, `ci(packaging): …`). Do not append `Co-Authored-By` trailers.

Only `feat`, `fix` and `perf` commits that touch the tracked paths (`src/**`, `pyproject.toml`) trigger a release; everything else is maintenance. The version bump and CHANGELOG are computed by [multicz](https://github.com/goabonga/multicz) — never edit the version or CHANGELOG by hand.

## Code Quality

Before pushing, make sure your code passes the same gates the `ci` workflow runs on every push and pull request:

```console
uv run ruff check src/ tests/   # lint (fails the build if anything reports)
uv run mypy src/                # static type check
uv run pytest                   # unit tests + coverage gate
```

### Coverage

The pytest config in `pyproject.toml` enforces a **100% coverage gate** (`--cov-fail-under=100`). New code must come with tests that keep the suite at 100% — use `monkeypatch`/mocks to cover the orchestration glue (pyvirtualcam, GStreamer, signal handlers and threads) rather than touching real hardware.

`htmlcov/` is git-ignored — generate it locally with `uv run pytest --cov-report=html` and open `htmlcov/index.html` to drill into uncovered lines.

### Type checking

`mypy` is configured permissively in `pyproject.toml` (`ignore_missing_imports = true`, `disallow_untyped_defs = false`) so untyped third-party libraries don't drown the output, but `check_untyped_defs = true` still inspects the body of every function. Expand the strictness as the codebase matures.

### Adding tests

Unit tests live in `tests/` and follow standard pytest discovery. Use `monkeypatch` for boundary mocks (subprocess, third-party SDK calls) and prefer testing pure logic (the `Session` class, parsing helpers, the backoff sequence) over orchestration. Keep tests fast — no real network or hardware access.

## Pull Request

1. Push your branch to your fork:

   ```bash
   git push origin feat/my-feature
   ```

2. Open a **Pull Request** against the `main` branch of `goabonga/reachy-mini-cam-relay`.

3. In your PR description:
   - Describe **what** the PR does and **why**.
   - Reference related issues (e.g. `Closes #42`).
   - Include steps to test or verify the changes (a quick `journalctl --user -u reachy-mini-cam-relay@<host>` snippet usually goes a long way for runtime regressions).

4. Make sure the `ci` workflow passes.

5. Wait for review and address feedback if needed.

### Release

Releases are automated. On every push to `main`, the `ci` workflow runs
`multicz bump`: it computes the next version from the Conventional Commits
since the last tag, updates `pyproject.toml`,
`src/reachy_mini_cam_relay/__init__.py` and `CHANGELOG.md`, creates a
signed commit and tag, builds the Debian packages (amd64 + arm64) and
attaches them to a GitHub Release. Maintainers do not bump versions or edit
the changelog by hand.
