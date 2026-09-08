"""Red Alert Entertainment – REST-API, Streaming-Loop und Ingress-Web-UI.

Der Dienst hält pro konfigurierter Hue Bridge (bis zu 3) einen eigenen
DTLS-Stream offen und schiebt ~25 Frames/s an die Kanäle: ein gemeinsames
Auf-/Ab-Blenden aller Lampen einer Bridge (``effect: pulse``, Standard), ein
umlaufender Komet mit Schweif (``effect: comet``), ein Diamant-Gefunkel aus
kurzen Farb-Blitzen (``effect: glitter``), ein Alarmlicht-Blinken zweier
Lampengruppen (``effect: police``), ein Gewitter aus zufälligen
Sammel-Blitzen (``effect: lightning``), ein Herzschlag-Doppelpuls
(``effect: heartbeat``), langsam wandernde Polarlicht-Farbwellen
(``effect: aurora``), ein phasenversetzter Regenbogen-Farbumlauf
(``effect: rainbow``), mehrere unabhängige Meteore (``effect: meteor``), ein
sequenzieller Auffüll-Balken (``effect: wipe``), wiederkehrende
Feuerwerk-Ausbrüche (``effect: firework``), für Gradient Lightstrips
weich überblendete Farbbänder (``effect: chase``) oder ein lampenweise
nachgezogener Farbverlauf durch drei Paletten (``effect: color_chase``).
Effekt, Farbe und Timing sind pro Bridge einzeln einstellbar; jede Bridge
läuft in ihrem eigenen, unabhängig start-/stoppbaren Task
(``state["tasks"]``) – ein ``POST /start``/``/stop`` mit ``bridge_host``
im Body betrifft nur diese eine Bridge, während andere unberührt
weiterlaufen. Mehrere Bridges im selben ``/start``-Aufruf starten trotzdem
gleichzeitig (eine gemeinsame Barriere lässt jeden Task nach seinem eigenen
DTLS-Handshake auf die anderen warten, bevor die Start-Uhr gesetzt wird).
Läuft für ``duration`` Sekunden (Standardwert aus der gleichnamigen
App-Option, für alle Bridges eines Aufrufs gemeinsam; `0` = unbegrenzt,
läuft bis ``POST /stop``).

Der komplette Satz an Start-Parametern (alle Bridges + Steuerung) lässt sich
als benanntes **Effektset** unter ``/data/presets.json`` ablegen
(``GET/PUT/DELETE /presets``) und per ``POST /start {"preset": "..."}``
wieder starten; ``POST /select {"preset": "..."}`` merkt ein Set nur als
*geladen* (``current_preset``), ohne es zu starten.
"""

import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path

import aiohttp
from aiohttp import web
from hue_entertainment import EntertainmentSession, HueEntertainmentAPI, LightColorCommand

import hue_entertainment.dtls as _hue_dtls

from chase import (
    RedAlertAurora,
    RedAlertChase,
    RedAlertColorChase,
    RedAlertComet,
    RedAlertDuel,
    RedAlertFirework,
    RedAlertFlicker,
    RedAlertGlitter,
    RedAlertLightning,
    RedAlertMeteor,
    RedAlertPolice,
    RedAlertPulse,
    RedAlertRainbow,
    RedAlertRipple,
    RedAlertStrobe,
    RedAlertWave,
    RedAlertWipe,
)

# DTLS-Handshake beschleunigen: der ServerHello-Timeout der Lib steht auf 5 s und
# schlägt bei Hue-Bridges fast immer einmal voll zu, bevor der Resend durchkommt –
# das ist der Löwenanteil der „einige Sekunden" zwischen /start und sichtbarem
# Effekt. Kürzeres Timeout, dafür mehr (kürzere) Resends. Beide Werte werden in der
# Lib zur Laufzeit gelesen (_DtlsConnection.__init__ bzw. _await_server_hello), der
# Patch wirkt also auch für später erzeugte Verbindungen. Das separate, hart
# kodierte settimeout(3.0) für das optionale Server-Finished (dtls.py) bleibt –
# es greift nur, wenn die Bridge das Finished gar nicht schickt.
_hue_dtls.HANDSHAKE_TIMEOUT = 1.5
_hue_dtls._SERVER_HELLO_RESENDS = 4

DATA_DIR = Path(os.environ.get("REDALERT_DATA_DIR", "/data"))
CRED_FILE = DATA_DIR / "credentials.json"
OPTIONS_FILE = DATA_DIR / "options.json"
PRESETS_FILE = DATA_DIR / "presets.json"

APP_DIR = Path(__file__).parent
PANEL_HTML = (APP_DIR / "panel.html").read_text(encoding="utf-8")

# Mehr konfigurierte bridges-Einträge als das werden beim Laden abgeschnitten.
MAX_BRIDGES = 3

# Timeout je Hue-CLIP-v2-Aufruf (Lichtzustand sichern/wiederherstellen) – ohne
# eigenes Limit greift aiohttps Standard von 300s, falls die Bridge kurz weg ist.
_CLIP_TIMEOUT = aiohttp.ClientTimeout(total=8)

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


_EFFECTS = (
    "pulse",
    "comet",
    "glitter",
    "chase",
    "police",
    "lightning",
    "heartbeat",
    "aurora",
    "rainbow",
    "meteor",
    "wipe",
    "firework",
    "ripple",
    "wave",
    "flicker",
    "strobe",
    "duel",
    "color_chase",
    "neutral",
)


def _effect_name(value) -> str:
    v = str(value or "").lower()
    return v if v in _EFFECTS else "pulse"


_GC_DIRECTIONS = ("forward", "backward", "bounce")


def _gc_direction(value) -> str:
    v = str(value or "").lower()
    return v if v in _GC_DIRECTIONS else "forward"


def _parse_gc_directions(value) -> str | list[str] | None:
    """``gc_direction`` aus Option/Body: eine Richtung (gilt für alle Strips
    dieser Bridge) oder eine Liste/kommagetrennte Liste (eine je Strip, siehe
    ``gc_strip_lengths``). ``None``/leer -> ``None`` (Standard "forward")."""
    if not value:
        return None
    if isinstance(value, (list, tuple)):
        parts = [str(x) for x in value]
    else:
        parts = [p for p in str(value).replace(",", " ").split() if p]
    if not parts:
        return None
    return _gc_direction(parts[0]) if len(parts) == 1 else [_gc_direction(p) for p in parts]


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


def _parse_int_list(value) -> list[int] | None:
    """Liste[int] aus Option/Body: Liste[int] oder "3,1,0,2,5,4".

    Für ``channel_order`` (Kanalreihenfolge) und ``gc_strip_lengths``
    (Segmentzahl je Gradient-Lightstrip innerhalb einer Bridge) genutzt.
    ``None`` / leer -> ``None`` (Standard). Ungültiges -> ``ValueError``.
    """
    if value is None:
        return None
    if isinstance(value, str):
        parts = [p for p in value.replace(",", " ").split() if p]
        value = parts
    if not isinstance(value, (list, tuple)):
        raise ValueError("muss eine Liste sein")
    order = [int(x) for x in value]  # wirft ValueError bei Nicht-Zahlen
    return order or None


# Pro-Bridge überschreibbare Effekt-Parameter: Name im bridges-Eintrag -> Cast.
# Fehlt der Schlüssel (oder ist er leer) in einem Eintrag, gilt der gleichnamige
# Wert aus dem /start-Body bzw. den App-Optionen als Standard für diese Bridge.
_BRIDGE_NUMERIC_OVERRIDES = (
    ("sweep_seconds", float),
    ("chase_pause", float),
    ("attack_ms", float),
    ("release_ms", float),
    ("glow_low", float),
    ("glow_high", float),
    ("glitter_interval_ms", float),
    ("glitter_flash_ms", float),
    ("gc_count", int),
    ("gc_length", float),
    ("gc_speed", float),
    ("meteor_count", int),
    ("meteor_speed", float),
    ("firework_interval_ms", float),
    ("firework_speed", float),
    ("lightning_interval_ms", float),
    ("lightning_flash_ms", float),
    ("ripple_interval_ms", float),
    ("ripple_speed", float),
    ("wave_length", float),
    ("flicker_interval_ms", float),
    ("flicker_dip_ms", float),
)


