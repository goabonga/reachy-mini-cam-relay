#!/usr/bin/env bash
# Install the gst-plugins-rs webrtc plugin (required by reachy-mini for
# `webrtcsrc`). Tries the prebuilt .deb from goabonga/gst-plugins-rs-rpi
# releases first (~10s); falls back to building from source if unavailable
# or if FROM_SOURCE=1 is set.
set -euo pipefail

PREBUILT_REPO="goabonga/gst-plugins-rs-rpi"
PREBUILT_TAG="${PREBUILT_TAG:-latest}"
FROM_SOURCE="${FROM_SOURCE:-0}"

REPO_URL="https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs.git"
BUILD_DIR="${BUILD_DIR:-/tmp/gst-plugins-rs}"

if gst-inspect-1.0 webrtcsrc >/dev/null 2>&1; then
    echo "ok: webrtcsrc already installed"
    exit 0
fi

_install_prebuilt() {
    local arch
    arch="$(dpkg --print-architecture 2>/dev/null || echo unknown)"
    case "$arch" in
        amd64|arm64) ;;
        *)
            echo "no prebuilt for arch=$arch"
            return 1
            ;;
    esac

    if ! command -v gh >/dev/null; then
        echo "gh CLI not found; install with 'sudo apt install gh' or set FROM_SOURCE=1"
        return 1
    fi

    local tmpdir
    tmpdir="$(mktemp -d)"
    trap "rm -rf '$tmpdir'" RETURN

    local pattern="gst-plugins-rs-webrtc_*_${arch}.deb"
    local download_args=(release download)
    [[ "$PREBUILT_TAG" != "latest" ]] && download_args+=("$PREBUILT_TAG")
    download_args+=(--repo "$PREBUILT_REPO" --pattern "$pattern" --dir "$tmpdir")

    echo "==> fetching $pattern from $PREBUILT_REPO (tag=$PREBUILT_TAG)"
    if ! gh "${download_args[@]}"; then
        echo "download failed"
        return 1
    fi

    local deb
    deb="$(find "$tmpdir" -name '*.deb' -print -quit)"
    if [[ -z "$deb" ]]; then
        echo "no .deb matched"
        return 1
    fi

    echo "==> installing $(basename "$deb") (sudo)"
    sudo dpkg -i "$deb" || sudo apt-get install -f -y
    return 0
}

_install_from_source() {
    echo "==> ensuring build dependencies (sudo)"
    # apt may fail because of UNRELATED broken packages — ignore and re-check below.
    sudo apt install -y \
        cargo \
        git \
        pkg-config \
        libssl-dev \
        libsoup-3.0-dev \
        libnice-dev \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev || true

    local missing=()
    local cmd pc
    for cmd in cargo git pkg-config; do
        command -v "$cmd" >/dev/null || missing+=("$cmd")
    done
    for pc in openssl libsoup-3.0 nice gstreamer-1.0 gstreamer-plugins-base-1.0; do
        pkg-config --exists "$pc" 2>/dev/null || missing+=("$pc (pkg-config)")
    done
    if (( ${#missing[@]} > 0 )); then
        echo "error: missing dependencies: ${missing[*]}" >&2
        echo "check the 'apt install' output above for the cause" >&2
        return 1
    fi

    local plugin_dir gst_minor git_ref so_path
    plugin_dir="$(pkg-config --variable=pluginsdir gstreamer-1.0)"

    gst_minor="$(pkg-config --modversion gstreamer-1.0 | cut -d. -f1,2)"
    git_ref="${GST_PLUGINS_RS_REF:-}"
    if [[ -z "$git_ref" ]]; then
        git_ref="$(git ls-remote --tags --refs "$REPO_URL" "gstreamer-${gst_minor}.*" 2>/dev/null \
            | awk '{print $2}' | sed 's|refs/tags/||' | sort -V | tail -1)"
        [[ -z "$git_ref" ]] && git_ref="main"
    fi
    echo "==> building from ref: $git_ref (override with GST_PLUGINS_RS_REF=...)"

    echo "==> fetching source into $BUILD_DIR"
    if [[ -d "$BUILD_DIR/.git" ]]; then
        git -C "$BUILD_DIR" fetch --tags --depth 1 origin "$git_ref"
        git -C "$BUILD_DIR" checkout --quiet "$git_ref"
    else
        git clone --depth 1 --branch "$git_ref" "$REPO_URL" "$BUILD_DIR"
    fi

    echo "==> building net/webrtc (a few minutes)"
    (cd "$BUILD_DIR/net/webrtc" && cargo build --release)

    so_path="$(find "$BUILD_DIR" -path '*/target/release/libgstrswebrtc.so' -print -quit)"
    if [[ -z "$so_path" ]]; then
        echo "error: libgstrswebrtc.so not produced by build" >&2
        return 1
    fi

    echo "==> installing $so_path -> $plugin_dir (sudo)"
    sudo install -m 0644 "$so_path" "$plugin_dir/"
}

if [[ "$FROM_SOURCE" = "1" ]]; then
    _install_from_source
elif ! _install_prebuilt; then
    echo "==> falling back to source build"
    _install_from_source
fi

echo "==> verifying"
gst-inspect-1.0 webrtcsrc >/dev/null && echo "ok: webrtcsrc now available"
