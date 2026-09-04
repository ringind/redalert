# Red Alert Entertainment Add-on

[![Build](https://github.com/ringind/redalert/actions/workflows/build.yaml/badge.svg)](https://github.com/ringind/redalert/actions/workflows/build.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home-Assistant-Add-on für eine Star-Trek-„Alarmstufe Rot“-Szene über mehrere
Philips-Hue-Lampen, gesteuert über das echte **Hue Entertainment API**
(DTLS-Streaming, nicht die normale Bridge-Szene). Unterstützt **bis zu 3 Hue
Bridges**, die gleichzeitig loslegen – jede mit ihrem eigenen Effekt, ihrer
eigenen Farbe und eigenem Timing. Zwei Effekte: `pulse` – alle Lampen einer
Bridge blenden gemeinsam auf und ab (Standard) – und `chase` – ein umlaufender
Komet, der einen Schweif hinter sich herzieht. Läuft für eine konfigurierbare
Dauer (Standard 30 s, gilt für alle Bridges gemeinsam).

Nutzt die Bibliothek [`hue-entertainment`](https://github.com/music-assistant/hue-entertainment)
(dieselbe, die auch das Hue-Entertainment-Plugin von Music Assistant antreibt).

> **Dieses Repository ist ein Home-Assistant-Add-on-Store-Repository.**
> Installation: **Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories**,
> die URL dieses Repos eintragen, dann **Red Alert Entertainment** installieren.
> Das eigentliche Add-on liegt im Unterordner [`redalert/`](redalert/); die in
> Home Assistant angezeigte Anleitung ist [`redalert/DOCS.md`](redalert/DOCS.md).
> Ein Web-UI zur Steuerung (Pairing, Bereiche, Start/Stop) erscheint nach der
> Installation als Seitenleisten-Eintrag **Red Alert** (Ingress).

Getestet mit Hue Bridge V2 (BSB002, API 1.78): Pairing, Bereichsabruf,
DTLS-Streaming und Start/Stop laufen end-to-end.

---

## Inhalt

1. [Überblick & Architektur](#überblick--architektur)
2. [Voraussetzungen](#voraussetzungen)
3. [Schnellstart](#schnellstart)
4. [Entertainment-Bereich in der Hue-App anlegen](#1-entertainment-bereich-in-der-hue-app-anlegen)
5. [Add-on installieren](#2-add-on-installieren)
6. [Einmalig mit der Bridge pairen](#3-einmalig-mit-der-bridge-pairen)
7. [Area-ID und Kanalreihenfolge ermitteln](#4-area-id-und-kanalreihenfolge-ermitteln)
8. [Add-on-Optionen](#5-add-on-optionen)
9. [REST-API](#6-rest-api)
10. [Home Assistant einbinden](#7-home-assistant-einbinden)
11. [Effekt anpassen](#8-effekt-anpassen)
12. [Fehlerbehebung](#9-fehlerbehebung)
13. [Rechtlicher Hinweis zur Audiodatei](#10-rechtlicher-hinweis-zur-audiodatei)
14. [Projektstruktur](#projektstruktur)

---

## Überblick & Architektur

Home Assistants normale Hue-Szenen laufen über die REST/CLIP-API der Bridge und
sind für ein sauberes, frame-genaues Lauflicht zu träge. Für ein echtes,
niedriglatentes Lauflicht braucht es einen dauerhaften **DTLS-Stream** zur
Bridge (dasselbe Protokoll, das Hue Sync/Gaming-Sync nutzt). Das leistet
Home Assistant nicht nativ, deshalb übernimmt das ein kleiner eigenständiger
Dienst – dieses Add-on:

```
HA-Automation ──┬──> media_player.play_media (dein Sound, z. B. Sonos)
                └──> rest_command → Add-on /start
                                        │
                                        ▼
                         Add-on (Python, aiohttp)
                         hält je Bridge (bis zu 3) einen
                         eigenen DTLS-Stream offen (~25 Hz),
                         jede mit eigenem Effekt/Farbe/Timing
                         (pulse: alle Lampen im Takt;
                          chase: umlaufender Komet mit Schweif)
                                        │
                              ┌─────────┼─────────┐
                              ▼         ▼         ▼
                          Bridge 1   Bridge 2   Bridge 3
                              │         │         │
                              ▼         ▼         ▼
                          Hue-Lampen  Hue-Lampen  Hue-Lampen
```

Das Add-on läuft dauerhaft im Hintergrund und stellt eine kleine REST-API
bereit (`/pair`, `/areas`, `/start`, `/stop`), die du aus Home-Assistant-
Automationen ansprichst.

## Voraussetzungen

- Home Assistant **OS oder Supervised** (Add-on-Store nötig; bei Core/Container
  müsste der Dienst stattdessen separat als Container/Systemd-Service laufen).
- Eine bis drei Hue Bridge **V2** („quadratisch“) oder Hue Pro Bridge –
  V1-Bridges unterstützen kein Entertainment-Streaming.
- Pro Bridge: Hue-Lampen (Farbe/Farbtemperatur-fähig), einem Entertainment-Bereich
  zugeordnet.
- Ein `media_player`-Entity in Home Assistant (Sonos/Chromecast/Speaker o. ä.)
  für die Sound-Wiedergabe.
- Eine eigene, legal erworbene Audiodatei mit dem Alarm-Sound (siehe
  [Rechtlicher Hinweis](#10-rechtlicher-hinweis-zur-audiodatei)).
- Zugriff auf den HA-Host per Samba- oder SSH-Add-on, um den Add-on-Ordner
  nach `/addons/` zu kopieren.

## Schnellstart

1. Entertainment-Bereich(e) in der Hue-App anlegen (einer pro Bridge).
2. Dieses Repo im Add-on Store als Repository hinzufügen, **Red Alert
   Entertainment** installieren und starten.
3. Pro Bridge: Link-Button drücken, dann im Web-UI **Pairen** klicken
   (oder `POST /pair` aufrufen).
4. Pro Bridge: `GET /areas?bridge_host=...` aufrufen, Ergebnis als Zeile in
   die Add-on-Option `bridges` eintragen.
5. `rest_command` + Automation in Home Assistant anlegen (Vorlage weiter unten).
6. Fertig – Trigger auslösen, alle konfigurierten Bridges spielen gleichzeitig.

---

## 1. Entertainment-Bereich in der Hue-App anlegen

1. Hue-App → Einstellungen → Entertainment-Bereiche → Neuer Bereich.
2. Alle 6 Lampen hinzufügen und im 3D-Raster grob so platzieren, wie sie
   physisch angeordnet sind (nur für die Hue-App-Vorschau relevant, nicht für
   dieses Add-on).
3. Bereich speichern. Die Reihenfolge, in der du die Lampen hinzufügst,
   bestimmt die `channel_id`-Reihenfolge, die später für den Lauflicht-Effekt
   genutzt wird.

## 2. Add-on installieren

**Einstellungen → Add-ons → Add-on Store → oben rechts „⋮“ → Repositories**,
dann die URL dieses GitHub-Repositories eintragen und hinzufügen. Das Add-on
erscheint anschließend im Store als **Red Alert Entertainment** – installieren
und starten. Empfohlen: „Start beim Booten“ aktivieren.

(Alternativ als lokales Add-on: den Unterordner `redalert/` nach
`/addons/redalert` auf den HA-Host kopieren und Repositories neu laden.)

## 3. Einmalig mit jeder Bridge pairen

Physischen Link-Button auf der Hue Bridge drücken, dann **innerhalb von
~30 Sekunden** pairen – entweder im Web-UI (Seitenleiste **Red Alert** →
Bridge-Karte unter „1 · Bridges“) oder per REST, für jede Bridge einzeln:

```bash
curl -X POST http://<home-assistant-ip>:8099/pair \
  -H "Content-Type: application/json" \
  -d '{"bridge_host": "192.168.1.50"}'
```

Antwort enthält `username` und `clientkey` – werden automatisch (pro Bridge)
im Add-on-Datenordner gespeichert (`/data/credentials.json`), du musst dir
nichts merken. Pairing muss pro Bridge nur einmal gemacht werden, außer du
setzt das Add-on komplett zurück.

## 4. Area-ID und Kanalreihenfolge ermitteln

```bash
curl "http://<home-assistant-ip>:8099/areas?bridge_host=192.168.1.50"
```

Liefert z. B.:

```json
[{"id": "abcd-1234", "name": "Red Alert", "channels": [0, 1, 2, 3, 4, 5]}]
```

Trage `bridge_host` + die `id` als Zeile der Add-on-Option `bridges` ein
(Konfiguration-Tab des Add-ons; eine Zeile pro Bridge). Falls die
`channels`-Reihenfolge nicht deiner physischen Anordnung entspricht, kannst
du die gewünschte Reihenfolge in derselben Zeile explizit als
`channel_order` setzen – als kommagetrennte Liste (z. B. `2,3,1,0,5,4`),
entweder als Add-on-Option oder direkt im Web-UI in der jeweiligen
Bridge-Karte. Welche `channel_id` welche Lampe ist, findest du in der
Bridge-Karte unter „Lampen zuordnen“ (leuchtet die Kanäle einzeln auf).
Add-on nach einer Options-Änderung neu starten.

## 5. Add-on-Optionen

| Option           | Typ           | Standard | Bedeutung                                                       |
|-------------------|--------------|----------|-------------------------------------------------------------------|
| `bridges`         | Liste (max. 3) | leer   | Eine Zeile pro Bridge: `bridge_host` (IP), `area_id` (siehe Schritt 4), optional `channel_order` sowie je Bridge optional `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high` (überschreiben die gleichnamige Option unten nur für diese Bridge). |
| `effect`          | `pulse`\|`chase` | `pulse` | Standard für Bridges ohne eigene Einstellung. `pulse` = alle Lampen zusammen `glow_low` → `glow_high` → `glow_low` im Takt. `chase` = umlaufender Komet mit Schweif. |
| `color`           | Hex-String    | `#FF0000`| Standard-Farbe für Bridges ohne eigene Einstellung.                |
| `fps`             | int (5–50)    | 25       | Frames/Sekunde des DTLS-Streams (für alle Bridges gleich).         |
| `sweep_seconds`   | float (0.3–5) | 1.4      | Standard für Bridges ohne eigene Einstellung. `chase`: Dauer einer vollen Umrundung. `pulse`: Zyklusdauer. |
| `chase_pause`     | float (0–60)  | 0        | Standard für Bridges ohne eigene Einstellung. `chase`: Pause (s) zwischen zwei Durchläufen. `0` = durchgehend; `> 0` = ein Durchlauf, dann alle Lampen `chase_pause` s auf `glow_low`. |
| `attack_ms`       | int (0–2000)  | 140      | Standard für Bridges ohne eigene Einstellung. `pulse`: Aufblendzeit `glow_low` → `glow_high`. |
| `release_ms`      | int (0–5000)  | 70       | Standard für Bridges ohne eigene Einstellung. `pulse`: Abblendzeit → `glow_low` (kleiner als `attack_ms`). |
| `glow_low`        | float (0–1)   | 0.08     | Standard für Bridges ohne eigene Einstellung. **Beide Effekte:** Ruhe-Helligkeit zwischen den Pulsen (`0` = ganz aus). |
| `glow_high`       | float (0–1)   | 1.0      | Standard für Bridges ohne eigene Einstellung. **Beide Effekte:** Helligkeit im Puls-Maximum (über `glow_low`). |
| `restore_state`   | bool          | `true`   | Lampenzustand vor dem Effekt sichern und danach wiederherstellen (für alle Bridges gleich). |
| `log_level`       | Liste         | `info`   | Ausführlichkeit des Add-on-Protokolls (`trace`…`fatal`).           |

## 6. REST-API

| Endpoint  | Methode | Zweck                                                                                 |
|-----------|---------|-----------------------------------------------------------------------------------------|
| `/`       | GET     | Web-UI (Ingress-Panel „Red Alert“)                                                      |
| `/health` | GET     | Status (mind. eine Bridge gepaart? läuft der Effekt gerade?) – auch Ziel des Container-HEALTHCHECK |
| `/config` | GET     | Effektive Konfiguration inkl. `bridges` (für das Web-UI)                                |
| `/pair`   | POST    | Einmalige Kopplung mit einer Bridge. Body: `{"bridge_host": "..."}` (Pflicht bei mehr als einer konfigurierten Bridge) |
| `/areas`  | GET     | Entertainment-Bereiche + Kanäle einer Bridge auflisten. Query `?bridge_host=...` (Pflicht bei mehr als einer gepaarten Bridge) |
| `/start`  | POST    | Effekt auf allen konfigurierten (oder im Body übergebenen) Bridges gleichzeitig starten (antwortet sofort; DTLS-Handshakes laufen parallel im Hintergrund). Body optional: `duration` (Sek., Standard 30), `fps`, `restore_state` (für alle Bridges gemeinsam); `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high` sind die Standardwerte für Bridges ohne eigene Einstellung. `bridges` (Liste von `{bridge_host, area_id, channel_order, effect?, color?, sweep_seconds?, chase_pause?, attack_ms?, release_ms?, glow_low?, glow_high?}`, `channel_order` als `[2,3,1,0,5,4]` oder `"2,3,1,0,5,4"`) übersteuert für diesen Aufruf die Option `bridges` – jede Bridge kann ihre eigenen Effekt-Parameter setzen. Antwort enthält `bridges` (gestartet, je mit aufgelösten Parametern) + `failed_bridges` (übersprungen); `502` nur wenn keine Bridge startet. |
| `/stop`   | POST    | Effekt auf allen laufenden Bridges sofort stoppen                                       |
| `/identify` | POST  | Lampen einer Bridge einzeln durchtesten (`channel_id` → Lampe). Body: `bridge_host` (Pflicht bei mehr als einer konfigurierten Bridge), `area_id` (optional, sonst aus der bridges-Konfiguration), `channel_id` (fehlt = alle nacheinander), `seconds`, `color`, `restore_state`. Ein DTLS-Handshake für den Durchlauf; belegt denselben Slot wie `/start`. |

`duration` weglassen → Effekt läuft **30 Sekunden**, dann endet er von selbst
(oder vorher per `/stop`). Ist eine Bridge nicht erreichbar, starten die
übrigen trotzdem (best effort) – siehe `failed_bridges`.

## 7. Home Assistant einbinden

`configuration.yaml`:

```yaml
rest_command:
  redalert_start:
    url: "http://<home-assistant-ip>:8099/start"
    method: POST
    content_type: "application/json"
    payload: '{}'   # Dauer ohne Angabe: 30 s

  redalert_stop:
    url: "http://<home-assistant-ip>:8099/stop"
    method: POST
```

Automation, die Sound und Lauflicht gemeinsam auslöst (eigene, legal
erworbene Audiodatei z. B. unter `config/www/red_alert.mp3` bzw. im
Medienordner):

```yaml
automation:
  - alias: "Alarmstufe Rot"
    trigger:
      - platform: state
        entity_id: input_boolean.red_alert
        to: "on"
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.wohnzimmer
        data:
          media_content_id: media-source://media_source/local/red_alert.mp3
          media_content_type: audio/mpeg
      - service: rest_command.redalert_start

  - alias: "Alarmstufe Rot – Ende"
    trigger:
      - platform: state
        entity_id: media_player.wohnzimmer
        to: "idle"
    action:
      - service: rest_command.redalert_stop
```

Tipp: `input_boolean.red_alert` lässt sich bequem als Dashboard-Kachel oder
per Sprachbefehl schalten.

## 8. Effekt anpassen

Effekt wählen: Option `effect` bzw. `"effect": "pulse"|"chase"` im `/start`-Body
(Standard für Bridges ohne eigene Einstellung), oder `effect` in der jeweiligen
Zeile der `bridges`-Option/-Liste für nur eine Bridge.

**Beide Effekte:** `glow_low` / `glow_high` (Optionen, `/start`-Body **oder**
je Bridge in `bridges`, `0`–`1`) legen fest, worauf die Lampen zwischen den
Pulsen zurückgehen bzw. wie hell das Puls-Maximum ist. Standard `0.08` / `1.0`;
`glow_low: 0` = geht ganz aus.

`pulse` (Standard) – alle Lampen gemeinsam von `glow_low` auf `glow_high` und
zurück:
- `attack_ms` / `release_ms` – Aufblend- bzw. Abblendzeit; `release_ms` kleiner
  wählen für schnelleres Abfallen als Aufblenden.
- `sweep_seconds` – Zyklusdauer eines Auf-/Ab-Durchlaufs.
- `RedAlertPulse` `lo` / `hi` / `hold_s` in `redalert/rootfs/app/chase.py` –
  Beat-Gate (Schmitt-Trigger): ab `hi` an, wieder aus, wenn der Pegel `hold_s`
  lang unter `lo` bleibt.

`chase` – umlaufender Komet; jede Lampe für sich pulst: kurz hell (`glow_high`),
langes Ausblenden, dann eine Ruhephase auf `glow_low`, dann wieder. Der Kopf ist
etwas breiter als der Lampenabstand, sodass zwei benachbarte Lampen kurz
gemeinsam auf 100 % stehen und dann nacheinander ausglühen (`RedAlertChase` in
`chase.py`):
- `sweep_seconds` – Dauer einer vollen Umrundung aller Lampen (Standard 1.4 s);
  zugleich der Abstand zwischen zwei Pulsen derselben Lampe.
- `chase_pause` – Pause in Sekunden zwischen zwei Durchläufen (Option,
  `/start`-Body **oder** je Bridge in `bridges`, Standard 0). `0` = nahtlos
  umlaufender Komet wie bisher; `> 0` =
  ein Durchlauf (jede Lampe pulst einmal, die letzte glüht aus), dann alle Lampen
  `chase_pause` s auf `glow_low`, dann der nächste Durchlauf.
- `attack_frac` – Anstiegszeit als Bruchteil von `sweep_seconds` (klein =
  schlagartig hell, Standard 0.07).
- `peak_frac` – Mindestbreite des flachen 100-%-Kopfes (Standard 0.08); hält die
  Spitze bei jeder Framerate treffsicher, damit sie nicht flackert.
- `overlap_frac` – wie lange (Bruchteil von `sweep_seconds`) zwei benachbarte
  Lampen gemeinsam auf 100 % stehen (Standard 0.10 ≈ 140 ms). Der Kopf ist damit
  `1/n + overlap_frac` breit.
- `decay_frac` – Abkling-Zeitkonstante als Bruchteil von `sweep_seconds`
  (Standard 0.22); bestimmt, wie steil der Anfang des Ausblendens ist.
- `fade_frac` – Bruchteil des Zyklus, nach dem die 0..1-Form **den Tiefpunkt**
  erreicht und bis zum nächsten Anstieg dort bleibt (Standard 0.62).

Farbe ist aktuell fest auf Rot (`green=0, blue=0`) gesetzt; über
`LightColorCommand` lassen sich bei Bedarf auch andere Farbverläufe fahren.

## 9. Fehlerbehebung

| Symptom                                   | Wahrscheinliche Ursache / Lösung                                                                 |
|--------------------------------------------|----------------------------------------------------------------------------------------------------|
| `/pair` schlägt fehl                       | Link-Button nicht rechtzeitig gedrückt (Zeitfenster ~30 s) oder falsche `bridge_host`.              |
| `/start` liefert `already_running`         | Erst `/stop` aufrufen, bevor ein neuer Lauf gestartet wird.                                        |
| `/start` liefert 502 `keine Bridge verfügbar` | Keine der konfigurierten Bridges war erreichbar/gepaart – bei nur teilweisem Ausfall antwortet `/start` trotzdem `200`, einzelne Fehler stehen in `failed_bridges`. |
| Lampen einer Bridge reagieren gar nicht    | Diese Bridge unterstützt evtl. kein Entertainment (V1-Bridge), oder UDP-Port 2100 zu ihr ist blockiert (Firewall/VLAN). |
| Lauflicht ruckelt                          | `fps` in den Add-on-Optionen erhöhen oder Netzwerklast zur Bridge prüfen.                          |
| Streaming einer Bridge bricht nach kurzer Zeit ab | Jede Bridge erlaubt nur **einen aktiven** Entertainment-Stream gleichzeitig (pro Bridge, nicht global) – Hue-Sync-App oder andere Streaming-Clients auf dieser Bridge währenddessen schließen. |

## 10. Rechtlicher Hinweis zur Audiodatei

Dieses Add-on kümmert sich ausschließlich um das Licht. Den Alarmstufe-Rot-Sound
aus der Serie musst du selbst aus einer legal erworbenen Quelle bereitstellen
(z. B. eigene Kaufversion, eigene Aufnahme).

## Projektstruktur

Add-on-Store-Repository: `repository.yaml` im Wurzelverzeichnis, das Add-on
selbst im Unterordner `redalert/`.

```
.
├── repository.yaml              Add-on-Store-Metadaten (name, url, maintainer)
├── README.md                   Diese Datei (Repo-Überblick)
├── redalert/                   >>> das eigentliche Add-on <<<
│   ├── config.yaml              Manifest: Optionen, Ingress, Ports
│   ├── build.yaml               Basis-Images (home-assistant/base-python)
│   ├── Dockerfile               Image-Build
│   ├── requirements.txt         Python-Abhängigkeiten (hue-entertainment, aiohttp)
│   ├── DOCS.md                  In HA angezeigte Anleitung (Tab „Dokumentation“)
│   ├── CHANGELOG.md             Versionshistorie (Tab „Changelog“)
│   ├── icon.png / logo.png      Store-Grafiken
│   ├── translations/{de,en}.yaml  Beschriftung der Konfigurationsoberfläche
│   └── rootfs/
│       ├── etc/s6-overlay/…      Service-Definition (Start, bashio-Logging)
│       └── app/
│           ├── main.py           REST-Server + Streaming-Loop + Ingress-Panel
│           ├── chase.py          Kometen-Effekt (umlaufend, mit Schweif)
│           └── panel.html        Web-UI (Steuerung)
```
