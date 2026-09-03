# Red Alert Entertainment

Rotes Star-Trek-„Alarmstufe Rot“-Lauflicht über mehrere Philips-Hue-Lampen,
gesteuert über die echte **Hue Entertainment API** (DTLS-Streaming, ~25 Hz –
nicht die träge Bridge-Szene), optional synchron zu deinem eigenen Alarm-Sound.

## Voraussetzungen

- Home Assistant **OS** oder **Supervised** (für Add-ons).
- Hue Bridge **V2** („quadratisch“) oder Hue Pro Bridge. V1-Bridges können kein
  Entertainment-Streaming.
- Mehrere farbfähige Hue-Lampen, einem **Entertainment-Bereich** zugeordnet
  (Hue-App → Einstellungen → Entertainment-Bereiche → Neuer Bereich). Die
  Reihenfolge, in der du die Lampen hinzufügst, bestimmt die Kanalreihenfolge.
- Ein `media_player` in HA (Sonos/Chromecast/…) für die Sound-Wiedergabe.
- Eine selbst bereitgestellte, legal erworbene Audiodatei mit dem Alarm-Sound.

## Installation

1. **Einstellungen → Add-ons → Add-on Store → ⋮ (oben rechts) → Repositories**
   und die URL dieses GitHub-Repositories hinzufügen.
2. Das Add-on **Red Alert Entertainment** aus dem Store installieren.
3. Optional „Start beim Booten“ aktivieren (empfohlen).
4. Add-on **starten**.

## Einrichtung

### 1 · Mit der Bridge pairen (einmalig)

Öffne das Web-UI (Seitenleisten-Eintrag **Red Alert**).

1. Physischen **Link-Button** auf der Hue Bridge drücken.
2. Innerhalb von ~30 s im Web-UI unter **„1 · Mit Bridge pairen“** die Bridge-IP
   eintragen und **Pairen** klicken.

`username` und `clientkey` werden automatisch unter `/data/credentials.json`
gespeichert – Pairing muss nur einmal gemacht werden.

Alternativ per REST:

```bash
curl -X POST http://<ha-ip>:8099/pair \
  -H "Content-Type: application/json" \
  -d '{"bridge_ip": "192.168.1.50"}'
```

### 2 · Entertainment-Bereich ermitteln

Im Web-UI **„Bereiche laden“** klicken – die Liste zeigt Name, `id` und
Kanäle. Mit **„übernehmen“** wird die `area_id` ins Steuerungsformular
übernommen. Trage sie zusätzlich als Add-on-Option **`area_id`** ein, damit
`rest_command`-Aufrufe ohne Body funktionieren, und starte das Add-on neu.

REST-Variante: `curl http://<ha-ip>:8099/areas`

### 3 · Steuerung

Im Web-UI unter **„3 · Steuerung“**: `area_id`, **Effekt**, Dauer (leer = Länge
der Cue-Datei), `cue_offset`, `fps`, `sweep_seconds`, Farbe, „Cue nutzen“ und
**`channel_order`** setzen, dann **Start** / **Stop**.

`channel_order` (leer = Bereichs-Standard) legt fest, in welcher Reihenfolge der
`chase`-Komet die Lampen durchläuft – als kommagetrennte Liste der
`channel_id`s, z. B. `2,3,1,0,5,4`. Es müssen genau die Kanäle des Bereichs
sein, nur in anderer Reihenfolge.

### 4 · Lampen zuordnen

Um herauszufinden, welche `channel_id` welche physische Lampe ist: Bereich
wählen, **„Bereiche laden“**, dann unter **„4 · Lampen zuordnen“** entweder
**„Alle Kanäle nacheinander“** (leuchtet 0, 1, 2, … je einige Sekunden rot auf)
oder einen einzelnen **„Kanal N“**-Button klicken. „Sekunden je Kanal“ steuert
die Leuchtdauer. Jeder Klick nutzt kurz den Entertainment-Stream (ein
DTLS-Handshake, ~3–9 s, dann leuchtet der Kanal). Danach wird der vorherige
Lampenzustand wiederhergestellt.

## Effekte

| `effect` | Verhalten |
|----------|-----------|
| `pulse` (Standard) | Alle Lampen **gemeinsam**: von `glow_low` linear auf `glow_high` im Takt der Musik, zwischen den Pulsen zurück auf `glow_low`. Ein Schmitt-Trigger auf der Cue-Hüllkurve macht aus jedem Beat ein sauberes Ein/Aus, der Anstieg läuft dadurch ruckelfrei-monoton hoch. `attack_ms` = Aufblend-, `release_ms` = Abblendzeit; `release_ms` kleiner = schnelleres Abfallen als Aufblenden. Ohne Cue: gleichmäßiger Puls mit Periode `sweep_seconds`. |
| `chase` | Ein Komet läuft **gleichmäßig in eine Richtung** um alle Kanäle (wraparound, konstante Geschwindigkeit). Jede Lampe für sich pulst dabei: **ganz kurz hell (`glow_high`), langes exponentielles Ausblenden, dann eine Ruhephase auf `glow_low`**, dann wieder; nacheinander ergibt das den Kometen mit Schweif. Optional durch die Cue gedimmt. |

