# Red Alert Entertainment

Rotes Star-Trek-„Alarmstufe Rot“-Lauflicht über mehrere Philips-Hue-Lampen,
gesteuert über die echte **Hue Entertainment API** (DTLS-Streaming, ~25 Hz –
nicht die träge Bridge-Szene). Unterstützt **bis zu 3 Hue Bridges**, die
gleichzeitig loslegen – jede mit ihrem eigenen Effekt, ihrer eigenen Farbe
und eigenem Timing.

## Voraussetzungen

- Home Assistant **OS** oder **Supervised** (für Add-ons).
- Eine bis drei Hue Bridge **V2** („quadratisch“) oder Hue Pro Bridge. V1-Bridges
  können kein Entertainment-Streaming.
- Pro Bridge: mehrere farbfähige Hue-Lampen, einem **Entertainment-Bereich**
  zugeordnet (Hue-App → Einstellungen → Entertainment-Bereiche → Neuer Bereich).
  Die Reihenfolge, in der du die Lampen hinzufügst, bestimmt die Kanalreihenfolge.

## Installation

1. **Einstellungen → Add-ons → Add-on Store → ⋮ (oben rechts) → Repositories**
   und die URL dieses GitHub-Repositories hinzufügen.
2. Das Add-on **Red Alert Entertainment** aus dem Store installieren.
3. Optional „Start beim Booten“ aktivieren (empfohlen).
4. Add-on **starten**.

## Einrichtung

Öffne das Web-UI (Seitenleisten-Eintrag **Red Alert**). Unter **„1 · Bridges“**
gibt es 3 gleich aufgebaute Karten, eine je Bridge – für eine einzelne Bridge
reicht die erste, leer gelassene Karten werden ignoriert.

### 1 · Bridges (pro Bridge wiederholen)

1. Physischen **Link-Button** auf der Hue Bridge drücken.
2. Innerhalb von ~30 s in der Bridge-Karte die **Bridge-IP** eintragen und
   **Pairen** klicken. `username`/`clientkey` werden automatisch unter
   `/data/credentials.json` gespeichert (pro Bridge) – Pairing muss nur einmal
   gemacht werden.
3. **„Bereiche laden“** klicken – die Liste zeigt Name, `id` und Kanäle.
   Mit **„übernehmen“** wird die `area_id` ins Feld der Karte übernommen.
4. Optional **`channel_order`** setzen (siehe unten). Über **„Lampen
   zuordnen“** (aufklappbar) lässt sich herausfinden, welche `channel_id`
   welche physische Lampe ist: entweder **„Alle Kanäle nacheinander“**
   (leuchtet 0, 1, 2, … je einige Sekunden rot auf) oder einen einzelnen
   **„Kanal N“**-Button klicken. Jeder Klick nutzt kurz den
   Entertainment-Stream (ein DTLS-Handshake, ~3–9 s, dann leuchtet der Kanal);
   danach wird der vorherige Lampenzustand wiederhergestellt.
5. Optional über **„Effekt für diese Bridge anpassen“** (aufklappbar) einen
   eigenen Effekt/Farbe/Timing nur für diese Bridge setzen – leer gelassene
   Felder übernehmen den Standard aus „2 · Steuerung“.

Trage Bridge-IP, `area_id` (und optional `channel_order` sowie die
Effekt-Overrides) zusätzlich als Zeile der Add-on-Option **`bridges`** ein,
damit `rest_command`-Aufrufe ohne Body funktionieren, und starte das Add-on
neu.

Alternativ per REST: `POST /pair` (Body `{"bridge_host": "192.168.1.50"}`),
`GET /areas?bridge_host=192.168.1.50`.

`channel_order` (leer = Bereichs-Standard) legt fest, in welcher Reihenfolge der
`chase`-Komet die Lampen dieser Bridge durchläuft – als kommagetrennte Liste
der `channel_id`s, z. B. `2,3,1,0,5,4`. Es müssen genau die Kanäle des
Bereichs sein, nur in anderer Reihenfolge.

### 2 · Steuerung

Im Web-UI unter **„2 · Steuerung“**: Dauer (leer = 30 s) und `fps` gelten
immer für **alle** Bridges gemeinsam. **Effekt**, `sweep_seconds`,
`chase_pause`, `glow_low`/`glow_high` und Farbe sind hier der **Standard** für
jede Bridge, die diese Werte nicht in ihrer eigenen Karte (siehe „1 ·
Bridges“) überschreibt. **Start** / **Stop** starten/stoppen alle
eingerichteten Bridges gleichzeitig; die beiden Knöpfe zeigen per gedrücktem
Zustand an, ob der Effekt gerade läuft.

## Effekte

