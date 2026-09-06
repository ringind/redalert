# Red Alert Entertainment – Home Assistant Integration

🇬🇧 English (this file) · 🇩🇪 [Deutsch](https://github.com/ringind/redalert/blob/main/info.md)

This integration controls the **Red Alert Entertainment App** from Home
Assistant – an app for freely configurable Hue Entertainment light effects
(17 effects, including pulse, comet, diamond sparkle, emergency lights,
storm, heartbeat, northern lights, rainbow, meteors, firework, duel, and a
running-lights chase for Gradient Lightstrips; colour, timing, and up to 3
bridges configurable per effect set).
The namesake Star Trek "Red Alert" scene is just one of any number of
saveable **effect sets**. This integration talks exclusively to the app's
REST API and contains no light/bridge logic of its own. Setting up the app
itself (pairing the Hue Bridge, Entertainment area, effects) is covered in
its own docs, not here:
[App documentation](https://github.com/ringind/redalert/blob/main/redalert/DOCS.en.md) ·
[Main README](https://github.com/ringind/redalert#readme).

Creates four entities on one device: `binary_sensor` (is the effect
currently running?), `switch` (animation on/off), `select` (pick & load a
saved effect set), `sensor` (name of the currently loaded set).

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ringind&repository=redalert&category=integration)

1. Click the button above – **or** manually: HACS → **⋮** (top right) →
   **Custom repositories** → URL `https://github.com/ringind/redalert`,
   category **Integration**.
2. Search "Red Alert Entertainment" in HACS → **Download**.
3. Restart Home Assistant.
4. **Settings → Devices & Services → Add Integration** → search "Red Alert
   Entertainment App", enter the app's host + port (default `8099`).

**Prerequisite:** the **Red Alert Entertainment** app must already be
installed and reachable – it is not part of this integration (see above,
"App Store" installation in the main README).

Detailed integration docs (config flow fields, entity behaviour in detail):
[`custom_components/redalert/README.en.md`](https://github.com/ringind/redalert/blob/main/custom_components/redalert/README.en.md).
