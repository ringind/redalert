🇬🇧 English (this file) · 🇩🇪 [Deutsch](DOCS.md)

# Red Alert Entertainment

Red Star Trek "Red Alert" light chase across multiple Philips Hue lamps,
driven by the real **Hue Entertainment API** (DTLS streaming, ~25 Hz – not
the sluggish Bridge scene). Supports **up to 3 Hue Bridges** that start
simultaneously – each with its own effect, its own colour and its own
timing.

## Prerequisites

- Home Assistant **OS** or **Supervised** (for apps).
- One to three Hue Bridge **V2** ("square") or Hue Pro Bridge. V1 bridges
  can't do Entertainment streaming.
- Per bridge: several colour-capable Hue lamps, assigned to an
  **Entertainment area** (Hue app → Settings → Entertainment areas → New
  area). The order in which you add the lamps determines the channel order.

## Installation

1. **Settings → Apps → App Store → ⋮ (top right) → Repositories** and add
   this GitHub repository's URL.
2. Install the **Red Alert Entertainment** app from the store.
3. Optionally enable "Start on boot" (recommended).
4. **Start** the app.

## Setup

Open the web UI (sidebar entry **Red Alert**). Under **"1 · Bridges"** there
are 3 identically structured cards, one per bridge – for a single bridge the
first is enough, cards left empty are ignored.

### 1 · Bridges (repeat per bridge)

1. Press the physical **link button** on the Hue Bridge.
2. Within ~30 s, enter the **Bridge IP** in the bridge card and click
   **Pair**. `username`/`clientkey` are saved automatically under
   `/data/credentials.json` (per bridge) – pairing only needs to be done
   once.
3. Click **"Load areas"** – the list shows name, `id` and channels. Click
   **"use"** to copy the `area_id` into the card's field.
4. Optionally set **`channel_order`** (see below). "**Map lamps**"
   (expandable) helps figure out which `channel_id` is which physical lamp:
   either **"All channels in sequence"** (lights up 0, 1, 2, … red for a few
   seconds each) or click an individual **"Channel N"** button. Each click
   briefly uses the Entertainment stream (one DTLS handshake, ~3–9 s, then
   the channel lights up); the previous lamp state is restored afterwards.
5. Optionally, under **"Customize effect for this bridge"** (expandable),
   set your own effect/colour/timing just for this bridge – "same as
   configuration" or a field left empty falls back to the app
   configuration's default. The parameters are grouped (universal
   parameters, then ones used by several effects, then per effect) instead
   of one long list.
