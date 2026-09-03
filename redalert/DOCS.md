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

Im Web-UI unter **„3 · Steuerung“**: `area_id`, Dauer (leer = Länge der
Cue-Datei), `fps`, `sweep_seconds`, Farbe und „Cue nutzen“ setzen, dann
**Start** / **Stop**.

## Konfiguration

| Option          | Typ                | Standard   | Bedeutung |
|-----------------|--------------------|------------|-----------|
| `bridge_host`   | String             | `""`       | IP der Hue Bridge. Optional, auch pro `/pair` übergebbar. |
| `area_id`       | String             | `""`       | ID des Entertainment-Bereichs (Schritt 2). |
| `channel_order` | Liste[int]         | `[]`       | Explizite Kanalreihenfolge für den Sweep. Leer = Bereichs-Standard. |
| `color`         | Hex-String         | `#FF0000`  | Farbe des Lauflichts. |
| `fps`           | int (5–50)         | `25`       | Frames/Sekunde des DTLS-Streams. |
| `sweep_seconds` | float (0.3–5.0)    | `1.4`      | Dauer eines Durchlaufs über alle Lampen. |
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
| `/start`  | POST    | Lauflicht starten (antwortet sofort; DTLS-Handshake läuft im Hintergrund). Body optional: `area_id`, `duration`, `fps`, `sweep_seconds`, `color`, `use_cue`. |
| `/stop`   | POST    | Lauflicht sofort stoppen. |

`duration` weglassen → bei aktiver Cue-Datei deren Länge, sonst läuft der Effekt
bis `/stop`.

## Home Assistant einbinden

`configuration.yaml`:

```yaml
rest_command:
  redalert_start:
    url: "http://<ha-ip>:8099/start"
    method: POST
    content_type: "application/json"
    payload: '{}'
  redalert_stop:
    url: "http://<ha-ip>:8099/stop"
    method: POST
```

Automation (Sound + Licht gemeinsam):

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

## Audio-Sync per Cue-Datei

Das Add-on lädt eine `redalert_cue.json`: eine reine Zahlenfolge (Helligkeit
0–1 pro Frame), abgeleitet aus der Lautstärke-Hüllkurve deiner Audiodatei –
**keine Audiodaten**. Der Comet-Sweep läuft durchgehend, wird aber nur dann
sichtbar hell, wenn im Original etwas zu hören ist.

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