def _parse_bridges_option(value) -> list[dict]:
    """``bridges``-Option/Body in normalisierte Einträge parsen.

    Jeder Eintrag braucht ``bridge_host`` + ``area_id`` (bei ``effect: neutral``
    reicht ``bridge_host`` – die Bridge wird dann gar nicht gesteuert);
    ``channel_order`` und die Effekt-Parameter (``effect``, ``color``,
    ``sweep_seconds``, ``chase_pause``, ``attack_ms``, ``release_ms``,
    ``glow_low``, ``glow_high``, ``glitter_interval_ms``, ``glitter_flash_ms``,
    ``glitter_colors``, ``gc_direction``, ``gc_strip_lengths``, ``gc_count``,
    ``gc_length``, ``gc_speed``, ``gc_background_color``, ``gc_chase_glitter``,
    ``gc_background_pulse``, ``color2``, ``meteor_count``,
    ``meteor_speed``, ``firework_interval_ms``, ``firework_speed``,
    ``lightning_interval_ms``, ``lightning_flash_ms``, ``ripple_interval_ms``,
    ``ripple_speed``, ``wave_length``, ``flicker_interval_ms``,
    ``flicker_dip_ms``) sind
    optional und überschreiben nur für diese eine
    Bridge den sonst gültigen Standard (Body bzw. App-Option). ``gc_strip_lengths``
    teilt die Kanäle dieser Bridge (nach ``channel_order``) in aufeinanderfolgende
    Gradient-Lightstrips auf, z. B. ``[7, 5]`` für zwei kombinierte Strips zu 7 bzw.
    5 Segmenten; ``gc_direction`` kann dann ebenfalls eine Liste sein (eine
    Richtung je Strip) statt eines einzelnen Werts für alle Strips. Unvollständige
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
            order = _parse_int_list(entry.get("channel_order"))
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
        if entry.get("gc_direction"):
            direction = _parse_gc_directions(entry["gc_direction"])
            if direction is not None:
                norm["gc_direction"] = direction
        if entry.get("gc_strip_lengths"):
            try:
                lengths = _parse_int_list(entry["gc_strip_lengths"])
            except (TypeError, ValueError):
                log.warning("Bridge %s: gc_strip_lengths ungültig – ignoriert", host)
                lengths = None
            if lengths:
                norm["gc_strip_lengths"] = lengths
        if entry.get("gc_background_color"):
            norm["gc_background_color"] = hex_to_rgb(entry["gc_background_color"])
        if entry.get("color2"):
            norm["color2"] = hex_to_rgb(entry["color2"])
        if "gc_chase_glitter" in entry:
            norm["gc_chase_glitter"] = bool(entry["gc_chase_glitter"])
        if "gc_background_pulse" in entry:
            norm["gc_background_pulse"] = bool(entry["gc_background_pulse"])
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
    # Nur effect chase (Gradient Lightstrips):
    "gc_direction": _gc_direction(options.get("gc_direction", "forward")),
    "gc_count": max(1, int(options.get("gc_count", 1))),
    "gc_length": min(max(float(options.get("gc_length", 2.0)), 0.2), 200.0),
    "gc_speed": max(0.01, float(options.get("gc_speed", 4.0))),
    "gc_background_color": hex_to_rgb(options.get("gc_background_color", "#000000")),
    "gc_chase_glitter": bool(options.get("gc_chase_glitter", False)),
    "gc_background_pulse": bool(options.get("gc_background_pulse", False)),
    # Zweite Farbe: effect police (zweite Lampengruppe) und effect duel
    # (zweiter Komet):
    "color2": hex_to_rgb(options.get("color2", "#0000FF")),
    # Nur effect meteor:
    "meteor_count": max(1, int(options.get("meteor_count", 3))),
    "meteor_speed": max(0.05, float(options.get("meteor_speed", 1.2))),
    # Nur effect firework:
    "firework_interval_ms": max(1.0, float(options.get("firework_interval_ms", 3000.0))),
    "firework_speed": max(0.5, float(options.get("firework_speed", 6.0))),
    # Nur effect lightning:
    "lightning_interval_ms": max(1.0, float(options.get("lightning_interval_ms", 4000.0))),
    "lightning_flash_ms": max(1.0, float(options.get("lightning_flash_ms", 500.0))),
    # Nur effect ripple:
    "ripple_interval_ms": max(1.0, float(options.get("ripple_interval_ms", 3000.0))),
    "ripple_speed": max(0.5, float(options.get("ripple_speed", 6.0))),
    # Nur effect wave:
    "wave_length": max(0.5, float(options.get("wave_length", 3.0))),
    # Nur effect flicker:
    "flicker_interval_ms": max(1.0, float(options.get("flicker_interval_ms", 600.0))),
    "flicker_dip_ms": max(1.0, float(options.get("flicker_dip_ms", 150.0))),
    "restore_state": bool(options.get("restore_state", True)),
    # 0 = unbegrenzt (läuft bis POST /stop).
    "duration": max(0.0, float(options.get("duration", 0.0))),
    # Ein asyncio.Task je Bridge, die gerade einen Effekt oder einen Identify-
    # Durchlauf fährt (bridge_host -> Task); beide teilen sich denselben Slot
    # pro Bridge (already_running-Guard), sind aber zwischen Bridges völlig
    # unabhängig – eine Bridge starten/stoppen berührt keine andere.
    "tasks": {},
    # Scharfgeschaltete Bridges (bridge_host -> ArmContext-Dict mit offenem,
    # dauerhaft gehaltenem DTLS-Stream). Ein /start für eine scharfe Bridge
    # überspringt Handshake + Snapshot; siehe _arm_one / _run_single_bridge.
    "armed": {},
    # Zuletzt aufgelöste Effekt-Parameter je Bridge (bridge_host -> Dict),
    # bleibt über einzelne /start-Aufrufe hinweg bestehen (ein Solo-Start
    # aktualisiert nur den eigenen Eintrag). Für die im Aufruf gemeinsam
    # geltenden Werte (duration/fps/restore_state) siehe last_start_meta.
    "last_start": {},
    "last_start_meta": {},
    # Name des zuletzt per {"preset": "..."} geladenen Effektsets – None bei
    # Ad-hoc-Starts ohne preset. Für die Home-Assistant-Integration (Select-
    # Entity "geladenes Effektset"), siehe /health & /config. Ein Solo-Start
    # für eine einzelne Bridge (bridge_host im Body) ändert dies nie – ein
    # Effektset gilt als Mehr-Bridge-Konzept, siehe handle_start.
    "current_preset": None,
}

log.info(
    "Konfiguration: bridges=%s (Standard) effect=%s color=%s fps=%s sweep=%ss chase_pause=%ss "
    "attack=%sms release=%sms glow=%s..%s glitter=%sms/%sms colors=%r "
    "chase=dir=%s/count=%s/length=%s/speed=%s bg=%s glitter=%s pulse=%s "
    "color2=%s meteor=count=%s/speed=%s firework=interval=%sms/speed=%s "
    "lightning=interval=%sms/flash=%sms "
    "ripple=interval=%sms/speed=%s wave=length=%s flicker=interval=%sms/dip=%sms "
    "duration=%ss (0=unbegrenzt) presets=%s",
    [
        {"bridge_host": b["bridge_host"], "area_id": b["area_id"], "channel_order": b["channel_order"],
         **{k: b[k] for k in ("effect", "color", "sweep_seconds", "chase_pause",
                               "attack_ms", "release_ms", "glow_low", "glow_high",
                               "glitter_interval_ms", "glitter_flash_ms", "glitter_colors",
                               "gc_direction", "gc_strip_lengths", "gc_count", "gc_length",
                               "gc_speed", "gc_background_color", "gc_chase_glitter",
                               "gc_background_pulse", "color2", "meteor_count",
                               "meteor_speed", "firework_interval_ms", "firework_speed",
                               "lightning_interval_ms", "lightning_flash_ms",
                               "ripple_interval_ms", "ripple_speed", "wave_length",
                               "flicker_interval_ms", "flicker_dip_ms") if k in b}}
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
    state["gc_direction"],
    state["gc_count"],
    state["gc_length"],
    state["gc_speed"],
    "#{:02X}{:02X}{:02X}".format(*state["gc_background_color"]),
    state["gc_chase_glitter"],
    state["gc_background_pulse"],
    "#{:02X}{:02X}{:02X}".format(*state["color2"]),
    state["meteor_count"],
    state["meteor_speed"],
    state["firework_interval_ms"],
    state["firework_speed"],
    state["lightning_interval_ms"],
    state["lightning_flash_ms"],
    state["ripple_interval_ms"],
    state["ripple_speed"],
    state["wave_length"],
    state["flicker_interval_ms"],
    state["flicker_dip_ms"],
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
        # Ohne Timeout hängt ein einzelner CLIP-v2-Aufruf bis zu 5 Minuten (aiohttp-
        # Standard), falls die Bridge genau jetzt kurz nicht erreichbar ist – so
        # lange bliebe die Bridge in state["tasks"] fälschlich "läuft" und
        # /start für sie "already_running".
        async with aiohttp.ClientSession(timeout=_CLIP_TIMEOUT) as sess:
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
        async with aiohttp.ClientSession(timeout=_CLIP_TIMEOUT) as sess:
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


def _is_running(host: str) -> bool:
    """Läuft gerade ein Effekt oder Identify-Durchlauf auf dieser Bridge?"""
    task = state["tasks"].get(host)
    return bool(task and not task.done())


def _any_running() -> bool:
    """Irgendeine Bridge aktiv? Für Konsumenten, die (noch) nicht je Bridge
    unterscheiden (z. B. die Home-Assistant-Integration – siehe /health)."""
    return any(not t.done() for t in state["tasks"].values())


# --------------------------------------------------------------------------- #
# Scharfschalten (Arming): DTLS-Stream dauerhaft offen halten
# --------------------------------------------------------------------------- #
# Eine „scharfe" Bridge hält ihren DTLS-Stream offen und streamt im Ruhezustand
# ein aus dem Lichtzustands-Snapshot abgeleitetes Standbild. Ein anschließendes
# /start überspringt dann Handshake *und* Snapshot und beginnt den Effekt
# innerhalb eines Frames statt nach den üblichen ~3–9 s Handshake. Preis:
# die Bridge belegt dauerhaft ihren einzigen Entertainment-Slot, und die
# Area-Lampen stehen unter Stream-Kontrolle (angenäherter Vorzustand) bis
# /disarm den exakten Zustand per CLIP v2 wiederherstellt.


async def _session_start(session: EntertainmentSession, area_id: str) -> None:
    """``session.start`` ohne das serielle Stoppen anderer Areas (spart HTTPS-
    Roundtrips vor dem Handshake). Schlägt es fehl – etwa weil doch ein
    verwaister fremder Stream läuft –, einmal mit ``stop_others=True``
    nachfassen."""
    try:
        await session.start(area_id, stop_others=False)
    except Exception:  # noqa: BLE001
        await session.start(area_id, stop_others=True)


def _xy_to_rgb(x: float, y: float, bri: float) -> tuple[int, int, int]:
    """CIE-xy + Helligkeit (0–100) → sRGB 0–255 (Näherung, Philips-Wide-Gamut)."""
    if y <= 0:
        return (0, 0, 0)
    yy = max(0.0, min(bri, 100.0)) / 100.0
    xx = (yy / y) * x
    zz = (yy / y) * (1.0 - x - y)
    r = xx * 1.656492 - yy * 0.354851 - zz * 0.255038
    g = -xx * 0.707196 + yy * 1.655397 + zz * 0.036152
    b = xx * 0.051713 - yy * 0.121364 + zz * 1.011530

    def _gamma(c: float) -> float:
        c = max(0.0, c)
        c = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
        return max(0.0, min(c, 1.0))

    return tuple(int(round(_gamma(c) * 255)) for c in (r, g, b))  # type: ignore[return-value]


def _mirek_to_rgb(mirek: float, bri: float) -> tuple[int, int, int]:
    """Farbtemperatur (Mikro-Reziprok-Kelvin) → grobes Warm/Kalt-Weiß, skaliert."""
    t = max(0.0, min((mirek - 153) / (500 - 153), 1.0))
    scale = max(0.0, min(bri, 100.0)) / 100.0
    return (
        int(round(255 * scale)),
        int(round((255 - 80 * t) * scale)),
        int(round((255 - 200 * t) * scale)),
    )


def _snapshot_light_rgb(st: dict) -> tuple[int, int, int]:
    """RGB einer einzelnen Snapshot-Lampe (aus, mit Farbe oder mit Weißton)."""
    if not st.get("on"):
        return (0, 0, 0)
    bri = st.get("brightness")
    bri = 100.0 if bri is None else float(bri)
    xy = st.get("xy")
    if xy and len(xy) == 2:
        return _xy_to_rgb(float(xy[0]), float(xy[1]), bri)
    if st.get("mirek") is not None:
        return _mirek_to_rgb(float(st["mirek"]), bri)
    s = bri / 100.0
    return (int(round(255 * s)), int(round(200 * s)), int(round(150 * s)))


def _idle_frame_from_snapshot(
    snapshot: list[dict], channel_ids: list[int]
) -> list[LightColorCommand]:
    """Ruhebild für eine scharfe Bridge: Mittelwert-RGB aller *eingeschalteten*
    Snapshot-Lampen, gleichförmig auf alle Kanäle. Alles aus → Frame mit 0.

    Bewusst kanal-uniform: Entertainment-Kanäle entsprechen nicht 1:1 der
    CLIP-Lichtliste; der exakte Zustand wird beim /disarm ohnehin per
    ``restore_light_state`` zurückgeschrieben."""
    lit = [_snapshot_light_rgb(st) for st in snapshot if st.get("on")]
    if lit:
        r = sum(c[0] for c in lit) / len(lit)
        g = sum(c[1] for c in lit) / len(lit)
        b = sum(c[2] for c in lit) / len(lit)
    else:
        r = g = b = 0.0
    return [
        LightColorCommand(
            channel_id=cid, red=int(r * 257), green=int(g * 257), blue=int(b * 257)
        )
        for cid in channel_ids
    ]


async def _arm_idle_loop(host: str) -> None:
    """Solange die Bridge scharf ist: alle 2 s das Ruhebild senden. Bricht ab,
    wenn der Stream stirbt (dann meldet /config die Bridge als nicht mehr
    scharf)."""
    try:
        while host in state["armed"]:
            ctx = state["armed"].get(host)
            if not ctx:
                return
            session = ctx["session"]
            if not session.is_streaming:
                log.warning("Scharfschaltung %s: DTLS-Stream weg – Bridge gilt als entschärft.", host)
                state["armed"].pop(host, None)
                with contextlib.suppress(Exception):
                    await session.aclose()
                return
            session.send(ctx["idle_frame"])
            await asyncio.sleep(2.0)
    except asyncio.CancelledError:
        pass


async def _arm_one(cfg: dict) -> dict:
    """Eine Bridge scharfschalten: Area/Kanäle auflösen, Lichtzustand sichern,
    DTLS-Stream öffnen und offen halten. Rückgabe ``{"bridge_host": ...}`` mit
    entweder ``"armed": True`` oder ``"error": "..."``."""
    host = cfg["bridge_host"]
    creds = state["credentials"].get(host)
    if not creds:
        return {"bridge_host": host, "error": "nicht gepaart"}
    session = EntertainmentSession(host, creds["username"], creds["clientkey"], idle_timeout=0)
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
    if order and sorted(order) != sorted(native_ids):
        await session.aclose()
        return {"bridge_host": host, "error": f"channel_order {order} passt nicht zum Bereich"}
    channel_ids = list(order) if order else native_ids

    # Snapshot immer aufnehmen (unabhängig von restore_state) – er ist die
    # Grundlage sowohl fürs Ruhebild als auch fürs Wiederherstellen bei /disarm.
    snapshot = await capture_light_state(host, creds["username"], cfg["area_id"])
    try:
        await _session_start(session, cfg["area_id"])
    except Exception as exc:  # noqa: BLE001
        await session.aclose()
        log.exception("Scharfschalten %s fehlgeschlagen (DTLS-Handshake)", host)
        return {"bridge_host": host, "error": f"DTLS-Handshake fehlgeschlagen ({exc})"}

    idle_frame = _idle_frame_from_snapshot(snapshot, channel_ids)
    session.send(idle_frame)
    state["armed"][host] = {
        "session": session,
        "app_key": creds["username"],
        "area_id": cfg["area_id"],
        "channel_ids": channel_ids,
        "snapshot": snapshot,
        "idle_frame": idle_frame,
        "idle_task": None,
    }
    state["armed"][host]["idle_task"] = asyncio.create_task(_arm_idle_loop(host))
    log.info("Bridge %s scharfgeschaltet (Stream offen, %d Kanäle).", host, len(channel_ids))
    return {"bridge_host": host, "armed": True}


async def _disarm_one(host: str) -> bool:
    """Eine Bridge entschärfen: Ruhe-Loop stoppen, Stream schließen, exakten
    Lichtzustand per CLIP v2 wiederherstellen. ``False``, wenn nicht scharf."""
    ctx = state["armed"].pop(host, None)
    if not ctx:
        return False
    idle_task = ctx.get("idle_task")
    if idle_task and not idle_task.done():
        idle_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await idle_task
    with contextlib.suppress(Exception):
        await ctx["session"].aclose()
    await restore_light_state(host, ctx["app_key"], ctx["snapshot"])
    log.info("Bridge %s entschärft (Stream zu, Lichtzustand wiederhergestellt).", host)
    return True


def _armed_all() -> bool:
    """Sind alle nicht-neutralen, gepaarten konfigurierten Bridges scharf?
    (Global-Flag für /health und die HA-Integration.)"""
    hosts = [
        b["bridge_host"]
        for b in state["bridges"]
        if b["bridge_host"] in state["credentials"] and b.get("effect") != "neutral"
    ]
    return bool(hosts) and all(h in state["armed"] for h in hosts)


# --------------------------------------------------------------------------- #
# Web-UI (Ingress) + Status
# --------------------------------------------------------------------------- #
async def handle_panel(request: web.Request) -> web.Response:
    return web.Response(text=PANEL_HTML, content_type="text/html")


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": "ok",
            "paired": bool(state["credentials"]),
            "running": _any_running(),
            "armed": _armed_all(),
            "current_preset": state["current_preset"],
        }
    )


def _bridge_color_hex(b: dict) -> str | None:
    if "color" not in b:
        return None
    cr, cg, cb = b["color"]
    return f"#{cr:02X}{cg:02X}{cb:02X}"


def _bridge_field_hex(b: dict, key: str) -> str | None:
    if key not in b:
        return None
    cr, cg, cb = b[key]
    return f"#{cr:02X}{cg:02X}{cb:02X}"


async def handle_config(request: web.Request) -> web.Response:
    r, g, b = state["color"]
    return web.json_response(
        {
            "bridges": [
                {
                    "bridge_host": bg["bridge_host"],
                    "area_id": bg["area_id"],
                    "channel_order": bg["channel_order"],
                    "paired": bg["bridge_host"] in state["credentials"],
                    "running": _is_running(bg["bridge_host"]),
                    "armed": bg["bridge_host"] in state["armed"],
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
                    "gc_direction": bg.get("gc_direction"),
                    "gc_strip_lengths": bg.get("gc_strip_lengths"),
                    "gc_count": bg.get("gc_count"),
                    "gc_length": bg.get("gc_length"),
                    "gc_speed": bg.get("gc_speed"),
                    "gc_background_color": _bridge_field_hex(bg, "gc_background_color"),
                    "gc_chase_glitter": bg.get("gc_chase_glitter"),
                    "gc_background_pulse": bg.get("gc_background_pulse"),
                    "color2": _bridge_field_hex(bg, "color2"),
                    "meteor_count": bg.get("meteor_count"),
                    "meteor_speed": bg.get("meteor_speed"),
                    "firework_interval_ms": bg.get("firework_interval_ms"),
                    "firework_speed": bg.get("firework_speed"),
                    "lightning_interval_ms": bg.get("lightning_interval_ms"),
                    "lightning_flash_ms": bg.get("lightning_flash_ms"),
                    "ripple_interval_ms": bg.get("ripple_interval_ms"),
                    "ripple_speed": bg.get("ripple_speed"),
                    "wave_length": bg.get("wave_length"),
                    "flicker_interval_ms": bg.get("flicker_interval_ms"),
                    "flicker_dip_ms": bg.get("flicker_dip_ms"),
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
            "gc_direction": state["gc_direction"],
            "gc_count": state["gc_count"],
            "gc_length": state["gc_length"],
            "gc_speed": state["gc_speed"],
            "gc_background_color": "#{:02X}{:02X}{:02X}".format(*state["gc_background_color"]),
            "gc_chase_glitter": state["gc_chase_glitter"],
            "gc_background_pulse": state["gc_background_pulse"],
            "color2": "#{:02X}{:02X}{:02X}".format(*state["color2"]),
            "meteor_count": state["meteor_count"],
            "meteor_speed": state["meteor_speed"],
            "firework_interval_ms": state["firework_interval_ms"],
            "firework_speed": state["firework_speed"],
            "lightning_interval_ms": state["lightning_interval_ms"],
            "lightning_flash_ms": state["lightning_flash_ms"],
            "ripple_interval_ms": state["ripple_interval_ms"],
            "ripple_speed": state["ripple_speed"],
            "wave_length": state["wave_length"],
            "flicker_interval_ms": state["flicker_interval_ms"],
            "flicker_dip_ms": state["flicker_dip_ms"],
            "restore_state": state["restore_state"],
            "log_level": str(options.get("log_level", "info")),
            "default_duration_s": state["duration"],
            "presets": sorted(state["presets"].keys()),
            "current_preset": state["current_preset"],
            "running": _any_running(),
            "armed": _armed_all(),
            "armed_bridges": sorted(state["armed"]),
            "last_start": {
                "duration": state["last_start_meta"].get("duration"),
                "fps": state["last_start_meta"].get("fps"),
                "restore_state": state["last_start_meta"].get("restore_state"),
                "bridges": list(state["last_start"].values()),
            } if state["last_start"] else None,
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
def _chase_chans(
    ctx: dict, elapsed: float, dt: float, glow_low: float, glow_span: float
) -> list[tuple[float, float, float, float]]:
    """Ein Frame ``effect: chase`` als ``(r, g, b, scaled_level)`` je Kanal.

    Holt pro Strip (``ctx["chase"]``, je eine ``RedAlertChase``-
    Instanz) den 0..1-Blend und reiht die Ergebnisse in Kanalreihenfolge
    aneinander; interpoliert je Kanal zwischen ``gc_background_color`` (Blend 0)
    und ``color`` (Blend 1). Die Chase-Bänder liegen dabei immer auf
    ``glow_high`` (wie der Kopf bei ``comet``); der Background ruht ohne
    ``gc_background_pulse`` auf ``glow_low`` und pulsiert mit gesetztem
    Parameter stattdessen zwischen ``glow_low`` und ``glow_high`` (gleiches
    Timing wie ``effect: pulse``). Chase-Glitter legt zusätzlich Funken nur
    innerhalb der Bänder (Blend > 0.5) obendrauf.
    """
    blend: list[float] = []
    for gc in ctx["chase"]:
        blend.extend(gc.blend_for(elapsed, dt))
    if ctx["gc_background_pulse"]:
        target = RedAlertPulse.periodic(elapsed, ctx["sweep_seconds"])
        bg_level = ctx["pulse"].step(target, dt)[0]
    else:
        bg_level = 0.0
    cr, cg, cb = ctx["color"]
    br, bgc, bb = ctx["gc_background_color"]
    glitter_vals = ctx["glitter"].step(dt) if ctx["gc_chase_glitter"] else None
    chans = []
    for idx, bl in enumerate(blend):
        r = br + (cr - br) * bl
        g = bgc + (cg - bgc) * bl
        b = bb + (cb - bb) * bl
        level = bl + (1.0 - bl) * bg_level
        if glitter_vals is not None and bl > 0.5:
            glvl, (gr, gg, gb) = glitter_vals[idx]
            if glvl > 0:
                r += (gr - r) * glvl
                g += (gg - g) * glvl
                b += (gb - b) * glvl
                level = max(level, glvl)
        chans.append((r, g, b, glow_low + glow_span * level))
    return chans


async def _run_single_bridge(
    ctx: dict,
    duration: float,
    fps: int,
    restore: bool,
    start_barrier: asyncio.Barrier | None,
    arm_ctx: dict | None = None,
) -> None:
    """Effekt auf einer einzelnen Bridge fahren – eigener Task, eigene Sitzung.

    Ist die Bridge scharfgeschaltet (``arm_ctx`` gesetzt), läuft der DTLS-Stream
    bereits: Handshake und Snapshot entfallen, der Effekt beginnt praktisch
    sofort. Die scharfe Ruhe-Loop (``arm_ctx["idle_task"]``) wird für die Dauer
    des Effekts pausiert und im ``finally`` wieder gestartet, sofern die Bridge
    noch scharf ist – nur eine zwischenzeitlich entschärfte (oder nie scharfe)
    Bridge schließt ihren Stream und stellt den Lichtzustand wieder her.

    Für einen gemeinsamen Batch-Start (mehrere Bridges im selben ``/start``-
    Aufruf, siehe ``handle_start``) teilen sich alle beteiligten Tasks eine
    ``start_barrier``: jeder Task wartet nach seinem eigenen erfolgreichen
    DTLS-Handshake dort, bis alle anderen ebenfalls so weit sind, bevor die
    ``start``-Zeit gesetzt wird – so leuchten alle Bridges eines Batches
    trotz unabhängiger Tasks gleichzeitig los, bleiben aber einzeln über
    ``state["tasks"]`` kündbar (Stop auf einer Bridge lässt die anderen
    unberührt). Scheitert der Handshake dieser Bridge, wird die Barriere
    abgebrochen (``abort()``), damit die übrigen nicht auf eine nie
    erscheinende Bridge warten, sondern sofort lostarten (best effort – wie
    zuvor im gemeinsamen Loop). Ein Solo-Start (keine weitere Bridge im
    selben Aufruf) bekommt ``start_barrier=None`` und startet ohne
    Wartezeit.
    """
    n = len(ctx["channel_ids"])
    ctx["pulse"] = RedAlertPulse(num_lights=n, attack_s=ctx["attack_s"], release_s=ctx["release_s"])
    ctx["comet"] = RedAlertComet(
        num_lights=n, sweep_seconds=ctx["sweep_seconds"], pause_seconds=ctx["chase_pause"]
    )
    ctx["glitter"] = RedAlertGlitter(
        num_lights=n,
        interval_s=ctx["glitter_interval_ms"] / 1000.0,
        flash_s=ctx["glitter_flash_ms"] / 1000.0,
        palette=ctx["glitter_palette"],
    )
    # Ein RedAlertChase je Gradient-Lightstrip dieser Bridge (siehe
    # gc_strips in handle_start._resolve) – jeder mit seiner eigenen
    # Chase-Richtung, aber gemeinsamer count/length/speed.
    ctx["chase"] = [
        RedAlertChase(
            num_lights=strip["length"],
            direction=strip["direction"],
            count=ctx["gc_count"],
            length_segments=ctx["gc_length"],
            speed_segments_per_s=ctx["gc_speed"],
            fps=fps,
        )
        for strip in ctx["gc_strips"]
    ]
    ctx["police"] = RedAlertPolice(num_lights=n, period_s=ctx["sweep_seconds"])
    ctx["lightning"] = RedAlertLightning(
        interval_s=ctx["lightning_interval_ms"] / 1000.0,
        flash_s=ctx["lightning_flash_ms"] / 1000.0,
    )
    ctx["aurora"] = RedAlertAurora(
        num_lights=n, palette=ctx["glitter_palette"], period_s=ctx["sweep_seconds"] * 4.0
    )
    ctx["rainbow"] = RedAlertRainbow(num_lights=n, period_s=ctx["sweep_seconds"] * 4.0)
    ctx["meteor"] = RedAlertMeteor(num_lights=n, count=ctx["meteor_count"], speed=ctx["meteor_speed"])
    ctx["wipe"] = RedAlertWipe(
        num_lights=n, sweep_seconds=ctx["sweep_seconds"], pause_seconds=ctx["chase_pause"]
    )
    ctx["firework"] = RedAlertFirework(
        num_lights=n,
        interval_s=ctx["firework_interval_ms"] / 1000.0,
        speed=ctx["firework_speed"],
    )
    ctx["ripple"] = RedAlertRipple(
        num_lights=n,
        interval_s=ctx["ripple_interval_ms"] / 1000.0,
        speed=ctx["ripple_speed"],
    )
    ctx["wave"] = RedAlertWave(num_lights=n, period_s=ctx["sweep_seconds"], wavelength=ctx["wave_length"])
    ctx["flicker"] = RedAlertFlicker(
        num_lights=n,
        interval_s=ctx["flicker_interval_ms"] / 1000.0,
        dip_s=ctx["flicker_dip_ms"] / 1000.0,
    )
    ctx["strobe"] = RedAlertStrobe(num_lights=n, period_s=ctx["sweep_seconds"])
    ctx["duel"] = RedAlertDuel(num_lights=n, period_s=ctx["sweep_seconds"])
    # color_chase teilt sich gc_speed (dann Lampen/Schritte pro Sekunde) und
    # gc_direction mit chase; keine gc_strips (arbeitet über alle Kanäle als
    # ein Array), daher die Richtung des ersten Strips.
    ctx["color_chase"] = RedAlertColorChase(
        num_lights=n,
        speed_steps_per_s=ctx["gc_speed"],
        direction=ctx["gc_strips"][0]["direction"],
    )

    frames = 0
    snapshot: list[dict] = []
    loop = asyncio.get_event_loop()
    host = ctx["bridge_host"]
    try:
        if arm_ctx is not None:
            # Scharfe Bridge: Stream läuft schon, Snapshot liegt vor. Nur die
            # Ruhe-Loop pausieren, damit sie nicht um session.send() konkurriert.
            snapshot = arm_ctx["snapshot"]
            idle_task = arm_ctx.get("idle_task")
            if idle_task and not idle_task.done():
                idle_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await idle_task
        else:
            # Vor dem Streaming den aktuellen Lichtzustand dieser Bridge sichern –
            # parallel zum Handshake (der dominiert die Zeit, ~1,5–9 s).
            snap_task = (
                asyncio.create_task(capture_light_state(host, ctx["app_key"], ctx["area_id"]))
                if restore
                else None
            )
            try:
                await _session_start(ctx["session"], ctx["area_id"])
            except Exception as exc:  # noqa: BLE001
                log.error("Bridge %s: DTLS-Handshake fehlgeschlagen (%s)", host, exc)
                if snap_task is not None:
                    snap_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await snap_task
                if start_barrier is not None:
                    start_barrier.abort()
                return
            if snap_task is not None:
                snapshot = await snap_task

        if start_barrier is not None:
            try:
                await start_barrier.wait()
            except asyncio.BrokenBarrierError:
                log.warning(
                    "Bridge %s: eine andere Bridge im selben Start ist ausgefallen – "
                    "startet ohne weiteres Warten.", host,
                )

        start = loop.time()
        log.info(
            "Effekt läuft: bridge=%s effect=%s fps=%s duration=%s",
            host, ctx["effect"], fps, duration if duration > 0 else "unbegrenzt",
        )
        prev = start
        while True:
            now = loop.time()
            elapsed = now - start
            if duration > 0 and elapsed >= duration:
                break
            dt = now - prev
            prev = now

            glow_low, glow_high = ctx["glow_low"], ctx["glow_high"]
            glow_span = glow_high - glow_low
            effect = ctx["effect"]
            if effect == "glitter":
                # jede Lampe eigene Farbe + eigener Pegel (Diamant-Gefunkel)
                chans = [
                    (r, g, b, glow_low + glow_span * lvl)
                    for lvl, (r, g, b) in ctx["glitter"].step(dt)
                ]
            elif effect == "chase":
                chans = _chase_chans(ctx, elapsed, dt, glow_low, glow_span)
            elif effect == "police":
                # zwei Lampengruppen blinken abwechselnd in zwei Farben
                levels = ctx["police"].brightness_for(elapsed)
                ca, cb = ctx["color"], ctx["color2"]
                chans = [
                    (*(ca if is_a else cb), glow_low + glow_span * lvl)
                    for lvl, is_a in zip(levels, ctx["police"].group_a)
                ]
            elif effect == "lightning":
                # alle Lampen zusammen blitzen (Gewitter), nicht je Lampe einzeln wie glitter
                lvl = ctx["lightning"].step(dt)
                cr, cg, cb = ctx["color"]
                chans = [(cr, cg, cb, glow_low + glow_span * lvl)] * len(ctx["channel_ids"])
            elif effect == "aurora":
                # Farbe driftet mit sweep_seconds*4 (bewusst langsam), aber die
                # Helligkeits-„Atmung" wird bei 12 s gedeckelt: sonst säßen die
                # Lampen bei sehr hohem sweep_seconds minutenlang nahe glow_low,
                # wo die Bridge Farben nur grob wiedergibt und phasenversetzte
                # Lampen sichtbar unterschiedliche (falsche) Töne zeigen.
                lvl = RedAlertPulse.periodic(elapsed, min(ctx["sweep_seconds"] * 4.0, 12.0))
                chans = [
                    (r, g, b, glow_low + glow_span * lvl)
                    for r, g, b in ctx["aurora"].colors_for(elapsed)
                ]
            elif effect == "rainbow":
                # reine Farbrotation, konstant auf glow_high
                chans = [(r, g, b, glow_high) for r, g, b in ctx["rainbow"].colors_for(elapsed)]
            elif effect == "color_chase":
                # Gradient füllt sich lampenweise, 3 Paletten im Wechsel;
                # absolute Farben, konstant auf glow_high (wie rainbow)
                chans = [(r, g, b, glow_high) for r, g, b in ctx["color_chase"].colors_for(elapsed)]
            elif effect == "flicker":
                # 1.0-Ruhezustand (= normales An) mit gelegentlichen Einbrüchen
                levels = ctx["flicker"].step(dt)
                cr, cg, cb = ctx["color"]
                chans = [(cr, cg, cb, glow_low + glow_span * lvl) for lvl in levels]
            elif effect == "duel":
                # zwei Kometen aus entgegengesetzten Enden, je eigene Farbe
                levels_a, levels_b = ctx["duel"].brightness_for(elapsed)
                ca, cb = ctx["color"], ctx["color2"]
                chans = []
                for la, lb in zip(levels_a, levels_b):
                    total = la + lb
                    if total > 1e-6:
                        r = (ca[0] * la + cb[0] * lb) / total
                        g = (ca[1] * la + cb[1] * lb) / total
                        b = (ca[2] * la + cb[2] * lb) / total
                    else:
                        r = g = b = 0.0
                    chans.append((r, g, b, glow_low + glow_span * min(1.0, total)))
            else:
                # Effekte, die nur eine 0..1-Helligkeitskurve je Lampe liefern
                # und dabei die gemeinsame Bridge-Farbe verwenden.
                if effect == "comet":
                    levels = ctx["comet"].brightness_for(elapsed)
                elif effect == "meteor":
                    levels = ctx["meteor"].brightness_for(elapsed)
                elif effect == "wipe":
                    levels = ctx["wipe"].brightness_for(elapsed)
                elif effect == "firework":
                    levels = ctx["firework"].brightness_for(elapsed)
                elif effect == "ripple":
                    levels = ctx["ripple"].brightness_for(elapsed)
                elif effect == "wave":
                    levels = ctx["wave"].brightness_for(elapsed)
                elif effect == "strobe":
                    levels = ctx["strobe"].brightness_for(elapsed)
                elif effect == "heartbeat":
                    target = RedAlertPulse.heartbeat(elapsed, ctx["sweep_seconds"])
                    levels = ctx["pulse"].step(target, dt)
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
        log.exception("Effekt-Loop (%s) abgebrochen (DTLS-Start oder Senden fehlgeschlagen)", host)
    finally:
        log.info("Effekt beendet (%s, %s Frames).", host, frames)
        if arm_ctx is not None and host in state["armed"]:
            # Bridge weiterhin scharf: Stream offen lassen, ins Ruhebild
            # zurückgehen und die Ruhe-Loop wieder aufnehmen.
            live = state["armed"][host]
            with contextlib.suppress(Exception):
                live["session"].send(live["idle_frame"])
            if live.get("idle_task") is None or live["idle_task"].done():
                live["idle_task"] = asyncio.create_task(_arm_idle_loop(host))
        else:
            await ctx["session"].aclose()
            # Nach dem Ende des Streams den gesicherten Lichtzustand zurückschreiben.
            await restore_light_state(host, ctx["app_key"], snapshot)


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
        await _session_start(session, area_id)
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

    Belegt denselben Task-Slot wie ein Effekt auf dieser Bridge
    (``state["tasks"][host]``) – blockiert also nur, wenn **diese** Bridge
    gerade einen Effekt oder einen anderen Identify-Durchlauf fährt, nicht
    wenn eine andere Bridge aktiv ist.
    """
    body = await _json_body(request)
    host = body.get("bridge_host") or body.get("bridge_ip")
    if not host and len(state["bridges"]) == 1:
        host = state["bridges"][0]["bridge_host"]
    if not host:
        return web.json_response(
            {"error": "bridge_host fehlt im Body – bei mehreren Bridges Pflichtfeld"}, status=400
        )
    if _is_running(host):
        return web.json_response({"status": "already_running", "bridge_host": host})
    if host in state["armed"]:
        # Die scharfe Bridge hält bereits den einzigen Entertainment-Slot.
        return web.json_response(
            {"status": "armed", "bridge_host": host,
             "error": "Bridge ist scharfgeschaltet – zuerst /disarm"},
            status=409,
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

    state["tasks"][host] = asyncio.create_task(
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
    Bridges gleichzeitig starten, oder – mit ``bridge_host`` im Body – auf nur
    einer einzelnen Bridge, unabhängig vom Zustand der anderen (siehe unten).

    Body optional: ``duration``, ``fps``, ``restore_state`` gelten für **alle**
    Bridges gemeinsam. ``effect``, ``color``, ``sweep_seconds``, ``chase_pause``,
    ``attack_ms``, ``release_ms``, ``glow_low``, ``glow_high``,
    ``glitter_interval_ms``, ``glitter_flash_ms``, ``glitter_colors``,
    ``gc_direction``, ``gc_count``, ``gc_length``, ``gc_speed``,
    ``gc_background_color``, ``gc_chase_glitter``, ``gc_background_pulse``,
    ``color2``, ``meteor_count``, ``meteor_speed``,
    ``firework_interval_ms``, ``firework_speed``, ``lightning_interval_ms``,
    ``lightning_flash_ms``, ``ripple_interval_ms``, ``ripple_speed``,
    ``wave_length``, ``flicker_interval_ms``, ``flicker_dip_ms`` im
    Body sind die **Standardwerte** für Bridges, die diese Parameter nicht
    selbst setzen. ``bridges`` (Liste von ``{bridge_host, area_id,
    channel_order, effect?, color?, sweep_seconds?, chase_pause?, attack_ms?,
    release_ms?, glow_low?, glow_high?, glitter_interval_ms?,
    glitter_flash_ms?, glitter_colors?, gc_direction?, gc_strip_lengths?,
    gc_count?, gc_length?, gc_speed?, gc_background_color?, gc_chase_glitter?,
    gc_background_pulse?, color2?, meteor_count?, meteor_speed?,
    firework_interval_ms?, firework_speed?, lightning_interval_ms?,
    lightning_flash_ms?, ripple_interval_ms?, ripple_speed?, wave_length?,
    flicker_interval_ms?, flicker_dip_ms?}``) übersteuert für diesen Aufruf die Option
    ``bridges`` – jede Bridge kann ihren eigenen Effekt/Farbe/Timing haben.
    ``gc_strip_lengths`` (nur ``effect: chase``, je Bridge, z. B.
    ``[7, 5]``) teilt die Kanäle dieser Bridge in aufeinanderfolgende Gradient-
    Lightstrips auf; ``gc_direction`` kann dann ebenfalls eine Liste sein
    (eine Chase-Richtung je Strip statt eines Werts für alle). ``effect:
    neutral`` (als Standard oder je Bridge) lässt die betreffende(n) Bridge(s)
    komplett unangetastet – kein Stream, kein Sichern/Wiederherstellen –, sodass
    in einem Effektset eine Bridge laufen und eine andere aus sein kann. Sind
    **alle** Bridges neutral, antwortet ``/start`` mit ``no_active_bridges``.

    ``preset``: Name eines gespeicherten Effektsets (siehe ``/presets``); dessen
    gespeicherter Body dient als Basis, alle weiteren Body-Felder überschreiben
    ihn für diesen Aufruf. Nicht mit ``bridge_host`` kombinierbar (400) – ein
    Effektset ist ein Mehr-Bridge-Konzept.

    ``bridge_host``: startet nur diese eine Bridge, unabhängig vom Zustand
    anderer Bridges – wirkt als Filter auf die oben aufgelöste ``bridges``-
    Liste (Option oder Body), keine eigene Auswahl. `already_running` gilt
    dann nur für diese eine Bridge. Ein Solo-Start setzt nie
    ``current_preset`` (siehe ``/health``/``/config``). Ohne ``bridge_host``
    (Standard, alle konfigurierten/übergebenen Bridges) werden bereits
    laufende Bridges übersprungen statt den ganzen Aufruf abzulehnen – die
    Antwort listet sie unter ``skipped_bridges``; nur wenn **keine** Bridge
    (weder neu noch bereits laufend) übrig bleibt und keine fehlgeschlagen
    ist, antwortet ``/start`` mit ``no_active_bridges``.
    """
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

    bridge_host = body.get("bridge_host")
    if bridge_host and preset_name:
        return web.json_response(
            {
                "error": "bridge_host und preset zusammen werden nicht unterstützt – "
                         "preset gilt nur für alle Bridges gemeinsam"
            },
            status=400,
        )
    if bridge_host and _is_running(bridge_host):
        return web.json_response({"status": "already_running", "bridge_host": bridge_host})

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
    if bridge_host:
        req_bridges = [c for c in req_bridges if c["bridge_host"] == bridge_host]
        if not req_bridges:
            return web.json_response(
                {"error": f"bridge_host {bridge_host} nicht in bridges (Option oder Body) konfiguriert"},
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
    # Nur effect chase (Gradient Lightstrips).
    defaults["gc_direction"] = _parse_gc_directions(body.get("gc_direction")) or state["gc_direction"]
    try:
        defaults["gc_count"] = max(1, int(body.get("gc_count") or state["gc_count"]))
    except (TypeError, ValueError):
        defaults["gc_count"] = state["gc_count"]
    try:
        defaults["gc_length"] = min(max(float(body.get("gc_length") or state["gc_length"]), 0.2), 200.0)
    except (TypeError, ValueError):
        defaults["gc_length"] = state["gc_length"]
    try:
        defaults["gc_speed"] = max(0.01, float(body.get("gc_speed") or state["gc_speed"]))
    except (TypeError, ValueError):
        defaults["gc_speed"] = state["gc_speed"]
    defaults["gc_background_color"] = (
        hex_to_rgb(body["gc_background_color"])
        if body.get("gc_background_color")
        else state["gc_background_color"]
    )
    defaults["gc_chase_glitter"] = bool(body.get("gc_chase_glitter", state["gc_chase_glitter"]))
    defaults["gc_background_pulse"] = bool(body.get("gc_background_pulse", state["gc_background_pulse"]))
    # Zweite Farbe: effect police (zweite Lampengruppe) und effect duel
    # (zweiter Komet).
    defaults["color2"] = (
        hex_to_rgb(body["color2"]) if body.get("color2") else state["color2"]
    )
    # Nur effect meteor.
    try:
        defaults["meteor_count"] = max(1, int(body.get("meteor_count") or state["meteor_count"]))
    except (TypeError, ValueError):
        defaults["meteor_count"] = state["meteor_count"]
    try:
        defaults["meteor_speed"] = max(0.05, float(body.get("meteor_speed") or state["meteor_speed"]))
    except (TypeError, ValueError):
        defaults["meteor_speed"] = state["meteor_speed"]
    # Nur effect firework.
    try:
        defaults["firework_interval_ms"] = max(
            1.0, float(body.get("firework_interval_ms") or state["firework_interval_ms"])
        )
    except (TypeError, ValueError):
        defaults["firework_interval_ms"] = state["firework_interval_ms"]
    try:
        defaults["firework_speed"] = max(0.5, float(body.get("firework_speed") or state["firework_speed"]))
    except (TypeError, ValueError):
        defaults["firework_speed"] = state["firework_speed"]
    # Nur effect lightning.
    try:
        defaults["lightning_interval_ms"] = max(
            1.0, float(body.get("lightning_interval_ms") or state["lightning_interval_ms"])
        )
    except (TypeError, ValueError):
        defaults["lightning_interval_ms"] = state["lightning_interval_ms"]
    try:
        defaults["lightning_flash_ms"] = max(
            1.0, float(body.get("lightning_flash_ms") or state["lightning_flash_ms"])
        )
    except (TypeError, ValueError):
        defaults["lightning_flash_ms"] = state["lightning_flash_ms"]
    # Nur effect ripple.
    try:
        defaults["ripple_interval_ms"] = max(
            1.0, float(body.get("ripple_interval_ms") or state["ripple_interval_ms"])
        )
    except (TypeError, ValueError):
        defaults["ripple_interval_ms"] = state["ripple_interval_ms"]
    try:
        defaults["ripple_speed"] = max(0.5, float(body.get("ripple_speed") or state["ripple_speed"]))
    except (TypeError, ValueError):
        defaults["ripple_speed"] = state["ripple_speed"]
    # Nur effect wave.
    try:
        defaults["wave_length"] = max(0.5, float(body.get("wave_length") or state["wave_length"]))
    except (TypeError, ValueError):
        defaults["wave_length"] = state["wave_length"]
    # Nur effect flicker.
    try:
        defaults["flicker_interval_ms"] = max(
            1.0, float(body.get("flicker_interval_ms") or state["flicker_interval_ms"])
        )
    except (TypeError, ValueError):
        defaults["flicker_interval_ms"] = state["flicker_interval_ms"]
    try:
        defaults["flicker_dip_ms"] = max(
            1.0, float(body.get("flicker_dip_ms") or state["flicker_dip_ms"])
        )
    except (TypeError, ValueError):
        defaults["flicker_dip_ms"] = state["flicker_dip_ms"]

    async def _resolve(cfg: dict) -> dict:
        """Eine Bridge auflösen: gepaart? erreichbar? area_id/Kanäle gültig?

        Effekt-Parameter, die dieser Bridge-Eintrag nicht selbst setzt, fallen
        auf ``defaults`` zurück (Body bzw. App-Option).
        """
        host = cfg["bridge_host"]
        creds = state["credentials"].get(host)
        if not creds:
            return {"bridge_host": host, "error": "nicht gepaart"}
        armed = state["armed"].get(host)
        # Scharfe Bridge: die vorhandene, dauerhaft offene Sitzung
        # wiederverwenden (Handshake + Snapshot entfallen später komplett) und
        # bei Fehlern *nicht* schließen – sie gehört der Scharfschaltung.
        session = armed["session"] if armed else EntertainmentSession(
            host, creds["username"], creds["clientkey"]
        )

        async def _bail(err: str) -> dict:
            if not armed:
                await session.aclose()
            return {"bridge_host": host, "error": err}

        try:
            areas = await session.get_entertainment_areas()
        except Exception as exc:  # noqa: BLE001
            return await _bail(f"Bridge nicht erreichbar ({exc})")
        area = next((a for a in areas if a.id == cfg["area_id"]), None)
        if area is None:
            return await _bail(f"area_id {cfg['area_id']} nicht gefunden")
        native_ids = [ch.channel_id for ch in area.channels]
        order = cfg.get("channel_order")
        if order:
            if sorted(order) != sorted(native_ids):
                return await _bail(
                    f"channel_order {order} passt nicht zum Bereich – "
                    f"genau die Kanäle {sorted(native_ids)} in gewünschter "
                    f"Reihenfolge angeben"
                )
            channel_ids = list(order)
        else:
            channel_ids = native_ids

        glow_low = min(max(cfg.get("glow_low", defaults["glow_low"]), 0.0), 1.0)
        glow_high = min(max(cfg.get("glow_high", defaults["glow_high"]), 0.0), 1.0)
        glow_high = max(glow_high, glow_low)
        color = cfg.get("color", defaults["color"])
        palette = cfg.get("glitter_colors", defaults["glitter_palette"]) or [color]

        # chase: Kanäle dieser Bridge in aufeinanderfolgende Gradient-
        # Lightstrips aufteilen (gc_strip_lengths), jeder mit eigener
        # Chase-Richtung (gc_direction darf eine Liste sein, eine je Strip).
        # Passt die Summe nicht zur tatsächlichen Kanalzahl, gilt best-effort
        # ein einzelner Strip über alle Kanäle dieser Bridge.
        gc_strip_lengths = cfg.get("gc_strip_lengths")
        if gc_strip_lengths and sum(gc_strip_lengths) == len(channel_ids):
            strip_lengths = list(gc_strip_lengths)
        else:
            if gc_strip_lengths:
                log.warning(
                    "Bridge %s: gc_strip_lengths %s ergibt nicht %d Kanäle – "
                    "ein einzelner Strip wird verwendet",
                    host, gc_strip_lengths, len(channel_ids),
                )
            strip_lengths = [len(channel_ids)]
        gc_direction_cfg = cfg.get("gc_direction", defaults["gc_direction"])
        directions = list(gc_direction_cfg) if isinstance(gc_direction_cfg, list) else [gc_direction_cfg]
        if len(directions) < len(strip_lengths):
            directions += [directions[-1]] * (len(strip_lengths) - len(directions))
        elif len(directions) > len(strip_lengths):
            directions = directions[: len(strip_lengths)]
        gc_strips = [
            {"length": length, "direction": direction}
            for length, direction in zip(strip_lengths, directions)
        ]

        return {
            "bridge_host": host,
            "area_id": cfg["area_id"],
            "channel_ids": channel_ids,
            "session": session,
            "armed": bool(armed),
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
            "gc_strips": gc_strips,
            "gc_count": max(1, cfg.get("gc_count", defaults["gc_count"])),
            "gc_length": min(max(cfg.get("gc_length", defaults["gc_length"]), 0.2), 200.0),
            "gc_speed": max(0.01, cfg.get("gc_speed", defaults["gc_speed"])),
            "gc_background_color": cfg.get("gc_background_color", defaults["gc_background_color"]),
            "gc_chase_glitter": cfg.get("gc_chase_glitter", defaults["gc_chase_glitter"]),
            "gc_background_pulse": cfg.get("gc_background_pulse", defaults["gc_background_pulse"]),
            "color2": cfg.get("color2", defaults["color2"]),
            "meteor_count": max(1, cfg.get("meteor_count", defaults["meteor_count"])),
            "meteor_speed": max(0.05, cfg.get("meteor_speed", defaults["meteor_speed"])),
            "firework_interval_ms": max(
                1.0, cfg.get("firework_interval_ms", defaults["firework_interval_ms"])
            ),
            "firework_speed": max(0.5, cfg.get("firework_speed", defaults["firework_speed"])),
            "lightning_interval_ms": max(
                1.0, cfg.get("lightning_interval_ms", defaults["lightning_interval_ms"])
            ),
            "lightning_flash_ms": max(
                1.0, cfg.get("lightning_flash_ms", defaults["lightning_flash_ms"])
            ),
            "ripple_interval_ms": max(
                1.0, cfg.get("ripple_interval_ms", defaults["ripple_interval_ms"])
            ),
            "ripple_speed": max(0.5, cfg.get("ripple_speed", defaults["ripple_speed"])),
            "wave_length": max(0.5, cfg.get("wave_length", defaults["wave_length"])),
            "flicker_interval_ms": max(
                1.0, cfg.get("flicker_interval_ms", defaults["flicker_interval_ms"])
            ),
            "flicker_dip_ms": max(
                1.0, cfg.get("flicker_dip_ms", defaults["flicker_dip_ms"])
            ),
        }

    # "neutral": diese Bridge wird gar nicht angefasst (kein DTLS, kein
    # Sichern/Wiederherstellen) – so lässt sich in einem Effektset eine Bridge
    # bewusst auslassen, während die anderen einen Effekt fahren.
    neutral = [c for c in req_bridges if c.get("effect", defaults["effect"]) == "neutral"]
    non_neutral = [c for c in req_bridges if c.get("effect", defaults["effect"]) != "neutral"]
    neutral_report = [{"bridge_host": c["bridge_host"], "effect": "neutral"} for c in neutral]
    for c in neutral:
        log.info("Start: Bridge %s neutral – wird nicht gesteuert.", c["bridge_host"])

    # Bereits laufende Bridges überspringen statt den ganzen Aufruf
    # abzulehnen – bei einem gezielten Solo-Start (bridge_host im Body) ist
    # das oben bereits per already_running abgelehnt worden, hier also nur
    # für einen Aufruf ohne bridge_host relevant, wenn einzelne Bridges
    # bereits unabhängig laufen.
    already = [c for c in non_neutral if _is_running(c["bridge_host"])]
    to_run = [c for c in non_neutral if not _is_running(c["bridge_host"])]
    skipped_report = [{"bridge_host": c["bridge_host"], "status": "already_running"} for c in already]
    for c in already:
        log.info("Start: Bridge %s läuft bereits – übersprungen.", c["bridge_host"])

    # area_id/Kanäle für alle zu fahrenden Bridges parallel auflösen (kein DTLS).
    resolved = await asyncio.gather(*(_resolve(cfg) for cfg in to_run))
    ctxs = [r for r in resolved if "session" in r]
    failed = [r for r in resolved if "session" not in r]
    for r in failed:
        log.warning("Start: Bridge %s übersprungen (%s)", r["bridge_host"], r["error"])

    if not ctxs:
        if not failed:
            # Nichts Neues zu starten (nur neutral und/oder bereits aktiv),
            # aber auch kein echter Fehler – für die HA-Integration
            # (Select/Sensor "geladenes Effektset") gilt ein reiner Batch-
            # Aufruf trotzdem als "geladen"; ein Solo-Start lässt
            # current_preset unangetastet (siehe Docstring oben).
            if bridge_host is None:
                state["current_preset"] = str(preset_name) if preset_name else None
            log.info(
                "Start: keine neue Bridge zu starten (neutral: %s, bereits aktiv: %s).",
                [c["bridge_host"] for c in neutral], [c["bridge_host"] for c in already],
            )
            return web.json_response({
                "status": "no_active_bridges",
                "duration": duration, "fps": fps, "restore_state": restore,
                "bridges": [], "failed_bridges": [],
                "neutral_bridges": neutral_report, "skipped_bridges": skipped_report,
            })
        return web.json_response(
            {
                "error": "keine Bridge verfügbar",
                "bridges": failed,
                "neutral_bridges": neutral_report,
                "skipped_bridges": skipped_report,
            },
            status=502,
        )

    # Für die HA-Integration (Select-Entity "geladenes Effektset"): erst hier
    # setzen, nicht schon bei jedem preset-Versuch – ein 400/404/502 vorher
    # soll "geladenes Effektset" nicht auf einen nie gestarteten Namen setzen.
    # Ad-hoc-Start ohne preset räumt die Anzeige wieder auf None. Ein Solo-
    # Start (bridge_host im Body) lässt current_preset unangetastet.
    if bridge_host is None:
        state["current_preset"] = str(preset_name) if preset_name else None

    # session.start() (DTLS-Handshake, ~einige Sekunden) passiert je Bridge in
    # einem eigenen Task, damit die HTTP-Antwort nicht blockiert (HA
    # rest_command-Timeout). Mehrere Bridges in diesem einen Aufruf teilen
    # sich eine Barriere, damit sie trotzdem gleichzeitig loslegen, bleiben
    # aber einzeln über state["tasks"] unabhängig kündbar.
    barrier = asyncio.Barrier(len(ctxs)) if len(ctxs) > 1 else None
    for c in ctxs:
        arm_ctx = state["armed"].get(c["bridge_host"]) if c.get("armed") else None
        state["tasks"][c["bridge_host"]] = asyncio.create_task(
            _run_single_bridge(c, duration, fps, restore, barrier, arm_ctx)
        )
    state["last_start_meta"] = {"duration": duration, "fps": fps, "restore_state": restore}
    started_report = []
    for c in ctxs:
        entry = {
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
            "gc_strips": c["gc_strips"],
            "gc_count": c["gc_count"],
            "gc_length": c["gc_length"],
            "gc_speed": c["gc_speed"],
            "gc_background_color": "#{:02X}{:02X}{:02X}".format(*c["gc_background_color"]),
            "gc_chase_glitter": c["gc_chase_glitter"],
            "gc_background_pulse": c["gc_background_pulse"],
            "color2": "#{:02X}{:02X}{:02X}".format(*c["color2"]),
            "meteor_count": c["meteor_count"],
            "meteor_speed": c["meteor_speed"],
            "firework_interval_ms": round(c["firework_interval_ms"]),
            "firework_speed": c["firework_speed"],
            "lightning_interval_ms": round(c["lightning_interval_ms"]),
            "lightning_flash_ms": round(c["lightning_flash_ms"]),
            "ripple_interval_ms": round(c["ripple_interval_ms"]),
            "ripple_speed": c["ripple_speed"],
            "wave_length": c["wave_length"],
            "flicker_interval_ms": round(c["flicker_interval_ms"]),
            "flicker_dip_ms": round(c["flicker_dip_ms"]),
        }
        state["last_start"][c["bridge_host"]] = entry
        started_report.append(entry)
    result = {
        "duration": duration,
        "fps": fps,
        "restore_state": restore,
        "neutral_bridges": neutral_report,
        "skipped_bridges": skipped_report,
        "bridges": started_report,
        "failed_bridges": failed,
    }
    log.info("Start angefordert: %s", result)
    return web.json_response({"status": "started", **result})


async def handle_stop(request: web.Request) -> web.Response:
    """POST /stop – Effekt(e) stoppen.

    Body optional: ``bridge_host`` – stoppt nur diese eine Bridge, unabhängig
    vom Zustand anderer Bridges. Ohne ``bridge_host``: stoppt alle gerade
    laufenden Bridges (bisheriges Verhalten).
    """
    body = await _json_body(request)
    bridge_host = body.get("bridge_host")

    if bridge_host:
        task = state["tasks"].get(bridge_host)
        if not task or task.done():
            return web.json_response({"status": "not_running", "bridge_host": bridge_host})
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        log.info("Effekt auf Bridge %s per /stop beendet.", bridge_host)
        return web.json_response({"status": "stopped", "bridge_hosts": [bridge_host]})

    running = {host: t for host, t in state["tasks"].items() if not t.done()}
    if not running:
        return web.json_response({"status": "not_running"})
    for t in running.values():
        t.cancel()
    await asyncio.gather(*running.values(), return_exceptions=True)
    log.info("Effekt auf allen Bridges per /stop beendet: %s", sorted(running))
    return web.json_response({"status": "stopped", "bridge_hosts": sorted(running)})


def _arm_targets(bridge_host: str | None) -> tuple[list[dict], web.Response | None]:
    """Zu (ent)schärfende Bridge-Konfigurationen ermitteln. Ohne ``bridge_host``
    alle konfigurierten, nicht-``neutral`` Bridges; sonst genau die eine."""
    cfgs = [b for b in state["bridges"] if b.get("effect") != "neutral"]
    if bridge_host:
        cfgs = [b for b in cfgs if b["bridge_host"] == bridge_host]
        if not cfgs:
            return [], web.json_response(
                {"error": f"bridge_host {bridge_host} nicht in bridges konfiguriert "
                          f"(oder als neutral markiert)"},
                status=400,
            )
    if not cfgs:
        return [], web.json_response(
            {"error": "keine (nicht-neutrale) Bridge konfiguriert"}, status=400
        )
    return cfgs, None


async def handle_arm(request: web.Request) -> web.Response:
    """POST /arm – DTLS-Stream einer/aller Bridge(s) dauerhaft offen halten
    („scharfschalten"), damit ein späteres /start den ~3–9 s Handshake
    überspringt. Body optional ``bridge_host`` (sonst alle konfigurierten,
    nicht-neutralen Bridges). Bereits laufende Bridges können nicht scharf-
    geschaltet werden (erst /stop)."""
    body = await _json_body(request)
    cfgs, err = _arm_targets(body.get("bridge_host"))
    if err is not None:
        return err

    armed_report, already, busy, failed = [], [], [], []
    to_arm = []
    for cfg in cfgs:
        host = cfg["bridge_host"]
        if host in state["armed"]:
            already.append(host)
        elif _is_running(host):
            busy.append(host)
        else:
            to_arm.append(cfg)

    results = await asyncio.gather(*(_arm_one(cfg) for cfg in to_arm))
    for r in results:
        if r.get("armed"):
            armed_report.append(r["bridge_host"])
        else:
            failed.append(r)
            log.warning("Scharfschalten %s fehlgeschlagen: %s", r["bridge_host"], r.get("error"))

    status = "armed" if armed_report else ("no_change" if not failed else "error")
    code = 502 if (failed and not armed_report and not already) else 200
    return web.json_response(
        {
            "status": status,
            "armed": armed_report,
            "already_armed": already,
            "busy": busy,
            "failed": failed,
        },
        status=code,
    )


async def handle_disarm(request: web.Request) -> web.Response:
    """POST /disarm – Stream schließen und den beim Scharfschalten gesicherten
    Lichtzustand per CLIP v2 wiederherstellen. Body optional ``bridge_host``.
    Ein gerade laufender Effekt auf der Bridge wird zuvor gestoppt."""
    body = await _json_body(request)
    bridge_host = body.get("bridge_host")
    hosts = [bridge_host] if bridge_host else list(state["armed"])
    if not hosts:
        return web.json_response({"status": "not_armed"})

    disarmed = []
    for host in hosts:
        if host not in state["armed"]:
            continue
        # Erst als „nicht mehr scharf" markieren, dann einen evtl. laufenden
        # Effekt stoppen – dessen finally sieht dadurch „entschärft" und
        # schließt den Stream selbst + stellt den Lichtzustand wieder her.
        if _is_running(host):
            # Aus state["armed"] entfernen, dann den Effekt-Task abbrechen:
            # dessen finally sieht „nicht mehr scharf" und übernimmt aclose() +
            # restore_light_state selbst.
            ctx = state["armed"].pop(host, None)
            if ctx and ctx.get("idle_task") and not ctx["idle_task"].done():
                ctx["idle_task"].cancel()
            task = state["tasks"].get(host)
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            log.info("Bridge %s entschärft (lief noch – Effekt gestoppt).", host)
            disarmed.append(host)
        elif await _disarm_one(host):
            disarmed.append(host)

    return web.json_response(
        {"status": "disarmed" if disarmed else "not_armed", "bridge_hosts": sorted(disarmed)}
    )


async def handle_select(request: web.Request) -> web.Response:
    """POST /select – ein Effektset als *geladen* merken, **ohne** es zu starten.

    Setzt nur ``state["current_preset"]`` (für die HA-Integration: Select-Entity
    „Effektset" + Sensor „geladenes Effektset"). Body ``{"preset": "<name>"}``
    (404, wenn unbekannt) oder ``{"preset": null}`` bzw. leer zum Zurücksetzen.
    Ein späteres ``POST /start`` (ohne eigenes ``preset``) fährt weiterhin die
    App-Standardwerte – das Laden hier ändert nur die Anzeige; die Integration
    ruft bei bereits laufender Animation zusätzlich ``/stop`` + ``/start
    {preset}`` auf, um sofort umzuschalten.
    """
    body = await _json_body(request)
    name = body.get("preset")
    if name in (None, ""):
        state["current_preset"] = None
        log.info("Effektset-Auswahl zurückgesetzt.")
        return web.json_response({"status": "cleared", "current_preset": None})
    name = str(name)
    if name not in state["presets"]:
        return web.json_response({"error": f"Effektset '{name}' nicht gefunden"}, status=404)
    state["current_preset"] = name
    log.info("Effektset '%s' geladen (nicht gestartet).", name)
    return web.json_response({"status": "selected", "current_preset": name})


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


async def _on_shutdown(app: web.Application) -> None:
    """Beim Herunterfahren (SIGTERM durch HA) laufende Effekte stoppen und alle
    scharfen Bridges entschärfen – sonst blieben Streams offen und der
    Lichtzustand nicht wiederhergestellt."""
    running = [t for t in state["tasks"].values() if not t.done()]
    for t in running:
        t.cancel()
    if running:
        await asyncio.gather(*running, return_exceptions=True)
    for host in list(state["armed"]):
        with contextlib.suppress(Exception):
            await _disarm_one(host)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_panel)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/config", handle_config)
    app.router.add_post("/pair", handle_pair)
    app.router.add_get("/areas", handle_areas)
    app.router.add_post("/start", handle_start)
    app.router.add_post("/stop", handle_stop)
    app.router.add_post("/arm", handle_arm)
    app.router.add_post("/disarm", handle_disarm)
    app.router.add_post("/select", handle_select)
    app.router.add_post("/identify", handle_identify)
    app.router.add_get("/presets", handle_presets_get)
    app.router.add_put("/presets", handle_presets_put)
    app.router.add_post("/presets", handle_presets_put)
    app.router.add_delete("/presets", handle_presets_delete)
    app.on_shutdown.append(_on_shutdown)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8099, access_log=None)
