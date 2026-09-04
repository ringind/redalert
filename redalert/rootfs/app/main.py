"""Red Alert Entertainment – REST-API, Streaming-Loop und Ingress-Web-UI.

Der Dienst hält pro konfigurierter Hue Bridge (bis zu 3) einen eigenen
DTLS-Stream offen und schiebt ~25 Frames/s an die Kanäle: ein gemeinsames
Auf-/Ab-Blenden aller Lampen einer Bridge (``effect: pulse``, Standard), das
originale Larson-Scanner-Lauflicht (``effect: chase``) oder ein
Diamant-Gefunkel aus kurzen Farb-Blitzen (``effect: glitter``).
Effekt, Farbe und Timing sind pro Bridge einzeln einstellbar; alle Bridges
starten trotzdem gleichzeitig (gemeinsame Start-Uhr nach parallelen
DTLS-Handshakes). Läuft für ``duration`` Sekunden (Standardwert aus der
gleichnamigen Add-on-Option, für alle Bridges gemeinsam; `0` = unbegrenzt,
läuft bis ``POST /stop``).

Der komplette Satz an Start-Parametern (alle Bridges + Steuerung) lässt sich
als benanntes **Effektset** unter ``/data/presets.json`` ablegen
(``GET/PUT/DELETE /presets``) und per ``POST /start {"preset": "..."}``
wieder starten.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import aiohttp
from aiohttp import web
from hue_entertainment import EntertainmentSession, HueEntertainmentAPI, LightColorCommand

from chase import RedAlertChase, RedAlertGlitter, RedAlertPulse

DATA_DIR = Path(os.environ.get("REDALERT_DATA_DIR", "/data"))
CRED_FILE = DATA_DIR / "credentials.json"
OPTIONS_FILE = DATA_DIR / "options.json"
PRESETS_FILE = DATA_DIR / "presets.json"

APP_DIR = Path(__file__).parent
PANEL_HTML = (APP_DIR / "panel.html").read_text(encoding="utf-8")

# Mehr konfigurierte bridges-Einträge als das werden beim Laden abgeschnitten.
MAX_BRIDGES = 3

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


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = (value or "#FF0000").lstrip("#")
    if len(value) != 6:
        return (255, 0, 0)
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return (255, 0, 0)


options = load_json(OPTIONS_FILE, {})


def _effect_name(value) -> str:
    v = str(value or "").lower()
    return v if v in ("pulse", "chase", "glitter", "neutral") else "pulse"


def _parse_color_list(value) -> list[tuple[int, int, int]]:
    """Farbliste aus Option/Body: ``["#FFF...", ...]`` oder ``"#FFF... #CFE..."``.

    Leer/``None`` -> ``[]`` (Aufrufer fällt auf die Einzelfarbe zurück).
    """
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        parts = [str(x) for x in value]
    else:
        parts = [p for p in str(value).replace(",", " ").split() if p]
    return [hex_to_rgb(p) for p in parts if p.strip()]


def _colors_to_hex(colors) -> str:
    """rgb-Tupel-Liste -> ``"#RRGGBB #RRGGBB"`` (für /config und das Web-UI)."""
    if not colors:
        return ""
    return " ".join("#{:02X}{:02X}{:02X}".format(*c) for c in colors)


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


# Pro-Bridge überschreibbare Effekt-Parameter: Name im bridges-Eintrag -> Cast.
# Fehlt der Schlüssel (oder ist er leer) in einem Eintrag, gilt der gleichnamige
# Wert aus dem /start-Body bzw. den Add-on-Optionen als Standard für diese Bridge.
_BRIDGE_NUMERIC_OVERRIDES = (
    ("sweep_seconds", float),
    ("chase_pause", float),
    ("attack_ms", float),
    ("release_ms", float),
    ("glow_low", float),
    ("glow_high", float),
    ("glitter_interval_ms", float),
    ("glitter_flash_ms", float),
)


def _parse_bridges_option(value) -> list[dict]:
    """``bridges``-Option/Body in normalisierte Einträge parsen.

    Jeder Eintrag braucht ``bridge_host`` + ``area_id`` (bei ``effect: neutral``
    reicht ``bridge_host`` – die Bridge wird dann gar nicht gesteuert);
    ``channel_order`` und die Effekt-Parameter (``effect``, ``color``,
    ``sweep_seconds``, ``chase_pause``, ``attack_ms``, ``release_ms``,
    ``glow_low``, ``glow_high``, ``glitter_interval_ms``, ``glitter_flash_ms``,
    ``glitter_colors``) sind optional und überschreiben nur für diese eine
    Bridge den sonst gültigen Standard (Body bzw. Add-on-Option). Unvollständige
    Einträge werden mit einer Warnung übersprungen, mehr als ``MAX_BRIDGES``
    Einträge werden abgeschnitten.
    """
    if not isinstance(value, list):
        return []
    result: list[dict] = []
    for entry in value:
        if not isinstance(entry, dict):
            log.warning("bridges-Eintrag ist kein Objekt, ignoriert: %r", entry)
            continue
        host = str(entry.get("bridge_host") or "").strip()
        area_id = str(entry.get("area_id") or "").strip()
        eff = _effect_name(entry["effect"]) if entry.get("effect") else None
        if not host or (not area_id and eff != "neutral"):
            log.warning("bridges-Eintrag ohne bridge_host/area_id ignoriert: %r", entry)
            continue
        try:
            order = _parse_channel_order(entry.get("channel_order"))
        except (TypeError, ValueError):
            log.warning("channel_order für Bridge %s ungültig – ignoriert", host)
            order = None
        norm = {"bridge_host": host, "area_id": area_id, "channel_order": order}
        if entry.get("effect"):
            norm["effect"] = _effect_name(entry["effect"])
        if entry.get("color"):
            norm["color"] = hex_to_rgb(entry["color"])
        if entry.get("glitter_colors"):
            palette = _parse_color_list(entry["glitter_colors"])
            if palette:
                norm["glitter_colors"] = palette
        for key, cast in _BRIDGE_NUMERIC_OVERRIDES:
            raw = entry.get(key)
            if raw is None or raw == "":
                continue
            try:
                norm[key] = cast(raw)
            except (TypeError, ValueError):
                log.warning("Bridge %s: %s ungültig – ignoriert", host, key)
        result.append(norm)
    if len(result) > MAX_BRIDGES:
        log.warning(
            "%d bridges konfiguriert, nur die ersten %d werden genutzt.", len(result), MAX_BRIDGES
        )
        result = result[:MAX_BRIDGES]
    return result


def _load_credentials() -> dict:
    """Pro-Bridge-Zugangsdaten laden: {bridge_host: {username, clientkey, bridge_host}}.

    Migriert transparent das alte Einzel-Bridge-Format (flaches
    {username, clientkey, bridge_host}) beim Laden.
    """
    data = load_json(CRED_FILE, {})
    if isinstance(data, dict) and "username" in data and "clientkey" in data:
        host = data.get("bridge_host")
        return {host: data} if host else {}
    return data if isinstance(data, dict) else {}


def _save_credentials(creds: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CRED_FILE.write_text(json.dumps(creds))


def _load_presets() -> dict:
    """Effektsets laden: ``{name: <start-Body-Dict>}`` aus ``/data/presets.json``."""
    data = load_json(PRESETS_FILE, {})
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def _save_presets(presets: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRESETS_FILE.write_text(json.dumps(presets, indent=2, ensure_ascii=False))


state = {
    "credentials": _load_credentials(),
    "presets": _load_presets(),
    "bridges": _parse_bridges_option(options.get("bridges")),
    "color": hex_to_rgb(options.get("color", "#FF0000")),
    "effect": _effect_name(options.get("effect", "pulse")),
    "attack_ms": int(options.get("attack_ms", 140)),
    "release_ms": int(options.get("release_ms", 70)),
    "glow_low": float(options.get("glow_low", 0.08)),
    "glow_high": float(options.get("glow_high", 1.0)),
    "chase_pause": float(options.get("chase_pause", 0.0)),
    "glitter_interval_ms": max(1.0, float(options.get("glitter_interval_ms", 90.0))),
    "glitter_flash_ms": max(1.0, float(options.get("glitter_flash_ms", 260.0))),
    # Roh-String wie konfiguriert; leer -> je Bridge die Einzelfarbe.
    "glitter_colors": str(options.get("glitter_colors", "") or ""),
    "restore_state": bool(options.get("restore_state", True)),
    # 0 = unbegrenzt (läuft bis POST /stop).
    "duration": max(0.0, float(options.get("duration", 0.0))),
    "task": None,
    "last_start": None,
}

log.info(
    "Konfiguration: bridges=%s (Standard) effect=%s color=%s fps=%s sweep=%ss chase_pause=%ss "
    "attack=%sms release=%sms glow=%s..%s glitter=%sms/%sms colors=%r duration=%ss (0=unbegrenzt) "
    "presets=%s",
    [
        {"bridge_host": b["bridge_host"], "area_id": b["area_id"], "channel_order": b["channel_order"],
         **{k: b[k] for k in ("effect", "color", "sweep_seconds", "chase_pause",
                               "attack_ms", "release_ms", "glow_low", "glow_high",
                               "glitter_interval_ms", "glitter_flash_ms", "glitter_colors") if k in b}}
        for b in state["bridges"]
    ],
    state["effect"],
    options.get("color", "#FF0000"),
    options.get("fps", 25),
    options.get("sweep_seconds", 1.4),
    state["chase_pause"],
    state["attack_ms"],
    state["release_ms"],
    state["glow_low"],
    state["glow_high"],
    state["glitter_interval_ms"],
    state["glitter_flash_ms"],
    state["glitter_colors"] or "(Bridge-Farbe)",
    state["duration"],
    sorted(state["presets"].keys()) or "(keine)",
)
if state["bridges"]:
    paired = [b["bridge_host"] for b in state["bridges"] if b["bridge_host"] in state["credentials"]]
    log.info("%d/%d konfigurierte Bridges bereits gepaart: %s", len(paired), len(state["bridges"]), paired)
else:
    log.warning(
        "Keine Bridge in der Option 'bridges' konfiguriert – Pairing/Bereich lassen sich "
        "trotzdem interaktiv im Web-UI einrichten."
    )


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
        log.info("Lichtzustand gesichert (%s: %d Lampen).", host, len(snap))
    except Exception:  # noqa: BLE001
        log.exception("Lichtzustand (%s) konnte nicht gesichert werden – wird nicht wiederhergestellt", host)
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
                    log.exception("Lampe %s (%s) konnte nicht wiederhergestellt werden", st["id"], host)
                await asyncio.sleep(0.06)  # Bridge nicht überfahren
        log.info("Lichtzustand wiederhergestellt (%s: %d/%d Lampen).", host, ok, len(snap))
    except Exception:  # noqa: BLE001
        log.exception("Wiederherstellung (%s) fehlgeschlagen", host)


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
            "paired": bool(state["credentials"]),
            "running": bool(task and not task.done()),
        }
    )


def _bridge_color_hex(b: dict) -> str | None:
    if "color" not in b:
        return None
    cr, cg, cb = b["color"]
    return f"#{cr:02X}{cg:02X}{cb:02X}"


async def handle_config(request: web.Request) -> web.Response:
    task = state["task"]
    r, g, b = state["color"]
    return web.json_response(
        {
            "bridges": [
                {
                    "bridge_host": bg["bridge_host"],
                    "area_id": bg["area_id"],
                    "channel_order": bg["channel_order"],
                    "paired": bg["bridge_host"] in state["credentials"],
                    "effect": bg.get("effect"),
                    "color": _bridge_color_hex(bg),
                    "sweep_seconds": bg.get("sweep_seconds"),
                    "chase_pause": bg.get("chase_pause"),
                    "attack_ms": bg.get("attack_ms"),
                    "release_ms": bg.get("release_ms"),
                    "glow_low": bg.get("glow_low"),
                    "glow_high": bg.get("glow_high"),
                    "glitter_interval_ms": bg.get("glitter_interval_ms"),
                    "glitter_flash_ms": bg.get("glitter_flash_ms"),
                    "glitter_colors": _colors_to_hex(bg["glitter_colors"]) if "glitter_colors" in bg else None,
                }
                for bg in state["bridges"]
            ],
            "effect": state["effect"],
            "color": f"#{r:02X}{g:02X}{b:02X}",
            "fps": int(options.get("fps", 25)),
            "sweep_seconds": float(options.get("sweep_seconds", 1.4)),
            "chase_pause": state["chase_pause"],
            "attack_ms": state["attack_ms"],
            "release_ms": state["release_ms"],
            "glow_low": state["glow_low"],
            "glow_high": state["glow_high"],
            "glitter_interval_ms": state["glitter_interval_ms"],
            "glitter_flash_ms": state["glitter_flash_ms"],
            "glitter_colors": state["glitter_colors"],
            "restore_state": state["restore_state"],
            "default_duration_s": state["duration"],
            "presets": sorted(state["presets"].keys()),
            "running": bool(task and not task.done()),
            "last_start": state["last_start"],
        }
    )


# --------------------------------------------------------------------------- #
# Bridge-Pairing / Areas
# --------------------------------------------------------------------------- #
async def handle_pair(request: web.Request) -> web.Response:
    body = await _json_body(request)
    host = body.get("bridge_ip") or body.get("bridge_host")
    if not host:
        # Bequemlichkeit: bei genau einer (noch ungepaarten) konfigurierten
        # Bridge reicht ein Body ohne bridge_host, wie schon im Einzel-Bridge-Fall.
        unpaired = [b["bridge_host"] for b in state["bridges"] if b["bridge_host"] not in state["credentials"]]
        if len(unpaired) == 1:
            host = unpaired[0]
        elif len(state["bridges"]) == 1:
            host = state["bridges"][0]["bridge_host"]
    if not host:
        return web.json_response(
            {"error": "bridge_ip fehlt im Body – bei mehreren Bridges Pflichtfeld"},
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
    state["credentials"][host] = creds
    _save_credentials(state["credentials"])
    log.info("Pairing mit Bridge %s erfolgreich.", host)
    return web.json_response({"status": "paired", "bridge_host": host})


async def handle_areas(request: web.Request) -> web.Response:
    host = request.query.get("bridge_host")
    if not host:
        if len(state["credentials"]) == 1:
            host = next(iter(state["credentials"]))
        else:
            return web.json_response(
                {"error": "bridge_host fehlt (Query-Parameter, z. B. /areas?bridge_host=192.168.1.50)"},
                status=400,
            )
    creds = state["credentials"].get(host)
    if not creds:
        return web.json_response(
            {"error": f"Bridge {host} noch nicht gepaart – zuerst POST /pair"}, status=400
        )

    session = EntertainmentSession(host, creds["username"], creds["clientkey"])
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
async def _run_effect(
    bridge_ctxs: list[dict],
    duration: float,
    fps: int,
    restore: bool,
) -> None:
    """Effekt auf mehreren Bridges gleichzeitig fahren, jede mit ihrem eigenen
    Effekt/Farbe/Timing (siehe ``handle_start._resolve``).

    Jede Bridge bekommt ihre eigenen ``RedAlertChase``/``RedAlertPulse``/
    ``RedAlertGlitter``-Instanzen (Kanalzahl, Timing und Effekt-Art können pro
    Bridge unterschiedlich sein). Damit sie trotzdem **gleichzeitig** loslegen statt
    nacheinander, starten alle DTLS-Handshakes parallel, und die gemeinsame
    ``elapsed``-Uhr beginnt erst, wenn alle fertig sind (oder fehlgeschlagen
    sind – eine fehlschlagende Bridge fliegt best-effort raus).
    """
    for ctx in bridge_ctxs:
        n = len(ctx["channel_ids"])
        ctx["pulse"] = RedAlertPulse(num_lights=n, attack_s=ctx["attack_s"], release_s=ctx["release_s"])
        ctx["chase"] = RedAlertChase(
            num_lights=n, sweep_seconds=ctx["sweep_seconds"], pause_seconds=ctx["chase_pause"]
        )
        ctx["glitter"] = RedAlertGlitter(
            num_lights=n,
            interval_s=ctx["glitter_interval_ms"] / 1000.0,
            flash_s=ctx["glitter_flash_ms"] / 1000.0,
            palette=ctx["glitter_palette"],
        )
    frames = 0
    snapshots: dict[str, list[dict]] = {}
    loop = asyncio.get_event_loop()
    active: list[dict] = []
    try:
        # Vor dem Streaming den aktuellen Lichtzustand aller Bridges sichern.
        if restore:
            snaps = await asyncio.gather(
                *(capture_light_state(c["bridge_host"], c["app_key"], c["area_id"]) for c in bridge_ctxs)
            )
            for ctx, snap in zip(bridge_ctxs, snaps):
                snapshots[ctx["bridge_host"]] = snap

        # Alle DTLS-Handshakes parallel (je ~3-9s) statt nacheinander, damit die
        # Bridges eine gemeinsame Startzeit bekommen. Eine fehlschlagende Bridge
        # fliegt raus (best effort), blockiert aber die anderen nicht.
        results = await asyncio.gather(
            *(ctx["session"].start(ctx["area_id"]) for ctx in bridge_ctxs), return_exceptions=True
        )
        for ctx, res in zip(bridge_ctxs, results):
            if isinstance(res, Exception):
                log.error("Bridge %s: DTLS-Handshake fehlgeschlagen (%s)", ctx["bridge_host"], res)
                continue
            active.append(ctx)
        if not active:
            log.error("Effekt-Loop: keine Bridge erfolgreich verbunden.")
            return

        start = loop.time()
        log.info(
            "Effekt läuft: bridges=%s fps=%s duration=%s",
            [(c["bridge_host"], c["effect"]) for c in active], fps,
            duration if duration > 0 else "unbegrenzt",
        )
        prev = start
        while True:
            now = loop.time()
            elapsed = now - start
            if duration > 0 and elapsed >= duration:
                break
            dt = now - prev
            prev = now

            for ctx in active:
                glow_low, glow_high = ctx["glow_low"], ctx["glow_high"]
                glow_span = glow_high - glow_low
                if ctx["effect"] == "glitter":
                    # jede Lampe eigene Farbe + eigener Pegel (Diamant-Gefunkel)
                    chans = [
                        (r, g, b, glow_low + glow_span * lvl)
                        for lvl, (r, g, b) in ctx["glitter"].step(dt)
                    ]
                else:
                    if ctx["effect"] == "chase":
                        levels = ctx["chase"].brightness_for(elapsed)
                    else:  # pulse
                        target = RedAlertPulse.periodic(elapsed, ctx["sweep_seconds"])
                        levels = ctx["pulse"].step(target, dt)
                    cr, cg, cb = ctx["color"]
                    chans = [(cr, cg, cb, glow_low + glow_span * lvl) for lvl in levels]
                ctx["session"].send(
                    [
                        LightColorCommand(
                            channel_id=cid,
                            red=int(r * 257 * s),
                            green=int(g * 257 * s),
                            blue=int(b * 257 * s),
                        )
                        for cid, (r, g, b, s) in zip(ctx["channel_ids"], chans)
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
        log.info("Effekt beendet (%s Frames).", frames)
        await asyncio.gather(
            *(ctx["session"].aclose() for ctx in bridge_ctxs), return_exceptions=True
        )
        # Nach dem Ende des Streams den gesicherten Lichtzustand zurückschreiben.
        await asyncio.gather(
            *(
                restore_light_state(ctx["bridge_host"], ctx["app_key"], snapshots.get(ctx["bridge_host"], []))
                for ctx in bridge_ctxs
            ),
            return_exceptions=True,
        )


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
            log.info("Identify (%s): Kanal %s an", bridge_host, cid)
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
        log.info("Identify (%s) beendet (%d Kanäle).", bridge_host, len(targets))
    except asyncio.CancelledError:
        pass
    except Exception:  # noqa: BLE001
        log.exception("Identify abgebrochen (DTLS-Start oder Senden fehlgeschlagen)")
    finally:
        await session.aclose()
        await restore_light_state(bridge_host, app_key, snapshot)


async def handle_identify(request: web.Request) -> web.Response:
    """POST /identify – Lampen einzeln durchtesten.

    Body: ``bridge_host`` (Pflicht bei mehr als einer konfigurierten Bridge),
    ``area_id`` (opt., sonst aus der bridges-Konfiguration), ``channel_id``
    (opt.; fehlt = alle nacheinander), ``seconds`` (opt.), ``color`` (opt.),
    ``restore_state`` (opt.).
    """
    existing = state["task"]
    if existing and not existing.done():
        return web.json_response({"status": "already_running"})

    body = await _json_body(request)
    host = body.get("bridge_host") or body.get("bridge_ip")
    if not host and len(state["bridges"]) == 1:
        host = state["bridges"][0]["bridge_host"]
    if not host:
        return web.json_response(
            {"error": "bridge_host fehlt im Body – bei mehreren Bridges Pflichtfeld"}, status=400
        )
    creds = state["credentials"].get(host)
    if not creds:
        return web.json_response(
            {"error": f"Bridge {host} noch nicht gepaart – zuerst POST /pair"}, status=400
        )

    cfg = next((b for b in state["bridges"] if b["bridge_host"] == host), None)
    area_id = body.get("area_id") or (cfg["area_id"] if cfg else None)
    if not area_id:
        return web.json_response(
            {"error": "area_id fehlt (im Body oder in der bridges-Konfiguration)"}, status=400
        )
    color = hex_to_rgb(body["color"]) if body.get("color") else state["color"]
    restore = bool(body.get("restore_state", state["restore_state"]))
    try:
        seconds = float(body.get("seconds") or 0.0)
    except (TypeError, ValueError):
        seconds = 0.0

    session = EntertainmentSession(host, creds["username"], creds["clientkey"])
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
            host, creds["username"], restore,
        )
    )
    result = {
        "status": "identify", "bridge_host": host, "area_id": area_id,
        "channels": targets, "seconds": hold,
    }
    log.info("Identify angefordert: %s", result)
    return web.json_response(result)


async def handle_start(request: web.Request) -> web.Response:
    """POST /start – Effekt auf allen konfigurierten (oder im Body übergebenen)
    Bridges gleichzeitig starten.

    Body optional: ``duration``, ``fps``, ``restore_state`` gelten für **alle**
    Bridges gemeinsam. ``effect``, ``color``, ``sweep_seconds``, ``chase_pause``,
    ``attack_ms``, ``release_ms``, ``glow_low``, ``glow_high``,
    ``glitter_interval_ms``, ``glitter_flash_ms``, ``glitter_colors`` im Body
    sind die **Standardwerte** für Bridges, die diese Parameter nicht selbst
    setzen. ``bridges`` (Liste von ``{bridge_host, area_id, channel_order,
    effect?, color?, sweep_seconds?, chase_pause?, attack_ms?, release_ms?,
    glow_low?, glow_high?, glitter_interval_ms?, glitter_flash_ms?,
    glitter_colors?}``) übersteuert für diesen Aufruf die Option ``bridges`` –
    jede Bridge kann ihren eigenen Effekt/Farbe/Timing haben. ``effect:
    neutral`` (als Standard oder je Bridge) lässt die betreffende(n) Bridge(s)
    komplett unangetastet – kein Stream, kein Sichern/Wiederherstellen –, sodass
    in einem Effektset eine Bridge laufen und eine andere aus sein kann. Sind
    **alle** Bridges neutral, antwortet ``/start`` mit ``no_active_bridges``.

    ``preset``: Name eines gespeicherten Effektsets (siehe ``/presets``); dessen
    gespeicherter Body dient als Basis, alle weiteren Body-Felder überschreiben
    ihn für diesen Aufruf.
    """
    existing = state["task"]
    if existing and not existing.done():
        return web.json_response({"status": "already_running"})

    body = await _json_body(request)

    preset_name = body.get("preset")
    if preset_name:
        base = state["presets"].get(str(preset_name))
        if not isinstance(base, dict):
            return web.json_response(
                {"error": f"Effektset '{preset_name}' nicht gefunden"}, status=404
            )
        merged = dict(base)
        merged.update({k: v for k, v in body.items() if k != "preset"})
        body = merged

    if "bridges" in body:
        req_bridges = _parse_bridges_option(body["bridges"])
        if not req_bridges:
            return web.json_response(
                {"error": "bridges muss eine Liste von {bridge_host, area_id} sein"}, status=400
            )
    else:
        req_bridges = state["bridges"]
    if not req_bridges:
        return web.json_response(
            {"error": "keine Bridge konfiguriert (Option bridges oder /start-Body bridges)"},
            status=400,
        )

    fps = int(body.get("fps") or options.get("fps", 25))
    restore = bool(body.get("restore_state", state["restore_state"]))
    # 0 = unbegrenzt (läuft bis POST /stop).
    try:
        duration = max(0.0, float(body.get("duration", state["duration"])))
    except (TypeError, ValueError):
        duration = state["duration"]

    # Standardwerte für Bridges, die diese Effekt-Parameter nicht selbst setzen.
    defaults = {"effect": _effect_name(body.get("effect") or state["effect"])}
    defaults["color"] = hex_to_rgb(body["color"]) if body.get("color") else state["color"]
    defaults["sweep_seconds"] = float(body.get("sweep_seconds") or options.get("sweep_seconds", 1.4))
    try:
        defaults["chase_pause"] = max(0.0, float(body.get("chase_pause", state["chase_pause"])))
    except (TypeError, ValueError):
        defaults["chase_pause"] = state["chase_pause"]
    defaults["attack_ms"] = float(body.get("attack_ms", state["attack_ms"]))
    defaults["release_ms"] = float(body.get("release_ms", state["release_ms"]))
    try:
        defaults["glow_low"] = min(max(float(body.get("glow_low", state["glow_low"])), 0.0), 1.0)
        defaults["glow_high"] = min(max(float(body.get("glow_high", state["glow_high"])), 0.0), 1.0)
    except (TypeError, ValueError):
        defaults["glow_low"], defaults["glow_high"] = state["glow_low"], state["glow_high"]
    try:
        defaults["glitter_interval_ms"] = max(
            1.0, float(body.get("glitter_interval_ms") or state["glitter_interval_ms"])
        )
    except (TypeError, ValueError):
        defaults["glitter_interval_ms"] = state["glitter_interval_ms"]
    try:
        defaults["glitter_flash_ms"] = max(
            1.0, float(body.get("glitter_flash_ms") or state["glitter_flash_ms"])
        )
    except (TypeError, ValueError):
        defaults["glitter_flash_ms"] = state["glitter_flash_ms"]
    _gc = body.get("glitter_colors")
    defaults["glitter_palette"] = _parse_color_list(
        _gc if _gc is not None else state["glitter_colors"]
    )

    async def _resolve(cfg: dict) -> dict:
        """Eine Bridge auflösen: gepaart? erreichbar? area_id/Kanäle gültig?

        Effekt-Parameter, die dieser Bridge-Eintrag nicht selbst setzt, fallen
        auf ``defaults`` zurück (Body bzw. Add-on-Option).
        """
        host = cfg["bridge_host"]
        creds = state["credentials"].get(host)
        if not creds:
            return {"bridge_host": host, "error": "nicht gepaart"}
        session = EntertainmentSession(host, creds["username"], creds["clientkey"])
        try:
            areas = await session.get_entertainment_areas()
        except Exception as exc:  # noqa: BLE001
            await session.aclose()
            return {"bridge_host": host, "error": f"Bridge nicht erreichbar ({exc})"}
        area = next((a for a in areas if a.id == cfg["area_id"]), None)
        if area is None:
            await session.aclose()
            return {"bridge_host": host, "error": f"area_id {cfg['area_id']} nicht gefunden"}
        native_ids = [ch.channel_id for ch in area.channels]
        order = cfg.get("channel_order")
        if order:
            if sorted(order) != sorted(native_ids):
                await session.aclose()
                return {
                    "bridge_host": host,
                    "error": f"channel_order {order} passt nicht zum Bereich – "
                             f"genau die Kanäle {sorted(native_ids)} in gewünschter "
                             f"Reihenfolge angeben",
                }
            channel_ids = list(order)
        else:
            channel_ids = native_ids

        glow_low = min(max(cfg.get("glow_low", defaults["glow_low"]), 0.0), 1.0)
        glow_high = min(max(cfg.get("glow_high", defaults["glow_high"]), 0.0), 1.0)
        glow_high = max(glow_high, glow_low)
        color = cfg.get("color", defaults["color"])
        palette = cfg.get("glitter_colors", defaults["glitter_palette"]) or [color]
        return {
            "bridge_host": host,
            "area_id": cfg["area_id"],
            "channel_ids": channel_ids,
            "session": session,
            "app_key": creds["username"],
            "effect": cfg.get("effect", defaults["effect"]),
            "color": color,
            "sweep_seconds": cfg.get("sweep_seconds", defaults["sweep_seconds"]),
            "chase_pause": max(0.0, cfg.get("chase_pause", defaults["chase_pause"])),
            "attack_s": cfg.get("attack_ms", defaults["attack_ms"]) / 1000.0,
            "release_s": cfg.get("release_ms", defaults["release_ms"]) / 1000.0,
            "glow_low": glow_low,
            "glow_high": glow_high,
            "glitter_interval_ms": max(1.0, cfg.get("glitter_interval_ms", defaults["glitter_interval_ms"])),
            "glitter_flash_ms": max(1.0, cfg.get("glitter_flash_ms", defaults["glitter_flash_ms"])),
            "glitter_palette": palette,
        }

    # "neutral": diese Bridge wird gar nicht angefasst (kein DTLS, kein
    # Sichern/Wiederherstellen) – so lässt sich in einem Effektset eine Bridge
    # bewusst auslassen, während die anderen einen Effekt fahren.
    neutral = [c for c in req_bridges if c.get("effect", defaults["effect"]) == "neutral"]
    to_run = [c for c in req_bridges if c.get("effect", defaults["effect"]) != "neutral"]
    neutral_report = [{"bridge_host": c["bridge_host"], "effect": "neutral"} for c in neutral]
    for c in neutral:
        log.info("Start: Bridge %s neutral – wird nicht gesteuert.", c["bridge_host"])

    # area_id/Kanäle für alle zu fahrenden Bridges parallel auflösen (kein DTLS).
    resolved = await asyncio.gather(*(_resolve(cfg) for cfg in to_run))
    ctxs = [r for r in resolved if "session" in r]
    failed = [r for r in resolved if "session" not in r]
    for r in failed:
        log.warning("Start: Bridge %s übersprungen (%s)", r["bridge_host"], r["error"])

    if not ctxs:
        if neutral and not failed:
            state["last_start"] = {
                "duration": duration, "fps": fps, "restore_state": restore,
                "bridges": [], "failed_bridges": [], "neutral_bridges": neutral_report,
            }
            log.info("Start: alle konfigurierten Bridges neutral – nichts zu tun.")
            return web.json_response({"status": "no_active_bridges", **state["last_start"]})
        return web.json_response(
            {"error": "keine Bridge verfügbar", "bridges": failed, "neutral_bridges": neutral_report},
            status=502,
        )

    # session.start() (DTLS-Handshake, ~einige Sekunden) passiert im Task,
    # damit die HTTP-Antwort nicht blockiert (HA rest_command-Timeout).
    state["task"] = asyncio.create_task(_run_effect(ctxs, duration, fps, restore))
    state["last_start"] = {
        "duration": duration,
        "fps": fps,
        "restore_state": restore,
        "neutral_bridges": neutral_report,
        "bridges": [
            {
                "bridge_host": c["bridge_host"],
                "area_id": c["area_id"],
                "channels": c["channel_ids"],
                "effect": c["effect"],
                "color": "#{:02X}{:02X}{:02X}".format(*c["color"]),
                "sweep_seconds": c["sweep_seconds"],
                "chase_pause": c["chase_pause"],
                "attack_ms": round(c["attack_s"] * 1000),
                "release_ms": round(c["release_s"] * 1000),
                "glow_low": round(c["glow_low"], 3),
                "glow_high": round(c["glow_high"], 3),
                "glitter_interval_ms": round(c["glitter_interval_ms"]),
                "glitter_flash_ms": round(c["glitter_flash_ms"]),
                "glitter_colors": _colors_to_hex(c["glitter_palette"]),
            }
            for c in ctxs
        ],
        "failed_bridges": failed,
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


# --------------------------------------------------------------------------- #
# Effektsets (Presets)
# --------------------------------------------------------------------------- #
def _preset_names() -> list[str]:
    return sorted(state["presets"].keys())


async def handle_presets_get(request: web.Request) -> web.Response:
    """GET /presets – alle gespeicherten Effektsets (Name -> /start-Body)."""
    name = request.query.get("name")
    if name is not None:
        cfg = state["presets"].get(name)
        if cfg is None:
            return web.json_response({"error": f"Effektset '{name}' nicht gefunden"}, status=404)
        return web.json_response({"name": name, "config": cfg})
    return web.json_response({"presets": state["presets"], "names": _preset_names()})


async def handle_presets_put(request: web.Request) -> web.Response:
    """PUT/POST /presets – ein Effektset speichern/überschreiben.

    Body: ``{"name": "...", "config": { <start-Body> }}``. ``config`` darf die
    kompletten ``/start``-Felder enthalten (inkl. ``bridges``); ein evtl.
    mitgeschicktes ``preset`` wird entfernt. Dient auch als Upload-Ziel.
    """
    body = await _json_body(request)
    name = str(body.get("name") or "").strip()
    if not name:
        return web.json_response({"error": "name fehlt"}, status=400)
    config = body.get("config")
    if config is None and isinstance(body.get("bridges"), list):
        # Bequemlichkeit: flacher Upload ohne {name, config}-Hülle.
        config = {k: v for k, v in body.items() if k != "name"}
    if not isinstance(config, dict):
        return web.json_response({"error": "config muss ein Objekt sein"}, status=400)
    config.pop("preset", None)
    state["presets"][name] = config
    _save_presets(state["presets"])
    log.info("Effektset '%s' gespeichert (%d gesamt).", name, len(state["presets"]))
    return web.json_response({"status": "saved", "name": name, "names": _preset_names()})


async def handle_presets_delete(request: web.Request) -> web.Response:
    """DELETE /presets?name=... – ein Effektset löschen."""
    name = request.query.get("name")
    if not name:
        name = (await _json_body(request)).get("name")
    name = str(name or "").strip()
    if name in state["presets"]:
        del state["presets"][name]
        _save_presets(state["presets"])
        log.info("Effektset '%s' gelöscht (%d verbleibend).", name, len(state["presets"]))
        return web.json_response({"status": "deleted", "name": name, "names": _preset_names()})
    return web.json_response({"status": "not_found", "name": name}, status=404)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_panel)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/config", handle_config)
    app.router.add_post("/pair", handle_pair)
    app.router.add_get("/areas", handle_areas)
    app.router.add_post("/start", handle_start)
    app.router.add_post("/stop", handle_stop)
    app.router.add_post("/identify", handle_identify)
    app.router.add_get("/presets", handle_presets_get)
    app.router.add_put("/presets", handle_presets_put)
    app.router.add_post("/presets", handle_presets_put)
    app.router.add_delete("/presets", handle_presets_delete)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8099, access_log=None)
