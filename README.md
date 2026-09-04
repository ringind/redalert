# Red Alert Entertainment Add-on

[![Build](https://github.com/ringind/redalert/actions/workflows/build.yaml/badge.svg)](https://github.com/ringind/redalert/actions/workflows/build.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home-Assistant-Add-on für eine Star-Trek-„Alarmstufe Rot“-Szene über mehrere
Philips-Hue-Lampen, gesteuert über das echte **Hue Entertainment API**
(DTLS-Streaming, nicht die normale Bridge-Szene). Zwei Effekte: `pulse` –
alle Lampen blenden gemeinsam auf und ab (Standard) – und `chase` – ein
umlaufender Komet, der einen Schweif hinter sich herzieht. Läuft für eine
konfigurierbare Dauer (Standard 30 s).

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
                         hält DTLS-Stream offen (~25 Hz)
                         pulse: alle Lampen gemeinsam im Takt
                         (chase: umlaufender Komet mit Schweif)
                                        │
                                        ▼
                              Hue Bridge (Entertainment API)
                                        │
                                        ▼
                                  6 Hue-Lampen
```

Das Add-on läuft dauerhaft im Hintergrund und stellt eine kleine REST-API
bereit (`/pair`, `/areas`, `/start`, `/stop`), die du aus Home-Assistant-
Automationen ansprichst.

## Voraussetzungen

- Home Assistant **OS oder Supervised** (Add-on-Store nötig; bei Core/Container
  müsste der Dienst stattdessen separat als Container/Systemd-Service laufen).
- Hue Bridge **V2** („quadratisch“) oder Hue Pro Bridge – V1-Bridges unterstützen
  kein Entertainment-Streaming.
- 6 Hue-Lampen (Farbe/Farbtemperatur-fähig), einem Entertainment-Bereich zugeordnet.
- Ein `media_player`-Entity in Home Assistant (Sonos/Chromecast/Speaker o. ä.)
  für die Sound-Wiedergabe.
- Eine eigene, legal erworbene Audiodatei mit dem Alarm-Sound (siehe
  [Rechtlicher Hinweis](#10-rechtlicher-hinweis-zur-audiodatei)).
- Zugriff auf den HA-Host per Samba- oder SSH-Add-on, um den Add-on-Ordner
  nach `/addons/` zu kopieren.

## Schnellstart

1. Entertainment-Bereich mit den 6 Lampen in der Hue-App anlegen.
2. Dieses Repo im Add-on Store als Repository hinzufügen, **Red Alert
   Entertainment** installieren und starten.
3. Link-Button auf der Bridge drücken, dann im Web-UI **Pairen** klicken
   (oder `POST /pair` aufrufen).
4. `GET /areas` aufrufen, `area_id` in die Add-on-Konfiguration eintragen.
5. `rest_command` + Automation in Home Assistant anlegen (Vorlage weiter unten).
6. Fertig – Trigger auslösen, Licht und Ton laufen synchron.

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

## 3. Einmalig mit der Bridge pairen

Physischen Link-Button auf der Hue Bridge drücken, dann **innerhalb von
~30 Sekunden** pairen – entweder im Web-UI (Seitenleiste **Red Alert** →
„1 · Mit Bridge pairen“) oder per REST:

```bash
curl -X POST http://<home-assistant-ip>:8099/pair \
  -H "Content-Type: application/json" \
  -d '{"bridge_ip": "192.168.1.50"}'
```

Antwort enthält `username` und `clientkey` – werden automatisch im
Add-on-Datenordner gespeichert (`/data/credentials.json`), du musst dir
nichts merken. Pairing muss nur einmal gemacht werden, außer du setzt das
Add-on komplett zurück.

## 4. Area-ID und Kanalreihenfolge ermitteln

```bash
curl http://<home-assistant-ip>:8099/areas
```

Liefert z. B.:

```json
[{"id": "abcd-1234", "name": "Red Alert", "channels": [0, 1, 2, 3, 4, 5]}]
```

Trage die `id` als Add-on-Option `area_id` ein (Konfiguration-Tab des
Add-ons). Falls die `channels`-Reihenfolge nicht deiner physischen Anordnung
entspricht, kannst du die gewünschte Reihenfolge explizit als
`channel_order` setzen – als kommagetrennte Liste (z. B. `2,3,1,0,5,4`),
entweder als Add-on-Option oder direkt im Web-UI unter „3 · Steuerung“.
Welche `channel_id` welche Lampe ist, findest du im Web-UI unter
„4 · Lampen zuordnen“ (leuchtet die Kanäle einzeln auf). Add-on nach einer
Options-Änderung neu starten.

## 5. Add-on-Optionen

| Option           | Typ           | Standard | Bedeutung                                                       |
|-------------------|--------------|----------|-------------------------------------------------------------------|
| `bridge_host`     | String        | leer     | IP der Hue Bridge. Kann auch pro `/pair`-Aufruf übergeben werden. |
| `area_id`         | String        | leer     | ID des Entertainment-Bereichs (siehe Schritt 4).                  |
| `channel_order`   | String        | leer     | Kanalreihenfolge (`chase`) als kommagetrennte Liste, z. B. `2,3,1,0,5,4`. |
| `effect`          | `pulse`\|`chase` | `pulse` | `pulse` = alle Lampen zusammen `glow_low` → `glow_high` → `glow_low` im Musiktakt. `chase` = umlaufender Komet mit Schweif. |
| `color`           | Hex-String    | `#FF0000`| Farbe des Effekts.                                                |
| `fps`             | int (5–50)    | 25       | Frames/Sekunde des DTLS-Streams.                                   |
| `sweep_seconds`   | float (0.3–5) | 1.4      | `chase`: Dauer einer vollen Umrundung. `pulse`: Zyklusdauer. |
| `chase_pause`     | float (0–60)  | 0        | `chase`: Pause (s) zwischen zwei Durchläufen. `0` = durchgehend; `> 0` = ein Durchlauf, dann alle Lampen `chase_pause` s auf `glow_low`. |
| `attack_ms`       | int (0–2000)  | 140      | `pulse`: Aufblendzeit `glow_low` → `glow_high`.                   |
| `release_ms`      | int (0–5000)  | 70       | `pulse`: Abblendzeit → `glow_low` (kleiner als `attack_ms`).       |
| `glow_low`        | float (0–1)   | 0.08     | **Beide Effekte:** Ruhe-Helligkeit zwischen den Pulsen (`0` = ganz aus). |
| `glow_high`       | float (0–1)   | 1.0      | **Beide Effekte:** Helligkeit im Puls-Maximum (über `glow_low`).   |
| `restore_state`   | bool          | `true`   | Lampenzustand vor dem Effekt sichern und danach wiederherstellen.  |
| `log_level`       | Liste         | `info`   | Ausführlichkeit des Add-on-Protokolls (`trace`…`fatal`).           |

## 6. REST-API

| Endpoint  | Methode | Zweck                                                                                 |
|-----------|---------|-----------------------------------------------------------------------------------------|
| `/`       | GET     | Web-UI (Ingress-Panel „Red Alert“)                                                      |
| `/health` | GET     | Status (gepaart? läuft der Effekt gerade?) – auch Ziel des Container-HEALTHCHECK                         |
| `/config` | GET     | Effektive Konfiguration (für das Web-UI)                                                |
| `/pair`   | POST    | Einmalige Kopplung mit der Bridge. Body: `{"bridge_ip": "..."}` (optional, falls Option gesetzt) |
| `/areas`  | GET     | Verfügbare Entertainment-Bereiche + Kanäle auflisten                                    |
| `/start`  | POST    | Effekt starten (antwortet sofort; DTLS-Handshake läuft im Hintergrund). Body optional: `area_id`, `effect`, `duration` (Sek., Standard 30), `fps`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `color`, `restore_state`, `channel_order` (`[2,3,1,0,5,4]` oder `"2,3,1,0,5,4"`) |
| `/stop`   | POST    | Effekt sofort stoppen                                                                   |
| `/identify` | POST  | Lampen einzeln durchtesten (`channel_id` → Lampe). Body optional: `area_id`, `channel_id` (fehlt = alle nacheinander), `seconds`, `color`, `restore_state`. Ein DTLS-Handshake für den Durchlauf; belegt denselben Slot wie `/start`. |

`duration` weglassen → Effekt läuft **30 Sekunden**, dann endet er von selbst
(oder vorher per `/stop`).

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

Effekt wählen: Option `effect` bzw. `"effect": "pulse"|"chase"` im `/start`-Body.

**Beide Effekte:** `glow_low` / `glow_high` (Optionen **oder** `/start`-Body,
`0`–`1`) legen fest, worauf die Lampen zwischen den Pulsen zurückgehen bzw. wie
hell das Puls-Maximum ist. Standard `0.08` / `1.0`; `glow_low: 0` = geht ganz
aus.

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
- `chase_pause` – Pause in Sekunden zwischen zwei Durchläufen (Option **oder**
  `/start`-Body, Standard 0). `0` = nahtlos umlaufender Komet wie bisher; `> 0` =
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
| `/pair` schlägt fehl                       | Link-Button nicht rechtzeitig gedrückt (Zeitfenster ~30 s) oder falsche `bridge_ip`.               |
| `/start` liefert `already_running`         | Erst `/stop` aufrufen, bevor ein neuer Lauf gestartet wird.                                        |
| `/start` liefert 404 `area_id nicht gefunden` | `GET /areas` erneut prüfen – Bereich evtl. in der Hue-App umbenannt/gelöscht.                    |
| Lampen reagieren gar nicht                 | Bridge unterstützt evtl. kein Entertainment (V1-Bridge), oder UDP-Port 2100 zur Bridge ist blockiert (Firewall/VLAN). |
| Lauflicht ruckelt                          | `fps` in den Add-on-Optionen erhöhen oder Netzwerklast zur Bridge prüfen.                          |
| Streaming bricht nach kurzer Zeit ab       | Die Bridge erlaubt nur **einen aktiven** Entertainment-Stream gleichzeitig – Hue-Sync-App oder andere Streaming-Clients währenddessen schließen. |

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
