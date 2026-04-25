#!/usr/bin/env bash
# Load v4l2loopback so /dev/video10 appears as "reachy-mini-cam-relay" to the browser.
# exclusive_caps=1 is required for Chrome to accept the device.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "error: run as root (sudo $0)" >&2
    exit 1
fi

modprobe -r v4l2loopback 2>/dev/null || true
modprobe v4l2loopback \
    devices=1 \
    video_nr=10 \
    card_label="reachy-mini-cam-relay" \
    exclusive_caps=1

echo "ok: /dev/video10 ready"
v4l2-ctl --list-devices 2>/dev/null || true
