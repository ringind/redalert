# Red Alert Entertainment App

[![Build](https://github.com/ringind/redalert/actions/workflows/build.yaml/badge.svg)](https://github.com/ringind/redalert/actions/workflows/build.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

🇩🇪 Deutsch (diese Datei) · 🇬🇧 [English](README.en.md)

Home-Assistant-App für frei konfigurierbare Licht-Effekte über mehrere
Philips-Hue-Lampen, gesteuert über das echte **Hue Entertainment API**
(DTLS-Streaming, nicht die normale, träge Bridge-Szene). Ursprünglich für die
Star-Trek-„Alarmstufe Rot“-Szene gebaut (daher der Name) – inzwischen ein
allgemeiner Lichteffekt-Player: beliebig viele **Effektsets** (Effekt, Farbe,
Timing je Bridge) lassen sich benannt speichern und per Knopfdruck, Sprache
oder Automation abrufen, von der namensgebenden roten Alarmstufe bis zu einer
ruhigen Ambiente-Beleuchtung oder einem Diamant-Funkeln zur Party. Unterstützt
**bis zu 3 Hue Bridges**, die gleichzeitig loslegen – jede mit ihrem eigenen
Effekt, ihrer eigenen Farbe und eigenem Timing – oder unabhängig
nacheinander per eigenem Start/Stop je Bridge, im Web-UI wie in der
Home-Assistant-Integration. **18 Effekte** stehen zur
Wahl – von ruhig (`pulse`, `aurora`) über klassisch (`comet`,
`chase`, `color_chase`, `wave`) bis actionreich (`police`, `lightning`,
`strobe`, `duel`, `meteor`, `firework`, `ripple`, `glitter`, `flicker`,
`heartbeat`, `wipe`) –
siehe [§8 „Effekt anpassen“](#8-effekt-anpassen) für alle im Detail. Farbe(n),
Timing und Helligkeit sind für jeden Effekt frei einstellbar
(Web-UI-Farbwähler, App-Option oder REST-Body), nicht nur Rot. Mit
`effect: neutral` je Bridge bleibt
eine Bridge ganz unangetastet, während die anderen laufen. Läuft für eine
konfigurierbare Dauer (Option `duration`, gilt für alle Bridges gemeinsam;
`0` = unbegrenzt, läuft bis `/stop`). Alle Start-Parameter lassen sich als
benanntes **Effektset** speichern, wieder laden/starten und als JSON-Datei
aus- und einlesen.

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
> Installation als Seitenleisten-Eintrag **Red Alert** (Ingress); oben rechts
> lässt sich zwischen Deutsch und Englisch umschalten.

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
13. [Projektstruktur](#projektstruktur)

---

## Überblick & Architektur

Home Assistants normale Hue-Szenen laufen über die REST/CLIP-API der Bridge und
sind für ein sauberes, frame-genaues Lauflicht zu träge. Für ein echtes,
niedriglatentes Lauflicht braucht es einen dauerhaften **DTLS-Stream** zur
Bridge (dasselbe Protokoll, das Hue Sync/Gaming-Sync nutzt). Das leistet
Home Assistant nicht nativ, deshalb übernimmt das eine kleine eigenständige
App:

```
HA-Automation ──┬──> media_player.play_media (optional: dein Sound, z. B. Sonos)
                └──> rest_command → App /start
                                        │
                                        ▼
                           App (Python, aiohttp)
                         hält je Bridge (bis zu 3) einen
                         eigenen DTLS-Stream offen (~25 Hz),
                         jede mit eigenem Effekt/Farbe/Timing
                         (18 Effekte, siehe §8)
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
- Zugriff auf den HA-Host per Samba- oder SSH-App, um den App-Ordner
  nach `/addons/` zu kopieren.

Nur für die Sound+Licht-Automation nach Star-Trek-Vorbild (optional – die App
selbst braucht keinen Ton):

- Ein `media_player`-Entity in Home Assistant (Sonos/Chromecast/Speaker o. ä.)
  für die Sound-Wiedergabe.
- Eine eigene, legal erworbene Audiodatei mit dem Alarm-Sound.

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
~30 Sekunden** pairen. Am einfachsten im Web-UI (Seitenleiste **Red Alert** →
Bridge-Karte unter „1 · Bridges“). Per REST geht es nur noch aus dem
HA-Container heraus (kein LAN-Port mehr) und mit API-Token:

```bash
curl -X POST http://<addon-hostname>:8099/pair \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <api_token>" \
  -d '{"bridge_host": "192.168.1.50"}'
```

Antwort enthält `username` und `clientkey` – werden automatisch (pro Bridge)
im App-Datenordner gespeichert (`/data/credentials.json`), du musst dir
nichts merken. Pairing muss pro Bridge nur einmal gemacht werden, außer du
setzt die App komplett zurück.

## 4. Area-ID und Kanalreihenfolge ermitteln

```bash
curl -H "Authorization: Bearer <api_token>" \
  "http://<addon-hostname>:8099/areas?bridge_host=192.168.1.50"
```

(oder im Web-UI „Bereiche laden“ – dort ohne Token.)

Liefert z. B.:

```json
[{"id": "abcd-1234", "name": "Red Alert", "channels": [0, 1, 2, 3, 4, 5]}]
```

Trage `bridge_host` + die `id` als Zeile der App-Option `bridges` ein
(Konfiguration-Tab der App; eine Zeile pro Bridge). Ein im Web-UI **geladenes
Effektset** ersetzt diese `area_id`s zur Laufzeit (siehe „Effektsets“). Falls die
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
| `api_token`       | String        | leer (auto) | Token für den REST-Zugriff von außerhalb (HA-Integration, `rest_command`). Leer lassen: Das Add-on erzeugt beim ersten Start selbst einen, trägt ihn hier ein und schreibt ihn ins Add-on-Log. Ingress (Web-UI) braucht keinen Token. |
| `bridges`         | Liste (max. 3) | leer   | Eine Zeile pro Bridge: `bridge_host` (IP), `area_id` (siehe Schritt 4), optional `channel_order` sowie je Bridge optional `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors`, `gc_direction`, `gc_strip_lengths`, `gc_count`, `gc_length`, `gc_speed`, `gc_background_color`, `gc_chase_glitter`, `gc_background_pulse`, `color2`, `lightning_interval_ms`, `lightning_flash_ms`, `meteor_count`, `meteor_speed`, `firework_interval_ms`, `firework_speed`, `ripple_interval_ms`, `ripple_speed`, `wave_length`, `flicker_interval_ms`, `flicker_dip_ms` (überschreiben die gleichnamige Option unten nur für diese Bridge). |
| `effect`          | `pulse`\|`comet`\|`glitter`\|`police`\|`lightning`\|`heartbeat`\|`aurora`\|`rainbow`\|`meteor`\|`wipe`\|`firework`\|`ripple`\|`wave`\|`flicker`\|`strobe`\|`duel`\|`chase`\|`neutral` | `pulse` | Standard für Bridges ohne eigene Einstellung, siehe §8 für alle Effekte im Detail. `neutral` (nur je Bridge sinnvoll) = Bridge wird nicht gesteuert. |
| `color`           | Hex-String    | `#FF0000`| Standard-Farbe für Bridges ohne eigene Einstellung.                |
| `fps`             | int (5–50)    | 25       | Frames/Sekunde des DTLS-Streams (für alle Bridges gleich).         |
| `sweep_seconds`   | float (0.3–300) | 1.4    | Standard für Bridges ohne eigene Einstellung. `comet`: Dauer einer vollen Umrundung. `pulse`/`heartbeat`: Zyklusdauer. `wave`/`strobe`/`duel`: Periodendauer. |
| `chase_pause`     | float (0–60)  | 0        | Standard für Bridges ohne eigene Einstellung. `comet`: Pause (s) zwischen zwei Durchläufen. `0` = durchgehend; `> 0` = ein Durchlauf, dann alle Lampen `chase_pause` s auf `glow_low`. |
| `attack_ms`       | int (0–2000)  | 140      | Standard für Bridges ohne eigene Einstellung. `pulse`: Aufblendzeit `glow_low` → `glow_high`. |
| `release_ms`      | int (0–5000)  | 70       | Standard für Bridges ohne eigene Einstellung. `pulse`: Abblendzeit → `glow_low` (kleiner als `attack_ms`). |
| `glow_low`        | float (0–1)   | 0.08     | Standard für Bridges ohne eigene Einstellung. **Alle Effekte:** Ruhe-Helligkeit zwischen den Pulsen (`0` = ganz aus). |
| `glow_high`       | float (0–1)   | 1.0      | Standard für Bridges ohne eigene Einstellung. **Alle Effekte:** Helligkeit im Puls-Maximum (über `glow_low`). |
| `glitter_interval_ms` | float (5–5000) | 90   | Nur `glitter`. Mittlerer Abstand (ms) zwischen zwei Funkel-Blitzen über alle Lampen einer Bridge. Je Bridge überschreibbar. |
| `glitter_flash_ms` | float (20–5000) | 260   | Nur `glitter`. Abkling-Zeitkonstante (ms) eines Funkens; > `glitter_interval_ms` ⇒ mehrere Lampen gleichzeitig. Je Bridge überschreibbar. |
| `glitter_colors`  | String        | `#FFFFFF #CFE8FF #FFF1D0` | Nur `glitter`. Hex-Farben (leerzeichengetrennt), aus denen jeder Funken zufällig zieht. Leer = Bridge-Farbe. Je Bridge überschreibbar. |
| `gc_direction`    | `forward`\|`backward`\|`bounce` | `forward` | Nur `chase`. Standard-Chaserichtung. Je Bridge überschreibbar, dort auch als kommagetrennte Liste (eine Richtung je Strip, siehe `gc_strip_lengths`). |
| `gc_strip_lengths` | String (je Bridge) | leer (ein Strip) | Nur `chase`, nur je Bridge. Teilt die Kanäle in aufeinanderfolgende Gradient-Lightstrips auf, z. B. `"7,5"`. |
| `gc_count`        | int (1–8)     | `1`      | Nur `chase`. Anzahl gleichzeitig laufender Chase-Bänder. Je Bridge überschreibbar. |
| `gc_length`       | float (0.2–200) | `2.0`  | Nur `chase`. Breite des vollfarbigen Kerns eines Bands in Segmenten. Je Bridge überschreibbar. |
| `gc_speed`        | float (0.01–50) | `4.0`  | Nur `chase`. Segmente pro Sekunde. Je Bridge überschreibbar. |
| `gc_background_color` | Hex-String | `#000000` | Nur `chase`. Farbe außerhalb der Chase-Bänder. Je Bridge überschreibbar. |
| `gc_chase_glitter` | bool         | `false`  | Nur `chase`. Bänder funkeln zusätzlich wie `glitter`. Je Bridge überschreibbar. |
| `gc_background_pulse` | bool     | `false`  | Nur `chase`. Background pulsiert zusätzlich wie `pulse` statt ruhig auf `glow_low` zu bleiben. Je Bridge überschreibbar. |
| `color2`   | Hex-String    | `#0000FF`| Zweite Farbe – `police` (Gruppe 2), `duel` (zweiter Komet). Je Bridge überschreibbar. |
| `lightning_interval_ms` | float (50–60000) | `4000` | Nur `lightning`. Mittlerer Abstand (ms) zwischen zwei gemeinsamen Blitzen. Je Bridge überschreibbar. |
| `lightning_flash_ms` | float (20–5000) | `500` | Nur `lightning`. Abkling-Zeitkonstante (ms) eines Blitzes. Je Bridge überschreibbar. |
| `meteor_count`    | int (1–8)     | `3`      | Nur `meteor`. Anzahl unabhängiger Meteore. Je Bridge überschreibbar. |
| `meteor_speed`    | float (0.05–20) | `1.2`  | Nur `meteor`. Mittlere Geschwindigkeit in Kanälen/Sekunde. Je Bridge überschreibbar. |
| `firework_interval_ms` | float (200–60000) | `3000` | Nur `firework`. Wie oft (ms) ein neuer Ausbruch startet. Je Bridge überschreibbar. |
| `firework_speed`  | float (0.5–50) | `6.0`   | Nur `firework`. Ausbreitungsgeschwindigkeit in Kanälen/Sekunde. Je Bridge überschreibbar. |
| `ripple_interval_ms` | float (200–60000) | `3000` | Nur `ripple`. Wie oft (ms) ein neuer Impuls startet. Je Bridge überschreibbar. |
| `ripple_speed`    | float (0.5–50) | `6.0`   | Nur `ripple`. Geschwindigkeit der Wellenfront in Kanälen/Sekunde. Je Bridge überschreibbar. |
| `wave_length`     | float (0.5–50) | `3.0`   | Nur `wave`. Kanäle pro voller Sinuswelle. Je Bridge überschreibbar. |
| `flicker_interval_ms` | float (20–10000) | `600` | Nur `flicker`. Mittlerer Abstand (ms) zwischen zwei Einbrüchen. Je Bridge überschreibbar. |
| `flicker_dip_ms`  | float (20–5000) | `150`  | Nur `flicker`. Erholzeit (ms) nach einem Einbruch. Je Bridge überschreibbar. |
| `restore_state`   | bool          | `true`   | Lampenzustand vor dem Effekt sichern und danach wiederherstellen (für alle Bridges gleich). |
| `duration`        | float (0–86400) | `0`    | Standard-Laufzeit in Sekunden (für alle Bridges gemeinsam; im `/start`-Body übersteuerbar). `0` = **unbegrenzt**, läuft bis `/stop`. |
| `log_level`       | Liste         | `info`   | Ausführlichkeit des App-Protokolls (`trace`…`fatal`).           |

## 6. REST-API

**Zugang (seit 2.0.0):** kein LAN-Port mehr. Erreichbar über **Ingress** (Web-UI,
ohne Token) und über das **interne Docker-Netz** unter
`http://<addon-hostname>:8099` (Hostname auf der Add-on-Seite unter *Info*).
Jeder Aufruf außerhalb von Ingress braucht den Header
`Authorization: Bearer <api_token>` (ersatzweise `?api_token=…`), sonst `401`.
Die HA-Integration übernimmt den Token unter Supervisor automatisch.

| Endpoint  | Methode | Zweck                                                                                 |
|-----------|---------|-----------------------------------------------------------------------------------------|
| `/`       | GET     | Web-UI (Ingress-Panel „Red Alert“)                                                      |
| `/health` | GET     | Status: `{status, paired, running, armed, current_preset}` – mind. eine Bridge gepaart? läuft der Effekt auf irgendeiner Bridge gerade (je-Bridge-Status siehe `/config`)? sind alle nicht-`neutral` Bridges scharfgeschaltet? Name des zuletzt geladenen Effektsets (`null` bei Ad-hoc-Start)? Auch Ziel des Container-HEALTHCHECK |
| `/config` | GET     | Effektive Konfiguration inkl. `bridges` (je Bridge zusätzlich `running: bool` und `armed: bool`), `armed`/`armed_bridges` (global), `presets` (Namen der Effektsets) und `current_preset` – für das Web-UI und die Home-Assistant-Integration |
| `/pair`   | POST    | Einmalige Kopplung mit einer Bridge. Body: `{"bridge_host": "..."}` (Pflicht bei mehr als einer konfigurierten Bridge) |
| `/areas`  | GET     | Entertainment-Bereiche + Kanäle einer Bridge auflisten. Query `?bridge_host=...` (Pflicht bei mehr als einer gepaarten Bridge) |
| `/start`  | POST    | Effekt auf allen konfigurierten (oder im Body übergebenen) Bridges gleichzeitig starten (antwortet sofort; DTLS-Handshakes laufen parallel im Hintergrund) – oder, mit `bridge_host` im Body, nur auf einer einzelnen Bridge, unabhängig vom Zustand der anderen. Body optional: `duration` (Sek., Standard aus der Option `duration`, `0` = unbegrenzt), `fps`, `restore_state` (für alle Bridges gemeinsam); `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors`, `gc_direction`, `gc_count`, `gc_length`, `gc_speed`, `gc_background_color`, `gc_chase_glitter`, `gc_background_pulse`, `color2`, `lightning_interval_ms`, `lightning_flash_ms`, `meteor_count`, `meteor_speed`, `firework_interval_ms`, `firework_speed`, `ripple_interval_ms`, `ripple_speed`, `wave_length`, `flicker_interval_ms`, `flicker_dip_ms` sind die Standardwerte für Bridges ohne eigene Einstellung. `bridges` (Liste von `{bridge_host, area_id, channel_order, effect?, color?, sweep_seconds?, chase_pause?, attack_ms?, release_ms?, glow_low?, glow_high?, glitter_interval_ms?, glitter_flash_ms?, glitter_colors?, gc_direction?, gc_strip_lengths?, gc_count?, gc_length?, gc_speed?, gc_background_color?, gc_chase_glitter?, gc_background_pulse?, color2?, lightning_interval_ms?, lightning_flash_ms?, meteor_count?, meteor_speed?, firework_interval_ms?, firework_speed?, ripple_interval_ms?, ripple_speed?, wave_length?, flicker_interval_ms?, flicker_dip_ms?}`, `channel_order` als `[2,3,1,0,5,4]` oder `"2,3,1,0,5,4"`) übersteuert für diesen Aufruf die Option `bridges`; `gc_strip_lengths` (nur `chase`, je Bridge, z. B. `[7,5]`) teilt die Kanäle dieser Bridge in mehrere Gradient-Lightstrips auf, `gc_direction` darf dann eine Liste sein (eine Richtung je Strip). `preset` = Name eines gespeicherten Effektsets als Basis (weitere Body-Felder überschreiben es) – nicht mit `bridge_host` kombinierbar; übernimmt die `bridges` (inkl. `area_id`) des Sets als neue effektive Konfiguration. Bei scharfer/laufender Bridge nur erlaubt, wenn das Set pro aktiver Bridge dieselbe `area_id` hat (dann werden laufende Effekte live umgeschaltet, `hotswapped_bridges`), sonst `409`. `bridge_host` (optional) filtert auf genau diese eine Bridge; `already_running` gilt dann nur für sie. Ohne `bridge_host` werden bereits laufende Bridges übersprungen (`skipped_bridges`) statt den Aufruf abzulehnen. Antwort enthält `bridges` (neu gestartet, je mit aufgelösten Parametern) + `failed_bridges`/`neutral_bridges`/`skipped_bridges`; `502` nur wenn keine Bridge startet und mindestens eine fehlschlägt. |
| `/stop`   | POST    | Effekt auf allen laufenden Bridges sofort stoppen – oder, mit `bridge_host` im Body, nur auf einer einzelnen Bridge                                       |
| `/arm`    | POST    | **Scharfschalten**: DTLS-Stream einer/aller Bridge(s) dauerhaft offen halten, damit ein späteres `/start` den ~3–9 s langen Handshake überspringt. Body optional `bridge_host` (sonst alle konfigurierten, nicht-`neutral` Bridges). Solange scharf belegt die Bridge ihren einzigen Entertainment-Slot; die Lampen zeigen ein angenähertes Standbild des vorherigen Zustands. Laufende Bridge → erst `/stop`. |
| `/disarm` | POST    | Scharfschaltung aufheben: Stream(s) schließen, Lichtzustand per CLIP v2 wiederherstellen. Body optional `bridge_host`. Ein laufender Effekt wird zuvor gestoppt. |
| `/select` | POST    | Ein Effektset **laden**: als `current_preset` merken **und** dessen Bridge-`area_id`s als neue effektive Konfiguration übernehmen (gilt auch für `/arm`, HA-Integration, `rest_command`). Body `{"preset": "<name>"}` (`404` wenn unbekannt) oder `{"preset": null}` zum Zurücksetzen. Laden geht immer, solange nichts scharfgeschaltet ist und keine Animation läuft; bei scharfer/laufender Bridge nur, wenn das Set pro aktiver Bridge dieselbe `area_id` hat – dann werden laufende Effekte live umgeschaltet (kein Neustart/Handshake), sonst **`409`**. |
| `/identify` | POST  | Lampen einer Bridge einzeln durchtesten (`channel_id` → Lampe). Body: `bridge_host` (Pflicht bei mehr als einer konfigurierten Bridge), `area_id` (optional, sonst aus der bridges-Konfiguration), `channel_id` (fehlt = alle nacheinander), `seconds`, `color`, `restore_state`. Ein DTLS-Handshake für den Durchlauf; belegt denselben Slot wie ein Effekt auf dieser einen Bridge (bei scharfer Bridge blockiert – erst `/disarm`). |
| `/presets` | GET / PUT / POST / DELETE | Effektsets verwalten (`/data/presets.json`). `GET` = alle (`{presets, names}`) bzw. `?name=…` eines. `PUT`/`POST` `{"name","config"}` = speichern/überschreiben (auch Datei-Upload). `DELETE ?name=…` = löschen. Jedes Set speichert die `area_id` pro Bridge mit. |

`duration` weglassen → Effekt läuft mit dem Standard aus der App-Option
`duration` (Vorgabe `0` = **unbegrenzt**, läuft bis `/stop`); mit einem
positiven Wert endet er nach so vielen Sekunden von selbst. Ist eine Bridge
nicht erreichbar, starten die übrigen trotzdem (best effort) – siehe
`failed_bridges`.

**Schnellerer Start:** Zwischen `/start` und dem sichtbaren Effekt liegt sonst
der DTLS-Handshake der Bridge (~1,5–9 s). `POST /arm` hält den Stream vorab
dauerhaft offen (Web-UI: Knopf „Scharfschalten“ je Bridge-Karte bzw. global;
Home Assistant: Schalter „Scharfgeschaltet“); ein anschließendes `/start`
beginnt dann innerhalb eines Frames. Solange scharf belegt die Bridge ihren
einzigen Entertainment-Slot und ihre Lampen zeigen ein angenähertes Standbild;
`POST /disarm` schließt den Stream und stellt den exakten Zustand wieder her.

## 7. Home Assistant einbinden

**Fertige Integration:** [`custom_components/redalert/`](custom_components/redalert)
in diesem Repo legt sechs Entities an (`binary_sensor` „Betriebszustand“,
`binary_sensor` „Scharfgeschaltet“, `switch` „Animation“, `switch`
„Scharfgeschaltet“, `select` „Effektset“ – lädt das Set (`area_id`s inklusive);
bei laufender/scharfer Bridge nur, wenn die Bereiche gleich bleiben, dann
Live-Umschaltung –, `sensor` „geladenes Effektset“). Installation
über **HACS** (repo-Kategorie *Integration* als benutzerdefiniertes Repository
hinzufügen – `hacs.json` im Wurzelverzeichnis) oder manuell (Ordner nach
`config/custom_components/` kopieren); danach HA neu starten und
**Einstellungen → Geräte & Dienste → Integration hinzufügen → „Red Alert
Entertainment App“**. Unter Supervisor werden Host und API-Token automatisch
erkannt – nur bestätigen. Details siehe [`custom_components/redalert/README.md`](custom_components/redalert/README.md).

**Ohne Zusatzinstallation** – `configuration.yaml` (`<addon-hostname>` von der
Add-on-Seite unter *Info*, `<api_token>` aus der Add-on-Konfiguration):

```yaml
rest_command:
  redalert_start:
    url: "http://<addon-hostname>:8099/start"
    method: POST
    content_type: "application/json"
    headers:
      Authorization: "Bearer <api_token>"
    payload: '{}'   # Dauer ohne Angabe: Standard aus der App-Option duration

  redalert_stop:
    url: "http://<addon-hostname>:8099/stop"
    method: POST
    headers:
      Authorization: "Bearer <api_token>"
```

Beispiel-Automation, die Sound und Licht zur namensgebenden Alarmstufe-Rot-
Szene kombiniert (eigene, legal erworbene Audiodatei z. B. unter
`config/www/red_alert.mp3` bzw. im Medienordner) – jedes andere Effektset
(ruhiges Ambiente, Diamant-Funkeln zur Party, …) lässt sich genauso an eine
Automation hängen, z. B. über `rest_command.redalert_start_preset` und
`{"preset": "<Name>"}`, siehe [„Effektsets“ in der App-Doku](redalert/DOCS.md#effektsets):

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

Effekt wählen: Option `effect` bzw.
`"effect": "pulse"|"comet"|"glitter"|"police"|"lightning"|"heartbeat"|"aurora"|"rainbow"|"meteor"|"wipe"|"firework"|"ripple"|"wave"|"flicker"|"strobe"|"duel"|"chase"` im `/start`-Body
(Standard für Bridges ohne eigene Einstellung), oder `effect` in der
jeweiligen Zeile der `bridges`-Option/-Liste für nur eine Bridge.

**Alle Effekte:** `glow_low` / `glow_high` (Optionen, `/start`-Body **oder**
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

`comet` – umlaufender Komet; jede Lampe für sich pulst: kurz hell (`glow_high`),
langes Ausblenden, dann eine Ruhephase auf `glow_low`, dann wieder. Der Kopf ist
etwas breiter als der Lampenabstand, sodass zwei benachbarte Lampen kurz
gemeinsam auf 100 % stehen und dann nacheinander ausglühen (`RedAlertComet` in
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

`police` – Alarmlicht; jede zweite Lampe (nach Kanalreihenfolge) bildet eine
Gruppe, die beiden Gruppen blinken abwechselnd (`RedAlertPolice` in
`chase.py`):
- `sweep_seconds` – Dauer eines vollen Wechsels (beide Gruppen einmal an).
- `color2` – Farbe der zweiten Gruppe (Option, `/start`-Body **oder**
  je Bridge in `bridges`, Standard `#0000FF`); die erste Gruppe nutzt die
  normale Bridge-`color`.

`lightning` – Gewitter; alle Lampen einer Bridge blitzen **gemeinsam** auf
(anders als `glitter`, wo jede Lampe für sich funkelt), mit gelegentlichem
Doppelblitz (`RedAlertLightning` in `chase.py`):
- `lightning_interval_ms` – mittlerer Abstand in Millisekunden zwischen zwei
  Blitzen (Option, `/start`-Body **oder** je Bridge in `bridges`, Standard
  4000).
- `lightning_flash_ms` – Abkling-Zeitkonstante eines Blitzes in Millisekunden
  (Standard 500).

`heartbeat` – ein Doppelpuls („lub-dub“) statt eines einzelnen Pulses,
läuft durch dasselbe Beat-Gate/Slew wie `pulse` (`RedAlertPulse.heartbeat`
in `chase.py`):
- `sweep_seconds` – Dauer eines vollen Herzschlags (beide Beats).
- `attack_ms` / `release_ms` – wie bei `pulse` die Auf-/Abblendzeit der
  beiden Beats.

`aurora` – Polarlicht; langsame, weich überblendete Farbwellen wandern über
die Lampen (`RedAlertAurora` in `chase.py`, berechnet die Farbe direkt statt
einer Helligkeitskurve):
- `glitter_colors` – Palette, durch die die Welle blendet (leer = nur die
  Bridge-`color`, dann ohne Farbwechsel).
- `sweep_seconds` – eine volle Farbwelle dauert `4 × sweep_seconds`. Die
  überlagerte Helligkeits-Atmung hat dieselbe Periode, aber **höchstens 12 s** –
  sonst säßen die Lampen bei hohem `sweep_seconds` minutenlang nahe `glow_low`
  und würden dort falsche Farbtöne zeigen.

`rainbow` – ein durchgehender Regenbogen-Farbumlauf, je Lampe phasenversetzt,
sodass ein Farbverlauf sichtbar über die Lampen wandert statt dass alle
gleichzeitig die Farbe wechseln (`RedAlertRainbow` in `chase.py`):
- `sweep_seconds` – eine volle Umdrehung dauert `4 × sweep_seconds`;
  Helligkeit ist konstant auf `glow_high`.

`meteor` – mehrere unabhängige Kometen mit zufälliger Geschwindigkeit,
Richtung und Spitzenhelligkeit – eine dichtere, unregelmäßigere Variante von
`comet` (`RedAlertMeteor` in `chase.py`):
- `meteor_count` – Anzahl gleichzeitig laufender Meteore (Option,
  `/start`-Body **oder** je Bridge in `bridges`, Standard 3).
- `meteor_speed` – mittlere Geschwindigkeit in Kanälen/Sekunde, jeder Meteor
  weicht zufällig davon ab, auch rückwärts (Standard 1.2).

`wipe` – ein Auffüll-Balken läuft einmal über die Kanäle, hält kurz voll und
beginnt von vorn (`RedAlertWipe` in `chase.py`):
- `sweep_seconds` – Dauer des Auffüllens von Kanal 0 bis zum letzten Kanal.
- `chase_pause` – wie lange der Balken voll gefüllt hält, bevor er
  zurückgesetzt wird (Standard 0).

`firework` – wiederkehrende Ausbrüche von der mittleren Lampe/dem mittleren
Kanal aus, die nach außen laufen und verblassen (`RedAlertFirework` in
`chase.py`):
- `firework_interval_ms` – wie oft ein neuer Ausbruch startet (Option,
  `/start`-Body **oder** je Bridge in `bridges`, Standard 3000).
- `firework_speed` – Ausbreitungsgeschwindigkeit in Kanälen/Sekunde
  (Standard 6.0).

`ripple` – wie `firework`, aber die Welle prallt an beiden Enden der Kanäle
ab und läuft als Echo zurück, bevor sie verblasst (`RedAlertRipple` in
`chase.py`):
- `ripple_interval_ms` – wie oft ein neuer Impuls startet (Option,
  `/start`-Body **oder** je Bridge in `bridges`, Standard 3000).
- `ripple_speed` – Geschwindigkeit der Wellenfront in Kanälen/Sekunde,
  auch beim Zurücklaufen (Standard 6.0).

`wave` – eine durchgehende Sinuswelle aus Helligkeit läuft über die Kanäle,
mehrere Wellenberge gleichzeitig sichtbar – anders als `comet`s einzelner,
lokalisierter Kopf (`RedAlertWave` in `chase.py`):
- `wave_length` – Anzahl Kanäle pro voller Welle (Option, `/start`-Body
  **oder** je Bridge in `bridges`, Standard 3.0); klein = mehr, engere
  Wellenberge gleichzeitig sichtbar.
- `sweep_seconds` – Zeit, die die Welle für einen Durchlauf braucht.

`flicker` – Lampen brechen sporadisch kurz von voller Helligkeit ein, wie
eine defekte Glühbirne – das Gegenteil von `glitter` (hellt auf) oder
`lightning` (ein gemeinsamer Blitz) (`RedAlertFlicker` in `chase.py`):
- `flicker_interval_ms` – mittlerer Abstand zwischen zwei Einbrüchen über
  alle Lampen einer Bridge (Option, `/start`-Body **oder** je Bridge in
  `bridges`, Standard 600).
- `flicker_dip_ms` – wie schnell eine Lampe sich nach einem Einbruch wieder
  erholt (Standard 150).

`strobe` – ein hartes, sofortiges Blitzen in der Bridge-`color` ohne jede
Überblendung, anders als `pulse`s weiches Auf-/Abblenden – klassischer
Party-Look (`RedAlertStrobe` in `chase.py`):
- `sweep_seconds` – Periodendauer (Zeit zwischen zwei Blitzen).

`duel` – zwei Kometen starten an entgegengesetzten Enden der Kanäle – einer
in der Bridge-`color`, einer in `color2` –, treffen sich in der Mitte
und laufen zurück, anders als `meteor` (unabhängig, zufällig) oder `comet`
(ein einzelner, deterministischer Umlauf) (`RedAlertDuel` in `chase.py`):
- `sweep_seconds` – Periodendauer eines vollen Hin- und Rücklaufs.
- `color2` – Farbe des zweiten Kometen (Standard `#0000FF`).

`chase` – **nur für Gradient Lightstrips** (jeder Kanal ist ein
Farb-Segment, keine eigene Lampe): ein oder mehrere weich überblendete Bänder
in der Bridge-`color` laufen über die Segmente, dazwischen
`gc_background_color` (`RedAlertChase` in `chase.py`):
- `gc_count` – Anzahl gleichzeitig laufender Bänder, gleichmäßig verteilt
  (Standard 1).
- `gc_length` – Breite des vollfarbigen Kerns eines Bands in Segmenten
  (Standard 2.0); der Übergang zur Background-Farbe an den Rändern ist weich
  (~1 Segment) statt hart – daher „Gradient“.
- `gc_speed` – Segmente pro Sekunde, die ein Band-Kopf zurücklegt
  (Standard 4.0).
- `gc_direction` – `forward`/`backward` laufen endlos umlaufend (wie
  `comet`), `bounce` prallt an beiden Enden ab (Larson-Scanner) statt
  umzulaufen.
- `gc_chase_glitter` – lässt die Bänder zusätzlich wie `glitter` funkeln
  (nutzt `glitter_interval_ms`/`glitter_flash_ms`/`glitter_colors`), Funken
  nur innerhalb der Bänder.
- `gc_background_pulse` – lässt den Hintergrund zusätzlich wie `pulse`
  zwischen `glow_low` und `glow_high` pulsieren (nutzt `attack_ms`/
  `release_ms`/`sweep_seconds`), statt ruhig auf `glow_low` zu bleiben; die
  Bänder selbst bleiben davon unberührt auf `glow_high`.

Mehrere Gradient Lightstrips lassen sich kombinieren, indem ihre Segmente in
einer gemeinsamen Entertainment Area liegen – die Bridge sieht dann einen
einzigen, durchgehenden `channel_ids`-Strip. `gc_strip_lengths` (nur je
Bridge, z. B. `[7, 5]` bzw. `"7,5"`) teilt diesen kombinierten Strip wieder in
die einzelnen physischen Lightstrips auf, sodass sich `gc_direction`
**je Strip** setzen lässt (als Liste, z. B. `["forward", "backward"]`) – z. B.
damit zwei gegenüberliegende Strips aufeinander zu oder auseinander laufen.

`color_chase` – **Farbverlauf-Lauflicht** (`RedAlertColorChase` in `chase.py`):
ein Farbverlauf füllt sich Lampe für Lampe auf – jede Lampe schaltet beim
Vorbeilauf des Kopfs **sofort** auf ihre Zielfarbe und hält sie,
bis der nächste Durchlauf sie überschreibt. Drei Paletten laufen abwechselnd,
je ein linearer Verlauf von der Startfarbe (Chase-Index 0) zur voll gemischten
Farbe (letzter Chase-Index): `(255,0,0)→(255,255,0)`, `(0,255,0)→(0,255,255)`,
`(0,0,255)→(255,0,255)`.
- `gc_speed` – Lampen (Schritte) pro Sekunde; die Schrittdauer wird auf ganze
  Frames gerundet, damit jeder Schritt exakt gleich lang ist.
- `gc_direction` – `forward`/`backward` füllen immer vom selben Ende,
  `bounce` kehrt die Füllrichtung mit jeder Palette um.
- Absolute Farben, konstant auf `glow_high` (wie `rainbow`); nutzt keine
  `gc_strips`/`gc_count`/`gc_length`/`gc_background_color`.

`neutral` – die Lampen dieser Bridge werden **nicht** angesteuert: kein
DTLS-Stream, kein Sichern/Wiederherstellen. Sinnvoll nur je Bridge
(`bridges[].effect: neutral`), damit ein Effektset auf einer Bridge einen
Effekt fahren und eine andere Bridge komplett auslassen kann; eine
`neutral`-Bridge braucht keine `area_id`. Sind alle Bridges `neutral`,
antwortet `/start` mit `no_active_bridges` (kein Fehler).

### Effektsets

Unter „2 · Steuerung“ im Web-UI lässt sich der komplette Formularzustand (alle
Bridge-Karten + Steuerung) unter einem Namen speichern (`/data/presets.json`),
wieder **Laden**, als JSON-Datei **Herunterladen** / **Hochladen** und
**Löschen**. Jedes Set speichert die `area_id` pro Bridge mit; **Laden**
übernimmt sie als neue effektive Konfiguration (auch für Scharfschalten, die
HA-Integration und `rest_command`). Laden geht immer, solange nichts
scharfgeschaltet ist und keine Animation läuft; bei scharfer/laufender Bridge
nur, wenn das Set pro Bridge dieselbe `area_id` hat – dann läuft die Animation
sofort mit dem neuen Set weiter (kein Neustart), sonst Fehlermeldung. Per REST:
`GET/PUT/DELETE /presets`, `POST /select {"preset": "<Name>"}` und
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

## Projektstruktur

App-Store-Repository: `repository.yaml` im Wurzelverzeichnis, die App
selbst im Unterordner `redalert/`, die optionale Home-Assistant-Integration
in `custom_components/redalert/`.

```
.
├── repository.yaml              App-Store-Metadaten (name, url, maintainer)
├── README.md / README.en.md    Diese Datei (Repo-Überblick, DE/EN)
├── hacs.json                    macht dieses Repo als HACS-Integrations-
│                                Repository hinzufügbar (Kategorie „Integration“)
├── info.md                      HACS-Kurzbeschreibung der Integration
├── custom_components/redalert/ Home-Assistant-Integration (optional)
│   ├── manifest.json, const.py, api.py, coordinator.py, config_flow.py,
│   │   entity.py                REST-Client + Config-Flow + gemeinsame Basis-Entity
│   ├── binary_sensor.py / switch.py / select.py / sensor.py
│   │                             die sechs Entities – spricht nur die REST-API
│   │                             der App an, siehe README.md darin
│   ├── strings.json (Englisch) / translations/{de,en}.json
│   │                             Entity-/Config-Flow-Beschriftungen
│   │                             (strings.json ist zusätzlich die Quelle für
│   │                             die technischen Entity-IDs, siehe README dort)
│   └── brand/icon.png, brand/logo.png  Kopien der Store-Grafiken (für HA-UI)
├── redalert/                   >>> die eigentliche App <<<
│   ├── config.yaml              Manifest: Optionen, Ingress (kein LAN-Port)
│   ├── build.yaml               Basis-Images (home-assistant/base-python)
│   ├── Dockerfile               Image-Build
│   ├── requirements.txt         Python-Abhängigkeiten (hue-entertainment, aiohttp)
│   ├── DOCS.md / DOCS.en.md     In HA angezeigte Anleitung (Tab „Dokumentation“, DE/EN)
│   ├── CHANGELOG.md             Versionshistorie (Tab „Changelog“)
│   ├── icon.png / logo.png      Store-Grafiken
│   ├── translations/{de,en}.yaml  Beschriftung der Konfigurationsoberfläche
│   └── rootfs/
│       ├── etc/s6-overlay/…      Service-Definition (Start, bashio-Logging)
│       └── app/
│           ├── main.py           REST-Server + Streaming-Loop + Ingress-Panel
│           ├── chase.py          Effekt-Mathematik (18 Effekte, siehe §8)
│           └── panel.html        Web-UI (Steuerung)
```
