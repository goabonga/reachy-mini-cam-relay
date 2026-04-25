# reachy-mini-cam-relay

Relay the Reachy Mini **camera, microphone and speakers** over the network into Linux virtual devices, so any browser-based video app (Jitsi, Google Meet, Teams, Discord…) sees them as standard devices — full two-way telepresence.

## How it works

```
                                                              ┌──────────────┐
                                                        ┌───▶ │ /dev/videoN  │ ─▶ browser cam
                                                        │     └──────────────┘
 ┌──────────────┐                   ┌──────────────┐    │     ┌──────────────┐
 │ Reachy Mini  │ ◀──── WebRTC ───▶ │  the relay   │ ───┼───▶ │  ReachyMic   │ ─▶ browser mic
 │   (daemon)   │   port 8443       │              │    │     └──────────────┘
 └──────────────┘                   └──────────────┘    │     ┌──────────────┐
                                                        └◀──  │ ReachySpeak. │ ◀─ browser output
                                                              └──────────────┘
```

The Reachy Mini daemon embeds a GStreamer `webrtcsink` signaling server on port **8443**, handling bidirectional H264/VP8 video + Opus audio. The `reachy-mini` SDK decodes video into BGR frames and audio into F32LE stereo samples, and accepts outgoing audio via `push_audio_sample()`. `reachy-mini-cam-relay` wires this to three virtual devices: a [`v4l2loopback`](https://github.com/umlaeute/v4l2loopback) video device, a PulseAudio remap-source for the mic, and a PulseAudio null-sink for the speakers.

If the Reachy is unreachable at startup or the WebRTC link drops mid-session, the process doesn't exit: it freezes the last frame on `/dev/videoN`, pushes silence to the virtual mic, and retries the connection with exponential backoff (1 s → 60 s). Once the daemon is back, streaming resumes without the user having to re-select devices in their meeting app.

**No app installation is needed on the Reachy** — the camera is streamed by the system daemon, which starts automatically at boot.

## Requirements

- Linux (v4l2loopback is Linux-only; Windows/Mac would need a different sink)
- Python 3.11+
- `v4l2loopback-dkms` kernel module
- GStreamer with WebRTC plugin (`gstreamer1.0-plugins-bad`, `gstreamer1.0-nice`)
- Reachy Mini reachable on the local network (port 8443 open)

## Install

```bash
# system packages
sudo apt install v4l2loopback-dkms \
    gstreamer1.0-plugins-bad gstreamer1.0-nice \
    python3-gi gir1.2-gst-plugins-bad-1.0

# gst-plugins-rs webrtc element (webrtcsrc) — not packaged on Ubuntu.
# By default this downloads a prebuilt .deb from
# https://github.com/goabonga/gst-plugins-rs-rpi/releases (~10 s). Requires
# `gh` CLI. Set FROM_SOURCE=1 to compile from source instead (~5 min).
./scripts/install-gst-webrtc-plugin.sh

# create the virtual camera device
sudo ./scripts/setup-v4l2loopback.sh

# create the virtual mic + speakers (optional, for audio relay)
./scripts/setup-virtual-audio.sh

# project (uv recommended — installs in seconds)
uv sync
# or with pip:
# pip install reachy-mini-cam-relay
```

## Usage

```bash
reachy-mini-cam-relay --reachy-host 192.168.1.231 --device /dev/video10
```

In the meeting app, pick in each selector:
- Camera → **reachy-mini-cam-relay**
- Microphone → **ReachyMic**
- Speakers / audio output → **ReachySpeakers** (selectable directly in Chrome/Firefox, or via `pavucontrol` → Playback tab, per-app)

Resolution is auto-detected from the incoming stream. Optional flags: `--fps 30`, `--no-mic`, `--no-speakers`.

## Known pitfalls

- Chrome ignores v4l2loopback devices unless the module is loaded with `exclusive_caps=1`. The setup script handles that.
- Port 8443 must be reachable on the Reachy. Verify with `nmap -p 8443 <reachy-ip>`.
- The Reachy daemon may hold the camera exclusively. If frames never arrive, hit `POST /api/media/acquire` on the dashboard (port 8000) to re-acquire.
- Building `gst-plugins-rs` requires a recent rustc. `main` is in alpha and often needs the bleeding edge (1.92+). The install script auto-picks a release tag aligned with your GStreamer minor version (e.g. `gstreamer-1.26.x`, MSRV ~1.82), which works with stock `rustup` stable. Override with `GST_PLUGINS_RS_REF=<ref> ./scripts/install-gst-webrtc-plugin.sh`.

## Development

See [CONTRIBUTING.md](https://github.com/goabonga/reachy-mini-cam-relay/blob/main/CONTRIBUTING.md) for the full contribution guide. By participating you agree to the [Code of Conduct](https://github.com/goabonga/reachy-mini-cam-relay/blob/main/CODE_OF_CONDUCT.md).

## License

[MIT](https://github.com/goabonga/reachy-mini-cam-relay/blob/main/LICENSE) © Chris
