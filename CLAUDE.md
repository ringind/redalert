# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Home Assistant add-on store repository**. `repository.yaml` at the root makes
it addable in HA under *Settings → Add-ons → Add-on Store → ⋮ → Repositories*;
the add-on itself lives in `redalert/`. The add-on drives a Star Trek "Red Alert"
scene across ~6 Philips Hue lamps on **up to 3 Hue Bridges simultaneously** via
the **Hue Entertainment API** (persistent DTLS stream per bridge, ~25 Hz) rather
than normal Bridge scenes — two effects, `pulse` (default: all lamps on that
bridge together, periodic) and `chase` (a comet with a tail). **Effect, colour,
and timing are configurable per bridge** (falling back to shared defaults when
not overridden); all bridges still start **simultaneously** (parallel DTLS
handshakes, shared start epoch) for a configurable `duration` (the `duration`
option, shared across all bridges; `0` = unlimited, runs until `/stop`). It
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
redalert/                  the add-on
  config.yaml              manifest: options schema, ingress, ports
  build.yaml               base images: ghcr.io/home-assistant/{arch}-base-python
  Dockerfile               installs requirements, copies rootfs, chmods s6 scripts
  DOCS.md / CHANGELOG.md   "Documentation" / "Changelog" tabs in HA
  translations/{de,en}.yaml  config-option labels shown in the HA UI
  icon.png / logo.png      store graphics (generated, solid-red beacon)
  rootfs/etc/s6-overlay/s6-rc.d/redalert/{type,run,finish}  s6 service (bashio)
  rootfs/app/main.py        REST server + streaming loop + serves panel.html
  rootfs/app/chase.py       RedAlertPulse (beat gate) + RedAlertChase (comet+tail) + RedAlertGlitter (per-lamp sparkle), no I/O
  rootfs/app/panel.html     Ingress web UI (vanilla JS, relative fetch URLs)