**Lichtzustand:** Vor dem Effekt sichert das Add-on an/aus, Helligkeit und Farbe
aller Lampen des Bereichs (Hue CLIP v2) und schreibt sie nach dem Effekt zurück
– auch Lampen, die vorher aus waren, gehen wieder aus. Abschaltbar mit
`restore_state: false` (dann greift nur die automatische Wiederherstellung der
Bridge nach dem Stream-Ende).

## Konfiguration

| Option          | Typ                | Standard   | Bedeutung |
|-----------------|--------------------|------------|-----------|
| `bridge_host`   | String             | `""`       | IP der Hue Bridge. Optional, auch pro `/pair` übergebbar. |
| `area_id`       | String             | `""`       | ID des Entertainment-Bereichs (Schritt 2). |
| `channel_order` | String             | `""`       | Kanalreihenfolge für `chase` als kommagetrennte Liste, z. B. `2,3,1,0,5,4`. Leer = Bereichs-Standard. |
| `effect`        | `pulse` \| `chase` | `pulse`    | Lichteffekt, siehe oben. |
| `color`         | Hex-String         | `#FF0000`  | Farbe des Effekts. |
| `fps`           | int (5–50)         | `25`       | Frames/Sekunde des DTLS-Streams. |
| `sweep_seconds` | float (0.3–5.0)    | `1.4`      | `chase`: Dauer einer vollen Umrundung. `pulse` ohne Cue: Zyklusdauer. |
| `attack_ms`     | int (0–2000)       | `140`      | `pulse`: Aufblendzeit `glow_low` → `glow_high`. |
| `release_ms`    | int (0–5000)       | `70`       | `pulse`: Abblendzeit → `glow_low` zwischen den Pulsen (kleiner als `attack_ms` = schnelleres Abfallen). |
| `glow_low`      | float (0–1)        | `0.08`     | **Beide Effekte:** Ruhe-Helligkeit zwischen den Pulsen. `0` = ganz aus. |
| `glow_high`     | float (0–1)        | `1.0`      | **Beide Effekte:** Helligkeit im Puls-Maximum. Muss über `glow_low` liegen. |
| `restore_state` | bool               | `true`     | Lampenzustand (an/aus, Helligkeit, Farbe) vor dem Effekt sichern und danach wiederherstellen. |
| `cue_file`      | String             | `""`       | Pfad zu alternativer `redalert_cue.json` (z. B. `/share/…`). |
| `log_level`     | Liste              | `info`     | `trace`,`debug`,`info`,`notice`,`warning`,`error`,`fatal`. |

## REST-API

Erreichbar unter `http://<ha-ip>:8099` (Port) bzw. über Ingress (relativ zum
Panel-Pfad).

| Endpoint  | Methode | Zweck |
|-----------|---------|-------|
| `/`       | GET     | Web-UI (Ingress-Panel). |
| `/health` | GET     | `{status, paired, running}` – auch Ziel des Container-HEALTHCHECK. |
| `/config` | GET     | Effektive Konfiguration (für das Web-UI). |
| `/pair`   | POST    | Einmalige Kopplung. Body: `{"bridge_ip": "..."}` (optional bei gesetzter Option). |
| `/areas`  | GET     | Entertainment-Bereiche + Kanäle auflisten. |
| `/start`  | POST    | Effekt starten (antwortet sofort; DTLS-Handshake läuft im Hintergrund). Body optional: `area_id`, `effect`, `duration`, `cue_offset`, `fps`, `sweep_seconds`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `color`, `use_cue`, `restore_state`, `channel_order`. `channel_order` als Liste (`[2,3,1,0,5,4]`) oder String (`"2,3,1,0,5,4"`); muss genau die Kanäle des Bereichs in gewünschter Reihenfolge enthalten, sonst `400`. |
| `/stop`   | POST    | Effekt sofort stoppen. |
| `/sync`   | POST    | Laufende Feinsynchronisation. Body: `{"position": <Sekunden im Track>}` – die echte Wiedergabeposition des media_player. Der Licht-Cue wird um die Differenz nachgezogen (max. ±0,5 s pro Aufruf, damit nichts springt). `409`, wenn kein Effekt läuft. |
| `/identify` | POST  | Lampen einzeln durchtesten (Zuordnung `channel_id` → Lampe). Body optional: `area_id`, `channel_id` (fehlt = alle Kanäle nacheinander), `seconds` (Standard 3 einzeln / 2 bei „alle“), `color`, `restore_state`. Ein DTLS-Handshake für den ganzen Durchlauf. Belegt denselben Slot wie `/start` (`already_running`, `/stop` bricht ab). |