| `effect` | Verhalten |
|----------|-----------|
| `pulse` (Standard) | Alle Lampen **gemeinsam**: von `glow_low` linear auf `glow_high` und zurück, ein voller Zyklus alle `sweep_seconds`. Ein Schmitt-Trigger auf dem periodischen Signal macht daraus ein sauberes Ein/Aus, der Anstieg läuft dadurch ruckelfrei-monoton hoch. `attack_ms` = Aufblend-, `release_ms` = Abblendzeit; `release_ms` kleiner = schnelleres Abfallen als Aufblenden. |
| `chase` | Ein Komet läuft **gleichmäßig in eine Richtung** um alle Kanäle (wraparound, konstante Geschwindigkeit) mit Zykluszeit `sweep_seconds`. Jede Lampe für sich pulst dabei: **kurz hell (`glow_high`), langes exponentielles Ausblenden, dann eine Ruhephase auf `glow_low`**, dann wieder. Der Kopf ist etwas breiter als der Lampenabstand – zwei benachbarte Lampen stehen kurz gemeinsam auf 100 % und glühen dann nacheinander aus, sodass immer mindestens eine Lampe voll leuchtet. Mit `chase_pause > 0` macht der Komet **einen** Durchlauf, danach ruhen alle Lampen `chase_pause` Sekunden auf `glow_low`, dann der nächste. |

**Mehrere Bridges:** Läuft mehr als eine Bridge, starten alle **gleichzeitig**
– die DTLS-Handshakes aller Bridges laufen parallel, und die gemeinsame
Effekt-Uhr beginnt erst, wenn alle fertig sind, damit keine Bridge nachhinkt.
Jede Bridge kann dabei ihren **eigenen** Effekt, ihre eigene Farbe und ihr
eigenes Timing haben (`effect`, `color`, `sweep_seconds`, `chase_pause`,
`attack_ms`, `release_ms`, `glow_low`, `glow_high` sind je Bridge
überschreibbar; nicht überschriebene Werte gelten aus „2 · Steuerung“ bzw. den
gleichnamigen Add-on-Optionen). `area_id` und `channel_order` sind immer je
Bridge eigene Werte; `duration`, `fps` und `restore_state` gelten dagegen
immer für alle Bridges gemeinsam. Ist eine Bridge nicht erreichbar oder nicht
gepaart, starten die übrigen trotzdem („best effort“) – die fehlgeschlagene
wird in der `/start`-Antwort unter `failed_bridges` gemeldet.

**Lichtzustand:** Vor dem Effekt sichert das Add-on an/aus, Helligkeit und Farbe
aller Lampen jedes Bereichs (Hue CLIP v2) und schreibt sie nach dem Effekt zurück
– auch Lampen, die vorher aus waren, gehen wieder aus. Abschaltbar mit
`restore_state: false` (dann greift nur die automatische Wiederherstellung der
Bridge nach dem Stream-Ende).

## Konfiguration

| Option          | Typ                | Standard   | Bedeutung |
|-----------------|--------------------|------------|-----------|
| `bridges`       | Liste (max. 3)     | `[]`       | Eine Zeile pro Bridge: `bridge_host` (IP), `area_id` (Schritt 1), optional `channel_order` sowie je Bridge optional `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high` (überschreiben die gleichnamige Option unten nur für diese Bridge). |
| `effect`        | `pulse` \| `chase` | `pulse`    | Standard-Lichteffekt für Bridges ohne eigene Einstellung, siehe oben. |
| `color`         | Hex-String         | `#FF0000`  | Standard-Farbe für Bridges ohne eigene Einstellung. |
| `fps`           | int (5–50)         | `25`       | Frames/Sekunde des DTLS-Streams (für alle Bridges gleich). |
| `sweep_seconds` | float (0.3–5.0)    | `1.4`      | Standard für Bridges ohne eigene Einstellung. `chase`: Dauer einer vollen Umrundung. `pulse`: Zyklusdauer. |
| `chase_pause`   | float (0–60)       | `0`        | Standard für Bridges ohne eigene Einstellung. `chase`: Pause (Sekunden) zwischen zwei Durchläufen. `0` = durchgehend umlaufender Komet. `> 0` = ein Durchlauf, dann alle Lampen für so viele Sekunden auf `glow_low`, dann der nächste. |
| `attack_ms`     | int (0–2000)       | `140`      | Standard für Bridges ohne eigene Einstellung. `pulse`: Aufblendzeit `glow_low` → `glow_high`. |
| `release_ms`    | int (0–5000)       | `70`       | Standard für Bridges ohne eigene Einstellung. `pulse`: Abblendzeit → `glow_low` zwischen den Pulsen (kleiner als `attack_ms` = schnelleres Abfallen). |
| `glow_low`      | float (0–1)        | `0.08`     | Standard für Bridges ohne eigene Einstellung. **Beide Effekte:** Ruhe-Helligkeit zwischen den Pulsen. `0` = ganz aus. |
| `glow_high`     | float (0–1)        | `1.0`      | Standard für Bridges ohne eigene Einstellung. **Beide Effekte:** Helligkeit im Puls-Maximum. Muss über `glow_low` liegen. |
| `restore_state` | bool               | `true`     | Lampenzustand (an/aus, Helligkeit, Farbe) vor dem Effekt sichern und danach wiederherstellen (für alle Bridges gleich). |
| `log_level`     | Liste              | `info`     | `trace`,`debug`,`info`,`notice`,`warning`,`error`,`fatal`. |

