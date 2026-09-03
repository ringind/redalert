"""Red Alert Entertainment – REST-API, Streaming-Loop und Ingress-Web-UI.

Der Dienst hält einen DTLS-Stream (Hue Entertainment API) zur Bridge offen und
schiebt ~25 Frames/s eines roten Larson-Scanner-Lauflichts über die Kanäle,
optional gedämpft durch die Lautstärke-Hüllkurve einer Cue-Datei.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from aiohttp import web
from hue_entertainment import EntertainmentSession, HueEntertainmentAPI, LightColorCommand

from chase import RedAlertChase

DATA_DIR = Path(os.environ.get("REDALERT_DATA_DIR", "/data"))
CRED_FILE = DATA_DIR / "credentials.json"
OPTIONS_FILE = DATA_DIR / "options.json"

APP_DIR = Path(__file__).parent
DEFAULT_CUE_PATH = APP_DIR / "redalert_cue.json"
PANEL_HTML = (APP_DIR / "panel.html").read_text(encoding="utf-8")

_LEVELS = {
    "trace": logging.DEBUG,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "notice": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
}
logging.basicConfig(
    level=_LEVELS.get(os.environ.get("REDALERT_LOG_LEVEL", "info").lower(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("redalert")


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def load_cue(path: Path | None):
    """Cue-Datei laden: {"fps": int, "duration_s": float, "gain": [0..1, ...]}."""
    if path and Path(path).exists():
        return load_json(Path(path), None)
    return None


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = (value or "#FF0000").lstrip("#")
    if len(value) != 6:
        return (255, 0, 0)
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return (255, 0, 0)


options = load_json(OPTIONS_FILE, {})

cue_option = options.get("cue_file")
cue = load_cue(Path(cue_option)) if cue_option else load_cue(DEFAULT_CUE_PATH)

state = {
    "credentials": load_json(CRED_FILE, None),
    "bridge_host": options.get("bridge_host") or None,
    "area_id": options.get("area_id") or None,
    "channel_order": options.get("channel_order") or None,
    "color": hex_to_rgb(options.get("color", "#FF0000")),
    "cue": cue,
    "cue_source": (cue_option or str(DEFAULT_CUE_PATH)) if cue else None,
    "task": None,
    "last_start": None,
}

log.info(
    "Konfiguration: bridge_host=%s area_id=%s channels=%s color=%s fps=%s sweep=%ss cue=%s",
    state["bridge_host"],
    state["area_id"],
    state["channel_order"],
    options.get("color", "#FF0000"),
    options.get("fps", 25),
    options.get("sweep_seconds", 1.4),
    "geladen" if cue else "keine",
)
if state["credentials"]:
    log.info("Bridge bereits gepaart (%s).", state["credentials"].get("bridge_host"))
else:
    log.warning("Noch nicht mit einer Hue Bridge gepaart – zuerst POST /pair aufrufen.")


def sample_gain(cue: dict, t: float) -> float:
    """Linear interpolierter Gain-Wert der Cue an Zeitpunkt t (Sekunden)."""
    fps = cue["fps"]
    gains = cue["gain"]
    if not gains:
        return 1.0
    idx = t * fps
    i0 = int(idx)
    if i0 >= len(gains) - 1:
        return gains[-1]
    frac = idx - i0
    return gains[i0] * (1 - frac) + gains[i0 + 1] * frac


async def _json_body(request: web.Request) -> dict:
    try:
        return await request.json()
    except Exception:
        return {}


def _save_credentials(creds: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CRED_FILE.write_text(json.dumps(creds))


# --------------------------------------------------------------------------- #
# Web-UI (Ingress) + Status
# --------------------------------------------------------------------------- #
async def handle_panel(request: web.Request) -> web.Response:
    return web.Response(text=PANEL_HTML, content_type="text/html")


async def handle_health(request: web.Request) -> web.Response:
    task = state["task"]
    return web.json_response(
        {
            "status": "ok",
            "paired": state["credentials"] is not None,
            "running": bool(task and not task.done()),
        }
    )


async def handle_config(request: web.Request) -> web.Response:
    task = state["task"]
    r, g, b = state["color"]
    return web.json_response(
        {
            "paired": state["credentials"] is not None,
            "bridge_host": state["bridge_host"],
            "area_id": state["area_id"],
            "channel_order": state["channel_order"],
            "color": f"#{r:02X}{g:02X}{b:02X}",
            "fps": int(options.get("fps", 25)),
            "sweep_seconds": float(options.get("sweep_seconds", 1.4)),
            "cue_loaded": state["cue"] is not None,
            "cue_source": state["cue_source"],
            "cue_duration_s": state["cue"]["duration_s"] if state["cue"] else None,
            "running": bool(task and not task.done()),
            "last_start": state["last_start"],
        }
    )


# --------------------------------------------------------------------------- #
# Bridge-Pairing / Areas
# --------------------------------------------------------------------------- #
async def handle_pair(request: web.Request) -> web.Response:
    body = await _json_body(request)
    host = body.get("bridge_ip") or body.get("bridge_host") or state["bridge_host"]
    if not host:
        return web.json_response(
            {"error": "bridge_ip fehlt (im Body oder als Add-on-Option bridge_host)"},
            status=400,
        )

    api = HueEntertainmentAPI(host)
    try:
        creds = await api.pair()
    except Exception as exc:  # noqa: BLE001 - Pairing-Fehler an den Aufrufer melden
        log.exception("Pairing fehlgeschlagen")
        return web.json_response(
            {"error": f"Pairing fehlgeschlagen – Link-Button auf der Bridge gedrückt? ({exc})"},
            status=400,
        )
    finally:
        await api.close()

    creds["bridge_host"] = host
    _save_credentials(creds)
    state["credentials"] = creds
    state["bridge_host"] = host
    log.info("Pairing mit Bridge %s erfolgreich.", host)
    return web.json_response({"status": "paired", "bridge_host": host})


async def handle_areas(request: web.Request) -> web.Response:
    creds = state["credentials"]
    if not creds:
        return web.json_response({"error": "Noch nicht gepaart – zuerst POST /pair"}, status=400)

    session = EntertainmentSession(creds["bridge_host"], creds["username"], creds["clientkey"])
    try:
        areas = await session.get_entertainment_areas()
    except Exception as exc:  # noqa: BLE001
        log.exception("Areas konnten nicht gelesen werden")
        return web.json_response({"error": f"Bridge nicht erreichbar ({exc})"}, status=502)
    finally:
        await session.aclose()

    result = [
        {
            "id": area.id,
            "name": getattr(area, "name", None),
            "channels": [ch.channel_id for ch in area.channels],
        }
        for area in areas
    ]
    return web.json_response(result)


# --------------------------------------------------------------------------- #
# Effekt starten / stoppen
# --------------------------------------------------------------------------- #
async def _run_chase(
    session: EntertainmentSession,
    area_id: str,
    channel_ids: list,
    duration,
    fps: int,
    sweep_seconds: float,
    cue: dict | None,
    color: tuple[int, int, int],
) -> None:
    chase = RedAlertChase(num_lights=len(channel_ids), sweep_seconds=sweep_seconds)
    cr, cg, cb = color
    frames = 0
    try:
        # DTLS-Handshake läuft hier im Hintergrund, damit /start sofort antwortet.
        await session.start(area_id)
        log.info(
            "Effekt läuft: area=%s channels=%s fps=%s duration=%s cue=%s",
            area_id, channel_ids, fps, duration, cue is not None,
        )
        loop = asyncio.get_event_loop()
        start = loop.time()
        while True:
            elapsed = loop.time() - start
            if duration is not None and elapsed >= duration:
                break
            levels = chase.brightness_for(elapsed)
            if cue is not None:
                gain = sample_gain(cue, elapsed)
                levels = [lvl * gain for lvl in levels]
            commands = [
                LightColorCommand(
                    channel_id=cid,
                    red=int(cr * 257 * lvl),
                    green=int(cg * 257 * lvl),
                    blue=int(cb * 257 * lvl),
                )
                for cid, lvl in zip(channel_ids, levels)
            ]
            session.send(commands)
            frames += 1
            await asyncio.sleep(1 / fps)
    except asyncio.CancelledError:
        pass
    except Exception:  # noqa: BLE001
        log.exception("Streaming-Loop abgebrochen (DTLS-Start oder Senden fehlgeschlagen)")
    finally:
        log.info("Effekt beendet (%s Frames).", frames)
        await session.aclose()


async def handle_start(request: web.Request) -> web.Response:
    existing = state["task"]
    if existing and not existing.done():
        return web.json_response({"status": "already_running"})

    creds = state["credentials"]
    if not creds:
        return web.json_response({"error": "Noch nicht gepaart – zuerst POST /pair"}, status=400)

    body = await _json_body(request)
    area_id = body.get("area_id") or state["area_id"]
    if not area_id:
        return web.json_response(
            {"error": "area_id fehlt (im Body oder als Add-on-Option area_id)"}, status=400
        )

    use_cue = bool(body.get("use_cue", True)) and state["cue"] is not None
    active_cue = state["cue"] if use_cue else None

    fps = int(body.get("fps") or options.get("fps", 25))
    sweep_seconds = float(body.get("sweep_seconds") or options.get("sweep_seconds", 1.4))
    color = hex_to_rgb(body["color"]) if body.get("color") else state["color"]
    duration = body.get("duration")  # weglassen = Cue-Dauer, sonst bis /stop
    if duration is None and active_cue is not None:
        duration = active_cue["duration_s"]

    session = EntertainmentSession(creds["bridge_host"], creds["username"], creds["clientkey"])
    try:
        areas = await session.get_entertainment_areas()
    except Exception as exc:  # noqa: BLE001
        await session.aclose()
        log.exception("Start fehlgeschlagen: Bridge nicht erreichbar")
        return web.json_response({"error": f"Bridge nicht erreichbar ({exc})"}, status=502)

    area = next((a for a in areas if a.id == area_id), None)
    if area is None:
        await session.aclose()
        return web.json_response({"error": f"area_id {area_id} nicht gefunden"}, status=404)

    channel_ids = state["channel_order"] or [ch.channel_id for ch in area.channels]

    # session.start() (DTLS-Handshake, ~einige Sekunden) passiert im Task,
    # damit die HTTP-Antwort nicht blockiert (HA rest_command-Timeout).
    state["task"] = asyncio.create_task(
        _run_chase(session, area_id, channel_ids, duration, fps, sweep_seconds, active_cue, color)
    )
    r, g, b = color
    state["last_start"] = {
        "area_id": area_id,
        "channels": channel_ids,
        "duration": duration,
        "fps": fps,
        "sweep_seconds": sweep_seconds,
        "color": f"#{r:02X}{g:02X}{b:02X}",
        "cue_active": use_cue,
    }
    log.info("Start angefordert: %s", state["last_start"])
    return web.json_response({"status": "started", **state["last_start"]})


async def handle_stop(request: web.Request) -> web.Response:
    task = state["task"]
    if not task or task.done():
        return web.json_response({"status": "not_running"})
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    log.info("Effekt per /stop beendet.")
    return web.json_response({"status": "stopped"})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_panel)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/config", handle_config)
    app.router.add_post("/pair", handle_pair)
    app.router.add_get("/areas", handle_areas)
    app.router.add_post("/start", handle_start)
    app.router.add_post("/stop", handle_stop)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8099, access_log=None)
