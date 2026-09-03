# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Home Assistant add-on store repository**. `repository.yaml` at the root makes
it addable in HA under *Settings → Add-ons → Add-on Store → ⋮ → Repositories*;
the add-on itself lives in `redalert/`. The add-on drives a Star Trek "Red Alert"
scene across ~6 Philips Hue lamps via the **Hue Entertainment API** (persistent
DTLS stream, ~25 Hz) rather than normal Bridge scenes — two effects, `pulse`
(default: all lamps together on the beat) and `chase` (a comet with a tail) —
timed to a locally-provided alarm sound via a precomputed loudness envelope. It
ships an aiohttp REST service **and** an Ingress web UI for control. HA builds the
image locally from `redalert/Dockerfile` (no `image:` key, no prebuilt registry).
Primary docs are German: repo overview in `README.md`, in-HA docs in
`redalert/DOCS.md`.

**Remote & CI:** `github.com/ringind/redalert` (branch `main`).
`.github/workflows/build.yaml` = `frenck/action-addon-linter` (strict: rejects any
*known HA* config.yaml/build.yaml key left at its default) + a `docker buildx`
test build for amd64 and (emulated) aarch64. Green in ~4 min. After every push,
watch it: `RUN=$(gh run list --workflow=build.yaml --branch main -L1 --json databaseId -q '.[0].databaseId'); until [ "$(gh run view $RUN --json status -q .status)" = completed ]; do sleep 30; done; gh run view $RUN --json conclusion,jobs -q '.conclusion, (.jobs[]|"\(.name)=\(.conclusion)")'`
(run it backgrounded). Releases are tags `vX.Y.Z` on a green commit — see the
`release` skill.

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
  rootfs/app/chase.py       RedAlertPulse (beat gate) + RedAlertChase (comet+tail), no I/O
  rootfs/app/panel.html     Ingress web UI (vanilla JS, relative fetch URLs)
  rootfs/app/redalert_cue.json  precomputed brightness envelope (no audio)
```

## Commands

No build system, linter, or test suite. Current version: **1.1.7**.

- `python3 -m py_compile redalert/rootfs/app/main.py redalert/rootfs/app/chase.py`
  after every code change — the only static check available.
- Container build (normally the HA Supervisor does this):
  `docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20 -t redalert redalert/`
- Regenerate the audio cue: `python3 tools/generate_cue.py input.mp3 redalert/rootfs/app/redalert_cue.json --fps 25`
  — needs `ffmpeg` + `numpy` (`scipy` optional). Keep `--fps` equal to the runtime `fps`.
- Regenerate store graphics: the generator lives in the scratchpad
  (`mkpng.py`); `icon.png`/`logo.png` are a solid-red beacon on near-black.
- Cut a versioned release: see the **`release`** skill.

## Local testing (real Hue bridge)

`main.py` only fully runs outside the container because `DATA_DIR` is overridable:
`REDALERT_DATA_DIR` (default `/data`). The dev setup is a venv at `.venv` and a
`devdata/` dir — **both gitignored; do not `rm -rf devdata`**, it holds
`credentials.json` and deleting it forces a physical re-pair (link button).

```bash
python3 -m venv .venv && .venv/bin/pip install -r redalert/requirements.txt   # once
mkdir -p devdata
REDALERT_DATA_DIR=./devdata REDALERT_LOG_LEVEL=debug .venv/bin/python redalert/rootfs/app/main.py &
B=http://localhost:8099
until curl -sf -o /dev/null $B/health; do sleep 0.5; done          # bind race: ~3 s, always gate
# pair only if devdata/credentials.json is missing (needs a fresh link-button press):
#   curl -s -X POST $B/pair -H 'Content-Type: application/json' -d '{"bridge_ip":"<ip>"}'
curl -s -X POST $B/start -H 'Content-Type: application/json' \
  -d '{"area_id":"<area>","effect":"pulse","duration":20,"use_cue":true}'
