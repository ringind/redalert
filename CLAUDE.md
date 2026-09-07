# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Home Assistant app store repository** (HA renamed "add-ons" to "apps" in
2026.2 — UI/docs wording only, Supervisor/Core APIs, schemas, and repo
mechanics are unchanged; this repo's own docs use "app" accordingly, `git
grep -i add-on` for any spot that still needs it). `repository.yaml` at the
root makes it addable in HA under *Settings → Apps → App Store → ⋮ →
Repositories*; the app itself lives in `redalert/`. The app drives a Star Trek "Red Alert"
scene across ~6 Philips Hue lamps on **up to 3 Hue Bridges simultaneously** via
the **Hue Entertainment API** (persistent DTLS stream per bridge, ~25 Hz) rather
than normal Bridge scenes — `effect` is one of `pulse` (default: all lamps on
that bridge together, periodic), `comet` (a comet with a tail), `glitter`
(per-lamp random colour sparkle), `police` (two lamp groups alternately
strobe two colours), `lightning` (whole array flashes together at random,
occasional double-strike), `heartbeat` (pulse driven by a two-beat "lub-dub"
instead of one cosine hump), `aurora` (slow colour waves blended from a
palette, drifting across lamps), `rainbow` (phase-offset hue-cycle sweeping
across lamps), `meteor` (several randomised independent comets), `wipe`
(sequential fill-and-hold, repeating), `firework` (one-shot bursts radiating
from the centre channel, repeating), `ripple` (like firework but the wave
reflects off both ends and echoes back), `wave` (scrolling spatial sine wave,
several crests visible at once), `flicker` (per-lamp brief dips from full
brightness, like a failing bulb), `strobe` (hard instant on/off flash, no
fade), `duel` (two comets launched from opposite ends, meeting and bouncing
back), `chase` (Gradient Lightstrips only — soft-edged two-colour bands
sliding along the segments) or `neutral` (bridge left untouched — no
stream/restore; per-bridge only, for effect sets where some bridges run and
others don't). 17 effects total. **Effect, colour, and timing are
configurable per bridge**
(falling back to shared defaults when not overridden); all bridges still start
**simultaneously** (parallel DTLS handshakes, shared start epoch) for a
configurable `duration` (the `duration` option, shared across all bridges; `0` =
unlimited, runs until `/stop`). The full `/start` payload (all bridges +
controls) can be saved as a named **effect set** in `/data/presets.json`
(`GET/PUT/DELETE /presets`, `POST /start {"preset": "..."}`). It ships an
aiohttp REST service **and** an Ingress web UI for control. HA builds the
image locally from `redalert/Dockerfile` (no `image:` key, no prebuilt registry).
Primary docs are German: repo overview in `README.md`, in-HA docs in
`redalert/DOCS.md`. Each has a standalone English counterpart
(`README.en.md`, `redalert/DOCS.en.md`, plus `custom_components/redalert/
README.en.md` and `info.en.md`) — separate files rather than one bilingual
file, since HA's in-app docs viewer has no locale switching; keep both
languages' content in sync when editing either one, and update the
language-switcher line at the top of each.

**Remote & CI:** `github.com/ringind/redalert` (branch `main`).
`.github/workflows/build.yaml` = `frenck/action-addon-linter` (strict: rejects any
*known HA* config.yaml/build.yaml key left at its default) + a `docker buildx`
test build for amd64 and (emulated) aarch64. Green in ~4 min. After every push,
watch it: `RUN=$(gh run list --workflow=build.yaml --branch main -L1 --json databaseId -q '.[0].databaseId'); until [ "$(gh run view $RUN --json status -q .status)" = completed ]; do sleep 30; done; gh run view $RUN --json conclusion,jobs -q '.conclusion, (.jobs[]|"\(.name)=\(.conclusion)")'`
(run it backgrounded). `.github/workflows/hacs.yaml` validates the
`custom_components/redalert` HA integration (`hacs/action` + `hassfest`,
weekly cron + on push/PR) — same watch pattern, `--workflow=hacs.yaml`.
`hassfest` requires `manifest.json` keys sorted `domain`, `name`, then
alphabetical — re-check order after adding/removing a key. `hacs/action` also
requires the GitHub repo itself to have topics set (`gh repo edit --add-topic
...`, not a repo file) and the `brand/` icon/logo (see Layout above).
Releases are tags `vX.Y.Z` on a green commit — see the `release` skill.

## Layout

```
repository.yaml            store metadata
README.md / README.en.md   repo overview (German / English)
hacs.json                  makes this repo addable in HACS as a custom
                            integration repository (category "Integration")
