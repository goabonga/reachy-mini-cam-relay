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
uv build                                   # build sdist + wheel into dist/
uv run reachy-mini-cam-relay --help        # run the CLI from the project venv
uv run ruff check src/ tests/              # lint
uv run mypy src/                           # static type check
uv run pytest                              # unit tests + coverage gate
uv run pytest --cov-report=html            # generate htmlcov/ for browsing
uv run cz commit                           # interactive Conventional Commits prompt
uv run cz bump --dry-run                   # preview the next release version
uv run cz bump --yes --changelog           # bump version + update CHANGELOG.md (release-only)
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

Use commitizen for an interactive prompt:

```bash
uv run cz commit
```

Or write the commit manually:

```bash
git commit -m "feat: support multiple Reachy hosts"
git commit -m "fix(reconnect): widen exponential backoff cap to 60s"
git commit -m "docs: add troubleshooting note for Chrome on Wayland"
```

Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`. Use the optional scope to point at a subsystem (e.g. `feat(head-tracking): …`, `ci(packaging): …`).

The release pipeline (`.github/workflows/release.yml`) is gated on a commit whose subject starts with `chore(release):` — the bump itself is performed by commitizen, no manual version edits.

## Code Quality

Before pushing, make sure your code passes the same gates the `Tests` workflow runs on every push and pull request:

```console
uv run ruff check src/ tests/   # lint (fails the build if anything reports)
uv run mypy src/                # static type check
uv run pytest                   # unit tests + coverage gate
```

### Coverage

The pytest config in `pyproject.toml` enforces a minimum coverage threshold (`--cov-fail-under=40`). The bar is intentionally set just below the current state so it acts as a regression guard rather than a hard quality target — raise it as the suite grows. The orchestrating `main()` and the head-tracking module are intentionally not unit-tested (they wire pyvirtualcam, GStreamer, signal handlers and threads together and belong in an integration test layer).

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

4. Make sure the `Tests` CI workflow passes.

5. Wait for review and address feedback if needed.
