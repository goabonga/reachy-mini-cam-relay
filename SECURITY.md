# Security Policy

## Supported versions

Security fixes are applied only to the latest released version on the
`main` branch (and the matching PyPI release of `reachy-mini-cam-relay`).

| Version | Supported |
| --- | --- |
| latest release | ✅ |
| older releases | ❌ |

## Reporting a vulnerability

**Please do not open a public issue.** GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
is the preferred channel:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the issue with reproduction steps and a suggested mitigation.

If you cannot use GitHub's form, email **goabonga@pm.me** with the same
information. PGP encryption is available on request.

You can expect an acknowledgement within **3 business days**, a triage
assessment within **10 business days**, and a fix or written mitigation
plan before any public disclosure.

## Scope

`reachy-mini-cam-relay` is a local CLI that connects to a Reachy Mini over
WebRTC and relays its camera, microphone and speakers into Linux virtual
devices. Security-relevant reports typically concern:

- the subprocess invocations of PulseAudio tools (`pactl`, `pacat`,
  `parec`) and the GStreamer/v4l2loopback setup scripts under `scripts/`;
- handling of the media streams received from the Reachy.

Vulnerabilities in third-party dependencies (e.g. `reachy-mini` or its
transitive web stack) should be reported upstream, but please let us know
so the pinned ranges can be bumped.

Thanks for helping keep the project and its users safe.
