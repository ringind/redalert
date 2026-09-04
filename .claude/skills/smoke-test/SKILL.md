---
name: smoke-test
description: Run the Red Alert app locally against the real Hue bridge and confirm an effect actually plays on the lamps. Use when the user asks for a "Testlauf", "test run", "prüfe den Effekt", "20 Sekunden Test", or after changing effect / streaming / sync / restore code and you need real-hardware verification (py_compile alone is not enough).
---

# Local smoke test against the real bridge

`redalert/rootfs/app/main.py` runs outside the container via
`REDALERT_DATA_DIR` (default `/data` → point it at `./devdata`).

## Setup (once)

```bash
python3 -m venv .venv && .venv/bin/pip install -r redalert/requirements.txt
```

`.venv/` and `devdata/` are gitignored. **Never `rm -rf devdata`** — it holds
`credentials.json` (keyed by `bridge_host` since multi-bridge support);
deleting it forces a physical link-button re-pair for every bridge.

## Run

```bash
python3 -m py_compile redalert/rootfs/app/main.py redalert/rootfs/app/chase.py   # always first

pkill -f "redalert/rootfs/app/main.py"; sleep 1
mkdir -p devdata
REDALERT_DATA_DIR=./devdata REDALERT_LOG_LEVEL=info \
  .venv/bin/python redalert/rootfs/app/main.py > /tmp/redalert.log 2>&1 &
B=http://localhost:8099
until curl -sf -o /dev/null $B/health; do sleep 0.5; done      # ~3 s bind race — always gate
```

If `curl -s $B/config` shows no bridge with `"paired": true` (no
`devdata/credentials.json` entry for it): ask the user to press the bridge
link button, then
`curl -s -X POST $B/pair -H 'Content-Type: application/json' -d '{"bridge_host":"192.168.178.84"}'`
within ~30 s. (`devdata/credentials.<ip>.json.bak` files hold prior pairings —
`cp` one back to `credentials.json`, or merge its entry in by hand, to switch
bridges without a link-button press.)

## Exercise an effect

Maintainer's test area **Houseparty Büro** = `226c7c2a-0a6d-4b01-a28a-8b29fd8cb219`
(3 channels; confirm with `GET /areas?bridge_host=192.168.178.84` — the
bridge/area may change). Only one real bridge is normally available for
testing — the `bridges` list still only needs one entry to exercise the
single-bridge path; a second, unreachable entry is a good way to check the
best-effort skip-and-continue behavior (see `failed_bridges` in the response).

```bash
curl -s -X POST $B/start -H 'Content-Type: application/json' \
  -d '{"bridges":[{"bridge_host":"192.168.178.84","area_id":"226c7c2a-0a6d-4b01-a28a-8b29fd8cb219"}],"effect":"pulse","duration":20}'
```

Then wait for it to finish and report — run this **backgrounded**:

```bash
until [ "$(curl -s $B/health | python3 -c 'import sys,json;print(json.load(sys.stdin)["running"])')" = "False" ]; do sleep 2; done
grep -E "Lichtzustand|Effekt läuft|Effekt beendet|konnte nicht" /tmp/redalert.log
pkill -f "redalert/rootfs/app/main.py"
```

## What "pass" looks like

- `Effekt läuft: effect=<x> ... duration=<d>` then, ~`d` s later,
  `Effekt beendet (N Frames)` with **N ≈ d * fps** (25 fps → 20 s = 500).
- With `restore_state` (default): `Lichtzustand gesichert (<host>: N Lampen)`
  before and `Lichtzustand wiederhergestellt (<host>: N/N Lampen)` after, once
  per bridge.
- A `DTLS ... ServerHello timeout ... resending` line is **normal** (handshake
  takes 3–9 s); only a `Traceback` / `konnte nicht` / non-`beendet` exit is a fail.
- `/start` returns immediately (before the handshake) — poll `/health` `running`,
  don't trust the HTTP response for "is it playing".

## Effect shape checks without hardware

`RedAlertPulse` / `RedAlertChase` are pure math — simulate without hardware:

```python
import sys; sys.path.insert(0, "redalert/rootfs/app")
from chase import RedAlertPulse, RedAlertChase
p = RedAlertPulse(num_lights=3)
# feed RedAlertPulse.periodic(t, 1.4) into p.step(level, 1/25) frame by frame;
# assert monotonic rise (no mid-ramp reversals), rests at exactly 0.0, peaks at exactly 1.0.
```
