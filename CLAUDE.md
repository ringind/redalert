# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Home Assistant add-on store repository**. `repository.yaml` at the root makes
it addable in HA under *Settings → Add-ons → Add-on Store → ⋮ → Repositories*;
the add-on itself lives in `redalert/`. The add-on drives a Star Trek "Red Alert"
running light across ~6 Philips Hue lamps via the **Hue Entertainment API**
(persistent DTLS stream, ~25 Hz) rather than normal Bridge scenes, optionally
gated by an audio loudness envelope so the light pulses with a locally-provided
alarm sound. It ships an aiohttp REST service **and** an Ingress web UI for
control. HA builds the image locally from `redalert/Dockerfile` (no `image:` key,
no prebuilt registry). Primary docs are German: repo overview in `README.md`,
in-HA docs in `redalert/DOCS.md`. Remote: `github.com/ringind/redalert` (branch
`main`). CI in `.github/workflows/build.yaml` runs `frenck/action-addon-linter`
(strict: it rejects any config.yaml/build.yaml key set to its default value) plus
a `home-assistant/builder --test` build for aarch64 + amd64.

## Layout

```
repository.yaml            store metadata
README.md                  repo overview (German)
tools/generate_cue.py      standalone cue generator (dev tool, not in the image)
redalert/                  the add-on
  config.yaml              manifest: options schema, ingress, ports
  build.yaml               base images: ghcr.io/home-assistant/{arch}-base-python
  Dockerfile               installs requirements, copies rootfs, chmods s6 scripts
  DOCS.md / CHANGELOG.md   "Documentation" / "Changelog" tabs in HA
  translations/{de,en}.yaml  config-option labels shown in the HA UI
  icon.png / logo.png      store graphics (generated, solid-red beacon)
  rootfs/etc/s6-overlay/s6-rc.d/redalert/{type,run,finish}  s6 service (bashio)
  rootfs/app/main.py        REST server + streaming loop + serves panel.html
  rootfs/app/chase.py       comet-sweep math (Larson scanner), no I/O
  rootfs/app/panel.html     Ingress web UI (vanilla JS, relative fetch URLs)
  rootfs/app/redalert_cue.json  precomputed brightness envelope (no audio)
```

## Commands

No build system, linter, or test suite. This code only fully runs inside the HA
add-on container (it reads `/data/options.json`, `/data/credentials.json`).

- Local smoke run: `cd redalert/rootfs/app && REDALERT_LOG_LEVEL=debug python3 main.py`
  — serves `0.0.0.0:8099`; unpaired with empty options since `/data/*` is absent.
  Needs `pip install -r redalert/requirements.txt` (`hue-entertainment`, `aiohttp`).
- Container build (normally the HA Supervisor does this):
  `docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20 -t redalert redalert/`
- Regenerate the audio cue: `python3 tools/generate_cue.py input.mp3 redalert/rootfs/app/redalert_cue.json --fps 25`
  — needs `ffmpeg` + `numpy` (`scipy` optional). Keep `--fps` equal to the runtime `fps`.
- Regenerate store graphics: the generator lives in the scratchpad
  (`mkpng.py`); `icon.png`/`logo.png` are a solid-red beacon on near-black.

## Architecture

Three layers under `redalert/rootfs/app/`:

- **`main.py`** — aiohttp server. Endpoints: `/` (serves `panel.html`),
  `/health` (also the Docker HEALTHCHECK target), `/config` (effective config for the UI),
  `/pair` (one-time Bridge link-button pairing → `/data/credentials.json`),
  `/areas`, `/start`, `/stop`, `/sync`. All mutable runtime state is one
  module-level `state` dict (incl. `state["sync"]` for the live sync loop).
  Options are read **once at import** from `/data/options.json`; the cue is
  loaded once at startup into `state["cue"]`. `REDALERT_LOG_LEVEL` (exported by
  the s6 `run` script from the `log_level` option) sets the logging level.
  `/start` body overrides per call: `area_id`, `effect`, `duration`,
  `cue_offset`, `fps`, `sweep_seconds`, `attack_ms`, `release_ms`, `color`,
  `use_cue`.
- **`chase.py`** — two generators, pure math, no I/O.
  - `RedAlertChase.brightness_for(t)` → per-light `[0,1]` list: triangle-wave
    "comet" (Larson scanner) with `tail_width` falloff over a `base_glow` wash.
  - `RedAlertPulse.step(target, dt)` → uniform level for all lights, an
    exponential attack/release follower toward `target` over a `base_glow` wash;
    `RedAlertPulse.periodic(t, period)` is the no-cue cosine fallback.
- **`redalert_cue.json`** — `{fps, duration_s, gain: [0..1, ...]}`, one value per
  frame from an audio RMS envelope, **no audio data**. `sample_gain()` in
  `main.py` linearly interpolates it at an arbitrary time.

**Effect loop (`_run_effect`):** `handle_start` creates the `EntertainmentSession`,
resolves the area (404/502 returned synchronously), then hands the session to a
single `asyncio` task and returns immediately. The task does the DTLS handshake
(`session.start(area_id)` — several seconds) itself, publishes its start time to
`state["sync"]`, then owns the session lifecycle and `aclose()`s it in `finally`.
Each frame computes `cue_t = elapsed + cue_offset + state["sync"]["correction"]`,
then for `effect == "pulse"` feeds `sample_gain(cue, cue_t)` (or `periodic`) into
`RedAlertPulse.step`; for `"chase"` runs the sweep dimmed by `sample_gain`.
Levels → per-channel `LightColorCommand` scaled by the colour
(`value_8bit * 257 * level`). Frames are paced against an **absolute** clock
(`start + n/fps`), not `sleep(1/fps)`, so the light timeline doesn't drift.
`/sync` (body `{position}`) nudges `state["sync"]["correction"]` toward the
player's real position, clamped to ±`MAX_SYNC_STEP_S` (0.5 s) per call.
Concurrency is guarded by `state["task"]` still running (`/start` →
`already_running`); `/stop` cancels and awaits it.

**Web UI (`panel.html`):** vanilla JS, all `fetch` calls use **relative** URLs so
it works both behind Ingress (path-prefixed) and via published port 8099. Polls
`/config` every 5 s.

**Constraints to keep in mind:**
- Effect color comes from the `color` option / `/start` body (default red);
  `chase.py` only computes brightness, `main.py` applies the color.
- `effect` default is `pulse` (all lamps together); `chase` is the old sweep.
- Channel order = `channel_order` option if set, else the area's native order
  (only meaningful for `chase`).
- The Bridge allows only **one** active Entertainment stream at a time; the DTLS
  handshake is 3–9 s and is the dominant music-sync error source — `/sync` +
  `cue_offset` exist to correct for it (see `DOCS.md` "Synchronisation zur Musik").
- `duration` omitted + cue active → `cue["duration_s"] - cue_offset`; omitted +
  no cue → runs until `/stop`.
- Keep in sync across files when adding an option: `config.yaml` (`options` +
  `schema`), `translations/{de,en}.yaml`, `main.py` (`options.get(...)` /
  `/config` / `/start`), and `panel.html` if it's user-facing.
- The s6 `run` script is `#!/command/with-contenv bashio`; the Dockerfile
  `chmod a+x`s `run` and `finish` (no reliable file mode without git).