```

## Commands

No build system, linter, or test suite. Current version: **1.5.0**.

- `python3 -m py_compile redalert/rootfs/app/main.py redalert/rootfs/app/chase.py`
  after every code change — the only static check available.
- Container build (normally the HA Supervisor does this):
  `docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20 -t redalert redalert/`
- Regenerate store graphics: the generator lives in the scratchpad
  (`mkpng.py`); `icon.png`/`logo.png` are a solid-red beacon on near-black.
- Cut a versioned release: see the **`release`** skill.

## Local testing (real Hue bridge)

`main.py` only fully runs outside the container because `DATA_DIR` is overridable:
`REDALERT_DATA_DIR` (default `/data`). The dev setup is a venv at `.venv` and a
`devdata/` dir — **both gitignored; do not `rm -rf devdata`**, it holds
`credentials.json` (now keyed by `bridge_host`, `{host: {username, clientkey,
bridge_host}, ...}`; an old flat single-bridge file is migrated in memory on
load, see `_load_credentials`) and deleting it forces a physical re-pair
(link button) for every bridge.

```bash
python3 -m venv .venv && .venv/bin/pip install -r redalert/requirements.txt   # once
mkdir -p devdata
REDALERT_DATA_DIR=./devdata REDALERT_LOG_LEVEL=debug .venv/bin/python redalert/rootfs/app/main.py &
B=http://localhost:8099
until curl -sf -o /dev/null $B/health; do sleep 0.5; done          # bind race: ~3 s, always gate
# pair only if devdata/credentials.json has no entry for this host (needs a fresh link-button press):
#   curl -s -X POST $B/pair -H 'Content-Type: application/json' -d '{"bridge_host":"<ip>"}'
# without devdata/options.json "bridges", pass it in the body instead:
curl -s -X POST $B/start -H 'Content-Type: application/json' \
  -d '{"bridges":[{"bridge_host":"<ip>","area_id":"<area>"}],"effect":"pulse","duration":20}'
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
  `/pair` (one-time Bridge link-button pairing, body `bridge_host` — Pflicht bei
  mehr als einer konfigurierten Bridge — → merged into `/data/credentials.json`),
  `/areas` (query `bridge_host` — Pflicht bei mehr als einer gepaarten Bridge),
  `/start`, `/stop`, `/identify`. All mutable runtime state is one module-level
  `state` dict; `state["bridges"]` is a list (≤ `MAX_BRIDGES` = 3) parsed by
  `_parse_bridges_option` from the `bridges` option — each entry always has
  `bridge_host`, `area_id`, `channel_order`, and *optionally* (sparse — key
  present only if this bridge overrides it) `effect`, `color`, `sweep_seconds`,
  `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`
  (`_BRIDGE_NUMERIC_OVERRIDES` lists the numeric ones + their cast).
  `state["credentials"]` is a dict keyed by `bridge_host` (`_load_credentials`
  transparently migrates the old flat single-bridge file). Options are read
  **once at import** from `/data/options.json`. `REDALERT_LOG_LEVEL` (exported
  by the s6 `run` script from the `log_level` option) sets the logging level.
  `/start` body: `duration` (default `state["duration"]`, i.e. the `duration`
  option; `0` = unlimited, runs until `/stop`), `fps`,
  `restore_state` apply to **all** bridges at once (frame rate and run length
  aren't per-bridge concepts); `effect`, `color`, `sweep_seconds`,
  `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high` in the body
  are the **defaults** dict for bridges that don't override them. `bridges`
  (list of entries shaped like the option, i.e. also with the optional
  per-bridge effect overrides) overrides `state["bridges"]` for that call only.
  Each bridge is resolved by `handle_start._resolve` (paired? reachable?
  `area_id` valid? `channel_order` — list[int] or `"2,3,1,0"` string via
  `_parse_channel_order` — matches the area's channels? then
  `cfg.get(key, defaults[key])` per effect param) concurrently via
  `asyncio.gather`; a bridge that fails resolution is skipped (best-effort,
  reported back as `failed_bridges`) without blocking the others — `/start`
  only 502s if **no** bridge resolved.
  `/identify` (body `bridge_host` — Pflicht bei mehr als einer konfigurierten
  Bridge —, `area_id?` defaulting to that bridge's configured entry,
  `channel_id?`, `seconds?`, `color?`, `restore_state?`) lights one channel of
  one bridge — or, with `channel_id` omitted, every channel in turn
  (~`seconds`+0.4 s gap each) — over a single DTLS handshake, to map channel_id
  → physical lamp. Shares the `state["task"]` slot with `/start`
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
    With `pause_seconds > 0` (`chase_pause` option / body) it branches to a
    non-looping model: one traversal via `_pulse_s` (absolute-time per-lamp pulse,
    rise leading in so lamp 0 doesn't snap), then all lamps at 0 for
    `pause_seconds`. `pause_seconds == 0` keeps the exact seamless loop above.
  - `RedAlertPulse.step(level, dt)` → uniform level for all lights. A Schmitt gate
    (on above `hi`, off after `hold_s` below `lo`) turns the periodic input into a
    stable 0/1, then a **linear** slew hits exactly 1.0 in `attack_s` / 0.0 in
    `release_s` (keep release < attack). `RedAlertPulse.periodic(t, period)`
    feeds the gate a cosine 0..1 pulse with period `sweep_seconds`.

**Effect loop (`_run_effect`):** `handle_start` resolves all bridges (area
lookup, no DTLS — 404/502-equivalent failures per bridge collected into
`failed_bridges` synchronously), then hands the whole list of resolved
bridge contexts (`{bridge_host, area_id, channel_ids, session, app_key,
effect, color, sweep_seconds, chase_pause, attack_s, release_s, glow_low,
glow_high}` — each bridge's own resolved effect config) to a **single**
`asyncio` task and returns immediately. The task, before any handshake,
snapshots every bridge's lights via Hue CLIP v2 concurrently
(`capture_light_state`, unless `restore_state` is false); starts **all**
DTLS handshakes concurrently via `asyncio.gather(..., return_exceptions=True)`
so a slow or failing bridge doesn't delay/block the others, and so every
surviving bridge gets the **same** `start = loop.time()` epoch — this is what
keeps bridges starting simultaneously, even though each can run a completely
different effect/colour/timing. A bridge whose handshake raises is dropped
from `active` and logged; if none survive, the loop returns early. Each
bridge gets its **own** `RedAlertChase`/`RedAlertPulse` instance (built once
before the loop, sized to that bridge's own channel count and timing); every
frame, each active bridge independently computes its 0..1 shape from the
**same shared** `elapsed`/`dt` (so e.g. two bridges both running `chase` with
the same `sweep_seconds` stay phase-identical, and a `pulse` bridge's beat
timing is anchored to the same clock as a `chase` bridge next to it) — there
is no longer a single shared level reused across bridges verbatim, since
bridges can now differ. Levels are mapped to `glow_low + (glow_high-glow_low)*lvl`
per bridge (so between pulses lamps rest at that bridge's `glow_low`, not 0) →
per-channel `LightColorCommand` scaled by that bridge's colour
(`value_8bit * 257 * level`), sent via `ctx["session"].send(...)`. Frames are
paced against a single **absolute** clock (`start + n/fps`, `fps` shared across
all bridges), not `sleep(1/fps)`, so the light timeline doesn't drift; the loop
breaks once `elapsed >= duration` (also shared). `finally` `aclose()`s every
session and `restore_light_state`s every snapshot (via `asyncio.gather`,
best-effort) — including bridges whose handshake failed, since their snapshot
was still captured beforehand.
Concurrency is guarded by `state["task"]` still running (`/start` →
`already_running`); `/stop` cancels and awaits it (cancelling the gathers
inside cancels every bridge's in-flight work too).

**Web UI (`panel.html`):** vanilla JS, all `fetch` calls use **relative** URLs so
it works both behind Ingress (path-prefixed) and via published port 8099. Polls
`/config` every 5 s. Section "1 · Bridges" renders `BRIDGE_COUNT` = 3 identical
cards (`bridgeCardHTML(i)`, ids `b${i}-*`) — pairing, area list/pick, own
`channel_order` field, a nested `<details>` "Effekt für diese Bridge anpassen"
(`b${i}-effect` with a blank "wie oben" option + `b${i}-color/sweep/chpause/
attack/release/glowlow/glowhigh`, all optional — empty means inherit the
shared default), and its own nested "Lampen zuordnen" (`AREAS[i]`,
`renderIdentify(i)`, each POSTs `/identify` with that card's `bridge_host` and,
if set, its own `b${i}-color` override). Section "2 · Steuerung" holds the
**shared** run controls (`duration`/`fps`, always global) plus the **default**
effect form (effect/color/sweep/chase_pause/glow) used by any bridge card that
doesn't override that field. On Start it assembles `body.bridges` from
whichever of the 3 cards have both `bridge_host` and `area_id` filled in, each
entry including only the per-bridge fields that were actually set (empty cards
are skipped entirely; if none are filled, `bridges` is omitted and the server
falls back to the configured `bridges` option).

**Two Hue API surfaces:** the `hue_entertainment` lib (`EntertainmentSession`,
`HueEntertainmentAPI`) does *only* DTLS streaming + pairing + area listing.
Anything else — reading/writing individual light state, `entertainment_configuration`
details — is a raw `aiohttp` call to `https://<bridge>/clip/v2/resource/...` with
header `hue-application-key: creds["username"]` and `ssl=False` (self-signed
cert). See `_clip` / `capture_light_state` / `restore_light_state`.

**Constraints to keep in mind:**
- Effect color comes from a bridge's own `bridges[].color` override, else the
  `color` option / `/start` body default (default red); `chase.py` only
  computes brightness, `main.py` applies the color.
- `effect` default is `pulse` (all lamps together); `chase` is the comet.
  Both are per-bridge overridable (`bridges[].effect`) — different bridges can
  run different effects at the same time.
- `restore_state` (default true) snapshots + restores every area lamp via CLIP v2;
  runs in `_run_effect` before the handshake / in `finally` after `aclose()`.
- Channel order = `channel_order` option if set, else the area's native order
  (only meaningful for `chase`); it's per-bridge, like `area_id`.
- Each Bridge allows only **one** active Entertainment stream at a time (this is
  per-*bridge*, not global — different bridges stream independently and
  concurrently); the DTLS handshake is 3–9 s per bridge.
- `MAX_BRIDGES` = 3; extra `bridges` entries (option or `/start` body) beyond
  that are dropped with a warning, not an error.
- `duration` omitted → the `duration` option (default `0`). `0` means
  **unlimited** — runs until `/stop`; any positive value self-terminates after
  that many seconds. This is the one place `/stop`-only-termination is
  intentional (opposite of the old cue-era default of always self-ending).
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
4. `redalert/rootfs/app/panel.html` — if user-facing and shared across bridges:
   an input in section "2 · Steuerung", the `body.*` in `btn-start`, the
   status-grid field, and the prefill in `refresh()`. If it's per-bridge (like
   `area_id`/`channel_order`): a field in `bridgeCardHTML(i)` instead, wired in
   `wireBridgeCard(i)`.
5. `redalert/DOCS.md` (options table + `/start` body list) and `README.md`
   (§5 options table + §6 `/start` row + §8 "Effekt anpassen" if it tunes an effect).
6. `redalert/CHANGELOG.md` + version bump (see the `release` skill).
7. Live-test on the real bridge (`smoke-test` skill) before committing.
