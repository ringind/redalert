"""Red Alert Entertainment – REST-API, Streaming-Loop und Ingress-Web-UI.

Der Dienst hält einen DTLS-Stream (Hue Entertainment API) zur Bridge offen und
schiebt ~25 Frames/s an die Kanäle: entweder ein gemeinsames Auf-/Ab-Blenden
aller Lampen im Takt der Musik (``effect: pulse``, Standard) oder das originale
Larson-Scanner-Lauflicht (``effect: chase``). Der Takt kommt aus der
Lautstärke-Hüllkurve einer Cue-Datei; ``cue_offset`` und ``POST /sync`` richten
ihn laufend an der echten Wiedergabeposition des media_player aus.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import aiohttp
from aiohttp import web
from hue_entertainment import EntertainmentSession, HueEntertainmentAPI, LightColorCommand

from chase import RedAlertChase, RedAlertPulse

DATA_DIR = Path(os.environ.get("REDALERT_DATA_DIR", "/data"))
CRED_FILE = DATA_DIR / "credentials.json"
OPTIONS_FILE = DATA_DIR / "options.json"

APP_DIR = Path(__file__).parent
DEFAULT_CUE_PATH = APP_DIR / "redalert_cue.json"
PANEL_HTML = (APP_DIR / "panel.html").read_text(encoding="utf-8")

# ``chase`` mit aktiver Cue: der rohe Gain zappelt mehrfach pro Beat über einen
# weiten Bereich und würde den Kometen flackern lassen. Er wird deshalb durch
# dasselbe Beat-Gate + Slew wie ``pulse`` geglättet und dimmt den Kometen nur
# zwischen ``CHASE_CUE_FLOOR`` (Beat aus) und 1.0 (Beat an) – nie ganz aus.
CHASE_CUE_FLOOR = 0.12

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

def _effect_name(value) -> str:
    return "chase" if str(value or "").lower() == "chase" else "pulse"


def _parse_channel_order(value) -> list[int] | None:
    """Kanalreihenfolge aus Option/Body: Liste[int] oder "3,1,0,2,5,4".

    ``None`` / leer -> ``None`` (Bereichs-Standard). Ungültiges -> ``ValueError``.
    """
    if value is None:
        return None
    if isinstance(value, str):
        parts = [p for p in value.replace(",", " ").split() if p]
        value = parts
    if not isinstance(value, (list, tuple)):
        raise ValueError("channel_order muss eine Liste sein")
    order = [int(x) for x in value]  # wirft ValueError bei Nicht-Zahlen
    return order or None


state = {
    "credentials": load_json(CRED_FILE, None),
    "bridge_host": options.get("bridge_host") or None,
    "area_id": options.get("area_id") or None,
    "channel_order": options.get("channel_order") or None,
    "color": hex_to_rgb(options.get("color", "#FF0000")),
    "effect": _effect_name(options.get("effect", "pulse")),
    "attack_ms": int(options.get("attack_ms", 140)),
    "release_ms": int(options.get("release_ms", 70)),
    "restore_state": bool(options.get("restore_state", True)),
    "cue": cue,
    "cue_source": (cue_option or str(DEFAULT_CUE_PATH)) if cue else None,
    "task": None,
    "last_start": None,
    # Laufende Synchronisation: von /sync gepflegt, vom Effekt-Loop gelesen.
    "sync": {"active": False, "loop_start": 0.0, "cue_offset": 0.0, "correction": 0.0},
}

log.info(
    "Konfiguration: bridge_host=%s area_id=%s channels=%s effect=%s color=%s fps=%s "
    "sweep=%ss attack=%sms release=%sms cue=%s",
    state["bridge_host"],
    state["area_id"],
    state["channel_order"],
    state["effect"],
    options.get("color", "#FF0000"),
    options.get("fps", 25),
    options.get("sweep_seconds", 1.4),
    state["attack_ms"],
    state["release_ms"],
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


# --------------------------------------------------------------------------- #
# Lichtzustand sichern / wiederherstellen (Hue CLIP v2, neben dem DTLS-Stream)
# --------------------------------------------------------------------------- #
async def _clip(sess, host: str, key: str, method: str, path: str, body: dict | None = None):
    url = f"https://{host}/clip/v2/resource/{path}"
    async with sess.request(
        method, url, headers={"hue-application-key": key}, json=body, ssl=False
    ) as resp:
        return await resp.json()


async def capture_light_state(host: str, key: str, area_id: str) -> list[dict]:
    """on/Helligkeit/Farbe aller Lampen des Entertainment-Bereichs als Snapshot."""
    snap: list[dict] = []
    try:
        async with aiohttp.ClientSession() as sess:
            cfg = await _clip(sess, host, key, "GET", f"entertainment_configuration/{area_id}")
            data = (cfg.get("data") or [{}])[0]
            light_ids = [
                ls["rid"] for ls in data.get("light_services", []) if ls.get("rtype") == "light"
            ]
            for lid in light_ids:
                d = (await _clip(sess, host, key, "GET", f"light/{lid}")).get("data") or [{}]
                d = d[0]
                snap.append(
                    {
                        "id": lid,
                        "on": d.get("on", {}).get("on", True),
                        "brightness": d.get("dimming", {}).get("brightness"),
                        "mirek": d.get("color_temperature", {}).get("mirek"),
                        "xy": d.get("color", {}).get("xy"),
                    }
                )
        log.info("Lichtzustand gesichert (%d Lampen).", len(snap))
    except Exception:  # noqa: BLE001
        log.exception("Lichtzustand konnte nicht gesichert werden – wird nicht wiederhergestellt")
        return []
    return snap


async def restore_light_state(host: str, key: str, snap: list[dict]) -> None:
    if not snap:
        return
    # Die Bridge stellt nach dem Ende des Entertainment-Streams von sich aus
    # wieder her; kurz warten, damit dieses PUT das letzte Wort hat.
    await asyncio.sleep(0.4)
    ok = 0
    try:
        async with aiohttp.ClientSession() as sess:
            for st in snap:
                body: dict = {"on": {"on": bool(st["on"])}}
                if st["brightness"] is not None:
                    body["dimming"] = {"brightness": st["brightness"]}
                if st["xy"] is not None:
                    body["color"] = {"xy": st["xy"]}
                elif st["mirek"] is not None:
                    body["color_temperature"] = {"mirek": st["mirek"]}
                try:
                    await _clip(sess, host, key, "PUT", f"light/{st['id']}", body)
                    ok += 1
                except Exception:  # noqa: BLE001
                    log.exception("Lampe %s konnte nicht wiederhergestellt werden", st["id"])
                await asyncio.sleep(0.06)  # Bridge nicht überfahren
        log.info("Lichtzustand wiederhergestellt (%d/%d Lampen).", ok, len(snap))
    except Exception:  # noqa: BLE001
        log.exception("Wiederherstellung fehlgeschlagen")


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
    sync = state["sync"]
    return web.json_response(
        {
            "paired": state["credentials"] is not None,
            "bridge_host": state["bridge_host"],
            "area_id": state["area_id"],
            "channel_order": state["channel_order"],
            "effect": state["effect"],
            "color": f"#{r:02X}{g:02X}{b:02X}",
            "fps": int(options.get("fps", 25)),
            "sweep_seconds": float(options.get("sweep_seconds", 1.4)),
            "attack_ms": state["attack_ms"],
            "release_ms": state["release_ms"],
            "restore_state": state["restore_state"],
            "cue_loaded": state["cue"] is not None,
            "cue_source": state["cue_source"],
            "cue_duration_s": state["cue"]["duration_s"] if state["cue"] else None,
            "running": bool(task and not task.done()),
            "sync_correction_s": round(sync["correction"], 3) if sync["active"] else None,
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
# Effekt starten / stoppen / synchronisieren
# --------------------------------------------------------------------------- #
async def _run_effect(
    session: EntertainmentSession,
    area_id: str,
    channel_ids: list,
    duration,
    fps: int,
    sweep_seconds: float,
    cue: dict | None,
    color: tuple[int, int, int],
    effect: str,
    cue_offset: float,
    attack_s: float,
    release_s: float,
    bridge_host: str,
    app_key: str,
    restore: bool,
) -> None:
    n = len(channel_ids)
    cr, cg, cb = color
    chase = RedAlertChase(num_lights=n, sweep_seconds=sweep_seconds)
    pulse = RedAlertPulse(num_lights=n, attack_s=attack_s, release_s=release_s)
    frames = 0
    snapshot: list[dict] = []
    try:
        # Vor dem Streaming den aktuellen Lichtzustand sichern.
        if restore:
            snapshot = await capture_light_state(bridge_host, app_key, area_id)
        # DTLS-Handshake läuft hier im Hintergrund, damit /start sofort antwortet.
        await session.start(area_id)
        loop = asyncio.get_event_loop()
        start = loop.time()
        # Für /sync sichtbar machen, ab wann und mit welchem Versatz der Loop läuft.
        state["sync"].update(
            {"active": True, "loop_start": start, "cue_offset": cue_offset, "correction": 0.0}
        )
        log.info(
            "Effekt läuft: effect=%s area=%s channels=%s fps=%s duration=%s cue=%s offset=%.3fs",
            effect, area_id, channel_ids, fps, duration, cue is not None, cue_offset,
        )
        prev = start
        while True:
            now = loop.time()
            elapsed = now - start
            if duration is not None and elapsed >= duration:
                break
            # Zeitpunkt in der Cue = Loop-Zeit + Start-Versatz + Live-Korrektur (/sync).
            cue_t = elapsed + cue_offset + state["sync"]["correction"]

            if effect == "chase":
                levels = chase.brightness_for(elapsed)
                if cue is not None:
                    # Cue-Gain durchs Beat-Gate glätten (sonst flackert der Komet),
                    # dann als Dimmfaktor CHASE_CUE_FLOOR..1.0 anlegen.
                    gate = pulse.step(sample_gain(cue, cue_t), now - prev)[0]
                    g = CHASE_CUE_FLOOR + (1.0 - CHASE_CUE_FLOOR) * gate
                    levels = [lvl * g for lvl in levels]
            else:  # pulse
                if cue is not None:
                    target = sample_gain(cue, cue_t)
                else:
                    target = RedAlertPulse.periodic(elapsed, sweep_seconds)
                levels = pulse.step(target, now - prev)

            prev = now
            session.send(
                [
                    LightColorCommand(
                        channel_id=cid,
                        red=int(cr * 257 * lvl),
                        green=int(cg * 257 * lvl),
                        blue=int(cb * 257 * lvl),
                    )
                    for cid, lvl in zip(channel_ids, levels)
                ]
            )
            frames += 1
            # Frames gegen eine absolute Uhr planen, damit die Licht-Zeitachse
            # nicht gegenüber der Wanduhr wegdriftet (sonst summiert sich der
            # Fehler von asyncio.sleep auf).
            sleep_for = (start + frames / fps) - loop.time()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
    except asyncio.CancelledError:
        pass
    except Exception:  # noqa: BLE001
        log.exception("Effekt-Loop abgebrochen (DTLS-Start oder Senden fehlgeschlagen)")
    finally:
        state["sync"]["active"] = False
        log.info("Effekt beendet (%s Frames).", frames)
        await session.aclose()
        # Nach dem Ende des Streams den gesicherten Lichtzustand zurückschreiben.
        await restore_light_state(bridge_host, app_key, snapshot)


async def _run_identify(
    session: EntertainmentSession,
    area_id: str,
    all_ids: list,
    targets: list,
    hold_s: float,
    color: tuple[int, int, int],
    bridge_host: str,
    app_key: str,
    restore: bool,
) -> None:
    """Kanäle nacheinander einzeln aufleuchten lassen (Zuordnungs-Hilfe).

    Für jeden ``channel_id`` in ``targets``: diesen Kanal ``hold_s`` s voll an,
    alle anderen aus, danach eine kurze Dunkelpause. Ein einziger DTLS-Handshake
    für den ganzen Durchlauf.
    """
    cr, cg, cb = color
    snapshot: list[dict] = []
    try:
        if restore:
            snapshot = await capture_light_state(bridge_host, app_key, area_id)
        await session.start(area_id)
        loop = asyncio.get_event_loop()
        for cid in targets:
            log.info("Identify: Kanal %s an", cid)
            for lit, until in ((True, hold_s), (False, 0.4 if len(targets) > 1 else 0.0)):
                end = loop.time() + until
                while loop.time() < end:
                    session.send([
                        LightColorCommand(
                            channel_id=c,
                            red=cr * 257 if (lit and c == cid) else 0,
                            green=cg * 257 if (lit and c == cid) else 0,
                            blue=cb * 257 if (lit and c == cid) else 0,
                        )
                        for c in all_ids
                    ])
                    await asyncio.sleep(0.05)
        log.info("Identify beendet (%d Kanäle).", len(targets))
    except asyncio.CancelledError:
        pass
    except Exception:  # noqa: BLE001
        log.exception("Identify abgebrochen (DTLS-Start oder Senden fehlgeschlagen)")
    finally:
        await session.aclose()
        await restore_light_state(bridge_host, app_key, snapshot)


async def handle_identify(request: web.Request) -> web.Response:
    """POST /identify – Lampen einzeln durchtesten.

    Body: ``area_id`` (opt.), ``channel_id`` (opt.; fehlt = alle nacheinander),
    ``seconds`` (opt.), ``color`` (opt.), ``restore_state`` (opt.).
    """
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
    color = hex_to_rgb(body["color"]) if body.get("color") else state["color"]
    restore = bool(body.get("restore_state", state["restore_state"]))
    try:
        seconds = float(body.get("seconds") or 0.0)
    except (TypeError, ValueError):
        seconds = 0.0

    session = EntertainmentSession(creds["bridge_host"], creds["username"], creds["clientkey"])
    try:
        areas = await session.get_entertainment_areas()
    except Exception as exc:  # noqa: BLE001
        await session.aclose()
        log.exception("Identify fehlgeschlagen: Bridge nicht erreichbar")
        return web.json_response({"error": f"Bridge nicht erreichbar ({exc})"}, status=502)

    area = next((a for a in areas if a.id == area_id), None)
    if area is None:
        await session.aclose()
        return web.json_response({"error": f"area_id {area_id} nicht gefunden"}, status=404)

    native_ids = [ch.channel_id for ch in area.channels]
    if body.get("channel_id") is None:
        targets, hold = native_ids, (seconds or 2.0)
    else:
        try:
            cid = int(body["channel_id"])
        except (TypeError, ValueError):
            await session.aclose()
            return web.json_response({"error": "channel_id muss eine Zahl sein"}, status=400)
        if cid not in native_ids:
            await session.aclose()
            return web.json_response(
                {"error": f"channel_id {cid} nicht im Bereich (verfügbar: {native_ids})"},
                status=400,
            )
        targets, hold = [cid], (seconds or 3.0)

    state["task"] = asyncio.create_task(
        _run_identify(
            session, area_id, native_ids, targets, hold, color,
            creds["bridge_host"], creds["username"], restore,
        )
    )
    result = {"status": "identify", "area_id": area_id, "channels": targets, "seconds": hold}
    log.info("Identify angefordert: %s", result)
    return web.json_response(result)


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

    effect = _effect_name(body.get("effect") or state["effect"])
    fps = int(body.get("fps") or options.get("fps", 25))
    sweep_seconds = float(body.get("sweep_seconds") or options.get("sweep_seconds", 1.4))
    color = hex_to_rgb(body["color"]) if body.get("color") else state["color"]
    attack_s = float(body.get("attack_ms", state["attack_ms"])) / 1000.0
    release_s = float(body.get("release_ms", state["release_ms"])) / 1000.0
    restore = bool(body.get("restore_state", state["restore_state"]))
    if "channel_order" in body:
        try:
            req_order = _parse_channel_order(body["channel_order"])
        except (TypeError, ValueError):
            return web.json_response(
                {"error": "channel_order muss eine Liste von Kanal-Indizes sein, "
                          "z. B. [2,3,1,0,5,4] oder \"2,3,1,0,5,4\""},
                status=400,
            )
    else:
        req_order = state["channel_order"]
    try:
        cue_offset = float(body.get("cue_offset", 0.0))
    except (TypeError, ValueError):
        cue_offset = 0.0
    duration = body.get("duration")  # weglassen = Cue-Dauer, sonst bis /stop
    if duration is None and active_cue is not None:
        duration = max(0.0, active_cue["duration_s"] - cue_offset)

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

    native_ids = [ch.channel_id for ch in area.channels]
    if req_order:
        if sorted(req_order) != sorted(native_ids):
            await session.aclose()
            return web.json_response(
                {"error": f"channel_order {req_order} passt nicht zum Bereich – "
                          f"genau die Kanäle {sorted(native_ids)} in gewünschter "
                          f"Reihenfolge angeben"},
                status=400,
            )
        channel_ids = list(req_order)
    else:
        channel_ids = native_ids

    # session.start() (DTLS-Handshake, ~einige Sekunden) passiert im Task,
    # damit die HTTP-Antwort nicht blockiert (HA rest_command-Timeout).
    state["sync"] = {
        "active": False, "loop_start": 0.0, "cue_offset": cue_offset, "correction": 0.0,
    }
    state["task"] = asyncio.create_task(
        _run_effect(
            session, area_id, channel_ids, duration, fps, sweep_seconds, active_cue, color,
            effect, cue_offset, attack_s, release_s,
            creds["bridge_host"], creds["username"], restore,
        )
    )
    r, g, b = color
    state["last_start"] = {
        "effect": effect,
        "area_id": area_id,
        "channels": channel_ids,
        "duration": duration,
        "fps": fps,
        "sweep_seconds": sweep_seconds,
        "color": f"#{r:02X}{g:02X}{b:02X}",
        "cue_active": use_cue,
        "cue_offset": cue_offset,
        "attack_ms": round(attack_s * 1000),
        "release_ms": round(release_s * 1000),
        "restore_state": restore,
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


# Größte Einzelkorrektur pro /sync-Aufruf – hält Nachführungen unter der
# Wahrnehmungsschwelle, wenn die Automation regelmäßig (alle paar Sekunden) synct.
MAX_SYNC_STEP_S = 0.5


async def handle_sync(request: web.Request) -> web.Response:
    """Licht-Cue an die echte Wiedergabeposition angleichen.

    Body: ``{"position": <sekunden im Track>}`` – die aktuelle Position des
    media_player (aus ``media_position`` + Zeit seit ``media_position_updated_at``).
    Die Differenz zur aktuellen Licht-Cue-Zeit wird auf ±MAX_SYNC_STEP_S begrenzt
    aufaddiert, damit kein sichtbarer Sprung entsteht.
    """
    task = state["task"]
    sync = state["sync"]
    if not (task and not task.done()) or not sync["active"]:
        return web.json_response({"status": "not_running"}, status=409)

    body = await _json_body(request)
    try:
        position = float(body["position"])
    except (KeyError, TypeError, ValueError):
        return web.json_response({"error": "position (Sekunden) fehlt oder ungültig"}, status=400)

    now = asyncio.get_event_loop().time()
    elapsed = now - sync["loop_start"]
    light_cue_t = elapsed + sync["cue_offset"] + sync["correction"]
    delta = position - light_cue_t
    step = max(-MAX_SYNC_STEP_S, min(MAX_SYNC_STEP_S, delta))
    sync["correction"] += step
    log.debug(
        "sync: player=%.3fs licht=%.3fs delta=%+.3fs -> korrektur=%+.3fs%s",
        position, light_cue_t, delta, sync["correction"],
        " (begrenzt)" if step != delta else "",
    )
    return web.json_response(
        {
            "status": "synced",
            "player_position_s": round(position, 3),
            "light_cue_s": round(light_cue_t, 3),
            "residual_s": round(delta - step, 3),
            "correction_s": round(sync["correction"], 3),
        }
    )


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_panel)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/config", handle_config)
    app.router.add_post("/pair", handle_pair)
    app.router.add_get("/areas", handle_areas)
    app.router.add_post("/start", handle_start)
    app.router.add_post("/stop", handle_stop)
    app.router.add_post("/sync", handle_sync)
    app.router.add_post("/identify", handle_identify)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8099, access_log=None)