```

- The maintainer's test rig (may change): bridge `192.168.178.84`, area
  **Houseparty Büro** = `226c7c2a-0a6d-4b01-a28a-8b29fd8cb219` (3 channels).
  `GET /areas` lists current ones. (An earlier rig was `192.168.178.50` / **Flur**
  `18aa512d-…`; `devdata/credentials.<ip>.json.bak` files hold prior pairings so
  you don't have to re-press a link button to switch back.)
- The DTLS handshake logs a `ServerHello timeout … resending` retry almost every
  time and takes ~3–9 s — **normal**, not a failure. `/start` returns *before* it
  (`_run_effect` does the handshake), so poll `/health` `running` for real state.
- `_run_effect` runs the effect for `duration` s at exactly `fps` (absolute-clock
  pacing) — verify with the `Effekt beendet (N Frames)` log line: `N ≈ duration*fps`.
- See the **`smoke-test`** skill for the full loop (start server, run, wait, report, stop).

## Architecture

Three layers under `redalert/rootfs/app/`:

- **`main.py`** — aiohttp server. Endpoints: `/` (serves `panel.html`),
  `/health` (also the Docker HEALTHCHECK target), `/config` (effective config for the UI),
  `/pair` (one-time Bridge link-button pairing → `/data/credentials.json`),
  `/areas`, `/start`, `/stop`, `/sync`, `/identify`. All mutable runtime state is
  one module-level `state` dict (incl. `state["sync"]` for the live sync loop).
  Options are read **once at import** from `/data/options.json`; the cue is
  loaded once at startup into `state["cue"]`. `REDALERT_LOG_LEVEL` (exported by
  the s6 `run` script from the `log_level` option) sets the logging level.
  `/start` body overrides per call: `area_id`, `effect`, `duration`,
  `cue_offset`, `fps`, `sweep_seconds`, `attack_ms`, `release_ms`, `glow_low`,
  `glow_high`, `color`, `use_cue`, `restore_state`, `channel_order` (list[int] or
  `"2,3,1,0"` string, parsed by `_parse_channel_order`; must be exactly the
  area's channels reordered). `use_cue` defaults per effect — **on for `pulse`,
  off for `chase`** (`bool(body.get("use_cue", effect == "pulse"))`); the cue is
  beat-sync and only a `pulse` feature. `effect` is resolved before `use_cue` for
  this reason.
  `/identify` (body `area_id?`, `channel_id?`, `seconds?`, `color?`,
  `restore_state?`) lights one channel — or, with `channel_id` omitted, every
  channel in turn (~`seconds`+0.4 s gap each) — over a single DTLS handshake, to
  map channel_id → physical lamp. Shares the `state["task"]` slot with `/start`
  (`already_running` guard, `/stop` cancels it).
- **`chase.py`** — two generators, pure math, no I/O. Both emit a **0..1 shape**;
  `_run_effect` maps it onto `[glow_low, glow_high]` (options / `/start` body,
  clamped, `glow_high` forced ≥ `glow_low`) — so "0" is the resting glow, not
  necessarily black.
  - `RedAlertChase.brightness_for(t)` → per-light `[0,1]` list. Per lamp, a pure
    function of `phase` (fraction of `sweep_seconds` since the head passed it):
    a flat `1.0` head of width `self.top` (= `max(peak_frac, 1/n + overlap_frac)`
    for n≥2 — wider than the lamp spacing so two adjacent lamps hold 100% together
    for `overlap_frac` of a sweep), then `exp(-·/decay_frac)` fall shifted to hit
    0 at `fade_frac`, held at 0 (resting glow) until the raised-cosine `attack_frac`
    rise. Flat top ⇒ peak is sampling-proof (no shimmer). `sweep_seconds` = one loop.
  - `RedAlertPulse.step(level, dt)` → uniform level for all lights. A Schmitt gate
    (on above `hi`, off after `hold_s` below `lo`) turns the noisy cue into a
    stable 0/1, then a **linear** slew hits exactly 1.0 in `attack_s` / 0.0 in
    `release_s` (keep release < attack). `RedAlertPulse.periodic(t, period)` is
    the no-cue cosine fallback fed into the same gate.
- **`redalert_cue.json`** — `{fps, duration_s, gain: [0..1, ...]}`, one value per
  frame from an audio RMS envelope, **no audio data**. `sample_gain()` in
  `main.py` linearly interpolates it at an arbitrary time.

**Effect loop (`_run_effect`):** `handle_start` creates the `EntertainmentSession`,
resolves the area (404/502 returned synchronously), then hands the session to a
single `asyncio` task and returns immediately. The task, before the handshake,
snapshots the area's lights via Hue CLIP v2 (`capture_light_state`, unless
`restore_state` is false); does the DTLS handshake (`session.start(area_id)` —
several seconds); publishes its start time to `state["sync"]`; owns the session
lifecycle and `aclose()`s it in `finally`, then `restore_light_state` PUTs the
snapshot back (the Bridge also auto-restores after streaming; this is belt-and-
suspenders and re-offs lights that were off).
Each frame computes `cue_t = elapsed + cue_offset + state["sync"]["correction"]`,
then for `effect == "pulse"` feeds `sample_gain(cue, cue_t)` (or `periodic`) into
`RedAlertPulse.step`; for `"chase"` it's `chase.brightness_for(elapsed)`, then —
only if `use_cue` was set true for this chase run (off by default) — multiplied by
`CHASE_CUE_FLOOR + (1-floor)*gate` where
`gate` is `sample_gain` run through the **same** `pulse` gate+slew (the raw gain
flickers the comet), so the cue dims the comet between `CHASE_CUE_FLOOR` and 1.0.
The resulting 0..1 levels are then mapped to `glow_low + (glow_high-glow_low)*lvl`
(one line before `session.send`), so between pulses lamps rest at `glow_low`, not 0.
Levels → per-channel `LightColorCommand` scaled by the colour
(`value_8bit * 257 * level`). Frames are paced against an **absolute** clock
(`start + n/fps`), not `sleep(1/fps)`, so the light timeline doesn't drift.
`/sync` (body `{position}`) nudges `state["sync"]["correction"]` toward the
player's real position, clamped to ±`MAX_SYNC_STEP_S` (0.5 s) per call.
Concurrency is guarded by `state["task"]` still running (`/start` →
`already_running`); `/stop` cancels and awaits it.

**Web UI (`panel.html`):** vanilla JS, all `fetch` calls use **relative** URLs so
it works both behind Ingress (path-prefixed) and via published port 8099. Polls
`/config` every 5 s. Section 3 has a `channel_order` text field (sent on `/start`);
section 4 "Lampen zuordnen" renders one button per channel of the currently
selected area (from the last `/areas` fetch, kept in `AREAS`; `renderIdentify()`)
plus "alle nacheinander" — each POSTs `/identify`.

**Two Hue API surfaces:** the `hue_entertainment` lib (`EntertainmentSession`,
`HueEntertainmentAPI`) does *only* DTLS streaming + pairing + area listing.
Anything else — reading/writing individual light state, `entertainment_configuration`
details — is a raw `aiohttp` call to `https://<bridge>/clip/v2/resource/...` with
header `hue-application-key: creds["username"]` and `ssl=False` (self-signed
cert). See `_clip` / `capture_light_state` / `restore_light_state`.

