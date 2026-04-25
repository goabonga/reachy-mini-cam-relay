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
uv run python -m compileall -q src/        # syntax check
uv run ruff check src/                     # lint
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

Before pushing, make sure your code passes:

```console
uv run python -m compileall -q src/    # syntax
uv run ruff check src/                 # lint
```

The `Tests` workflow (`.github/workflows/tests.yml`) runs the same checks on every push and pull request, plus a smoke import.

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
