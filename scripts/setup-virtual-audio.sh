#!/usr/bin/env bash
# Create PulseAudio/PipeWire virtual audio devices for reachy-mini-cam-relay:
#   - "ReachyMic"       : what browsers see as a microphone.
#                         the relay writes the Reachy's incoming audio into it.
#   - "ReachySpeakers"  : what browsers see as an output device.
#                         the relay reads from its monitor and pushes to the Reachy.
set -euo pipefail

MIC_SINK_NAME="reachy_sink"
MIC_SOURCE_NAME="reachy_source"
MIC_DESCRIPTION="ReachyMic"

SPK_SINK_NAME="reachy_speakers"
SPK_DESCRIPTION="ReachySpeakers"

if ! command -v pactl >/dev/null; then
    echo "==> installing pulseaudio-utils (sudo)"
    sudo apt install -y pulseaudio-utils
fi

if ! pactl info >/dev/null 2>&1; then
    echo "error: no PulseAudio/PipeWire server reachable from this session" >&2
    exit 1
fi

sinks="$(pactl list short sinks | awk '{print $2}')"

if grep -qx "$MIC_SINK_NAME" <<< "$sinks"; then
    echo "ok: \"$MIC_DESCRIPTION\" already set up"
else
    echo "==> creating \"$MIC_DESCRIPTION\" (null-sink $MIC_SINK_NAME + remap-source $MIC_SOURCE_NAME)"
    pactl load-module module-null-sink \
        sink_name="$MIC_SINK_NAME" \
        sink_properties=device.description="$MIC_DESCRIPTION" >/dev/null
    pactl load-module module-remap-source \
        master="$MIC_SINK_NAME.monitor" \
        source_name="$MIC_SOURCE_NAME" \
        source_properties=device.description="$MIC_DESCRIPTION" >/dev/null
fi

if grep -qx "$SPK_SINK_NAME" <<< "$sinks"; then
    echo "ok: \"$SPK_DESCRIPTION\" already set up"
else
    echo "==> creating \"$SPK_DESCRIPTION\" (null-sink $SPK_SINK_NAME)"
    pactl load-module module-null-sink \
        sink_name="$SPK_SINK_NAME" \
        sink_properties=device.description="$SPK_DESCRIPTION" >/dev/null
fi

echo "ok: browser selectors now show \"$MIC_DESCRIPTION\" (input) and \"$SPK_DESCRIPTION\" (output)"