6. **Start**/**Stop** on the bridge card itself (next to the Pair button)
   runs the effect on **only this one** bridge, regardless of the others'
   state – so several bridges can be started one after another instead of
   only together. The pill next to it shows whether this bridge is
   currently active.

Also enter the bridge IP, `area_id` (and optionally `channel_order` plus the
effect overrides) as a row of the **`bridges`** app option, so that
`rest_command` calls without a body work, and restart the app.

Alternatively via REST: `POST /pair` (body `{"bridge_host": "192.168.1.50"}`),
`GET /areas?bridge_host=192.168.1.50`.

`channel_order` (empty = area's default) sets the order in which `comet`
loops through this bridge's lamps – as a comma-separated list of
`channel_id`s, e.g. `2,3,1,0,5,4`. It must contain exactly the area's
channels, just in a different order.

### 2 · Control

In the web UI under **"2 · Control"** there's only **Start** / **Stop** –
all parameters (effect, colour, timing, duration, `fps`, …) come from the
app configuration or from the overrides on the respective bridge card (see
"1 · Bridges"); the "Status" section above shows the currently effective
values. **Start** / **Stop** start/stop all configured bridges at once;
both buttons show a pressed state to indicate whether the effect is
currently running. For individual bridges, see the Start/Stop buttons on
that bridge's card under "1 · Bridges".

## Effects

| `effect` | Behaviour |
|----------|-----------|
| `pulse` (default) | All lamps **together**: linearly from `glow_low` to `glow_high` and back, one full cycle every `sweep_seconds`. A Schmitt trigger on the periodic signal turns this into a clean on/off, so the rise runs smoothly and monotonically. `attack_ms` = ramp-up, `release_ms` = ramp-down time; a smaller `release_ms` gives a faster fall than rise. |
| `comet` | A comet runs **evenly in one direction** around all channels (wraparound, constant speed) with cycle time `sweep_seconds`. Each lamp pulses on its own: **briefly bright (`glow_high`), a long exponential fade, then a rest at `glow_low`**, then again. The head is a bit wider than the lamp spacing – two adjacent lamps briefly sit at 100 % together and then fade out one after another, so at least one lamp is always fully lit. With `chase_pause > 0` the comet does **one** run, then all lamps rest at `glow_low` for `chase_pause` seconds, then the next run. |
| `glitter` | **Diamond twinkle:** each lamp sparkles on its own. At random moments (on average every `glitter_interval_ms` ms across all of a bridge's lamps) a lamp jumps to `glow_high` in a colour picked at random from `glitter_colors`, then decays back to `glow_low` with time constant `glitter_flash_ms`. If `glitter_flash_ms` is larger than `glitter_interval_ms`, several lamps sparkle at once. `glitter_colors` empty = all sparks in the bridge colour. |
| `police` | **Emergency lights:** a bridge's lamps are split into two groups (every other lamp in channel order); group 1 flashes in the bridge `color`, group 2 in `color2` (default blue) – the two flash alternately, never together. `sweep_seconds` is the duration of one full switch (both groups once). |
| `lightning` | **Storm:** all lamps of a bridge flash **together** in the bridge `color` and then decay – unlike `glitter`, where each lamp sparkles on its own. `lightning_interval_ms` = mean gap between two strikes, `lightning_flash_ms` = decay time constant; occasionally (not configurable) a quick second flash follows, like a real lightning strike. |
| `heartbeat` | **Heartbeat:** a double pulse ("lub-dub", one big and one smaller pulse) instead of a single pulse like `pulse`, timed by `sweep_seconds`. Uses the same beat gate/slew as `pulse` (`attack_ms`/`release_ms`), just with a different input curve. |
| `aurora` | **Northern lights:** slow, softly blended colour waves drift across the lamps, blended from `glitter_colors` (empty = bridge `color`, then just a quiet fade up/down with no colour change). One full colour wave takes `4 × sweep_seconds`; brightness gently breathes between `glow_low` and `glow_high` meanwhile – with a period of `4 × sweep_seconds`, **capped at 12 s**, so a high `sweep_seconds` doesn't park the lamps near `glow_low` for minutes (where the bridge renders hues poorly). |
| `rainbow` | **Rainbow:** a continuous colour cycle (full hue circle) across all lamps, phase-offset per lamp, so a colour gradient visibly travels across the channels instead of all lamps changing colour in sync. One full rotation takes `4 × sweep_seconds`; brightness constant at `glow_high`. |
| `meteor` | **Meteor shower:** several independent comets (`meteor_count`, default 3) run at randomised speed (around `meteor_speed` channels/second, including backwards), start position and peak brightness in the bridge `color` around the channels – a denser, less orderly variant of `comet`, which drives only a single, deterministic comet. |
| `wipe` | **Fill bar:** the channels fill up one after another (in channel order) with the bridge `color`, like a loading bar – duration `sweep_seconds`. The bar then holds fully filled for `chase_pause` seconds before it resets and starts over. |
| `firework` | **Firework:** starting from the middle lamp/channel, a new burst in the bridge `color` spreads outward every `firework_interval_ms` milliseconds (`firework_speed` channels/second) and fades. |
| `ripple` | **Echo:** like `firework`, but the wave bounces off both ends of the channels and echoes back before it fades and the next pulse (`ripple_interval_ms`) starts; `ripple_speed` = wavefront speed in channels/second. |
| `wave` | **Wave:** a continuous brightness sine wave runs across the channels, several crests visible at once (unlike `comet`'s single, localised head). `wave_length` = number of channels per full wave (small = more, tighter crests), `sweep_seconds` = time the wave takes for one pass. |
| `flicker` | **Flicker:** lamps sporadically dip briefly from full brightness, like a failing bulb – the opposite of `glitter` (brightens) or `lightning` (one shared flash). `flicker_interval_ms` = mean gap between two dips across all of a bridge's lamps, `flicker_dip_ms` = how fast a lamp recovers afterwards. |
| `strobe` | **Strobe:** a hard, instant flash in the bridge `color` with no fade at all (unlike `pulse`'s soft ramp) – classic party look. `sweep_seconds` sets the period (time between two flashes). |
| `duel` | **Duel:** two comets launch from opposite ends of the channels – one in the bridge `color`, one in `color2` – meet in the middle and run back again; unlike `meteor` (independent, random) or `comet` (a single, deterministic loop). `sweep_seconds` sets the period of one full there-and-back run. |
| `chase` | **Gradient Lightstrips only** (each channel is a colour segment, not a separate lamp): `gc_count` soft-edged bands in the bridge `color` run at `gc_speed` segments/second across the channels, with `gc_background_color` in between. `gc_length` = width of a band's solid-colour core in segments (with a soft ~1-segment transition at the edges – hence "gradient"). `gc_direction`: `forward`/`backward` loop endlessly, `bounce` reflects off both ends (Larson scanner). With `gc_chase_glitter` the bands additionally sparkle like `glitter` (uses `glitter_interval_ms`/`glitter_flash_ms`/`glitter_colors`, sparks only inside the bands); with `gc_background_pulse` the background pulses between `glow_low` and `glow_high` like `pulse` (uses `attack_ms`/`release_ms`/`sweep_seconds`) instead of resting quietly at `glow_low` – the bands themselves stay unaffected at `glow_high`. Several Gradient Lightstrips can be combined by putting their segments in a shared Entertainment Area (one `channel_ids` strip); `gc_strip_lengths` (per bridge, e.g. `[7, 5]`) splits this combined strip back into the individual physical lightstrips, so `gc_direction` can be set **per strip** (as a list, e.g. `["forward", "backward"]`) – e.g. so two opposite strips run towards or away from each other. |
| `color_chase` | **Gradient-fill chase:** a colour gradient repaints itself lamp by lamp – as the head passes, each lamp fades over exactly one step to its target colour and holds it until the next sweep overwrites it. Three palettes run in turn, each a linear ramp from the start colour (chase-index 0) to the fully-mixed colour (last chase-index): `(255,0,0)→(255,255,0)`, `(0,255,0)→(0,255,255)`, `(0,0,255)→(255,0,255)`. `gc_speed` = lamps (steps) per second; also sets the per-step fade time (`1/gc_speed` s – high enough and the step becomes a hard snap). `gc_direction`: `forward`/`backward` always fill from the same end, `bounce` flips the fill direction with every palette. Absolute colours at a constant `glow_high` (like `rainbow`); no `gc_strips`/`gc_count`/`gc_length`/`gc_background_color`. |
| `neutral` | **No effect:** this bridge's lamps are not driven at all – no DTLS stream, no save/restore. Only useful set per bridge (`bridges[].effect: neutral`): so an effect set can run an effect on one bridge and leave another bridge out entirely. A `neutral` bridge doesn't need an `area_id`. If **all** bridges are `neutral`, `/start` responds with `no_active_bridges` (not an error). |

**Several bridges:** if more than one bridge is running, all start
**simultaneously** – every bridge's DTLS handshake runs in parallel, and the
shared effect clock only starts once all are done, so no bridge lags behind.
Each bridge can have its **own** effect, its own colour and its own timing
(`effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`,
`release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`,
`glitter_flash_ms`, `glitter_colors`, `gc_direction`, `gc_strip_lengths`,
`gc_count`, `gc_length`, `gc_speed`, `gc_background_color`,
`gc_chase_glitter`, `gc_background_pulse`, `color2`,
`lightning_interval_ms`, `lightning_flash_ms`, `meteor_count`,
`meteor_speed`, `firework_interval_ms`, `firework_speed`,
`ripple_interval_ms`, `ripple_speed`, `wave_length`, `flicker_interval_ms`,
`flicker_dip_ms` are all per-bridge overridable; values not overridden come
from the like-named app options. With `effect: neutral` per bridge, that
bridge stays completely off while the others run. `area_id` and
`channel_order` are always per-bridge values; `duration`, `fps` and
`restore_state`, on the other hand, always apply to all bridges together. If
a bridge is unreachable or not paired, the others still start (best effort)
– the failed one is reported in the `/start` response under
`failed_bridges`.

**Light state:** before the effect, the app snapshots on/off, brightness and
colour of every lamp in each area (Hue CLIP v2) and writes them back after
the effect – lamps that were off before go back off too. Can be disabled
with `restore_state: false` (then only the bridge's own automatic recovery
after the stream ends applies).

## Configuration

| Option          | Type               | Default    | Meaning |
|-----------------|--------------------|------------|-----------|
| `bridges`       | List (max. 3)      | `[]`       | One row per bridge: `bridge_host` (IP), `area_id` (step 1), optional `channel_order`, plus optional per-bridge `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors`, `gc_direction`, `gc_strip_lengths`, `gc_count`, `gc_length`, `gc_speed`, `gc_background_color`, `gc_chase_glitter`, `gc_background_pulse`, `color2`, `lightning_interval_ms`, `lightning_flash_ms`, `meteor_count`, `meteor_speed`, `firework_interval_ms`, `firework_speed`, `ripple_interval_ms`, `ripple_speed`, `wave_length`, `flicker_interval_ms`, `flicker_dip_ms` (override the like-named option below only for this bridge). |
| `effect`        | `pulse` \| `comet` \| `glitter` \| `police` \| `lightning` \| `heartbeat` \| `aurora` \| `rainbow` \| `meteor` \| `wipe` \| `firework` \| `ripple` \| `wave` \| `flicker` \| `strobe` \| `duel` \| `chase` \| `color_chase` \| `neutral` | `pulse`    | Default light effect for bridges without their own setting, see above. `neutral` only useful per bridge. |
| `color`         | Hex string         | `#FF0000`  | Default colour for bridges without their own setting. |
| `fps`           | int (5–50)         | `25`       | Frames/second of the DTLS stream (same for all bridges). |
| `sweep_seconds` | float (0.3–300.0)  | `1.4`      | Default for bridges without their own setting. `comet`: duration of one full loop. `pulse`/`heartbeat`: cycle length. `wave`/`strobe`/`duel`: period length. |
| `chase_pause`   | float (0–60)       | `0`        | Default for bridges without their own setting. `comet`: pause (seconds) between two runs. `0` = continuous looping comet. `> 0` = one run, then all lamps rest at `glow_low` for that many seconds, then the next. |
| `attack_ms`     | int (0–2000)       | `140`      | Default for bridges without their own setting. `pulse`: ramp-up time `glow_low` → `glow_high`. |
| `release_ms`    | int (0–5000)       | `70`       | Default for bridges without their own setting. `pulse`: ramp-down time → `glow_low` between pulses (smaller than `attack_ms` = faster fall). |
| `glow_low`      | float (0–1)        | `0.08`     | Default for bridges without their own setting. **All effects:** resting brightness between pulses. `0` = fully off. |
| `glow_high`     | float (0–1)        | `1.0`      | Default for bridges without their own setting. **All effects:** brightness at the pulse peak. Must be above `glow_low`. |
| `glitter_interval_ms` | float (5–5000) | `90`     | `effect: glitter` only. Mean gap (ms) between two sparkle flashes across all of a bridge's lamps. Small = frantic twinkle. Per-bridge overridable. |
| `glitter_flash_ms` | float (20–5000) | `260`     | `effect: glitter` only. Decay time constant (ms) of a single spark. Larger than `glitter_interval_ms` = several lamps sparkle at once. Per-bridge overridable. |
| `glitter_colors` | String            | `#FFFFFF #CFE8FF #FFF1D0` | `effect: glitter` only. Hex colours (space-separated) each spark picks from at random. Empty = the respective bridge's colour. Per-bridge overridable. |
| `gc_direction`  | `forward` \| `backward` \| `bounce` | `forward` | `effect: chase` only. Default chase direction. Per-bridge overridable, also as a comma-separated list there (one direction per strip, see `gc_strip_lengths`). |
| `gc_strip_lengths` | String (per bridge) | empty (one strip) | `effect: chase` only, per bridge only. Splits this bridge's channels into consecutive Gradient Lightstrips, e.g. `"7,5"`. Sum must match the channel count, otherwise a single strip applies. |
| `gc_count`      | int (1–8)          | `1`        | `effect: chase` only. Number of chase bands running at once, evenly spaced. Per-bridge overridable. |
| `gc_length`     | float (0.2–200)    | `2.0`      | `effect: chase` only. Width of a band's solid-colour core in segments. Per-bridge overridable. |
| `gc_speed`      | float (0.01–50)    | `4.0`      | `effect: chase` only. Segments per second a chase head travels. Per-bridge overridable. |
| `gc_background_color` | Hex string   | `#000000`  | `effect: chase` only. Colour outside the chase bands. Per-bridge overridable. |
| `gc_chase_glitter` | bool            | `false`    | `effect: chase` only. Makes the bands additionally sparkle like `glitter`. Per-bridge overridable. |
| `gc_background_pulse` | bool         | `false`    | `effect: chase` only. Makes the background additionally pulse like `pulse` instead of resting quietly at `glow_low`. Per-bridge overridable. |
| `color2` | Hex string         | `#0000FF`  | Second colour – `effect: police` (colour of the second lamp group, the first uses `color`) and `effect: duel` (colour of the second comet). Per-bridge overridable. |
| `lightning_interval_ms` | float (50–60000) | `4000` | `effect: lightning` only. Mean gap (ms) between two strikes that light every lamp of a bridge together. Per-bridge overridable. |
| `lightning_flash_ms` | float (20–5000) | `500`   | `effect: lightning` only. Decay time constant (ms) of a strike. Per-bridge overridable. |
| `meteor_count`  | int (1–8)          | `3`        | `effect: meteor` only. Number of independent meteors running at once. Per-bridge overridable. |
| `meteor_speed`  | float (0.05–20)    | `1.2`      | `effect: meteor` only. Average meteor speed in channels/second (each varies randomly around it). Per-bridge overridable. |
| `firework_interval_ms` | float (200–60000) | `3000` | `effect: firework` only. How often (ms) a new burst starts from the middle of the channels. Per-bridge overridable. |
| `firework_speed` | float (0.5–50)    | `6.0`      | `effect: firework` only. Outward expansion speed of the burst in channels/second. Per-bridge overridable. |
| `ripple_interval_ms` | float (200–60000) | `3000` | `effect: ripple` only. How often (ms) a new pulse starts from the middle of the channels. Per-bridge overridable. |
| `ripple_speed`  | float (0.5–50)     | `6.0`      | `effect: ripple` only. Wavefront speed in channels/second. Per-bridge overridable. |
| `wave_length`   | float (0.5–50)     | `3.0`      | `effect: wave` only. Channels per full sine wave. Per-bridge overridable. |
| `flicker_interval_ms` | float (20–10000) | `600`   | `effect: flicker` only. Mean gap (ms) between two dips across all of a bridge's lamps. Per-bridge overridable. |
| `flicker_dip_ms` | float (20–5000)   | `150`      | `effect: flicker` only. Recovery time (ms) of a lamp after a dip. Per-bridge overridable. |
| `restore_state` | bool               | `true`     | Snapshot lamp state (on/off, brightness, colour) before the effect and restore it afterwards (same for all bridges). |
| `duration`      | float (0–86400)    | `0`        | How long the effect runs by default before ending on its own (shared across all bridges; overridable per `/start` call). `0` = **unlimited**, runs until `/stop`. |
| `log_level`     | List               | `info`     | `trace`,`debug`,`info`,`notice`,`warning`,`error`,`fatal`. |

## REST API

Reachable at `http://<ha-ip>:8099` (port) or via Ingress (relative to the
panel path).

| Endpoint  | Method  | Purpose |
|-----------|---------|-------|
| `/`       | GET     | Web UI (Ingress panel). |
| `/health` | GET     | `{status, paired, running, armed, current_preset}` – `paired` is `true` once at least one bridge is paired; `running` is `true` once **any** bridge is currently running (for per-bridge status see `/config`'s `bridges[].running`); `armed` is `true` when **all** non-`neutral` paired bridges are armed; `current_preset` is the name of the effect set most recently started via `preset` (`null` on an ad-hoc start without `preset`). Also the container HEALTHCHECK target. |
| `/config` | GET     | Effective configuration incl. `bridges` (each entry also has `running: bool` and `armed: bool`), `armed` (global) + `armed_bridges` (list), `presets` (names of the saved effect sets) and `current_preset` – for the web UI and the Home Assistant integration. |
| `/pair`   | POST    | One-time pairing. Body: `{"bridge_host": "..."}` – required once more than one bridge is configured (optional with exactly one, still-unpaired, configured bridge). |
| `/areas`  | GET     | List a bridge's Entertainment areas + channels. Query `?bridge_host=...` – required once more than one bridge is paired. |
| `/start`  | POST    | Start the effect on all configured (or body-supplied) bridges simultaneously (returns immediately; DTLS handshakes run in the background, in parallel) – or, with `bridge_host` in the body, on only a single bridge, regardless of the others' state. Body optional: `duration`, `fps`, `restore_state` apply to all bridges together; `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors`, `gc_direction`, `gc_count`, `gc_length`, `gc_speed`, `gc_background_color`, `gc_chase_glitter`, `gc_background_pulse`, `color2`, `lightning_interval_ms`, `lightning_flash_ms`, `meteor_count`, `meteor_speed`, `firework_interval_ms`, `firework_speed`, `ripple_interval_ms`, `ripple_speed`, `wave_length`, `flicker_interval_ms`, `flicker_dip_ms` are the **default values** for bridges without their own setting. `bridges` (list of `{bridge_host, area_id, channel_order, effect?, color?, sweep_seconds?, chase_pause?, attack_ms?, release_ms?, glow_low?, glow_high?, glitter_interval_ms?, glitter_flash_ms?, glitter_colors?, gc_direction?, gc_strip_lengths?, gc_count?, gc_length?, gc_speed?, gc_background_color?, gc_chase_glitter?, gc_background_pulse?, color2?, lightning_interval_ms?, lightning_flash_ms?, meteor_count?, meteor_speed?, firework_interval_ms?, firework_speed?, ripple_interval_ms?, ripple_speed?, wave_length?, flicker_interval_ms?, flicker_dip_ms?}`) overrides the `bridges` option for this one call – each bridge can set its own effect parameters; `channel_order` as a list (`[2,3,1,0,5,4]`) or string (`"2,3,1,0,5,4"`), must contain exactly the respective area's channels, otherwise that one bridge is skipped. `gc_strip_lengths` (`chase` only, per bridge, e.g. `[7, 5]` or `"7,5"`) splits this bridge's channels into consecutive Gradient Lightstrips; `gc_direction` may then also be a list (one direction per strip). `preset` (name of a saved effect set) loads its body as a base; further body fields override it – not combinable with `bridge_host` (`400`). `bridge_host` (optional): filters to exactly this one bridge (must be present in `bridges`, option or body); `already_running` then only applies to it, and a solo start never touches `current_preset`. Without `bridge_host`, already-running bridges are skipped rather than rejecting the whole call (`skipped_bridges` in the response). The response contains `bridges` (actually newly started, each with resolved effect parameters), `failed_bridges` (skipped, with a reason), `neutral_bridges` and `skipped_bridges` (already active); `/start` responds `no_active_bridges` only if **no** bridge starts anew and none failed; if at least one failed and none are left, it responds `502`. |
| `/stop`   | POST    | Stop the effect on all running bridges immediately – or, with `bridge_host` in the body, on only a single bridge, regardless of the others' state. |
| `/arm`    | POST    | **Arm**: keep the DTLS stream to one/all bridge(s) permanently open so a later `/start` skips the ~3–9 s handshake and the effect begins almost instantly. Body optional `bridge_host` (otherwise all configured, non-`neutral` bridges). While armed, the bridge holds its single Entertainment slot and its lamps show an approximated still of the previous state. A bridge that is currently running cannot be armed (stop it first); response: `{status, armed:[...], already_armed:[...], busy:[...], failed:[...]}`. |
| `/disarm` | POST    | Undo arming: close the stream(s) and restore the light state captured at arm time via CLIP v2. Body optional `bridge_host` (otherwise all armed bridges). A still-running effect is stopped first. |
| `/select` | POST    | Remember an effect set as *loaded* **without** starting it – sets only `current_preset` (for the HA integration: select entity + "loaded effect set" sensor). Body `{"preset": "<name>"}` (`404` if unknown) or `{"preset": null}` / empty to clear. No streaming. |
| `/identify` | POST  | Cycle through a bridge's lamps individually (`channel_id` → lamp mapping). Body: `bridge_host` (required once more than one bridge is configured), `area_id` (optional, otherwise from the bridges configuration), `channel_id` (omitted = all channels in sequence), `seconds` (default 3 individually / 2 for "all"), `color`, `restore_state`. One DTLS handshake for the whole run. Occupies the same slot as an effect on this one bridge (`already_running`, `/stop` with the matching `bridge_host` cancels it) – other bridges are unaffected. |
| `/presets` | GET    | All saved effect sets: `{"presets": {name: body, …}, "names": [...]}`. With `?name=…` just that one (`{"name", "config"}`, `404` if unknown). |
| `/presets` | PUT / POST | Save/overwrite an effect set (also the upload target). Body `{"name": "...", "config": { <start body> }}` – `config` is the complete set of `/start` fields incl. `bridges`; stored under `/data/presets.json`. |
| `/presets` | DELETE | Delete an effect set. Query `?name=…` (or body `{"name": …}`). `404` if unknown. |

- `duration` (seconds, default from the like-named app option, **`0` =
  unlimited**) – how long the effect runs before ending on its own; can be
  cancelled at any time via `/stop`.

## Arming (faster start)

Between `/start` and the visible effect sits the bridge's DTLS handshake
(~1.5–9 s). To avoid that delay, **arm** the bridge beforehand (`POST /arm`,
in the web UI the "Arm" button on each bridge card or the global one under
"2 · Control", in Home Assistant the "Armed" switch): the DTLS stream then
stays open permanently and a following `/start` begins the effect within a
single frame.

While a bridge is armed:

- it holds its **single** Entertainment slot – other Entertainment apps and
  `/identify` for this bridge are blocked until `/disarm`;
- its lamps are under stream control and show an **approximated still** of the
  state present at arm time (the exact colours are restored only on `/disarm`
  via CLIP v2);
- it stays armed until `/disarm` is called or the app restarts (on shutdown
  the app disarms automatically and restores the light state).

`/start` still works without arming – just with the usual handshake first.

## Effect Sets

The complete set of start parameters (all bridge cards from "1 · Bridges"
**and** the controls from "2 · Control") can be saved under a name (e.g.
*Star Trek – Red Alert*) under "3 · Effect Sets" in the web UI. A saved set
can be

- **Loaded** – fills the whole form back in with the set's values,
- **Started** – starts it directly (without the detour via "Load" + "Start"),
- **Downloaded** – saved as a JSON file (`{"name": …, "config": {…}}`),
- **Uploaded** – re-imported from such a JSON file and stored as a set,
- **Deleted**.

Sets live as `/data/presets.json` in the app's data folder and survive
restarts. Via REST: `GET /presets` (all), `PUT /presets`
(`{"name", "config"}` – save/upload), `DELETE /presets?name=…` (delete) and
`POST /start {"preset": "<name>"}` (start; further body fields override the
set for this one call).

## Integrate with Home Assistant

**Ready-made integration (recommended):** in this repo, under
[`custom_components/redalert/`](https://github.com/ringind/redalert/tree/main/custom_components/redalert)
lies a standalone `custom_component` that creates six entities – two
`binary_sensor` (is the effect running? / are the bridges armed?), three
`switch` (animation on/off, per bridge, arm all bridges), a `select` (load a
saved effect set – only starts it if an animation is already running), and a
`sensor` (name of the loaded set). Install via **HACS** (the repo is HACS-capable
– `hacs.json` at the repo root – but not listed in the default store: HACS →
*Custom repositories* → `https://github.com/ringind/redalert`, category
*Integration*) or manually (copy the folder to `config/custom_components/`).
Then restart HA, then **Settings → Devices & Services → Add Integration →
"Red Alert Entertainment App"** (host + port 8099). Details: the
`README.en.md` in that folder.

**Without extra installation:** the REST API (see above) can also be used
directly via the built-in
**[`rest_command`](https://www.home-assistant.io/integrations/rest_command/)**
integration as a plain HA service (`rest_command.<name>`). Every
`rest_command` entry in `configuration.yaml` becomes a 1:1 service you can
call from automations, scripts, dashboard buttons, or **Developer Tools →
Actions**.

### Basics: passing parameters at call time

`rest_command` lets a service call carry **arbitrary extra fields** under
`data:` – those are then available as Jinja variables in this entry's
`payload` (or `url`). That way a single service, defined once in
`configuration.yaml`, can be fed different values on every call, without
needing a separate `rest_command` line for every combination. For JSON
bodies, use the `to_json` filter (correctly escapes quotes, special
characters and numbers) instead of embedding values by hand in `"…"`.
`{% if <name> is defined %}…{% endif %}` leaves out a field if no variable
of that name was passed at call time – so e.g. `duration` stays unset and
the app falls back to its own default (from the effect set or the option),
instead of a template-side default (e.g. `0`) unintentionally overriding it.

### `configuration.yaml`

```yaml
rest_command:
  # Starts with the app's configured default values (options or web UI).
  redalert_start:
    url: "http://<ha-ip>:8099/start"
    method: POST
    content_type: "application/json"
    payload: '{}'   # duration omitted: default from the duration app option

  # Starts a saved effect set (web UI "3 · Effect Sets" or PUT /presets).
  # Call e.g. with data: {preset: "Star Trek – Red Alert"}
  # optionally add data: {duration: 30} to override the duration for this one call.
  redalert_start_preset:
    url: "http://<ha-ip>:8099/start"
    method: POST
    content_type: "application/json"
    payload: >-
      {"preset": {{ preset | to_json }}
      {%- if duration is defined %}, "duration": {{ duration | float }}{% endif -%}
      }

  redalert_stop:
    url: "http://<ha-ip>:8099/stop"
    method: POST
```

After saving, **Developer Tools → YAML → Reload All YAML Configurations**
(or restart HA) so the new services show up.

### Starting an effect set from Home Assistant

The exact name of the set (case and spaces matter) is shown either in the
dropdown under "3 · Effect Sets" in the web UI, or via `GET /presets` (field
`names`).

**Test directly** – Developer Tools → Actions →
`rest_command.redalert_start_preset` → in YAML mode:

```yaml
preset: "Star Trek – Red Alert"
```

**Fixed service per set** (convenient for a dashboard button that always
starts the same set):

```yaml
script:
  redalert_red_alert:
    alias: "Red Alert: Red Alert"
    sequence:
      - service: rest_command.redalert_start_preset
        data:
          preset: "Star Trek – Red Alert"
```

`script.redalert_red_alert` then appears like any other entity and can be
triggered from a dashboard, by voice, or from an automation.

**Dropdown selection** – an `input_select` with the set names, plus a
script that starts whichever entry is currently selected:

```yaml
input_select:
  redalert_preset:
    name: Red Alert effect set
    options:
      - "Star Trek – Red Alert"
      - "Diamond Sparkle"   # maintain options by hand, see GET /presets

script:
  redalert_start_selected_preset:
    alias: "Red Alert: start selected set"
    sequence:
      - service: rest_command.redalert_start_preset
        data:
          preset: "{{ states('input_select.redalert_preset') }}"
```

Put `input_select.redalert_preset` on a dashboard, pick a set, then trigger
`script.redalert_start_selected_preset` via a button.

### Passing further parameters dynamically

All fields from the `/start` row of the REST API table above (`effect`,
`color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`,
`glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`,
`glitter_colors`, `bridges`, `fps`, `restore_state`, …) can be added
following the same pattern as `preset`/`duration` above – add one
`{% if <name> is defined %}, "<name>": {{ <name> | to_json }}{% endif %}`
block per field in the `payload` and pass the variable at call time via
`data:`. Example: set effect and colour independently of the configured
default:

```yaml
rest_command:
  redalert_start_custom:
    url: "http://<ha-ip>:8099/start"
    method: POST
    content_type: "application/json"
    payload: >-
      {"effect": {{ effect | to_json }}, "color": {{ color | to_json }}
      {%- if duration is defined %}, "duration": {{ duration | float }}{% endif -%}
      }
```

called e.g. with `data: {effect: "glitter", color: "#00FF88", duration: 20}`.

### Automation examples

Sound + light together (default effect):

```yaml
automation:
  - alias: "Red Alert"
    trigger:
      - platform: state
        entity_id: input_boolean.red_alert
        to: "on"
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.living_room
        data:
          media_content_id: media-source://media_source/local/red_alert.mp3
          media_content_type: audio/mpeg
      - service: rest_command.redalert_start

  - alias: "Red Alert – End"
    trigger:
      - platform: state
        entity_id: media_player.living_room
        to: "idle"
    action:
      - service: rest_command.redalert_stop
```

Trigger a specific effect set, e.g. briefly play the saved "Diamond Sparkle"
set instead of the default when the doorbell rings:

```yaml
automation:
  - alias: "Doorbell – Diamond Sparkle"
    trigger:
      - platform: state
        entity_id: binary_sensor.doorbell
        to: "on"
    action:
      - service: rest_command.redalert_start_preset
        data:
          preset: "Diamond Sparkle"
          duration: 8
      - delay: "00:00:08"
      - service: rest_command.redalert_stop   # optional safety net in case duration doesn't apply
```

## Log

The app's **log** (Log tab) shows the configuration at startup, pairing,
start/stop events and errors. Verbosity via `log_level`. The web UI
additionally shows the most recent API calls in the "Log" section – the
"Show requests" checkbox also shows the sent request bodies, and the
buttons next to it clear the log or download it as a text file.

## Troubleshooting

| Symptom | Cause / fix |
|---------|------------------|
| `/pair` fails | Link button not pressed in time (~30 s) or wrong IP. |
| `/start` → `already_running` | This bridge (or, for a call without `bridge_host`, all requested ones) is already running. Call `/stop` first, or – without `bridge_host` – just call `/start` again: already-running bridges are skipped (`skipped_bridges`), only the rest are newly started. |
| `/start` → 404 `area_id not found` | Check `/areas` – the area may have been renamed/deleted. |
| `/start` → 404 `effect set '…' not found` | The `preset` name doesn't exactly match (case, spaces) a saved set – check `GET /presets` or the "3 · Effect Sets" web UI dropdown. |
| `rest_command` call with `preset`/`duration`/… changes nothing | After changing `configuration.yaml`, **Developer Tools → YAML → Reload All YAML Configurations** (or restart HA); the "Show requests" checkbox in the web UI log, or the request under Developer Tools → Actions, shows the `payload` that was actually sent. |
| `/start` → 502 `no bridge reachable` | Did the bridge IP change? Network/VLAN between the HA host and the bridge (UDP 2100). With multiple bridges, `502` only means **none** of them were reachable – individual failures are in the `/start` response's `failed_bridges`, the other bridges still run. |
| The light only starts after a few seconds | Normal DTLS handshake; on Wi-Fi bridges sometimes a `ServerHello timeout` retry appears in the log. `/start` itself still responds immediately regardless. |
| Lamps don't react | V1 bridge (no Entertainment) or UDP port 2100 to the bridge is blocked. |
| Streaming stops | Each bridge allows only **one** active Entertainment stream (per bridge, not global) – close the Hue Sync app/other clients on the same bridge. |
| The light chase stutters | Increase `fps` or check network load to the bridge. |
| Start fails with `/bin/sh: can't open '/init': Permission denied` | Fixed as of 1.0.1 (no more custom AppArmor profile). Update the app; uninstall and reinstall an older version if the update doesn't take effect. |
