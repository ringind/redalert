# Red Alert Entertainment – Home Assistant Integration

🇬🇧 English (this file) · 🇩🇪 [Deutsch](README.md)

Standalone `custom_component` for the [`redalert`](../../redalert) app: talks
to its REST API (see [`redalert/DOCS.en.md`](../../redalert/DOCS.en.md#rest-api))
and creates four entities – without the `rest_command`/template detour (see
["Integrate with Home Assistant"](../../redalert/DOCS.en.md#integrate-with-home-assistant)
for the variant without any extra installation).

| Entity | Domain | Shows / does |
|---|---|---|
| **Operating state** | `binary_sensor` | `on` while the app is currently running an effect (`running` from `/config`). |
| **Animation** | `switch` | On = `POST /start` (with the currently loaded effect set, if one is selected, otherwise the app default). Off = `POST /stop`. |
| **Effect set** | `select` | Dropdown with all saved effect sets (`GET /presets` names); picking one loads **and starts** the set immediately (`POST /start {"preset": …}`). |
| **Loaded effect set** | `sensor` | Name of the most recently loaded set (empty on an ad-hoc start without `preset`, e.g. via the app's web UI or a direct `/start` call without `preset`). |

All four attach to one shared device ("Red Alert (<Host>)"); one config
entry = one app instance.

## Installation

### Via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ringind&repository=redalert&category=integration)

This repo is HACS-capable (`hacs.json` at the repo root), but **not** listed
in the HACS default store – add it as a **custom repository**:

1. Click the button above – opens the dialog directly in your Home Assistant
   instance. **Or** manually: HACS → **⋮** (top right) →
   **Custom repositories** → URL `https://github.com/ringind/redalert`,
   category **Integration**.
2. Search/open "Red Alert Entertainment" in HACS → **Download**.
3. Restart Home Assistant.

HACS reads the same repo state as the App Store – a release tag (`vX.Y.Z`,
see [`redalert/CHANGELOG.md`](../../redalert/CHANGELOG.md)) determines which
integration state HACS offers as an installable version; without picking a
version, HACS installs the `main` branch.

### Manually (without HACS)

Copy the `custom_components/redalert/` folder from this repo into the
`custom_components/` folder of your Home Assistant configuration (resulting
path: `config/custom_components/redalert/…`), then restart Home Assistant.

## Setup

**Settings → Devices & Services → Add Integration → "Red Alert
Entertainment App".** You'll be asked for:

- **Host / IP** – e.g. `homeassistant.local` or the HA host's IP (**not**
  the Ingress path – the fixed REST port).
- **Port** – default `8099` (app tab "Network", if remapped there).
- **SSL** / **Verify SSL certificate** – only relevant if the app runs
  behind its own TLS reverse proxy; normally leave both off/on (no SSL).

The integration checks `GET /health` during setup; if no bridge is paired
yet, only a warning is logged (no abort) – pairing can be done in the app's
web UI at any later time.

## Behaviour in detail

- Poll interval: `GET /config` every 10 s (one call returns `running`,
  `presets` and `current_preset` together).
- "Loaded effect set" comes from the app itself (`current_preset` in
  `/health`/`/config`) – so it applies even when a set was started via the
  web UI or a raw `/start` call with `preset`, not just via this
  integration.
- An ad-hoc start with no `preset` at all (e.g. the plain "Start" button in
  the web UI without picking an effect set) clears "Loaded effect set" back
  to empty.
- `switch.animation` off stops **the entire running animation** (`/stop`) –
  regardless of whether it was started via the web UI, a direct `/start`
  call, or this integration.

## Icon/Logo

`custom_components/redalert/brand/{icon,logo}.png` supply the brand image
for this integration – as of Home Assistant 2026.3, HA shows it directly
(device page, "Add Integration" search), with no entry needed in the
central [`home-assistant/brands`](https://github.com/home-assistant/brands)
repo. HACS's **own** downloads overview may still show a placeholder
instead – a known, open HACS bug for custom (not default-store-listed)
repositories with only a local brand image
([hacs/integration#5223](https://github.com/hacs/integration/issues/5223),
[#5171](https://github.com/hacs/integration/issues/5171)); that's on HACS,
not this repo, and resolves itself once HACS fixes it.
