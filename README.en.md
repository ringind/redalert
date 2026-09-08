# Red Alert Entertainment App

[![Build](https://github.com/ringind/redalert/actions/workflows/build.yaml/badge.svg)](https://github.com/ringind/redalert/actions/workflows/build.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

🇬🇧 English (this file) · 🇩🇪 [Deutsch](README.md)

Home Assistant app for freely configurable light effects across multiple
Philips Hue lamps, driven by the real **Hue Entertainment API** (DTLS
streaming, not the normal, sluggish Bridge scene). Originally built for the
Star Trek "Red Alert" scene (hence the name) – now a general-purpose light
effect player: any number of **effect sets** (effect, colour, timing per
bridge) can be saved under a name and recalled at the press of a button, by
voice, or from an automation, from the namesake red alert to calm ambient
lighting or a diamond-sparkle party effect. Supports **up to 3 Hue Bridges**
running simultaneously – each with its own effect, its own colour and its own
timing – or independently, one after another, via their own Start/Stop, in
the web UI and in the Home Assistant integration alike. **18 effects** are
available – from calm (`pulse`, `aurora`)
through classic (`comet`, `chase`, `wave`) to action-packed
(`police`, `lightning`, `strobe`, `duel`, `meteor`, `firework`, `ripple`,
`glitter`, `flicker`, `heartbeat`, `wipe`) – see
[§8 "Customizing Effects"](#8-customizing-effects) for all of them in detail.
Colour(s), timing and brightness are freely configurable for every effect
(web UI colour picker, app option, or REST body), not just red. With
`effect: neutral` per bridge, one bridge stays completely untouched while the
others run. Runs for a configurable duration (option `duration`, applies to
all bridges together; `0` = unlimited, runs until `/stop`). All start
parameters can be saved as a named **effect set**, loaded/started again, and
exported/imported as a JSON file.

Uses the [`hue-entertainment`](https://github.com/music-assistant/hue-entertainment)
library (the same one that powers Music Assistant's Hue Entertainment plugin).

> **This repository is a Home Assistant App Store repository**
> (Home Assistant renamed "add-ons" to "apps" as of version 2026.2 – purely
> a wording change, still Docker containers via the Supervisor under the
> hood). Installation: **Settings → Apps → App Store → ⋮ → Repositories**,
> add this repo's URL, then install **Red Alert Entertainment**. The actual
> app lives in the [`redalert/`](redalert/) subfolder; the instructions shown
> inside Home Assistant are [`redalert/DOCS.en.md`](redalert/DOCS.en.md).
> A web UI for control (pairing, areas, start/stop) appears after
> installation as the **Red Alert** sidebar entry (Ingress); a toggle in the
> top-right corner switches between German and English.

Tested with Hue Bridge V2 (BSB002, API 1.78): pairing, area discovery,
DTLS streaming and start/stop work end-to-end.

---

## Contents

1. [Overview & Architecture](#overview--architecture)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Create an Entertainment Area in the Hue App](#1-create-an-entertainment-area-in-the-hue-app)
5. [Install the App](#2-install-the-app)
6. [Pair with Each Bridge Once](#3-pair-with-each-bridge-once)
7. [Determine Area ID and Channel Order](#4-determine-area-id-and-channel-order)
8. [App Options](#5-app-options)
9. [REST API](#6-rest-api)
10. [Integrate with Home Assistant](#7-integrate-with-home-assistant)
11. [Customizing Effects](#8-customizing-effects)
12. [Troubleshooting](#9-troubleshooting)
13. [Project Structure](#project-structure)

---

## Overview & Architecture

Home Assistant's normal Hue scenes run over the Bridge's REST/CLIP API and
are too sluggish for a clean, frame-accurate light effect. A real,
low-latency light effect needs a persistent **DTLS stream** to the bridge
(the same protocol Hue Sync/Gaming Sync uses). Home Assistant doesn't do
this natively, so a small standalone app takes care of it:

```
HA automation ──┬──> media_player.play_media (optional: your sound, e.g. Sonos)
                └──> rest_command → app /start
                                        │
                                        ▼
                           App (Python, aiohttp)
                         keeps its own DTLS stream open
                         per bridge (up to 3, ~25 Hz),
                         each with its own effect/colour/timing
                         (18 effects, see §8)
                                        │
                              ┌─────────┼─────────┐
                              ▼         ▼         ▼
                          Bridge 1   Bridge 2   Bridge 3
                              │         │         │
                              ▼         ▼         ▼
                          Hue lamps  Hue lamps  Hue lamps
```

The app runs permanently in the background and exposes a small REST API
(`/pair`, `/areas`, `/start`, `/stop`) that you call from Home Assistant
automations.

## Prerequisites

- Home Assistant **OS or Supervised** (App Store required; on Core/Container
  the service would have to run separately as a container/systemd service
  instead).
- One to three Hue Bridge **V2** ("square") or Hue Pro Bridge – V1 bridges
  don't support Entertainment streaming.
- Per bridge: Hue lamps (colour/colour-temperature capable), assigned to an
  Entertainment area.
- Access to the HA host via a Samba or SSH app, to copy the app folder to
  `/addons/`.

Only needed for the Star-Trek-style sound+light automation (optional – the
app itself doesn't need any audio):

- A `media_player` entity in Home Assistant (Sonos/Chromecast/speaker etc.)
  for sound playback.
- Your own, legally obtained audio file with the alert sound.

## Quick Start

1. Create Entertainment area(s) in the Hue app (one per bridge).
2. Add this repo to the App Store as a repository, install and start
   **Red Alert Entertainment**.
3. Per bridge: press the link button, then click **Pair** in the web UI
   (or call `POST /pair`).
4. Per bridge: call `GET /areas?bridge_host=...`, enter the result as a row
   in the `bridges` app option.
5. Create a `rest_command` + automation in Home Assistant (template below).
6. Done – fire the trigger, all configured bridges play simultaneously.

---

## 1. Create an Entertainment Area in the Hue App

1. Hue app → Settings → Entertainment areas → New area.
2. Add all 6 lamps and roughly place them in the 3D grid to match their
   physical arrangement (only relevant for the Hue app's preview, not for
   this app).
3. Save the area. The order in which you add the lamps determines the
   `channel_id` order later used for the light effect.

## 2. Install the App

**Settings → Apps → App Store → "⋮" top right → Repositories**, then enter
and add this GitHub repository's URL. The app then appears in the store as
**Red Alert Entertainment** – install and start it. Recommended: enable
"Start on boot".

(Alternatively, as a local app: copy the `redalert/` subfolder to
`/addons/redalert` on the HA host and reload repositories.)

## 3. Pair with Each Bridge Once

Press the physical link button on the Hue Bridge, then pair **within
~30 seconds** – either in the web UI (sidebar **Red Alert** → bridge card
under "1 · Bridges") or via REST, for each bridge individually:

```bash
curl -X POST http://<home-assistant-ip>:8099/pair \
  -H "Content-Type: application/json" \
  -d '{"bridge_host": "192.168.1.50"}'
```

The response contains `username` and `clientkey` – automatically saved (per
bridge) in the app's data folder (`/data/credentials.json`), nothing to
remember. Pairing only needs to be done once per bridge, unless you reset
the app completely.

## 4. Determine Area ID and Channel Order

```bash
curl "http://<home-assistant-ip>:8099/areas?bridge_host=192.168.1.50"
```

Returns e.g.:

```json
[{"id": "abcd-1234", "name": "Red Alert", "channels": [0, 1, 2, 3, 4, 5]}]
```

Enter `bridge_host` + the `id` as a row in the `bridges` app option
(the app's Configuration tab; one row per bridge). If the `channels` order
doesn't match your physical arrangement, you can explicitly set the desired
order in the same row as `channel_order` – as a comma-separated list (e.g.
`2,3,1,0,5,4`), either as an app option or directly in the web UI in the
respective bridge card. Which `channel_id` is which lamp can be found in the
bridge card under "Assign lamps" (lights up the channels one by one).
Restart the app after changing options.

## 5. App Options

| Option           | Type          | Default | Meaning                                                       |
|-------------------|--------------|----------|-------------------------------------------------------------------|
| `bridges`         | List (max. 3) | empty   | One row per bridge: `bridge_host` (IP), `area_id` (see step 4), optional `channel_order`, plus optional per-bridge `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors`, `gc_direction`, `gc_strip_lengths`, `gc_count`, `gc_length`, `gc_speed`, `gc_background_color`, `gc_chase_glitter`, `gc_background_pulse`, `color2`, `lightning_interval_ms`, `lightning_flash_ms`, `meteor_count`, `meteor_speed`, `firework_interval_ms`, `firework_speed`, `ripple_interval_ms`, `ripple_speed`, `wave_length`, `flicker_interval_ms`, `flicker_dip_ms` (override the like-named option below only for this bridge). |
| `effect`          | `pulse`\|`comet`\|`glitter`\|`police`\|`lightning`\|`heartbeat`\|`aurora`\|`rainbow`\|`meteor`\|`wipe`\|`firework`\|`ripple`\|`wave`\|`flicker`\|`strobe`\|`duel`\|`chase`\|`neutral` | `pulse` | Default for bridges without their own setting, see §8 for all effects in detail. `neutral` (only useful per bridge) = bridge is not driven. |
| `color`           | Hex string    | `#FF0000`| Default colour for bridges without their own setting.                |
| `fps`             | int (5–50)    | 25       | Frames/second of the DTLS stream (same for all bridges).         |
| `sweep_seconds`   | float (0.3–300) | 1.4    | Default for bridges without their own setting. `comet`: duration of one full loop. `pulse`/`heartbeat`: cycle length. `wave`/`strobe`/`duel`: period length. |
| `chase_pause`     | float (0–60)  | 0        | Default for bridges without their own setting. `comet`: pause (s) between two runs. `0` = continuous; `> 0` = one run, then all lamps rest at `glow_low` for `chase_pause` s. |
| `attack_ms`       | int (0–2000)  | 140      | Default for bridges without their own setting. `pulse`: ramp-up time `glow_low` → `glow_high`. |
| `release_ms`      | int (0–5000)  | 70       | Default for bridges without their own setting. `pulse`: ramp-down time → `glow_low` (smaller than `attack_ms`). |
| `glow_low`        | float (0–1)   | 0.08     | Default for bridges without their own setting. **All effects:** resting brightness between pulses (`0` = fully off). |
| `glow_high`       | float (0–1)   | 1.0      | Default for bridges without their own setting. **All effects:** brightness at the pulse peak (above `glow_low`). |
| `glitter_interval_ms` | float (5–5000) | 90   | `glitter` only. Mean gap (ms) between two sparkle flashes across all of a bridge's lamps. Per-bridge overridable. |
| `glitter_flash_ms` | float (20–5000) | 260   | `glitter` only. Decay time constant (ms) of a spark; > `glitter_interval_ms` ⇒ several lamps sparkle at once. Per-bridge overridable. |
| `glitter_colors`  | String        | `#FFFFFF #CFE8FF #FFF1D0` | `glitter` only. Space-separated hex colours each spark picks from at random. Empty = bridge colour. Per-bridge overridable. |
| `gc_direction`    | `forward`\|`backward`\|`bounce` | `forward` | `chase` only. Default chase direction. Per-bridge overridable, also as a comma-separated list there (one direction per strip, see `gc_strip_lengths`). |
| `gc_strip_lengths` | String (per bridge) | empty (one strip) | `chase` only, per bridge only. Splits the channels into consecutive Gradient Lightstrips, e.g. `"7,5"`. |
| `gc_count`        | int (1–8)     | `1`      | `chase` only. Number of chase bands running at once. Per-bridge overridable. |
| `gc_length`       | float (0.2–200) | `2.0`  | `chase` only. Width of a band's solid-colour core in segments. Per-bridge overridable. |
| `gc_speed`        | float (0.01–50) | `4.0`  | `chase` only. Segments per second. Per-bridge overridable. |
| `gc_background_color` | Hex string | `#000000` | `chase` only. Colour outside the chase bands. Per-bridge overridable. |
| `gc_chase_glitter` | bool         | `false`  | `chase` only. Makes the bands additionally sparkle like `glitter`. Per-bridge overridable. |
| `gc_background_pulse` | bool     | `false`  | `chase` only. Makes the background additionally pulse like `pulse` instead of resting quietly at `glow_low`. Per-bridge overridable. |
| `color2`   | Hex string    | `#0000FF`| Second colour – `police` (group 2), `duel` (second comet). Per-bridge overridable. |
| `lightning_interval_ms` | float (50–60000) | `4000` | `lightning` only. Mean gap (ms) between two shared flashes. Per-bridge overridable. |
| `lightning_flash_ms` | float (20–5000) | `500` | `lightning` only. Decay time constant (ms) of a flash. Per-bridge overridable. |
| `meteor_count`    | int (1–8)     | `3`      | `meteor` only. Number of independent meteors. Per-bridge overridable. |
| `meteor_speed`    | float (0.05–20) | `1.2`  | `meteor` only. Average speed in channels/second. Per-bridge overridable. |
| `firework_interval_ms` | float (200–60000) | `3000` | `firework` only. How often (ms) a new burst starts. Per-bridge overridable. |
| `firework_speed`  | float (0.5–50) | `6.0`   | `firework` only. Outward expansion speed in channels/second. Per-bridge overridable. |
| `ripple_interval_ms` | float (200–60000) | `3000` | `ripple` only. How often (ms) a new pulse starts. Per-bridge overridable. |
| `ripple_speed`    | float (0.5–50) | `6.0`   | `ripple` only. Wavefront speed in channels/second. Per-bridge overridable. |
| `wave_length`     | float (0.5–50) | `3.0`   | `wave` only. Channels per full sine wave. Per-bridge overridable. |
| `flicker_interval_ms` | float (20–10000) | `600` | `flicker` only. Mean gap (ms) between two dips. Per-bridge overridable. |
| `flicker_dip_ms`  | float (20–5000) | `150`  | `flicker` only. Recovery time (ms) after a dip. Per-bridge overridable. |
| `restore_state`   | bool          | `true`   | Snapshot lamp state before the effect and restore it afterwards (same for all bridges). |
| `duration`        | float (0–86400) | `0`    | Default runtime in seconds (shared across all bridges; overridable in the `/start` body). `0` = **unlimited**, runs until `/stop`. |
| `log_level`       | List          | `info`   | Verbosity of the app log (`trace`…`fatal`).           |

## 6. REST API

| Endpoint  | Method  | Purpose                                                                                 |
|-----------|---------|-----------------------------------------------------------------------------------------|
| `/`       | GET     | Web UI (Ingress panel "Red Alert")                                                      |
| `/health` | GET     | Status: `{status, paired, running, armed, current_preset}` – at least one bridge paired? is the effect currently running on **any** bridge (see `/config` for per-bridge status)? are all non-`neutral` bridges armed? name of the most recently loaded effect set (`null` on an ad-hoc start)? Also the container HEALTHCHECK target |
| `/config` | GET     | Effective configuration incl. `bridges` (each entry also has `running: bool` and `armed: bool`), `armed`/`armed_bridges` (global), `presets` (effect set names) and `current_preset` – for the web UI and the Home Assistant integration |
| `/pair`   | POST    | One-time pairing with a bridge. Body: `{"bridge_host": "..."}` (required when more than one bridge is configured) |
| `/areas`  | GET     | List Entertainment areas + channels of a bridge. Query `?bridge_host=...` (required when more than one bridge is paired) |
| `/start`  | POST    | Start the effect on all configured (or body-supplied) bridges simultaneously (returns immediately; DTLS handshakes run in the background, in parallel) – or, with `bridge_host` in the body, on only a single bridge, regardless of the others' state. Body optional: `duration` (s, default from the `duration` option, `0` = unlimited), `fps`, `restore_state` (shared across all bridges); `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors`, `gc_direction`, `gc_count`, `gc_length`, `gc_speed`, `gc_background_color`, `gc_chase_glitter`, `gc_background_pulse`, `color2`, `lightning_interval_ms`, `lightning_flash_ms`, `meteor_count`, `meteor_speed`, `firework_interval_ms`, `firework_speed`, `ripple_interval_ms`, `ripple_speed`, `wave_length`, `flicker_interval_ms`, `flicker_dip_ms` are the defaults for bridges without their own setting. `bridges` (list of `{bridge_host, area_id, channel_order, effect?, color?, sweep_seconds?, chase_pause?, attack_ms?, release_ms?, glow_low?, glow_high?, glitter_interval_ms?, glitter_flash_ms?, glitter_colors?, gc_direction?, gc_strip_lengths?, gc_count?, gc_length?, gc_speed?, gc_background_color?, gc_chase_glitter?, gc_background_pulse?, color2?, lightning_interval_ms?, lightning_flash_ms?, meteor_count?, meteor_speed?, firework_interval_ms?, firework_speed?, ripple_interval_ms?, ripple_speed?, wave_length?, flicker_interval_ms?, flicker_dip_ms?}`, `channel_order` as `[2,3,1,0,5,4]` or `"2,3,1,0,5,4"`) overrides the `bridges` option for this one call; `gc_strip_lengths` (`chase` only, per bridge, e.g. `[7,5]`) splits this bridge's channels into several Gradient Lightstrips, `gc_direction` may then be a list (one direction per strip). `preset` = name of a saved effect set as a base (further body fields override it) – not combinable with `bridge_host`. `bridge_host` (optional) filters to exactly this one bridge; `already_running` then only applies to it. Without `bridge_host`, already-running bridges are skipped (`skipped_bridges`) rather than rejecting the call. The response contains `bridges` (newly started, each with resolved parameters) + `failed_bridges`/`neutral_bridges`/`skipped_bridges`; `502` only if no bridge starts and at least one failed. |
| `/stop`   | POST    | Stop the effect on all running bridges immediately – or, with `bridge_host` in the body, on only a single bridge                                       |
| `/arm`    | POST    | **Arm**: keep the DTLS stream to one/all bridge(s) permanently open so a later `/start` skips the ~3–9 s handshake. Body optional `bridge_host` (otherwise all configured, non-`neutral` bridges). While armed the bridge holds its single Entertainment slot; its lamps show an approximated still of the previous state. Running bridge → stop it first. |
| `/disarm` | POST    | Undo arming: close the stream(s), restore the light state via CLIP v2. Body optional `bridge_host`. A running effect is stopped first. |
| `/select` | POST    | Remember an effect set as *loaded* (`current_preset`), **without** starting it. Body `{"preset": "<name>"}` (`404` if unknown) or `{"preset": null}` to clear. For the HA integration (select entity + sensor). |
| `/identify` | POST  | Cycle through a bridge's lamps individually (`channel_id` → lamp). Body: `bridge_host` (required when more than one bridge is configured), `area_id` (optional, otherwise from the bridges configuration), `channel_id` (omitted = all in sequence), `seconds`, `color`, `restore_state`. One DTLS handshake for the whole run; occupies the same slot as an effect on this one bridge (blocked while the bridge is armed – disarm first). |
| `/presets` | GET / PUT / POST / DELETE | Manage effect sets (`/data/presets.json`). `GET` = all (`{presets, names}`) or `?name=…` one. `PUT`/`POST` `{"name","config"}` = save/overwrite (also the upload target). `DELETE ?name=…` = delete. |

Omit `duration` → the effect runs with the default from the `duration` app
option (default `0` = **unlimited**, runs until `/stop`); with a positive
value it ends by itself after that many seconds. If a bridge is unreachable,
the others still start (best effort) – see `failed_bridges`.

**Faster start:** otherwise the bridge's DTLS handshake (~1.5–9 s) sits between
`/start` and the visible effect. `POST /arm` keeps the stream open beforehand
(web UI: "Arm" button per bridge card or global; Home Assistant: "Armed"
switch); a following `/start` then begins within a single frame. While armed
the bridge holds its single Entertainment slot and its lamps show an
approximated still; `POST /disarm` closes the stream and restores the exact
state.

## 7. Integrate with Home Assistant

**Ready-made integration:** [`custom_components/redalert/`](custom_components/redalert)
in this repo creates six entities (`binary_sensor` "Operating state",
`binary_sensor` "Armed", `switch` "Animation", `switch` "Armed", `select`
"Effect set" – loads only, starts only if an animation is running –, `sensor`
"Loaded effect set").
Install via **HACS** (repo category *Integration*, add as a custom
repository – `hacs.json` at the repo root) or manually (copy the folder to
`config/custom_components/`); then restart HA and go to
**Settings → Devices & Services → Add Integration → "Red Alert
Entertainment App"**. Details in
[`custom_components/redalert/README.md`](custom_components/redalert/README.md).

**Without extra installation** – `configuration.yaml`:

```yaml
rest_command:
  redalert_start:
    url: "http://<home-assistant-ip>:8099/start"
    method: POST
    content_type: "application/json"
    payload: '{}'   # duration omitted: default from the duration app option

  redalert_stop:
    url: "http://<home-assistant-ip>:8099/stop"
    method: POST
```

Example automation combining sound and light for the namesake red-alert
scene (your own, legally obtained audio file, e.g. under
`config/www/red_alert.mp3` or in the media folder) – any other effect set
(calm ambience, diamond sparkle for a party, …) can be hooked up to an
automation the same way, e.g. via `rest_command.redalert_start_preset` and
`{"preset": "<name>"}`, see
["Effect sets" in the app docs](redalert/DOCS.en.md#effect-sets):

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

Tip: `input_boolean.red_alert` is easy to toggle from a dashboard tile or by
voice.

## 8. Customizing Effects

Choose the effect: option `effect` or
`"effect": "pulse"|"comet"|"glitter"|"police"|"lightning"|"heartbeat"|"aurora"|"rainbow"|"meteor"|"wipe"|"firework"|"ripple"|"wave"|"flicker"|"strobe"|"duel"|"chase"` in the `/start` body
(default for bridges without their own setting), or `effect` in the
respective row of the `bridges` option/list for just one bridge.

**All effects:** `glow_low` / `glow_high` (options, `/start` body **or**
per bridge in `bridges`, `0`–`1`) set what the lamps return to between
pulses and how bright the pulse peak is. Default `0.08` / `1.0`;
`glow_low: 0` = fully off.

`pulse` (default) – all lamps together from `glow_low` to `glow_high` and
back:
- `attack_ms` / `release_ms` – ramp-up/ramp-down time; pick a smaller
  `release_ms` for a faster fall than rise.
- `sweep_seconds` – cycle length of one up/down run.
- `RedAlertPulse` `lo` / `hi` / `hold_s` in `redalert/rootfs/app/chase.py` –
  beat gate (Schmitt trigger): turns on above `hi`, off again once the level
  has stayed below `lo` for `hold_s`.

`comet` – a comet loops around; each lamp pulses on its own: briefly bright
(`glow_high`), a long fade, then a rest at `glow_low`, then again. The head
is a bit wider than the lamp spacing, so two adjacent lamps briefly sit at
100 % together and then fade out one after another
(`RedAlertComet` in `chase.py`):
- `sweep_seconds` – duration of one full loop around all lamps (default
  1.4 s); also the gap between two pulses of the same lamp.
- `chase_pause` – pause in seconds between two runs (option, `/start` body
  **or** per bridge in `bridges`, default 0). `0` = seamlessly looping comet
  as before; `> 0` = one run (every lamp pulses once, the last one fades
  out), then all lamps rest at `glow_low` for `chase_pause` s, then the next
  run.
- `attack_frac` – rise time as a fraction of `sweep_seconds` (small = snaps
  bright, default 0.07).
- `peak_frac` – minimum width of the flat 100 % head (default 0.08); keeps
  the peak sampling-proof at any frame rate so it doesn't flicker.
- `overlap_frac` – how long (fraction of `sweep_seconds`) two adjacent lamps
  sit at 100 % together (default 0.10 ≈ 140 ms). The head is thus
  `1/n + overlap_frac` wide.
- `decay_frac` – decay time constant as a fraction of `sweep_seconds`
  (default 0.22); how steep the start of the fade is.
- `fade_frac` – fraction of the cycle after which the 0..1 shape **reaches
  the floor** and stays there until the next rise (default 0.62).

`glitter` – diamond twinkle; each lamp sparkles independently and decays
fast (`RedAlertGlitter` in `chase.py`):
- `glitter_interval_ms` – mean gap in milliseconds between two sparkles
  across all of a bridge's lamps (option, `/start` body **or** per bridge in
  `bridges`, default 90). Small = more frantic twinkle.
- `glitter_flash_ms` – decay time constant of a single spark in
  milliseconds (default 260). Larger than `glitter_interval_ms` ⇒ several
  lamps sparkle at once.
- `glitter_colors` – space-separated list of hex colours each spark picks
  from at random, e.g. `#FFFFFF #CFE8FF #FFF1D0`. Empty = the (bridge)
  colour. `glow_low` / `glow_high` apply as with the other effects for the
  resting/peak brightness.

The effect colour comes from the respective bridge's `color` (or the
option/`/start` body default); `chase.py` only computes the brightness,
`main.py` sets the colour via `LightColorCommand`. For `glitter`, `chase.py`
additionally supplies a colour per spark from `glitter_colors`.

`police` – emergency lights; every other lamp (in channel order) forms a
group, the two groups flash alternately (`RedAlertPolice` in `chase.py`):
- `sweep_seconds` – duration of one full switch (both groups on once).
- `color2` – colour of the second group (option, `/start` body **or**
  per bridge in `bridges`, default `#0000FF`); the first group uses the
  normal bridge `color`.

`lightning` – storm; all lamps of a bridge flash **together** (unlike
`glitter`, where each lamp sparkles on its own), with an occasional
double-strike (`RedAlertLightning` in `chase.py`):
- `lightning_interval_ms` – mean gap in milliseconds between two strikes
  (option, `/start` body **or** per bridge in `bridges`, default 4000).
- `lightning_flash_ms` – decay time constant of a strike in milliseconds
  (default 500).

`heartbeat` – a double pulse ("lub-dub") instead of a single pulse, runs
through the same beat gate/slew as `pulse` (`RedAlertPulse.heartbeat` in
`chase.py`):
- `sweep_seconds` – duration of one full heartbeat (both beats).
- `attack_ms` / `release_ms` – as with `pulse`, the ramp-up/ramp-down time
  of both beats.

`aurora` – northern lights; slow, softly blended colour waves drift across
the lamps (`RedAlertAurora` in `chase.py`, computes the colour directly
instead of a brightness curve):
- `glitter_colors` – palette the wave blends through (empty = just the
  bridge `color`, then with no colour change).
- `sweep_seconds` – one full colour wave takes `4 × sweep_seconds`. The
  overlaid brightness breath uses the same period but **at most 12 s** –
  otherwise a high `sweep_seconds` would park the lamps near `glow_low` for
  minutes, where they render wrong hues.

`rainbow` – a continuous rainbow hue-cycle, phase-offset per lamp, so a
colour gradient visibly travels across the lamps instead of all of them
changing colour at once (`RedAlertRainbow` in `chase.py`):
- `sweep_seconds` – one full rotation takes `4 × sweep_seconds`; brightness
  is constant at `glow_high`.

`meteor` – several independent comets with randomised speed, direction and
peak brightness – a denser, less orderly variant of `comet`
(`RedAlertMeteor` in `chase.py`):
- `meteor_count` – number of meteors running at once (option, `/start` body
  **or** per bridge in `bridges`, default 3).
- `meteor_speed` – average speed in channels/second, each meteor varies
  randomly around it, including backwards (default 1.2).

`wipe` – a fill bar runs once across the channels, holds briefly, then
starts over (`RedAlertWipe` in `chase.py`):
- `sweep_seconds` – duration of filling from channel 0 to the last channel.
- `chase_pause` – how long the bar holds fully filled before it resets
  (default 0).

`firework` – recurring bursts from the middle lamp/channel that spread
outward and fade (`RedAlertFirework` in `chase.py`):
- `firework_interval_ms` – how often a new burst starts (option, `/start`
  body **or** per bridge in `bridges`, default 3000).
- `firework_speed` – expansion speed in channels/second (default 6.0).

`ripple` – like `firework`, but the wave bounces off both ends of the
channels and echoes back before fading (`RedAlertRipple` in `chase.py`):
- `ripple_interval_ms` – how often a new pulse starts (option, `/start`
  body **or** per bridge in `bridges`, default 3000).
- `ripple_speed` – wavefront speed in channels/second, also on the way back
  (default 6.0).

`wave` – a continuous sine wave of brightness runs across the channels,
several crests visible at once – unlike `comet`'s single, localised head
(`RedAlertWave` in `chase.py`):
- `wave_length` – number of channels per full wave (option, `/start` body
  **or** per bridge in `bridges`, default 3.0); small = more, tighter crests
  visible at once.
- `sweep_seconds` – time the wave takes for one pass.

`flicker` – lamps sporadically dip briefly from full brightness, like a
failing bulb – the opposite of `glitter` (brightens) or `lightning` (one
shared flash) (`RedAlertFlicker` in `chase.py`):
- `flicker_interval_ms` – mean gap between two dips across all of a
  bridge's lamps (option, `/start` body **or** per bridge in `bridges`,
  default 600).
- `flicker_dip_ms` – how fast a lamp recovers after a dip (default 150).

`strobe` – a hard, instant flash in the bridge `color` with no fade at all,
unlike `pulse`'s soft ramp – classic party look (`RedAlertStrobe` in
`chase.py`):
- `sweep_seconds` – period length (time between two flashes).

`duel` – two comets launch from opposite ends of the channels – one in the
bridge `color`, one in `color2` – meet in the middle and bounce back,
unlike `meteor` (independent, random) or `comet` (a single, deterministic
loop) (`RedAlertDuel` in `chase.py`):
- `sweep_seconds` – period length of one full there-and-back run.
- `color2` – colour of the second comet (default `#0000FF`).

`chase` – **Gradient Lightstrips only** (each channel is a colour segment,
not a separate lamp): one or more soft-edged bands in the bridge `color`
slide across the segments, `gc_background_color` in between
(`RedAlertChase` in `chase.py`):
- `gc_count` – number of bands running at once, evenly spaced (default 1).
- `gc_length` – width of a band's solid-colour core in segments (default
  2.0); the transition to the background colour at the edges is soft (~1
  segment) rather than hard – hence "gradient".
- `gc_speed` – segments per second a band head travels (default 4.0).
- `gc_direction` – `forward`/`backward` loop endlessly (like `comet`),
  `bounce` reflects off both ends (Larson scanner) instead of looping.
- `gc_chase_glitter` – makes the bands additionally sparkle like `glitter`
  (uses `glitter_interval_ms`/`glitter_flash_ms`/`glitter_colors`), sparks
  only inside the bands.
- `gc_background_pulse` – makes the background additionally pulse between
  `glow_low` and `glow_high` like `pulse` (uses `attack_ms`/`release_ms`/
  `sweep_seconds`), instead of resting quietly at `glow_low`; the bands
  themselves stay unaffected at `glow_high`.

Several Gradient Lightstrips can be combined by putting their segments in a
shared Entertainment Area – the bridge then sees one single, continuous
`channel_ids` strip. `gc_strip_lengths` (per bridge only, e.g. `[7, 5]` or
`"7,5"`) splits this combined strip back into the individual physical
lightstrips, so `gc_direction` can be set **per strip** (as a list, e.g.
`["forward", "backward"]`) – e.g. so two opposite strips run towards or away
from each other.

`color_chase` – **gradient-fill chase** (`RedAlertColorChase` in `chase.py`):
a colour gradient repaints itself lamp by lamp – as the head passes, each lamp
switches **instantly** to its target colour and holds it until the next
sweep overwrites it. Three palettes run in turn, each a linear ramp from the
start colour (chase-index 0) to the fully-mixed colour (last chase-index):
`(255,0,0)→(255,255,0)`, `(0,255,0)→(0,255,255)`, `(0,0,255)→(255,0,255)`.
- `gc_speed` – lamps (steps) per second; the dwell is rounded to a whole
  number of frames so every step lasts exactly the same time.
- `gc_direction` – `forward`/`backward` always fill from the same end,
  `bounce` flips the fill direction with every palette.
- Absolute colours at a constant `glow_high` (like `rainbow`); uses no
  `gc_strips`/`gc_count`/`gc_length`/`gc_background_color`.

`neutral` – this bridge's lamps are **not** driven at all: no DTLS stream,
no save/restore. Only useful per bridge (`bridges[].effect: neutral`), so an
effect set can run an effect on one bridge and leave another one out
entirely; a `neutral` bridge doesn't need an `area_id`. If all bridges are
`neutral`, `/start` responds with `no_active_bridges` (not an error).

### Effect Sets

Under "3 · Effect Sets" in the web UI, the complete form state (all bridge
cards + controls) can be saved under a name (`/data/presets.json`), **Loaded**
again, **Started** directly, **Downloaded**/**Uploaded** as a JSON file, and
**Deleted**. Via REST: `GET/PUT/DELETE /presets` and
`POST /start {"preset": "<name>"}`.

## 9. Troubleshooting

| Symptom                                   | Likely cause / fix                                                                 |
|--------------------------------------------|----------------------------------------------------------------------------------------------------|
| `/pair` fails                       | Link button not pressed in time (~30 s window) or wrong `bridge_host`.              |
| `/start` returns `already_running`         | Call `/stop` first before starting a new run.                                        |
| `/start` returns 502 `keine Bridge verfügbar` | None of the configured bridges were reachable/paired – on a partial failure `/start` still responds `200`, individual errors are in `failed_bridges`. |
| A bridge's lamps don't react at all    | This bridge may not support Entertainment (V1 bridge), or UDP port 2100 to it is blocked (firewall/VLAN). |
| The light effect stutters                          | Increase `fps` in the app options or check network load to the bridge.                          |
| A bridge's streaming stops after a short time | Each bridge allows only **one active** Entertainment stream at a time (per bridge, not global) – close the Hue Sync app or other streaming clients on that bridge in the meantime. |

## Project Structure

App Store repository: `repository.yaml` at the root, the app itself in the
`redalert/` subfolder, the optional Home Assistant integration in
`custom_components/redalert/`.

```
.
├── repository.yaml              App Store metadata (name, url, maintainer)
├── README.md / README.en.md    This file (repo overview, DE/EN)
├── hacs.json                    makes this repo addable as a HACS
│                                integration repository (category "Integration")
├── info.md                      HACS short description of the integration
├── custom_components/redalert/ Home Assistant integration (optional)
│   ├── manifest.json, const.py, api.py, coordinator.py, config_flow.py,
│   │   entity.py                REST client + config flow + shared base entity
│   ├── binary_sensor.py / switch.py / select.py / sensor.py
│   │                             the six entities – only talks to the app's
│   │                             REST API, see README.md in there
│   ├── strings.json (English) / translations/{de,en}.json
│   │                             entity/config-flow labels
│   │                             (strings.json is also the source for the
│   │                             technical entity IDs, see the README there)
│   └── brand/icon.png, brand/logo.png  copies of the store graphics (for the HA UI)
├── redalert/                   >>> the actual app <<<
│   ├── config.yaml              manifest: options, ingress, ports
│   ├── build.yaml               base images (home-assistant/base-python)
│   ├── Dockerfile               image build
│   ├── requirements.txt         Python dependencies (hue-entertainment, aiohttp)
│   ├── DOCS.md / DOCS.en.md     docs shown inside HA ("Documentation" tab, DE/EN)
│   ├── CHANGELOG.md             version history ("Changelog" tab)
│   ├── icon.png / logo.png      store graphics
│   ├── translations/{de,en}.yaml  labels for the configuration UI
│   └── rootfs/
│       ├── etc/s6-overlay/…      service definition (start, bashio logging)
│       └── app/
│           ├── main.py           REST server + streaming loop + Ingress panel
│           ├── chase.py          effect math (18 effects, see §8)
│           └── panel.html        web UI (control)
```
