---
name: smoke-test
description: Run the Red Alert app locally against the real Hue bridge and confirm an effect actually plays on the lamps, and/or check the Ingress web UI in a real browser. Use when the user asks for a "Testlauf", "test run", "prüfe den Effekt", "20 Sekunden Test", or after changing effect / streaming / sync / restore / per-bridge-task code (real-hardware verification) or panel.html (browser + console verification) — py_compile / node --check alone is not enough for either.
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
single-bridge path; a second, unreachable or unpaired entry is a good way to
check the best-effort skip-and-continue behavior (see `failed_bridges` in
the response — a bridge that fails to *resolve*, e.g. unpaired/unreachable,
lands there; a bridge that's simply *already running* lands in
`skipped_bridges` instead, see below).

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

### Per-bridge start/stop (since 1.15.0)

Every bridge runs in its own task (`state["tasks"][bridge_host]`) — when
touching `_run_single_bridge`, `handle_start`, or `handle_stop`, exercise the
per-bridge paths specifically, not just the all-bridges default:

```bash
# solo start: only this bridge, regardless of others' state
curl -s -X POST $B/start -H 'Content-Type: application/json' \
  -d '{"bridges":[{"bridge_host":"192.168.178.84","area_id":"226c7c2a-0a6d-4b01-a28a-8b29fd8cb219"}],"bridge_host":"192.168.178.84","effect":"pulse","duration":15}'
# already_running scoped to just that bridge (call /start again with the same bridge_host while running)
# stop just that bridge (others, if any, keep running)
curl -s -X POST $B/stop -H 'Content-Type: application/json' -d '{"bridge_host":"192.168.178.84"}'
# skip-and-continue: start once (no bridge_host) while a solo start is already running the same
# bridge — expect "no_active_bridges" (or "started" for any newly-added bridges) with that
# bridge listed under "skipped_bridges", not a flat rejection.
```

With only one real bridge available, the synchronized-batch path (multiple
bridges sharing one `asyncio.Barrier`, one handshake failing mid-barrier)
can't be exercised on real hardware — that logic rests on documented
`asyncio.Barrier` semantics reviewed at implementation time, not live-tested;
say so explicitly rather than claiming full coverage.

## What "pass" looks like

- `Effekt läuft: bridge=<host> effect=<x> ... duration=<d>` then, ~`d` s
  later, `Effekt beendet (<host>, N Frames)` with **N ≈ d * fps** (25 fps →
  20 s = 500) — both lines carry the bridge host since 1.15.0 (one task per
  bridge, not one shared loop).
- With `restore_state` (default): `Lichtzustand gesichert (<host>: N Lampen)`
  before and `Lichtzustand wiederhergestellt (<host>: N/N Lampen)` after, once
  per bridge.
- A `DTLS ... ServerHello timeout ... resending` line is **normal** (handshake
  takes 3–9 s); only a `Traceback` / `konnte nicht` / non-`beendet` exit is a fail.
- `/start` returns immediately (before the handshake) — poll `/health` `running`
  (or `/config`'s per-bridge `bridges[].running`), don't trust the HTTP
  response for "is it playing".

## Effect shape checks without hardware

Every effect class in `chase.py` is pure math — simulate without hardware:

```python
import sys; sys.path.insert(0, "redalert/rootfs/app")
from chase import RedAlertPulse, RedAlertComet
p = RedAlertPulse(num_lights=3)
# feed RedAlertPulse.periodic(t, 1.4) into p.step(level, 1/25) frame by frame;
# assert monotonic rise (no mid-ramp reversals), rests at exactly 0.0, peaks at exactly 1.0.
```

### Flicker/snap reports ("lamps flicker when turning on/off") — check for aliasing

A user-reported flicker at a specific effect is very likely a **frame-rate
aliasing** bug, not a hardware/network issue, if the effect has any feature
(a peak, a soft edge, a transition) whose *width* is expressed in a unit
other than time (segments, a fixed fraction, …) without being floored
against how far the effect moves per frame at the configured speed/fps.
Found and fixed twice in `chase.py` already (`RedAlertComet`'s `peak_frac`,
`RedAlertChase`'s `smooth`, 1.15.2) — same root cause both times: a shape
function sampled once per frame with no `dt`, so a too-narrow feature gets
skipped or straddled inconsistently between frames, and a lamp's rendered
brightness jumps most of the way from 0 to 1 (or back) in a single frame
instead of fading — reads as "flicker" or "snapping" especially right where
a lamp is entering/leaving the lit region. To verify (and to size a fix):

```python
import sys; sys.path.insert(0, "redalert/rootfs/app")
from chase import RedAlertChase  # or whichever class is suspect
for speed, fps in [(4.0, 25), (10.0, 25), (20.0, 25), (4.0, 10)]:  # default + escalating
    gc = RedAlertChase(num_lights=9, speed_segments_per_s=speed, fps=fps)
    dt = 1.0 / fps
    prev, max_jump, t = None, 0.0, 0.0
    for _ in range(300):
        v = gc.blend_for(t)[4]  # track one lamp across many frames
        if prev is not None:
            max_jump = max(max_jump, abs(v - prev))
        prev, t = v, t + dt
    print(speed, fps, max_jump)  # should stay roughly flat across the sweep, not blow up
```

If `max_jump` grows sharply away from the default speed/fps, that confirms
aliasing — fix by flooring the narrow feature's width against
`speed * K / fps` for a small constant `K`, **calibrated so the app's
existing default speed/fps reproduces the old fixed width exactly** (no
behaviour change at default settings, only non-default combinations get
widened) — then re-run this same sweep to confirm `max_jump` flattens out,
before live-testing on the real bridge.

## Web UI changes: verify in a real browser, and check the console

`node --check` on the extracted `<script>` only catches syntax errors — it
proves nothing about runtime behaviour. After any `panel.html` change:

1. Restart the dev server (`PANEL_HTML` is read once at import — an edit
   without a restart tests the *old* file).
2. Load the page in a real browser tab and interact with whatever changed
   (click the button, toggle the language, expand the details block, …).
3. **Read the browser console** (`read_console_messages`, pattern
   `error|Error|exception`) — not just a screenshot. A screenshot only shows
   what *did* render; it says nothing about a promise rejection or thrown
   error that failed silently. This caught a real bug during 1.15.0
   development: a temporal-dead-zone `ReferenceError` inside an unawaited
   `async function` (`setLang()`'s trailing `refresh()` call, referencing a
   `let` declared later in the same script) — the page still rendered fine
   at a glance, the error only showed up in the console, and the practical
   symptom (Status section empty for up to 5 s after load) would have been
   easy to misdiagnose as "just the periodic poll being slow" without it.
   Chrome-extension noise (`passkeys-inject.js`, "message channel closed",
   etc.) is expected and unrelated — only page-origin (`localhost:8099`)
   exceptions matter.
4. For layout changes (new CSS, reordered fields), a screenshot is still the
   right tool — console-checking and visual-checking catch different classes
   of bug, do both.
