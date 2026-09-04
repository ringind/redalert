# Red Alert Entertainment App

[![Build](https://github.com/ringind/redalert/actions/workflows/build.yaml/badge.svg)](https://github.com/ringind/redalert/actions/workflows/build.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home-Assistant-App für eine Star-Trek-„Alarmstufe Rot“-Szene über mehrere
Philips-Hue-Lampen, gesteuert über das echte **Hue Entertainment API**
(DTLS-Streaming, nicht die normale Bridge-Szene). Unterstützt **bis zu 3 Hue
Bridges**, die gleichzeitig loslegen – jede mit ihrem eigenen Effekt, ihrer
eigenen Farbe und eigenem Timing. Drei Effekte: `pulse` – alle Lampen einer
Bridge blenden gemeinsam auf und ab (Standard) –, `chase` – ein umlaufender
Komet, der einen Schweif hinter sich herzieht – und `glitter` – jede Lampe
funkelt für sich in sehr kurzen Abständen in wechselnden Farben auf
(Diamant-Gefunkel). Mit `effect: neutral` je Bridge bleibt eine Bridge ganz
unangetastet, während die anderen laufen. Läuft für eine konfigurierbare Dauer
(Option `duration`, gilt für alle Bridges gemeinsam; `0` = unbegrenzt, läuft
bis `/stop`). Alle Start-Parameter lassen sich als benanntes **Effektset**
speichern, wieder laden/starten und als JSON-Datei aus- und einlesen.

Nutzt die Bibliothek [`hue-entertainment`](https://github.com/music-assistant/hue-entertainment)
(dieselbe, die auch das Hue-Entertainment-Plugin von Music Assistant antreibt).

> **Dieses Repository ist ein Home-Assistant-App-Store-Repository**
> (Home Assistant nennt „Add-ons“ seit Version 2026.2 „Apps“ – rein
> begrifflich, technisch weiterhin Docker-Container über den Supervisor).
> Installation: **Einstellungen → Apps → App Store → ⋮ → Repositories**,
> die URL dieses Repos eintragen, dann **Red Alert Entertainment** installieren.
> Die eigentliche App liegt im Unterordner [`redalert/`](redalert/); die in
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
5. [App installieren](#2-app-installieren)
6. [Einmalig mit der Bridge pairen](#3-einmalig-mit-der-bridge-pairen)
7. [Area-ID und Kanalreihenfolge ermitteln](#4-area-id-und-kanalreihenfolge-ermitteln)
8. [App-Optionen](#5-app-optionen)
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
Home Assistant nicht nativ, deshalb übernimmt das eine kleine eigenständige
App:

```
HA-Automation ──┬──> media_player.play_media (dein Sound, z. B. Sonos)
                └──> rest_command → App /start
                                        │
                                        ▼
                           App (Python, aiohttp)
                         hält je Bridge (bis zu 3) einen
                         eigenen DTLS-Stream offen (~25 Hz),
                         jede mit eigenem Effekt/Farbe/Timing
                         (pulse: alle Lampen im Takt;
                          chase: umlaufender Komet mit Schweif;
                          glitter: Diamant-Gefunkel)
                                        │
                              ┌─────────┼─────────┐
                              ▼         ▼         ▼
                          Bridge 1   Bridge 2   Bridge 3
                              │         │         │
                              ▼         ▼         ▼
                          Hue-Lampen  Hue-Lampen  Hue-Lampen
```

Die App läuft dauerhaft im Hintergrund und stellt eine kleine REST-API
bereit (`/pair`, `/areas`, `/start`, `/stop`), die du aus Home-Assistant-
Automationen ansprichst.

## Voraussetzungen

- Home Assistant **OS oder Supervised** (App-Store nötig; bei Core/Container
  müsste der Dienst stattdessen separat als Container/Systemd-Service laufen).
- Eine bis drei Hue Bridge **V2** („quadratisch“) oder Hue Pro Bridge –
  V1-Bridges unterstützen kein Entertainment-Streaming.
- Pro Bridge: Hue-Lampen (Farbe/Farbtemperatur-fähig), einem Entertainment-Bereich
  zugeordnet.
- Ein `media_player`-Entity in Home Assistant (Sonos/Chromecast/Speaker o. ä.)
  für die Sound-Wiedergabe.
- Eine eigene, legal erworbene Audiodatei mit dem Alarm-Sound (siehe
  [Rechtlicher Hinweis](#10-rechtlicher-hinweis-zur-audiodatei)).
- Zugriff auf den HA-Host per Samba- oder SSH-App, um den App-Ordner
  nach `/addons/` zu kopieren.

## Schnellstart

1. Entertainment-Bereich(e) in der Hue-App anlegen (einer pro Bridge).
2. Dieses Repo im App Store als Repository hinzufügen, **Red Alert
   Entertainment** installieren und starten.
3. Pro Bridge: Link-Button drücken, dann im Web-UI **Pairen** klicken
   (oder `POST /pair` aufrufen).
4. Pro Bridge: `GET /areas?bridge_host=...` aufrufen, Ergebnis als Zeile in
   die App-Option `bridges` eintragen.
5. `rest_command` + Automation in Home Assistant anlegen (Vorlage weiter unten).
6. Fertig – Trigger auslösen, alle konfigurierten Bridges spielen gleichzeitig.

---

## 1. Entertainment-Bereich in der Hue-App anlegen

1. Hue-App → Einstellungen → Entertainment-Bereiche → Neuer Bereich.
2. Alle 6 Lampen hinzufügen und im 3D-Raster grob so platzieren, wie sie
   physisch angeordnet sind (nur für die Hue-App-Vorschau relevant, nicht für
   diese App).
3. Bereich speichern. Die Reihenfolge, in der du die Lampen hinzufügst,
   bestimmt die `channel_id`-Reihenfolge, die später für den Lauflicht-Effekt
   genutzt wird.

## 2. App installieren

**Einstellungen → Apps → App Store → oben rechts „⋮“ → Repositories**,
dann die URL dieses GitHub-Repositories eintragen und hinzufügen. Die App
erscheint anschließend im Store als **Red Alert Entertainment** – installieren
und starten. Empfohlen: „Start beim Booten“ aktivieren.

(Alternativ als lokale App: den Unterordner `redalert/` nach
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
im App-Datenordner gespeichert (`/data/credentials.json`), du musst dir
nichts merken. Pairing muss pro Bridge nur einmal gemacht werden, außer du
setzt die App komplett zurück.

## 4. Area-ID und Kanalreihenfolge ermitteln

```bash
curl "http://<home-assistant-ip>:8099/areas?bridge_host=192.168.1.50"
```

Liefert z. B.:

```json
[{"id": "abcd-1234", "name": "Red Alert", "channels": [0, 1, 2, 3, 4, 5]}]
```

Trage `bridge_host` + die `id` als Zeile der App-Option `bridges` ein
(Konfiguration-Tab der App; eine Zeile pro Bridge). Falls die
`channels`-Reihenfolge nicht deiner physischen Anordnung entspricht, kannst
du die gewünschte Reihenfolge in derselben Zeile explizit als
`channel_order` setzen – als kommagetrennte Liste (z. B. `2,3,1,0,5,4`),
entweder als App-Option oder direkt im Web-UI in der jeweiligen
Bridge-Karte. Welche `channel_id` welche Lampe ist, findest du in der
Bridge-Karte unter „Lampen zuordnen“ (leuchtet die Kanäle einzeln auf).
App nach einer Options-Änderung neu starten.

## 5. App-Optionen

| Option           | Typ           | Standard | Bedeutung                                                       |
|-------------------|--------------|----------|-------------------------------------------------------------------|
| `bridges`         | Liste (max. 3) | leer   | Eine Zeile pro Bridge: `bridge_host` (IP), `area_id` (siehe Schritt 4), optional `channel_order` sowie je Bridge optional `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors` (überschreiben die gleichnamige Option unten nur für diese Bridge). |
| `effect`          | `pulse`\|`chase`\|`glitter`\|`neutral` | `pulse` | Standard für Bridges ohne eigene Einstellung. `pulse` = alle Lampen zusammen `glow_low` → `glow_high` → `glow_low` im Takt. `chase` = umlaufender Komet mit Schweif. `glitter` = jede Lampe funkelt für sich in kurzen Farb-Blitzen auf. `neutral` (nur je Bridge sinnvoll) = Bridge wird nicht gesteuert. |
| `color`           | Hex-String    | `#FF0000`| Standard-Farbe für Bridges ohne eigene Einstellung.                |
| `fps`             | int (5–50)    | 25       | Frames/Sekunde des DTLS-Streams (für alle Bridges gleich).         |
| `sweep_seconds`   | float (0.3–5) | 1.4      | Standard für Bridges ohne eigene Einstellung. `chase`: Dauer einer vollen Umrundung. `pulse`: Zyklusdauer. |
| `chase_pause`     | float (0–60)  | 0        | Standard für Bridges ohne eigene Einstellung. `chase`: Pause (s) zwischen zwei Durchläufen. `0` = durchgehend; `> 0` = ein Durchlauf, dann alle Lampen `chase_pause` s auf `glow_low`. |
| `attack_ms`       | int (0–2000)  | 140      | Standard für Bridges ohne eigene Einstellung. `pulse`: Aufblendzeit `glow_low` → `glow_high`. |
| `release_ms`      | int (0–5000)  | 70       | Standard für Bridges ohne eigene Einstellung. `pulse`: Abblendzeit → `glow_low` (kleiner als `attack_ms`). |
| `glow_low`        | float (0–1)   | 0.08     | Standard für Bridges ohne eigene Einstellung. **Beide Effekte:** Ruhe-Helligkeit zwischen den Pulsen (`0` = ganz aus). |
| `glow_high`       | float (0–1)   | 1.0      | Standard für Bridges ohne eigene Einstellung. **Beide Effekte:** Helligkeit im Puls-Maximum (über `glow_low`). |
| `glitter_interval_ms` | float (5–5000) | 90   | Nur `glitter`. Mittlerer Abstand (ms) zwischen zwei Funkel-Blitzen über alle Lampen einer Bridge. Je Bridge überschreibbar. |
| `glitter_flash_ms` | float (20–5000) | 260   | Nur `glitter`. Abkling-Zeitkonstante (ms) eines Funkens; > `glitter_interval_ms` ⇒ mehrere Lampen gleichzeitig. Je Bridge überschreibbar. |
| `glitter_colors`  | String        | `#FFFFFF #CFE8FF #FFF1D0` | Nur `glitter`. Hex-Farben (leerzeichengetrennt), aus denen jeder Funken zufällig zieht. Leer = Bridge-Farbe. Je Bridge überschreibbar. |
| `restore_state`   | bool          | `true`   | Lampenzustand vor dem Effekt sichern und danach wiederherstellen (für alle Bridges gleich). |
| `duration`        | float (0–86400) | `0`    | Standard-Laufzeit in Sekunden (für alle Bridges gemeinsam; im `/start`-Body übersteuerbar). `0` = **unbegrenzt**, läuft bis `/stop`. |
| `log_level`       | Liste         | `info`   | Ausführlichkeit des App-Protokolls (`trace`…`fatal`).           |

## 6. REST-API

| Endpoint  | Methode | Zweck                                                                                 |
|-----------|---------|-----------------------------------------------------------------------------------------|
| `/`       | GET     | Web-UI (Ingress-Panel „Red Alert“)                                                      |
| `/health` | GET     | Status: `{status, paired, running, current_preset}` – mind. eine Bridge gepaart? läuft der Effekt gerade? Name des zuletzt geladenen Effektsets (`null` bei Ad-hoc-Start)? Auch Ziel des Container-HEALTHCHECK |
| `/config` | GET     | Effektive Konfiguration inkl. `bridges`, `presets` (Namen der Effektsets) und `current_preset` – für das Web-UI und die Home-Assistant-Integration |
| `/pair`   | POST    | Einmalige Kopplung mit einer Bridge. Body: `{"bridge_host": "..."}` (Pflicht bei mehr als einer konfigurierten Bridge) |
| `/areas`  | GET     | Entertainment-Bereiche + Kanäle einer Bridge auflisten. Query `?bridge_host=...` (Pflicht bei mehr als einer gepaarten Bridge) |
| `/start`  | POST    | Effekt auf allen konfigurierten (oder im Body übergebenen) Bridges gleichzeitig starten (antwortet sofort; DTLS-Handshakes laufen parallel im Hintergrund). Body optional: `duration` (Sek., Standard aus der Option `duration`, `0` = unbegrenzt), `fps`, `restore_state` (für alle Bridges gemeinsam); `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors` sind die Standardwerte für Bridges ohne eigene Einstellung. `bridges` (Liste von `{bridge_host, area_id, channel_order, effect?, color?, sweep_seconds?, chase_pause?, attack_ms?, release_ms?, glow_low?, glow_high?, glitter_interval_ms?, glitter_flash_ms?, glitter_colors?}`, `channel_order` als `[2,3,1,0,5,4]` oder `"2,3,1,0,5,4"`) übersteuert für diesen Aufruf die Option `bridges`. `preset` = Name eines gespeicherten Effektsets als Basis (weitere Body-Felder überschreiben es). Antwort enthält `bridges` (gestartet, je mit aufgelösten Parametern) + `failed_bridges` (übersprungen); `502` nur wenn keine Bridge startet. |
| `/stop`   | POST    | Effekt auf allen laufenden Bridges sofort stoppen                                       |
| `/identify` | POST  | Lampen einer Bridge einzeln durchtesten (`channel_id` → Lampe). Body: `bridge_host` (Pflicht bei mehr als einer konfigurierten Bridge), `area_id` (optional, sonst aus der bridges-Konfiguration), `channel_id` (fehlt = alle nacheinander), `seconds`, `color`, `restore_state`. Ein DTLS-Handshake für den Durchlauf; belegt denselben Slot wie `/start`. |
| `/presets` | GET / PUT / POST / DELETE | Effektsets verwalten (`/data/presets.json`). `GET` = alle (`{presets, names}`) bzw. `?name=…` eines. `PUT`/`POST` `{"name","config"}` = speichern/überschreiben (auch Datei-Upload). `DELETE ?name=…` = löschen. |

`duration` weglassen → Effekt läuft mit dem Standard aus der App-Option
`duration` (Vorgabe `0` = **unbegrenzt**, läuft bis `/stop`); mit einem
positiven Wert endet er nach so vielen Sekunden von selbst. Ist eine Bridge
nicht erreichbar, starten die übrigen trotzdem (best effort) – siehe
`failed_bridges`.

## 7. Home Assistant einbinden

**Fertige Integration:** [`custom_components/redalert/`](custom_components/redalert)
in diesem Repo legt vier Entities an (`binary_sensor` „läuft“, `switch`
„Animation“, `select` „Effektset“, `sensor` „geladenes Effektset“). Installation
über **HACS** (repo-Kategorie *Integration* als benutzerdefiniertes Repository
hinzufügen – `hacs.json` im Wurzelverzeichnis) oder manuell (Ordner nach
`config/custom_components/` kopieren); danach HA neu starten und
**Einstellungen → Geräte & Dienste → Integration hinzufügen → „Red Alert
Entertainment App“**. Details siehe das `README.md` in diesem Ordner.

**Ohne Zusatzinstallation** – `configuration.yaml`:

```yaml
rest_command:
  redalert_start:
    url: "http://<home-assistant-ip>:8099/start"
    method: POST
    content_type: "application/json"
    payload: '{}'   # Dauer ohne Angabe: Standard aus der App-Option duration

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

Effekt wählen: Option `effect` bzw. `"effect": "pulse"|"chase"|"glitter"` im
`/start`-Body (Standard für Bridges ohne eigene Einstellung), oder `effect` in
der jeweiligen Zeile der `bridges`-Option/-Liste für nur eine Bridge.

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

`glitter` – Diamant-Gefunkel; jede Lampe funkelt unabhängig auf und klingt
schnell wieder ab (`RedAlertGlitter` in `chase.py`):
- `glitter_interval_ms` – mittlerer Abstand in Millisekunden zwischen zwei
  Funken über alle Lampen einer Bridge (Option, `/start`-Body **oder** je Bridge
  in `bridges`, Standard 90). Klein = hektischeres Gefunkel.
- `glitter_flash_ms` – Abkling-Zeitkonstante eines einzelnen Funkens in
  Millisekunden (Standard 260). Größer als `glitter_interval_ms` ⇒ mehrere
  Lampen funkeln gleichzeitig.
- `glitter_colors` – Liste von Hex-Farben (leerzeichengetrennt, z. B.
  `#FFFFFF #CFE8FF #FFF1D0`), aus denen jeder Funken zufällig eine Farbe zieht.
  Leer = die (Bridge-)Farbe. `glow_low` / `glow_high` gelten wie bei den anderen
  Effekten als Ruhe- bzw. Spitzenhelligkeit.

Die Effektfarbe kommt aus der jeweiligen Bridge-`color` (bzw. der Option/dem
`/start`-Body-Standard); `chase.py` berechnet nur die Helligkeit, `main.py`
setzt die Farbe über `LightColorCommand`. Bei `glitter` liefert `chase.py`
zusätzlich je Funken eine Farbe aus `glitter_colors`.

`neutral` – die Lampen dieser Bridge werden **nicht** angesteuert: kein
DTLS-Stream, kein Sichern/Wiederherstellen. Sinnvoll nur je Bridge
(`bridges[].effect: neutral`), damit ein Effektset auf einer Bridge einen
Effekt fahren und eine andere Bridge komplett auslassen kann; eine
`neutral`-Bridge braucht keine `area_id`. Sind alle Bridges `neutral`,
antwortet `/start` mit `no_active_bridges` (kein Fehler).

### Effektsets

Unter „3 · Effektsets“ im Web-UI lässt sich der komplette Formularzustand (alle
Bridge-Karten + Steuerung) unter einem Namen speichern (`/data/presets.json`),
wieder **Laden**, direkt **Starten**, als JSON-Datei **Herunterladen** /
**Hochladen** und **Löschen**. Per REST: `GET/PUT/DELETE /presets` und
`POST /start {"preset": "<Name>"}`.

## 9. Fehlerbehebung

| Symptom                                   | Wahrscheinliche Ursache / Lösung                                                                 |
|--------------------------------------------|----------------------------------------------------------------------------------------------------|
| `/pair` schlägt fehl                       | Link-Button nicht rechtzeitig gedrückt (Zeitfenster ~30 s) oder falsche `bridge_host`.              |
| `/start` liefert `already_running`         | Erst `/stop` aufrufen, bevor ein neuer Lauf gestartet wird.                                        |
| `/start` liefert 502 `keine Bridge verfügbar` | Keine der konfigurierten Bridges war erreichbar/gepaart – bei nur teilweisem Ausfall antwortet `/start` trotzdem `200`, einzelne Fehler stehen in `failed_bridges`. |
| Lampen einer Bridge reagieren gar nicht    | Diese Bridge unterstützt evtl. kein Entertainment (V1-Bridge), oder UDP-Port 2100 zu ihr ist blockiert (Firewall/VLAN). |
| Lauflicht ruckelt                          | `fps` in den App-Optionen erhöhen oder Netzwerklast zur Bridge prüfen.                          |
| Streaming einer Bridge bricht nach kurzer Zeit ab | Jede Bridge erlaubt nur **einen aktiven** Entertainment-Stream gleichzeitig (pro Bridge, nicht global) – Hue-Sync-App oder andere Streaming-Clients auf dieser Bridge währenddessen schließen. |

## 10. Rechtlicher Hinweis zur Audiodatei

Diese App kümmert sich ausschließlich um das Licht. Den Alarmstufe-Rot-Sound
aus der Serie musst du selbst aus einer legal erworbenen Quelle bereitstellen
(z. B. eigene Kaufversion, eigene Aufnahme).

## Projektstruktur

App-Store-Repository: `repository.yaml` im Wurzelverzeichnis, die App
selbst im Unterordner `redalert/`.

```
.
├── repository.yaml              App-Store-Metadaten (name, url, maintainer)
├── README.md                   Diese Datei (Repo-Überblick)
├── custom_components/redalert/ Home-Assistant-Integration (binary_sensor,
│                                switch, select, sensor – spricht die REST-API
│                                der App an, siehe README darin)
├── redalert/                   >>> die eigentliche App <<<
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
│           ├── chase.py          Effekt-Mathematik (chase-Komet, pulse, glitter-Funkeln)
│           └── panel.html        Web-UI (Steuerung)
```