## REST-API

Erreichbar unter `http://<ha-ip>:8099` (Port) bzw. über Ingress (relativ zum
Panel-Pfad).

| Endpoint  | Methode | Zweck |
|-----------|---------|-------|
| `/`       | GET     | Web-UI (Ingress-Panel). |
| `/health` | GET     | `{status, paired, running}` – `paired` ist `true`, sobald mindestens eine Bridge gepaart ist. Auch Ziel des Container-HEALTHCHECK. |
| `/config` | GET     | Effektive Konfiguration inkl. `bridges` (für das Web-UI). |
| `/pair`   | POST    | Einmalige Kopplung. Body: `{"bridge_host": "..."}` – Pflicht, sobald mehr als eine Bridge konfiguriert ist (bei genau einer, noch ungepaarten, konfigurierten Bridge optional). |
| `/areas`  | GET     | Entertainment-Bereiche + Kanäle einer Bridge auflisten. Query `?bridge_host=...` – Pflicht, sobald mehr als eine Bridge gepaart ist. |
| `/start`  | POST    | Effekt auf allen konfigurierten (oder im Body übergebenen) Bridges gleichzeitig starten (antwortet sofort; DTLS-Handshakes laufen im Hintergrund, parallel). Body optional: `duration`, `fps`, `restore_state` gelten für alle Bridges gemeinsam; `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high` sind die **Standardwerte** für Bridges ohne eigene Einstellung. `bridges` (Liste von `{bridge_host, area_id, channel_order, effect?, color?, sweep_seconds?, chase_pause?, attack_ms?, release_ms?, glow_low?, glow_high?}`) übersteuert für diesen Aufruf die Option `bridges` – jede Bridge kann ihre eigenen Effekt-Parameter setzen; `channel_order` als Liste (`[2,3,1,0,5,4]`) oder String (`"2,3,1,0,5,4"`), muss genau die Kanäle des jeweiligen Bereichs enthalten, sonst wird diese eine Bridge übersprungen. Antwort enthält `bridges` (tatsächlich gestartet, je mit aufgelösten Effekt-Parametern) und `failed_bridges` (übersprungen, mit Fehlergrund); nur wenn **keine** Bridge startet, antwortet `/start` mit `502`. |
| `/stop`   | POST    | Effekt auf allen laufenden Bridges sofort stoppen. |
| `/identify` | POST  | Lampen einer Bridge einzeln durchtesten (Zuordnung `channel_id` → Lampe). Body: `bridge_host` (Pflicht, sobald mehr als eine Bridge konfiguriert ist), `area_id` (optional, sonst aus der bridges-Konfiguration), `channel_id` (fehlt = alle Kanäle nacheinander), `seconds` (Standard 3 einzeln / 2 bei „alle“), `color`, `restore_state`. Ein DTLS-Handshake für den ganzen Durchlauf. Belegt denselben Slot wie `/start` (`already_running`, `/stop` bricht ab). |

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
| `/start` → 502 `Bridge nicht erreichbar` | Bridge-IP geändert? Netzwerk/VLAN zwischen HA-Host und Bridge (UDP 2100). Bei mehreren Bridges bedeutet `502` nur, dass **keine** davon erreichbar war – einzelne Ausfälle stehen in `failed_bridges` der `/start`-Antwort, die übrigen Bridges laufen trotzdem. |
| Licht startet erst nach einigen Sekunden | Normaler DTLS-Handshake; bei WLAN-Bridges teils ein `ServerHello timeout`-Retry im Protokoll. `/start` selbst antwortet trotzdem sofort. |
| Lampen reagieren nicht | V1-Bridge (kein Entertainment) oder UDP-Port 2100 zur Bridge blockiert. |
| Streaming bricht ab | Jede Bridge erlaubt nur **einen** aktiven Entertainment-Stream (pro Bridge, nicht global) – Hue-Sync-App/andere Clients auf derselben Bridge schließen. |
| Lauflicht ruckelt | `fps` erhöhen oder Netzlast zur Bridge prüfen. |
| Start bricht ab mit `/bin/sh: can't open '/init': Permission denied` | Behoben ab 1.0.1 (kein eigenes AppArmor-Profil mehr). Add-on aktualisieren; ältere Version deinstallieren und neu installieren, falls das Update nicht greift. |

## Rechtlicher Hinweis zur Audiodatei

Das Add-on kümmert sich ausschließlich um das Licht. Spielst du wie im
Automations-Beispiel oben zusätzlich einen Alarmstufe-Rot-Sound über einen
`media_player` ab, musst du diese Audiodatei selbst aus einer legal erworbenen
Quelle bereitstellen.