info.md / info.en.md       what HACS renders instead of README.md when
                            present — integration-only blurb + the standard
                            my.home-assistant.io HACS-install badge, points
                            to the app's own docs rather than duplicating them
custom_components/redalert/  HA integration talking to the app's REST API
  manifest.json, const.py, api.py, coordinator.py, config_flow.py, entity.py
  binary_sensor.py (running, any bridge) / switch.py (global start+stop, plus
  one per-bridge switch per paired bridge since 1.15.0 — dynamically added
  from coordinator data via a coordinator-listener, this platform's only
  dynamic-entity registration) / select.py (pick+load a preset) / sensor.py
  (currently loaded preset) — one DataUpdateCoordinator polling GET /config
  every 10s; README.md/README.en.md document install + entities
  brand/icon.png, brand/logo.png — copies of redalert/{icon,logo}.png; HA
  2026.3+ shows these inline (no home-assistant/brands PR needed), and the
  `hacs/action` CI check requires them regardless of HA version
redalert/                  the app
  config.yaml              manifest: options schema, ingress, ports
  build.yaml               base images: ghcr.io/home-assistant/{arch}-base-python
  Dockerfile               installs requirements, copies rootfs, chmods s6 scripts
  DOCS.md / DOCS.en.md / CHANGELOG.md   "Documentation" / "Changelog" tabs in
                           HA (CHANGELOG.md is German only, no .en.md)
  translations/{de,en}.yaml  config-option labels shown in the HA UI
  icon.png / logo.png      store graphics (generated, solid-red beacon)
  rootfs/etc/s6-overlay/s6-rc.d/redalert/{type,run,finish}  s6 service (bashio)
  rootfs/app/main.py        REST server + streaming loop + serves panel.html
  rootfs/app/chase.py       17 effects' pure math, no I/O: RedAlertPulse
    (pulse beat-gate, also drives heartbeat via .heartbeat()) +
    RedAlertComet (comet+tail) + RedAlertGlitter (per-lamp sparkle) +
    RedAlertChase (Gradient Lightstrip bands) + RedAlertPolice (two-group
    strobe) + RedAlertLightning (shared flash, stateful) + RedAlertAurora /
    RedAlertRainbow (per-lamp colour, no brightness shape) + RedAlertMeteor
    (randomised multi-comet) + RedAlertWipe (fill-and-hold) + RedAlertFirework
    (radiating one-shot bursts) + RedAlertRipple (firework that echoes back) +
    RedAlertWave (scrolling sine) + RedAlertFlicker (per-lamp dips, stateful) +
    RedAlertStrobe (hard on/off) + RedAlertDuel (two comets, two shapes)
  rootfs/app/panel.html     Ingress web UI (vanilla JS, relative fetch URLs,
    bilingual DE/EN via an I18N dict + data-i18n attributes, see below)