- `duration` weglassen → bei aktiver Cue-Datei deren Restlänge ab `cue_offset`,
  sonst läuft der Effekt bis `/stop`.
- `cue_offset` (Sekunden) = an welcher Stelle der Cue der Effekt beginnt. Damit
  richtest du das Licht auf die schon laufende Musik aus (siehe
  [Synchronisation zur Musik](#synchronisation-zur-musik)).

## Home Assistant einbinden

`configuration.yaml`:

```yaml
rest_command:
  redalert_start:
    url: "http://<ha-ip>:8099/start"
    method: POST
    content_type: "application/json"
    payload: >-
      {"cue_offset": {{ offset | default(0) }}}
  redalert_sync:
    url: "http://<ha-ip>:8099/sync"
    method: POST
    content_type: "application/json"
    payload: '{"position": {{ position }}}'
  redalert_stop:
    url: "http://<ha-ip>:8099/stop"
    method: POST
```

Einfache Automation (Sound + Licht gemeinsam, fester Versatz):

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

## Synchronisation zur Musik

**Kurzantwort:** exakt geht es nur, wenn *eine* Uhr beides steuert. Hier spielt
Home Assistant den Ton auf einem `media_player`, das Add-on das Licht – zwei
unabhängige Zeitachsen. „Beides gleichzeitig auslösen“ heißt **nicht** „beides
kommt gleichzeitig raus“. Die Lösung: (1) Start-Jitter beseitigen und (2) das
Licht laufend an der **echten Wiedergabeposition** des Players ausrichten.

### Die drei Fehlerquellen

1. **Start-Versatz.** Schon der DTLS-Handshake zur Bridge dauert 3–9 s und
   schwankt; dazu Puffer im Lautsprecher (Sonos & Co. oft 0,3–0,8 s). Der Ton
   läuft also, bevor die erste helle Lichtframe kommt.
2. **Drift.** Licht-Loop (monotone Uhr, 25 fps) und Player-Uhr laufen minimal
   verschieden schnell – über eine Minute einige 10 ms.
3. **Cue-Auflösung.** Die Cue wird alle 10 ms abgetastet und interpoliert; feiner
   wird's mit höherem `--fps` beim Erzeugen und höherem `fps` im Add-on.

Gegen (2) plant der Effekt-Loop seine Frames seit 1.1.0 gegen eine absolute Uhr –
die Licht-Zeitachse driftet nicht mehr gegen die Wanduhr. Bleiben (1) und (3).

### Empfohlenes Vorgehen (geschlossene Regelschleife)

1. **Ton starten**, kurz warten (~1 s), bis der Player wirklich spielt.
2. **Position lesen** und als `cue_offset` an `/start` geben. Die echte Position
   jetzt ist
   `media_position + (now() - media_position_updated_at)`.
3. **Nachführen:** alle 3–5 s die Position erneut lesen und an `/sync` schicken.
   Das Add-on zieht den Licht-Cue an die Position heran – pro Aufruf max. ±0,5 s,
   also unsichtbar, solange regelmäßig gesynct wird. Das fängt auch den
   Handshake-Verzug und die Lautsprecher-Latenz mit ein.
4. **Feinversatz** (einmalig messen): die konstante Restlatenz deines
   Lautsprechers von der gemessenen Position abziehen, bevor du sie sendest.

```yaml
automation:
  - alias: "Alarmstufe Rot – synchron"
    trigger:
      - platform: state
        entity_id: input_boolean.red_alert
        to: "on"
    variables:
      player: media_player.wohnzimmer
      speaker_latency: 0.4   # einmalig für deinen Lautsprecher messen
    action:
      - service: media_player.play_media
        target: { entity_id: "{{ player }}" }
        data:
          media_content_id: media-source://media_source/local/red_alert.mp3
          media_content_type: audio/mpeg
      - delay: "00:00:01"
      - service: rest_command.redalert_start
        data:
          offset: >-
            {{ (state_attr(player,'media_position') | float(0))
               + (now() - state_attr(player,'media_position_updated_at')).total_seconds()
               - speaker_latency }}
      # laufend nachführen, solange der Player spielt
      - repeat:
          while:
            - condition: template
              value_template: "{{ is_state(player, 'playing') }}"
          sequence:
            - service: rest_command.redalert_sync
              data:
                position: >-
                  {{ (state_attr(player,'media_position') | float(0))
                     + (now() - state_attr(player,'media_position_updated_at')).total_seconds()
                     - speaker_latency }}
            - delay: "00:00:03"

  - alias: "Alarmstufe Rot – Ende"
    trigger:
      - platform: state
        entity_id: media_player.wohnzimmer
        to: "idle"
    action:
      - service: rest_command.redalert_stop
```

### Wenn du die Regelschleife nicht willst

Reicht meist auch: **konstanten Versatz einmal messen** (Ton vs. Licht mit dem
Handy filmen), Ton und Licht aus derselben Automation mit festem `delay:`
dazwischen starten und einen passenden `cue_offset` setzen. Für einen Puls sind
±50–100 ms kaum sichtbar. Der größte Brocken bleibt der Handshake – ihn
verkleinert am wirksamsten ein dauerhaft offener Stream (geplante Option
`keep_stream_warm`, noch nicht enthalten).

### Was hier bewusst *nicht* geht

Live-Beaterkennung aus dem laufenden Ton – das Add-on „hört“ die Musik nicht,
es kennt nur die vorab erzeugte Cue. Und der Ton im Add-on selbst abspielen
(eine Uhr für beides) scheitert daran, dass HA-Add-ons i. d. R. keine
Audio-Hardware erreichen und du Multiroom verlierst.

## Audio-Sync per Cue-Datei

Das Add-on lädt eine `redalert_cue.json`: eine reine Zahlenfolge (Helligkeit
0–1 pro Frame), abgeleitet aus der Lautstärke-Hüllkurve deiner Audiodatei –
**keine Audiodaten**. Bei `pulse` ist diese Kurve direkt die gemeinsame
Helligkeit aller Lampen; bei `chase` dimmt sie den durchlaufenden Kometen, der
so nur bei Ton sichtbar hell wird.

Eine vorgefertigte Cue liegt bei. Für einen anderen Sound-Clip:

```bash
python3 tools/generate_cue.py meine_datei.mp3 redalert_cue.json --fps 25
```

Benötigt `ffmpeg` sowie `pip install numpy` (`scipy` optional). Ergebnis
entweder ins Add-on einbauen (`redalert/rootfs/app/redalert_cue.json` ersetzen,
neu bauen) oder unter `/share/` ablegen und `cue_file: /share/redalert_cue.json`
setzen (nur Add-on-Neustart nötig).

## Protokoll

Das Add-on-**Protokoll** (Log-Tab) zeigt Konfiguration beim Start, Pairing-,
Start-/Stop-Ereignisse und Fehler. Ausführlichkeit über `log_level`. Das Web-UI
zeigt zusätzlich die letzten API-Antworten im Abschnitt „Protokoll (Antworten)“.

## Fehlerbehebung

| Symptom | Ursache / Lösung |
|---------|------------------|
| `/pair` schlägt fehl | Link-Button nicht rechtzeitig gedrückt (~30 s) oder falsche IP. |
| `/start` → `already_running` | Erst `/stop` aufrufen. |
| `/start` → 404 `area_id nicht gefunden` | `/areas` prüfen – Bereich evtl. umbenannt/gelöscht. |
| `/start` → 502 `Bridge nicht erreichbar` | Bridge-IP geändert? Netzwerk/VLAN zwischen HA-Host und Bridge (UDP 2100). |
| Licht startet erst nach einigen Sekunden | Normaler DTLS-Handshake; bei WLAN-Bridges teils ein `ServerHello timeout`-Retry im Protokoll. `/start` selbst antwortet trotzdem sofort. |
| Lampen reagieren nicht | V1-Bridge (kein Entertainment) oder UDP-Port 2100 zur Bridge blockiert. |
| Streaming bricht ab | Die Bridge erlaubt nur **einen** aktiven Entertainment-Stream – Hue-Sync-App/andere Clients schließen. |
| Lauflicht ruckelt | `fps` erhöhen oder Netzlast zur Bridge prüfen. |
| Start bricht ab mit `/bin/sh: can't open '/init': Permission denied` | Behoben ab 1.0.1 (kein eigenes AppArmor-Profil mehr). Add-on aktualisieren; ältere Version deinstallieren und neu installieren, falls das Update nicht greift. |

## Rechtlicher Hinweis zur Audiodatei

Das Add-on kümmert sich ausschließlich um das Licht. Den Alarmstufe-Rot-Sound
musst du selbst aus einer legal erworbenen Quelle bereitstellen. Die
mitgelieferte `redalert_cue.json` enthält keinerlei Audiomaterial, sondern nur
eine daraus abgeleitete numerische Helligkeitskurve.