**Constraints to keep in mind:**
- Effect color comes from the `color` option / `/start` body (default red);
  `chase.py` only computes brightness, `main.py` applies the color.
- `effect` default is `pulse` (all lamps together); `chase` is the comet.
- `restore_state` (default true) snapshots + restores every area lamp via CLIP v2;
  runs in `_run_effect` before the handshake / in `finally` after `aclose()`.
- Channel order = `channel_order` option if set, else the area's native order
  (only meaningful for `chase`).
- The Bridge allows only **one** active Entertainment stream at a time; the DTLS
  handshake is 3–9 s and is the dominant music-sync error source — `/sync` +
  `cue_offset` exist to correct for it (see `DOCS.md` "Synchronisation zur Musik").
- `duration` omitted → `cue["duration_s"] - cue_offset` whenever a cue is
  **loaded** (even with `use_cue` false, so the effect still self-terminates);
  only runs until `/stop` if no cue file is loaded at all.
- The s6 `run` script is `#!/command/with-contenv bashio`; the Dockerfile
  `chmod a+x`s `run` and `finish` (no reliable file mode without git).

**Adding a config option — touch every one of these (proven by every option so far):**
1. `redalert/config.yaml` — `options:` default **and** `schema:` entry. The
   linter rejects a `schema` type without `?` if it duplicates a HA default, and
   rejects any *known HA key* left at its default — but custom option keys are free.
2. `redalert/translations/de.yaml` **and** `en.yaml` — `configuration:` name +
   description (missing one is a lint failure).
3. `redalert/rootfs/app/main.py` — `state[...]` default from `options.get(...)`;
   the startup config `log.info(...)` line; `handle_start` body parse
   (`body.get(..., state[...])`); the `/config` JSON; the `state["last_start"]` dict.
4. `redalert/rootfs/app/panel.html` — if user-facing: an input in section 3, the
   `body.*` in `btn-start`, the status-grid field, and the prefill in `refresh()`.
5. `redalert/DOCS.md` (options table + `/start` body list) and `README.md`
   (§5 options table + §6 `/start` row + §9 "Effekt anpassen" if it tunes an effect).
6. `redalert/CHANGELOG.md` + version bump (see the `release` skill).
7. Live-test on the real bridge (`smoke-test` skill) before committing.