```

## Commands

No build system, linter, or test suite. Current version: **1.15.2**.

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
  (`_run_single_bridge` does the handshake, one per bridge), so poll `/health`
  `running` for real state.
- `_run_single_bridge` runs its bridge's effect for `duration` s at exactly `fps`
  (absolute-clock pacing) — verify with the `Effekt beendet (<host>, N Frames)`
  log line: `N ≈ duration*fps`.
- See the **`smoke-test`** skill for the full loop (start server, run, wait, report, stop).

## Architecture

Three layers under `redalert/rootfs/app/`:

- **`main.py`** — aiohttp server. Endpoints: `/` (serves `panel.html`),
  `/health` (also the Docker HEALTHCHECK target; `{status, paired, running,
  current_preset}` — `current_preset` is `state["current_preset"]`, the name
  of the last `preset` started via `/start`, `None` after an ad-hoc start with
  no `preset`; consumed by `custom_components/redalert`'s select/sensor pair),
  `/config` (effective config for the UI, same `current_preset` field),
  `/pair` (one-time Bridge link-button pairing, body `bridge_host` — Pflicht bei
  mehr als einer konfigurierten Bridge — → merged into `/data/credentials.json`),
  `/areas` (query `bridge_host` — Pflicht bei mehr als einer gepaarten Bridge),
  `/start`, `/stop`, `/identify`. All mutable runtime state is one module-level
  `state` dict; `state["tasks"]` is a `dict[bridge_host, asyncio.Task]` — since
  1.15.0 every bridge runs its effect (or an `/identify` run) in its **own**
  task, independently start-/stoppable via an optional `bridge_host` in the
  `/start`/`/stop` body (see below), replacing the old single global
  `state["task"]`. `state["bridges"]` is a list (≤ `MAX_BRIDGES` = 3) parsed by
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
  An optional `bridge_host` in the `/start`/`/stop` body targets a single
  bridge, independent of any others' state — `already_running` then only
  checks that one bridge; not combinable with `preset` (400 — a preset is a
  multi-bridge concept) and never touches `state["current_preset"]`. Without
  `bridge_host` (the default "start everyone" call), bridges that are
  already running are **skipped, not rejected** — reported back as
  `skipped_bridges`, alongside `failed_bridges`/`neutral_bridges` — so the
  same button can be used to top up whichever bridges aren't running yet.
  `/identify` (body `bridge_host` — Pflicht bei mehr als einer konfigurierten
  Bridge —, `area_id?` defaulting to that bridge's configured entry,
  `channel_id?`, `seconds?`, `color?`, `restore_state?`) lights one channel of
  one bridge — or, with `channel_id` omitted, every channel in turn
  (~`seconds`+0.4 s gap each) — over a single DTLS handshake, to map channel_id
  → physical lamp. Shares that bridge's `state["tasks"][host]` slot with
  `/start` (`already_running` guard for that bridge only; `/stop` with that
  `bridge_host`, or no `bridge_host` at all, cancels it).
- **`chase.py`** — one class per effect (17 total), pure math, no I/O, each
  emitting a **0..1 shape**/blend; `_run_single_bridge` maps brightness shapes
  onto `[glow_low, glow_high]` (options / `/start` body, clamped, `glow_high`
  forced ≥ `glow_low`) — so "0" is the resting glow, not necessarily black.
  Two classes are worth understanding in detail as templates for the rest —
  both had to be hardened against the same **frame-rate aliasing** failure
  mode, once found in each:
  - `RedAlertComet.brightness_for(t)` → per-light `[0,1]` list. Per lamp, a pure
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
  - `RedAlertChase.blend_for(t)` → per-segment `[0,1]` band blend (Gradient
    Lightstrips). `_band(dist)` is a flat `1.0` core (`half_width`, from
    `gc_length`) with a raised-cosine soft edge (`smooth`) trailing off to
    `0.0`. **Bug found & fixed in 1.15.2** (reported: lamps flicker/snap when
    entering or leaving a band, at higher `gc_speed` — the same symptom the
    comet's `peak_frac` floor already prevents for its head): `blend_for(t)`
    is sampled once per frame with no `dt`, so a `smooth` width fixed only in
    *segments* can become narrower in *time* than one frame interval once
    `speed_segments_per_s` is high enough (or `fps` low enough) — the head
    then crosses it between two consecutive frames and a lamp's blend jumps
    most of the way from 0 to 1 (or back) in a single frame instead of
    fading, i.e. aliasing, not a hardware/network issue. Fixed the same way
    as the comet: floor `smooth` by a **time**-based minimum, not just a
    segment-count one — `self.smooth = max(base_smooth, 6.25 * speed / fps)`
    (capped at `max(1.0, num_lights/2)` so extreme `speed`+low-`fps`
    combinations degrade to "softer than ideal" rather than eating the whole
    strip). The `6.25` constant is calibrated so the *previous* default
    (`gc_speed=4.0`, `fps=25`) reproduces the old fixed `smooth=1.0` exactly
    — i.e. default-settings behaviour is unchanged, only non-default
    speed/fps combinations get a wider (smoother) edge than before. `fps`
    therefore had to be threaded into `RedAlertChase.__init__` (from
    `_run_single_bridge`'s own `fps` parameter) — the first `chase.py` class
    that needs to know the frame rate at construction time, not just at
    `main.py`'s pacing loop; keep this in mind if another effect ever shows
    the same "fine by default, aliases at extreme settings" symptom — the
    fix pattern (verify with a small blend-jump simulation across a range of
    speed/fps values, not just eyeballing the default) transfers directly.

**Effect loop (`_run_single_bridge`):** `handle_start` resolves all requested
bridges (area lookup, no DTLS — 404/502-equivalent failures per bridge
collected into `failed_bridges` synchronously; bridges already running are
filtered out first into `skipped_bridges`, see above), then creates **one
independent `asyncio.Task` per resolved bridge** (`_run_single_bridge`,
stored as `state["tasks"][bridge_host]`) and returns immediately — this is
what lets a per-bridge `/stop` cancel just one bridge without touching
others, even ones started in the same `/start` call. Each bridge's own task,
before its handshake, snapshots that bridge's lights via Hue CLIP v2
(`capture_light_state`, unless `restore_state` is false) and starts its own
DTLS handshake. To keep **multiple** bridges from one `/start` call lighting
up at the same instant despite now being separate tasks, `handle_start`
hands them all a shared `asyncio.Barrier(len(ctxs))` (only when `len(ctxs) >
1`; a solo start gets `None`) — each task `await`s the barrier right after
its own successful handshake, before recording its `start = loop.time()`
epoch, so every task's epoch is set only once all of that batch's handshakes
are done. If one bridge's handshake fails, its task calls `barrier.abort()`
so the others get `asyncio.BrokenBarrierError` from `.wait()` and proceed
immediately instead of hanging — same best-effort spirit as before ("a
failing bridge doesn't block the others"), now implemented via the barrier
rather than a shared `asyncio.gather`. Each bridge's task builds its **own**
`RedAlertComet`/`RedAlertPulse`/etc. instances (sized to its own channel
count and timing) and runs its own per-frame `while True` loop against its
own `elapsed`/`dt` clock — two bridges both running `comet` with the same
`sweep_seconds` only stay phase-identical if they were part of the same
barrier-synchronized batch start (their `start` epochs coincide), not
inherently across independent solo starts. Levels are mapped to
`glow_low + (glow_high-glow_low)*lvl` (so between pulses lamps rest at that
bridge's `glow_low`, not 0) → per-channel `LightColorCommand` scaled by that
bridge's colour (`value_8bit * 257 * level`), sent via `ctx["session"].send(...)`.
Frames are paced against that task's own **absolute** clock (`start +
n/fps`), not `sleep(1/fps)`, so the light timeline doesn't drift; the loop
breaks once `elapsed >= duration`. `finally` `aclose()`s the session and
`restore_light_state`s the snapshot — even if the handshake failed, since
the snapshot was still captured beforehand.
Concurrency is guarded per bridge by `state["tasks"][host]` still running
(`/start` with that `bridge_host` → `already_running` for just that bridge);
`/stop` with a `bridge_host` cancels only that task, `/stop` without one
cancels every currently-running task.

**Web UI (`panel.html`):** vanilla JS, bilingual since 1.13.0 — an `I18N` object
(`{de:{...}, en:{...}}`, flat `"key": "value"` maps, both kept in lockstep;
a value can be a function for interpolated strings, e.g. `(i) => \`Bridge
${i}\``) backs a `t(key, ...args)` lookup. Static markup carries
`data-i18n`/`-html`/`-ph`/`-title` attributes; `applyI18n()` walks the DOM and
fills them in, run once at load and again on every `setLang()` call (toggle
buttons top-right, persisted to `localStorage["redalert-lang"]`, default from
`navigator.language`). Content built once from a JS template literal at
bridge-card-creation time (the per-bridge pairing pill, area list placeholder,
channel-identify placeholder) carries no `data-i18n` and must be re-rendered
explicitly in `setLang()` instead — a bridge card the server doesn't know
about yet is otherwise never touched by the periodic `/config`-driven
`refresh()`, so its pill would stay in the old language after a toggle.
`PANEL_HTML` is read once at import in `main.py`, so any edit to `panel.html`
needs a server restart to show up when testing locally.
**Script-ordering hazard (found & fixed in 1.15.0):** the whole `<script>`
block is one top-level scope, so a top-level call that runs immediately
(not inside a later event handler/timer) must not reference a `let`/`const`
declared *further down* in the same file — it'll throw `ReferenceError:
Cannot access '<name>' before initialization` (temporal dead zone), and
because the offending call sat inside an unawaited `async function`, the
throw became a *silently swallowed promise rejection* instead of a visible
crash — the page still rendered, just without that call's effect, so it
only surfaced via the browser console, not a screenshot. Concretely:
`setLang(LANG)` — called synchronously right after `wireBridgeCard()` — must
run *after* every `let`/`const` its call chain touches has executed,
notably `refreshBusy`/`refreshQueued` (`refresh()`) and `PRESETS`
(`loadPresets()`, called from `doRefresh()`); it's placed right before
`setInterval(refresh, 5000)` at the very end of the script for exactly this
reason — don't move it earlier without moving those declarations too.
**Lesson: after any web UI change, check the browser console
(`read_console_messages`), not just a screenshot** — an unhandled rejection
like this one doesn't visibly break anything at first glance. All
requests go through `api()`, which wraps `fetch` in an `AbortController` timeout
(`DEFAULT_TIMEOUT_MS` = 15 s; `/pair` passes 35 s since the server itself awaits
up to 30 s for the link-button press) — since 1.9.1, after a bug where a hung
fetch (no timeout) plus the naive 5 s poll piled up requests against the
browser's per-origin connection limit until the whole panel stopped responding
until reload. `refresh()` guards against overlapping polls with a
`refreshBusy`/`refreshQueued` pair (since 1.15.0, was `refreshBusy`-only
through 1.14.0) — a call arriving while one is in flight no longer just
returns and gets silently dropped, it sets `refreshQueued` and is re-run
once the in-flight call finishes; without this, a button handler's own
trailing `refresh()` could collide with the periodic 5 s poll and get
dropped, leaving the UI looking unresponsive for up to 5 s after a click. A
`visibilitychange` listener also forces an immediate refresh when the tab
regains focus (browsers throttle `setInterval` in hidden tabs).
Polls `/config` every 5 s. Section "1 · Bridges" renders `BRIDGE_COUNT` = 3 identical
cards (`bridgeCardHTML(i)`, ids `b${i}-*`) — pairing (`b${i}-pill`), a
per-bridge **Start**/**Stop** button pair (`b${i}-start`/`b${i}-stop`, since
1.15.0) that POSTs `/start`/`/stop` with `bridge_host` set to just this
card's host — the Start handler reuses the same `collectBody()` the global
button uses (so this card's own overrides apply identically), `bridge_host`
just tells the server to filter to one bridge — plus a running-status pill
(`b${i}-run-pill`, synced from `/config`'s per-bridge `running` field the
same way `b${i}-pill` mirrors `paired`), area list/pick, own `channel_order`
field, a nested `<details>` "Effekt für diese Bridge anpassen" (`b${i}-effect`
with a blank "wie Konfiguration" option, then the per-bridge parameter
fields grouped under heading rows — `.field-group-heading` divs with
`flex-basis: 100%` to break the flex `.row` — in three tiers: universal
`glow_low`/`glow_high`, then params shared by 2+ effects (`color`
immediately followed by `color2`, then `sweep_seconds`/`chase_pause`/
`attack_ms`/`release_ms`/`glitter_*` — the latter four are shared because
`chase`'s optional `gc_background_pulse`/`gc_chase_glitter` overlays reuse
the same `RedAlertPulse`/`RedAlertGlitter` instances — **since 1.15.1 this
tier's labels spell out every effect that actually reads the parameter**,
e.g. `card.sweep` = `"sweep_seconds – für pulse, comet, police, heartbeat,
aurora, rainbow, wipe, wave, strobe, duel, chase (wenn „Background
pulsiert“ aktiv)"`, not just the bare option name — determine the list from
`_run_single_bridge`'s dispatch code (`main.py`), not from what an effect's
name/description implies, since a conditional reuse like `chase`'s is easy
to miss by inspection alone), then one heading per
single-effect group alphabetically (Chase/Firework/Flicker/Lightning/
Meteor/Ripple/Wave — the other effects have no exclusively-own params so
get no heading; all fields optional, empty means inherit the app
configuration), and its own nested "Lampen zuordnen"
(`AREAS[i]`, `renderIdentify(i)`, each POSTs `/identify` with that card's
`bridge_host` and, if set, its own `b${i}-color` override). Colour parameters
(`color`, `gc_background_color`, `glitter_colors`) are `<input type=color>`
pickers gated by a same-row "eigene Farbe verwenden" checkbox (`b${i}-color-en`
etc. — unchecked = disabled input = inherit; `glitter_colors` uses three
pickers `b${i}-gcolor0/1/2` behind one checkbox). Every bridge-card field sets
`dataset.touched = "1"` on user interaction (`wireBridgeCard`'s generic
listener); the periodic `/config` sync in `refresh()` (`syncIfUntouched` /
`syncColorOverride`) only ever writes a field that isn't touched yet, so a
deliberate choice (including explicitly picking "wie Konfiguration") survives
later polls. Section "2 · Steuerung" has **no input fields** — effect
parameters, `duration` and `fps` all come from the app configuration (or a
bridge's own override); the section renders **Start**/**Stop** first (these
still start/stop **every** configured bridge simultaneously — a synchronized
batch via the barrier described below — the per-bridge buttons on each card
are for controlling just one), then the parameter descriptions below them.
On Start, `collectBody()` assembles `body.bridges`
from whichever of the 3 cards have both `bridge_host` and `area_id` filled in
(each entry including only the per-bridge fields actually overridden; empty
cards are skipped, and if none are filled `bridges` is omitted so the server
falls back to the configured `bridges` option), merged over `LOADED_EXTRA` —
any non-`bridges` fields from a preset loaded via `applyBody()`, preserved
verbatim on save even though the UI no longer exposes controls for them.

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
- `effect` default is `pulse` (all lamps together); `comet` is the comet with
  a tail; `chase` is the Gradient Lightstrip band effect (renamed from
  `gradient_chase` in 1.9.0 — `comet` was itself renamed from the old
  `chase`). All are per-bridge overridable (`bridges[].effect`) — different
  bridges can run different effects at the same time.
