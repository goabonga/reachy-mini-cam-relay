# reachy-mini-cam-relay

[![CI](https://github.com/goabonga/reachy-mini-cam-relay/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/goabonga/reachy-mini-cam-relay/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/goabonga/reachy-mini-cam-relay.svg)](https://github.com/goabonga/reachy-mini-cam-relay/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/goabonga/reachy-mini-cam-relay/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

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

### Debian / Ubuntu / Raspberry Pi OS (`.deb`)

Download the package for your architecture (`amd64` or `arm64`) from the
[latest release](https://github.com/goabonga/reachy-mini-cam-relay/releases/latest),
then let apt pull its system dependencies:

```bash
sudo apt install ./reachy-mini-cam-relay_*_amd64.deb
```

The package bundles the Python app and all its Python dependencies in a
self-contained virtualenv under `/opt/venvs`, exposes the
`reachy-mini-cam-relay` command, ships a systemd **user** service template,
and installs the setup scripts under `/usr/share/reachy-mini-cam-relay/scripts/`.

One-time host setup (the GStreamer WebRTC element is not packaged in Debian,
and the virtual devices must be created):

```bash
# gst-plugins-rs webrtc element (webrtcsrc) — not packaged in Debian.
# Downloads a prebuilt .deb from
# https://github.com/goabonga/gst-plugins-rs-rpi/releases (~10 s, needs `gh`),
# or set FROM_SOURCE=1 to compile from source (~5 min).
/usr/share/reachy-mini-cam-relay/scripts/install-gst-webrtc-plugin.sh

# create the virtual camera device
sudo /usr/share/reachy-mini-cam-relay/scripts/setup-v4l2loopback.sh

# create the virtual mic + speakers (optional, for audio relay)
/usr/share/reachy-mini-cam-relay/scripts/setup-virtual-audio.sh
```

### From source (development)

```bash
sudo apt install v4l2loopback-dkms \
    gstreamer1.0-plugins-bad gstreamer1.0-nice \
    python3-gi gir1.2-gst-plugins-bad-1.0
./scripts/install-gst-webrtc-plugin.sh
sudo ./scripts/setup-v4l2loopback.sh
./scripts/setup-virtual-audio.sh
uv sync   # build a local dev virtualenv from uv.lock
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

### As a systemd service

The `.deb` ships a systemd **user** service template (`%i` = the Reachy host).
Audio runs in your user session, so enable it as a user unit:

```bash
systemctl --user enable --now reachy-mini-cam-relay@192.168.1.231
journalctl --user -u reachy-mini-cam-relay@192.168.1.231 -f
```

## Known pitfalls

- Chrome ignores v4l2loopback devices unless the module is loaded with `exclusive_caps=1`. The setup script handles that.
- Port 8443 must be reachable on the Reachy. Verify with `nmap -p 8443 <reachy-ip>`.
- The Reachy daemon may hold the camera exclusively. If frames never arrive, hit `POST /api/media/acquire` on the dashboard (port 8000) to re-acquire.
- Building `gst-plugins-rs` requires a recent rustc. `main` is in alpha and often needs the bleeding edge (1.92+). The install script auto-picks a release tag aligned with your GStreamer minor version (e.g. `gstreamer-1.26.x`, MSRV ~1.82), which works with stock `rustup` stable. Override with `GST_PLUGINS_RS_REF=<ref> ./scripts/install-gst-webrtc-plugin.sh`.

## Development

See [CONTRIBUTING.md](https://github.com/goabonga/reachy-mini-cam-relay/blob/main/CONTRIBUTING.md) for the full contribution guide. By participating you agree to the [Code of Conduct](https://github.com/goabonga/reachy-mini-cam-relay/blob/main/CODE_OF_CONDUCT.md).

## License

[MIT](https://github.com/goabonga/reachy-mini-cam-relay/blob/main/LICENSE) © Chris
