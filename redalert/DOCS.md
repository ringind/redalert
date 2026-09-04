# Red Alert Entertainment

Rotes Star-Trek-„Alarmstufe Rot“-Lauflicht über mehrere Philips-Hue-Lampen,
gesteuert über die echte **Hue Entertainment API** (DTLS-Streaming, ~25 Hz –
nicht die träge Bridge-Szene).

## Voraussetzungen

- Home Assistant **OS** oder **Supervised** (für Add-ons).
- Hue Bridge **V2** („quadratisch“) oder Hue Pro Bridge. V1-Bridges können kein
  Entertainment-Streaming.
- Mehrere farbfähige Hue-Lampen, einem **Entertainment-Bereich** zugeordnet
  (Hue-App → Einstellungen → Entertainment-Bereiche → Neuer Bereich). Die
  Reihenfolge, in der du die Lampen hinzufügst, bestimmt die Kanalreihenfolge.

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

Im Web-UI unter **„3 · Steuerung“**: `area_id`, **Effekt**, Dauer (leer = 30 s),
`fps`, `sweep_seconds`, `chase_pause`, Farbe und **`channel_order`** setzen,
dann **Start** / **Stop**. Die beiden Knöpfe zeigen per gedrücktem Zustand an,
ob der Effekt gerade läuft.

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
| `pulse` (Standard) | Alle Lampen **gemeinsam**: von `glow_low` linear auf `glow_high` und zurück, ein voller Zyklus alle `sweep_seconds`. Ein Schmitt-Trigger auf dem periodischen Signal macht daraus ein sauberes Ein/Aus, der Anstieg läuft dadurch ruckelfrei-monoton hoch. `attack_ms` = Aufblend-, `release_ms` = Abblendzeit; `release_ms` kleiner = schnelleres Abfallen als Aufblenden. |
| `chase` | Ein Komet läuft **gleichmäßig in eine Richtung** um alle Kanäle (wraparound, konstante Geschwindigkeit) mit Zykluszeit `sweep_seconds`. Jede Lampe für sich pulst dabei: **kurz hell (`glow_high`), langes exponentielles Ausblenden, dann eine Ruhephase auf `glow_low`**, dann wieder. Der Kopf ist etwas breiter als der Lampenabstand – zwei benachbarte Lampen stehen kurz gemeinsam auf 100 % und glühen dann nacheinander aus, sodass immer mindestens eine Lampe voll leuchtet. Mit `chase_pause > 0` macht der Komet **einen** Durchlauf, danach ruhen alle Lampen `chase_pause` Sekunden auf `glow_low`, dann der nächste. |

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
| `sweep_seconds` | float (0.3–5.0)    | `1.4`      | `chase`: Dauer einer vollen Umrundung. `pulse`: Zyklusdauer. |
| `chase_pause`   | float (0–60)       | `0`        | `chase`: Pause (Sekunden) zwischen zwei Durchläufen. `0` = durchgehend umlaufender Komet. `> 0` = ein Durchlauf, dann alle Lampen für so viele Sekunden auf `glow_low`, dann der nächste. |
| `attack_ms`     | int (0–2000)       | `140`      | `pulse`: Aufblendzeit `glow_low` → `glow_high`. |
| `release_ms`    | int (0–5000)       | `70`       | `pulse`: Abblendzeit → `glow_low` zwischen den Pulsen (kleiner als `attack_ms` = schnelleres Abfallen). |
| `glow_low`      | float (0–1)        | `0.08`     | **Beide Effekte:** Ruhe-Helligkeit zwischen den Pulsen. `0` = ganz aus. |
| `glow_high`     | float (0–1)        | `1.0`      | **Beide Effekte:** Helligkeit im Puls-Maximum. Muss über `glow_low` liegen. |
| `restore_state` | bool               | `true`     | Lampenzustand (an/aus, Helligkeit, Farbe) vor dem Effekt sichern und danach wiederherstellen. |
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
| `/start`  | POST    | Effekt starten (antwortet sofort; DTLS-Handshake läuft im Hintergrund). Body optional: `area_id`, `effect`, `duration`, `fps`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `color`, `restore_state`, `channel_order`. `channel_order` als Liste (`[2,3,1,0,5,4]`) oder String (`"2,3,1,0,5,4"`); muss genau die Kanäle des Bereichs in gewünschter Reihenfolge enthalten, sonst `400`. |
| `/stop`   | POST    | Effekt sofort stoppen. |
| `/identify` | POST  | Lampen einzeln durchtesten (Zuordnung `channel_id` → Lampe). Body optional: `area_id`, `channel_id` (fehlt = alle Kanäle nacheinander), `seconds` (Standard 3 einzeln / 2 bei „alle“), `color`, `restore_state`. Ein DTLS-Handshake für den ganzen Durchlauf. Belegt denselben Slot wie `/start` (`already_running`, `/stop` bricht ab). |

- `duration` (Sekunden, **Standard 30**) – wie lange der Effekt läuft, bevor er
  von selbst endet; vorher jederzeit per `/stop` abbrechbar.

## Home Assistant einbinden

`configuration.yaml`:

```yaml
rest_command:
  redalert_start:
    url: "http://<ha-ip>:8099/start"
    method: POST
    content_type: "application/json"
    payload: >-
      {"duration": {{ duration | default(30) }}}
  redalert_stop:
    url: "http://<ha-ip>:8099/stop"
    method: POST
```

Einfache Automation (Sound + Licht gemeinsam):

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

## Protokoll

Das Add-on-**Protokoll** (Log-Tab) zeigt Konfiguration beim Start, Pairing-,
Start-/Stop-Ereignisse und Fehler. Ausführlichkeit über `log_level`. Das Web-UI
zeigt zusätzlich die letzten API-Aufrufe im Abschnitt „Protokoll“ – die
Checkbox „Anfragen einblenden“ zeigt zusätzlich die gesendeten Request-Bodys,
und die Knöpfe daneben löschen das Protokoll oder laden es als Textdatei
herunter.

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

Das Add-on kümmert sich ausschließlich um das Licht. Spielst du wie im
Automations-Beispiel oben zusätzlich einen Alarmstufe-Rot-Sound über einen
`media_player` ab, musst du diese Audiodatei selbst aus einer legal erworbenen
Quelle bereitstellen.