- `restore_state` (default true) snapshots + restores every area lamp via CLIP v2;
  runs in `_run_single_bridge` before the handshake / in `finally` after `aclose()`.
- Channel order = `channel_order` option if set, else the area's native order
  (only meaningful for `comet`); it's per-bridge, like `area_id`.
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
   (`body.get(..., state[...])`); the `/config` JSON (both the top-level
   default and each per-bridge entry); the per-bridge `entry`/`state["last_start"][host]`
   dict built in `handle_start`'s success path.
4. `redalert/rootfs/app/panel.html` — since 1.9.0, section "2 · Steuerung" has
   no input fields (only descriptions + Start/Stop): a **shared** option (not
   per-bridge) only needs its read-only line added to the `fields` object in
   `refresh()` (Status). A **per-bridge** option (like `area_id`/
   `channel_order`, or any of the effect parameters) needs a field in
   `bridgeCardHTML(i)`'s "Effekt für diese Bridge anpassen" `<details>` —
   since 1.15.0 that block is grouped under heading rows (universal → shared
   by 2+ effects → one heading per single-effect group, alphabetical; see
   the Web UI paragraph above), place a new field under whichever tier
   actually reads it in `_run_single_bridge`'s dispatch, not just its
   "primary" effect — if it lands in the "shared by 2+ effects" tier, its
   `data-i18n` label text (since 1.15.1) must list every effect that reads
   it, e.g. `"… – für pulse, heartbeat, chase (wenn „Background pulsiert“
   aktiv)"`, in **both** `I18N.de`/`I18N.en` — wired in `wireBridgeCard(i)` (the generic
   `input`/`select` loop already attaches `dataset.touched` tracking — a
   colour value instead needs an `<input type=color>` + "eigene Farbe
   verwenden" checkbox pair like `b${i}-color`/`b${i}-color-en`, synced via
   `syncColorOverride`/`setColorOverride` and read via `colorOverride()` in
   `collectBody()`), plus its `syncIfUntouched`/`syncColorOverride` line in
   `refresh()` and its entry in `collectBody()`/`applyBody()`.
5. `redalert/DOCS.md` (options table + `/start` body list) and `README.md`
   (§5 options table + §6 `/start` row + §8 "Effekt anpassen" if it tunes an effect)
   — and their English counterparts `redalert/DOCS.en.md`/`README.en.md`.
6. `redalert/CHANGELOG.md` + version bump (see the `release` skill).
7. Live-test on the real bridge (`smoke-test` skill) before committing.
