# Red Alert Entertainment

🇩🇪 Deutsch (diese Datei) · 🇬🇧 [English](DOCS.en.md)

Rotes Star-Trek-„Alarmstufe Rot“-Lauflicht über mehrere Philips-Hue-Lampen,
gesteuert über die echte **Hue Entertainment API** (DTLS-Streaming, ~25 Hz –
nicht die träge Bridge-Szene). Unterstützt **bis zu 3 Hue Bridges**, die
gleichzeitig loslegen – jede mit ihrem eigenen Effekt, ihrer eigenen Farbe
und eigenem Timing.

## Voraussetzungen

- Home Assistant **OS** oder **Supervised** (für Apps).
- Eine bis drei Hue Bridge **V2** („quadratisch“) oder Hue Pro Bridge. V1-Bridges
  können kein Entertainment-Streaming.
- Pro Bridge: mehrere farbfähige Hue-Lampen, einem **Entertainment-Bereich**
  zugeordnet (Hue-App → Einstellungen → Entertainment-Bereiche → Neuer Bereich).
  Die Reihenfolge, in der du die Lampen hinzufügst, bestimmt die Kanalreihenfolge.

## Installation

1. **Einstellungen → Apps → App Store → ⋮ (oben rechts) → Repositories**
   und die URL dieses GitHub-Repositories hinzufügen.
2. Die App **Red Alert Entertainment** aus dem Store installieren.
3. Optional „Start beim Booten“ aktivieren (empfohlen).
4. App **starten**.

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
   eigenen Effekt/Farbe/Timing nur für diese Bridge setzen – „wie
   Konfiguration“ bzw. leer gelassene Felder übernehmen den Standard aus der
   App-Konfiguration. Die Parameter sind gruppiert (Übergreifende Parameter,
   dann von mehreren Effekten genutzte, dann je Effekt) statt einer langen
   Liste.
6. Mit **Start**/**Stop** in der Bridge-Karte (neben der Pairen-Schaltfläche)
   läuft der Effekt nur auf **dieser einen** Bridge, unabhängig vom Zustand
   der anderen – so lassen sich mehrere Bridges nacheinander statt nur
   gleichzeitig starten. Die daneben stehende Pille zeigt, ob diese Bridge
   gerade aktiv ist.

Damit die Bridge-Konfiguration auch **außerhalb des Web-UI-Start-Knopfs**
gilt (Scharfschalten, Home-Assistant-Integration, `rest_command`), trage
Bridge-IP, `area_id` (und optional `channel_order` sowie die Effekt-Overrides)
als Zeile der App-Option **`bridges`** ein (Tab „Konfiguration") und starte die
App neu.

Zusätzlich speichert jedes **Effektset** die `area_id` (und alle weiteren
Parameter) pro Bridge mit. Ein im Web-UI unter „2 · Steuerung" **geladenes**
Effektset – oder `POST /select` / `POST /start {"preset": …}` – übernimmt diese
`area_id`s zur Laufzeit als neue effektive Konfiguration (siehe „Effektsets").

Alternativ per REST: `POST /pair` (Body `{"bridge_host": "192.168.1.50"}`),
`GET /areas?bridge_host=192.168.1.50`.

`channel_order` (leer = Bereichs-Standard) legt fest, in welcher Reihenfolge der
`comet` die Lampen dieser Bridge durchläuft – als kommagetrennte Liste
der `channel_id`s, z. B. `2,3,1,0,5,4`. Es müssen genau die Kanäle des
Bereichs sein, nur in anderer Reihenfolge.

### 2 · Steuerung

Im Web-UI unter **„2 · Steuerung“** stehen **Start** / **Stop**,
**Scharfschalten** und die **Effektset-Bedienung** (Auswählen, Laden,
Herunterladen, Hochladen, Löschen, Speichern) zusammen. Alle Parameter (Effekt,
Farbe, Timing, Dauer, `fps`, …) kommen aus der App-Konfiguration bzw. aus den
Overrides der jeweiligen Bridge-Karte (siehe „1 · Bridges“); die aktuell
wirksamen Werte zeigt der Abschnitt „Status“ oben, die Parametererklärungen
stehen unter **„3 · Parameter“** ganz unten. **Start** / **Stop**
starten/stoppen alle eingerichteten Bridges gleichzeitig; die beiden Knöpfe
zeigen per gedrücktem Zustand an, ob der Effekt gerade läuft. Für einzelne
Bridges siehe die Start/Stop-Knöpfe auf der jeweiligen Bridge-Karte unter
„1 · Bridges“. Zur Effektset-Bedienung siehe „Effektsets“ weiter unten.

## Effekte

| `effect` | Verhalten |
|----------|-----------|
| `pulse` (Standard) | Alle Lampen **gemeinsam**: von `glow_low` linear auf `glow_high` und zurück, ein voller Zyklus alle `sweep_seconds`. Ein Schmitt-Trigger auf dem periodischen Signal macht daraus ein sauberes Ein/Aus, der Anstieg läuft dadurch ruckelfrei-monoton hoch. `attack_ms` = Aufblend-, `release_ms` = Abblendzeit; `release_ms` kleiner = schnelleres Abfallen als Aufblenden. |
| `comet` | Ein Komet läuft **gleichmäßig in eine Richtung** um alle Kanäle (wraparound, konstante Geschwindigkeit) mit Zykluszeit `sweep_seconds`. Jede Lampe für sich pulst dabei: **kurz hell (`glow_high`), langes exponentielles Ausblenden, dann eine Ruhephase auf `glow_low`**, dann wieder. Der Kopf ist etwas breiter als der Lampenabstand – zwei benachbarte Lampen stehen kurz gemeinsam auf 100 % und glühen dann nacheinander aus, sodass immer mindestens eine Lampe voll leuchtet. Mit `chase_pause > 0` macht der Komet **einen** Durchlauf, danach ruhen alle Lampen `chase_pause` Sekunden auf `glow_low`, dann der nächste. |
| `glitter` | **Diamant-Gefunkel:** jede Lampe funkelt für sich. In zufälligen Momenten (im Mittel alle `glitter_interval_ms` ms über alle Lampen einer Bridge) springt eine Lampe auf `glow_high` in einer zufällig aus `glitter_colors` gezogenen Farbe und klingt dann mit der Zeitkonstante `glitter_flash_ms` wieder auf `glow_low` ab. Ist `glitter_flash_ms` größer als `glitter_interval_ms`, funkeln mehrere Lampen gleichzeitig. `glitter_colors` leer = alle Funken in der Bridge-Farbe. |
| `police` | **Alarmlicht:** die Lampen einer Bridge werden in zwei Gruppen aufgeteilt (jede zweite Lampe in Kanalreihenfolge); Gruppe 1 blinkt in der Bridge-`color`, Gruppe 2 in `color2` (Standard Blau) – die beiden blinken abwechselnd, nie gleichzeitig. `sweep_seconds` ist die Dauer eines vollen Wechsels (beide Gruppen einmal). |
| `lightning` | **Gewitter:** alle Lampen einer Bridge blitzen **gemeinsam** in der Bridge-`color` auf und klingen dann ab – anders als `glitter`, wo jede Lampe für sich funkelt. `lightning_interval_ms` = mittlerer Abstand zwischen zwei Blitzen, `lightning_flash_ms` = Abkling-Zeitkonstante; gelegentlich (nicht konfigurierbar) folgt ein schneller zweiter Blitz, wie bei echtem Blitzschlag. |
| `heartbeat` | **Herzschlag:** ein Doppelpuls („lub-dub“, ein großer und ein kleinerer Puls) statt eines einzelnen Pulses wie bei `pulse`, im Takt von `sweep_seconds`. Nutzt dasselbe Beat-Gate/Slew wie `pulse` (`attack_ms`/`release_ms`), nur mit anderer Eingangskurve. |
| `aurora` | **Polarlicht:** langsame, weich überblendete Farbwellen wandern über die Lampen, geblendet aus `glitter_colors` (leer = Bridge-`color`, dann nur ein ruhiges Auf-/Abdimmen ohne Farbwechsel). Eine volle Farbwelle dauert `4 × sweep_seconds`; die Helligkeit atmet dabei sanft zwischen `glow_low` und `glow_high` – mit einer Periode von `4 × sweep_seconds`, **gedeckelt bei 12 s**, damit die Lampen bei hohem `sweep_seconds` nicht minutenlang nahe `glow_low` stehen (dort gibt die Bridge Farbtöne nur grob wieder). |
| `rainbow` | **Regenbogen:** ein durchgehender Farbumlauf (voller Hue-Kreis) über alle Lampen, je Lampe phasenversetzt, sodass ein Farbverlauf sichtbar über die Kanäle wandert statt dass alle Lampen synchron die Farbe wechseln. Eine volle Umdrehung dauert `4 × sweep_seconds`; Helligkeit konstant auf `glow_high`. |
| `meteor` | **Meteorschauer:** mehrere unabhängige Kometen (`meteor_count`, Standard 3) laufen mit zufälliger Geschwindigkeit (um `meteor_speed` Kanäle/Sekunde, auch rückwärts), Startposition und Spitzenhelligkeit in der Bridge-`color` um die Kanäle – eine unregelmäßigere, dichtere Variante von `comet`, das nur einen einzelnen, deterministischen Kometen fährt. |
| `wipe` | **Auffüll-Balken:** die Kanäle füllen sich nacheinander (in Kanalreihenfolge) mit der Bridge-`color`, wie ein Ladebalken – Dauer `sweep_seconds`. Danach hält der Balken `chase_pause` Sekunden voll gefüllt, bevor er zurückgesetzt wird und von vorn beginnt. |
| `firework` | **Feuerwerk:** von der mittleren Lampe/dem mittleren Kanal ausgehend breitet sich alle `firework_interval_ms` Millisekunden ein neuer Ausbruch in der Bridge-`color` nach außen aus (`firework_speed` Kanäle/Sekunde) und verblasst dabei. |
| `ripple` | **Echo:** wie `firework`, aber die Welle prallt an beiden Enden der Kanäle ab und läuft als Echo zurück, bevor sie verblasst und der nächste Impuls (`ripple_interval_ms`) startet; `ripple_speed` = Geschwindigkeit der Wellenfront in Kanälen/Sekunde. |
| `wave` | **Welle:** eine durchgehende Sinuswelle aus Helligkeit läuft über die Kanäle, mehrere Wellenberge gleichzeitig sichtbar (anders als `comet`s einzelner, lokalisierter Kopf). `wave_length` = Anzahl Kanäle pro voller Welle (klein = mehr, engere Wellenberge), `sweep_seconds` = Zeit, die die Welle für einen Durchlauf braucht. |
| `flicker` | **Flackern:** Lampen brechen sporadisch kurz von voller Helligkeit ein, wie eine defekte Glühbirne – das Gegenteil von `glitter` (das aufhellt) oder `lightning` (ein einzelner gemeinsamer Blitz). `flicker_interval_ms` = mittlerer Abstand zwischen zwei Einbrüchen über alle Lampen einer Bridge, `flicker_dip_ms` = wie schnell eine Lampe sich danach wieder erholt. |
| `strobe` | **Stroboskop:** ein hartes, sofortiges Blitzen in der Bridge-`color` ohne jede Überblendung (anders als `pulse`s weiches Auf-/Abblenden) – klassischer Party-Look. `sweep_seconds` bestimmt die Periode (Zeit zwischen zwei Blitzen). |
| `duel` | **Duell:** zwei Kometen starten an entgegengesetzten Enden der Kanäle – einer in der Bridge-`color`, einer in `color2` –, treffen sich in der Mitte und laufen wieder zurück; anders als `meteor` (unabhängig, zufällig) oder `comet` (ein einzelner, deterministischer Umlauf). `sweep_seconds` bestimmt die Periode eines vollen Hin- und Rücklaufs. |
| `chase` | **Nur für Gradient Lightstrips** (jeder Kanal ein Farb-Segment statt einer eigenen Lampe): `gc_count` weich überblendete Bänder in der Bridge-`color` laufen mit `gc_speed` Segmenten/Sekunde über die Kanäle, dazwischen `gc_background_color`. `gc_length` = Breite des vollfarbigen Kerns eines Bands in Segmenten (mit sanftem ~1-Segment-Übergang an den Rändern – daher „Gradient“). `gc_direction`: `forward`/`backward` laufen endlos umlaufend, `bounce` prallt an beiden Enden ab (Larson-Scanner). Mit `gc_chase_glitter` funkeln die Bänder zusätzlich wie `glitter` (nutzt `glitter_interval_ms`/`glitter_flash_ms`/`glitter_colors`, Funken nur innerhalb der Bänder); mit `gc_background_pulse` pulsiert der Hintergrund zwischen `glow_low` und `glow_high` wie `pulse` (nutzt `attack_ms`/`release_ms`/`sweep_seconds`) statt ruhig auf `glow_low` zu bleiben – die Bänder bleiben davon unberührt auf `glow_high`. Mehrere Gradient Lightstrips lassen sich kombinieren, indem ihre Segmente in einer gemeinsamen Entertainment Area liegen (ein `channel_ids`-Strip); `gc_strip_lengths` (je Bridge, z. B. `[7, 5]`) teilt diesen kombinierten Strip wieder in die einzelnen physischen Lightstrips auf, damit `gc_direction` **je Strip** gesetzt werden kann (als Liste, z. B. `["forward", "backward"]`) – etwa damit zwei gegenüberliegende Strips aufeinander zu oder auseinander laufen. |
| `color_chase` | **Farbverlauf-Lauflicht:** ein Farbverlauf füllt sich Lampe für Lampe auf – jede Lampe schaltet beim Vorbeilauf des Kopfs **sofort** auf ihre Zielfarbe und hält sie, bis der nächste Durchlauf sie überschreibt. Drei Paletten laufen abwechselnd, jede ein linearer Verlauf von der Startfarbe (Chase-Index 0) zur voll gemischten Farbe (letzter Chase-Index): `(255,0,0)→(255,255,0)`, `(0,255,0)→(0,255,255)`, `(0,0,255)→(255,0,255)`. `gc_speed` = Lampen (Schritte) pro Sekunde. `gc_direction`: `forward`/`backward` füllen immer vom selben Ende, `bounce` kehrt die Füllrichtung mit jeder Palette um. Absolute Farben, konstant auf `glow_high` (wie `rainbow`); keine `gc_strips`/`gc_count`/`gc_length`/`gc_background_color`. |
| `neutral` | **Kein Effekt:** die Lampen dieser Bridge werden gar nicht angesteuert – kein DTLS-Stream, kein Sichern/Wiederherstellen. Nur sinnvoll je Bridge gesetzt (`bridges[].effect: neutral`): so kann ein Effektset auf einer Bridge einen Effekt fahren und eine andere Bridge komplett auslassen. Eine `neutral`-Bridge braucht keine `area_id`. Sind **alle** Bridges `neutral`, antwortet `/start` mit `no_active_bridges` (kein Fehler). |

**Mehrere Bridges:** Läuft mehr als eine Bridge, starten alle **gleichzeitig**
– die DTLS-Handshakes aller Bridges laufen parallel, und die gemeinsame
Effekt-Uhr beginnt erst, wenn alle fertig sind, damit keine Bridge nachhinkt.
Jede Bridge kann dabei ihren **eigenen** Effekt, ihre eigene Farbe und ihr
eigenes Timing haben (`effect`, `color`, `sweep_seconds`, `chase_pause`,
`attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`,
`glitter_flash_ms`, `glitter_colors`, `gc_direction`, `gc_strip_lengths`,
`gc_count`, `gc_length`, `gc_speed`, `gc_background_color`,
`gc_chase_glitter`, `gc_background_pulse`, `color2`,
`lightning_interval_ms`, `lightning_flash_ms`, `meteor_count`,
`meteor_speed`, `firework_interval_ms`, `firework_speed`,
`ripple_interval_ms`, `ripple_speed`, `wave_length`, `flicker_interval_ms`,
`flicker_dip_ms` sind je Bridge
überschreibbar; nicht
überschriebene Werte gelten aus den gleichnamigen App-Optionen. Mit
`effect: neutral` je Bridge bleibt diese Bridge komplett
aus, während die anderen laufen. `area_id` und `channel_order` sind immer je
Bridge eigene Werte; `duration`, `fps` und `restore_state` gelten dagegen
immer für alle Bridges gemeinsam. Ist eine Bridge nicht erreichbar oder nicht
gepaart, starten die übrigen trotzdem („best effort“) – die fehlgeschlagene
wird in der `/start`-Antwort unter `failed_bridges` gemeldet.

**Lichtzustand:** Vor dem Effekt sichert die App an/aus, Helligkeit und Farbe
aller Lampen jedes Bereichs (Hue CLIP v2) und schreibt sie nach dem Effekt zurück
– auch Lampen, die vorher aus waren, gehen wieder aus. Abschaltbar mit
`restore_state: false` (dann greift nur die automatische Wiederherstellung der
Bridge nach dem Stream-Ende).

## Konfiguration

| Option          | Typ                | Standard   | Bedeutung |
|-----------------|--------------------|------------|-----------|
| `api_token`     | String             | `""` (auto) | Token für den Zugriff auf die REST-API von außerhalb (HA-Integration, `rest_command`). Leer lassen: Das Add-on erzeugt beim ersten Start selbst einen Token, trägt ihn hier ein (sichtbar nach einem Reload des Konfigurationsdialogs) und schreibt ihn ins Add-on-Log. Zugriffe über Ingress (Web-UI) brauchen keinen Token. |
| `bridges`       | Liste (max. 3)     | `[]`       | Eine Zeile pro Bridge: `bridge_host` (IP), `area_id` (Schritt 1), optional `channel_order` sowie je Bridge optional `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors`, `gc_direction`, `gc_strip_lengths`, `gc_count`, `gc_length`, `gc_speed`, `gc_background_color`, `gc_chase_glitter`, `gc_background_pulse`, `color2`, `lightning_interval_ms`, `lightning_flash_ms`, `meteor_count`, `meteor_speed`, `firework_interval_ms`, `firework_speed`, `ripple_interval_ms`, `ripple_speed`, `wave_length`, `flicker_interval_ms`, `flicker_dip_ms` (überschreiben die gleichnamige Option unten nur für diese Bridge). |
| `effect`        | `pulse` \| `comet` \| `glitter` \| `police` \| `lightning` \| `heartbeat` \| `aurora` \| `rainbow` \| `meteor` \| `wipe` \| `firework` \| `ripple` \| `wave` \| `flicker` \| `strobe` \| `duel` \| `chase` \| `color_chase` \| `neutral` | `pulse`    | Standard-Lichteffekt für Bridges ohne eigene Einstellung, siehe oben. `neutral` sinnvoll nur je Bridge. |
| `color`         | Hex-String         | `#FF0000`  | Standard-Farbe für Bridges ohne eigene Einstellung. |
| `fps`           | int (5–50)         | `25`       | Frames/Sekunde des DTLS-Streams (für alle Bridges gleich). |
| `sweep_seconds` | float (0.3–300.0)  | `1.4`      | Standard für Bridges ohne eigene Einstellung. `comet`: Dauer einer vollen Umrundung. `pulse`/`heartbeat`: Zyklusdauer. `wave`/`strobe`/`duel`: Periodendauer. |
| `chase_pause`   | float (0–60)       | `0`        | Standard für Bridges ohne eigene Einstellung. `comet`: Pause (Sekunden) zwischen zwei Durchläufen. `0` = durchgehend umlaufender Komet. `> 0` = ein Durchlauf, dann alle Lampen für so viele Sekunden auf `glow_low`, dann der nächste. |
| `attack_ms`     | int (0–2000)       | `140`      | Standard für Bridges ohne eigene Einstellung. `pulse`: Aufblendzeit `glow_low` → `glow_high`. |
| `release_ms`    | int (0–5000)       | `70`       | Standard für Bridges ohne eigene Einstellung. `pulse`: Abblendzeit → `glow_low` zwischen den Pulsen (kleiner als `attack_ms` = schnelleres Abfallen). |
| `glow_low`      | float (0–1)        | `0.08`     | Standard für Bridges ohne eigene Einstellung. **Alle Effekte:** Ruhe-Helligkeit zwischen den Pulsen. `0` = ganz aus. |
| `glow_high`     | float (0–1)        | `1.0`      | Standard für Bridges ohne eigene Einstellung. **Alle Effekte:** Helligkeit im Puls-Maximum. Muss über `glow_low` liegen. |
| `glitter_interval_ms` | float (5–5000) | `90`     | Nur `effect: glitter`. Mittlerer Abstand (ms) zwischen zwei Funkel-Blitzen über alle Lampen einer Bridge. Klein = hektisches Gefunkel. Je Bridge überschreibbar. |
| `glitter_flash_ms` | float (20–5000) | `260`     | Nur `effect: glitter`. Abkling-Zeitkonstante (ms) eines einzelnen Funkens. Größer als `glitter_interval_ms` = mehrere Lampen funkeln gleichzeitig. Je Bridge überschreibbar. |
| `glitter_colors` | String            | `#FFFFFF #CFE8FF #FFF1D0` | Nur `effect: glitter`. Hex-Farben (durch Leerzeichen getrennt), aus denen jeder Funken zufällig zieht. Leer = Farbe der jeweiligen Bridge. Je Bridge überschreibbar. |
| `gc_direction`  | `forward` \| `backward` \| `bounce` | `forward` | Nur `effect: chase`. Standard-Chaserichtung. Je Bridge überschreibbar; dort auch als kommagetrennte Liste möglich (eine Richtung je Strip, siehe `gc_strip_lengths`). |
| `gc_strip_lengths` | String (je Bridge) | leer (ein Strip) | Nur `effect: chase`, nur je Bridge. Teilt die Kanäle dieser Bridge in aufeinanderfolgende Gradient-Lightstrips auf, z. B. `"7,5"`. Summe muss der Kanalzahl entsprechen, sonst gilt ein einzelner Strip. |
| `gc_count`      | int (1–8)          | `1`        | Nur `effect: chase`. Anzahl gleichzeitig laufender Chase-Bänder, gleichmäßig verteilt. Je Bridge überschreibbar. |
| `gc_length`     | float (0.2–200)    | `2.0`      | Nur `effect: chase`. Breite des vollfarbigen Kerns eines Bands in Segmenten. Je Bridge überschreibbar. |
| `gc_speed`      | float (0.01–50)    | `4.0`      | Nur `effect: chase`. Segmente pro Sekunde, die ein Chase-Kopf zurücklegt. Je Bridge überschreibbar. |
| `gc_background_color` | Hex-String   | `#000000`  | Nur `effect: chase`. Farbe außerhalb der Chase-Bänder. Je Bridge überschreibbar. |
| `gc_chase_glitter` | bool            | `false`    | Nur `effect: chase`. Lässt die Bänder zusätzlich wie `glitter` funkeln (nutzt `glitter_interval_ms`/`glitter_flash_ms`/`glitter_colors`). Je Bridge überschreibbar. |
| `gc_background_pulse` | bool         | `false`    | Nur `effect: chase`. Lässt den Hintergrund zusätzlich wie `pulse` pulsieren (nutzt `attack_ms`/`release_ms`/`sweep_seconds`) statt ruhig auf `glow_low` zu bleiben. Je Bridge überschreibbar. |
| `color2` | Hex-String         | `#0000FF`  | Zweite Farbe – `effect: police` (Farbe der zweiten Lampengruppe, die erste nutzt `color`) und `effect: duel` (Farbe des zweiten Kometen). Je Bridge überschreibbar. |
| `lightning_interval_ms` | float (50–60000) | `4000` | Nur `effect: lightning`. Mittlerer Abstand (ms) zwischen zwei Blitzen, die alle Lampen einer Bridge gemeinsam aufleuchten lassen. Je Bridge überschreibbar. |
| `lightning_flash_ms` | float (20–5000) | `500`   | Nur `effect: lightning`. Abkling-Zeitkonstante (ms) eines Blitzes. Je Bridge überschreibbar. |
| `meteor_count`  | int (1–8)          | `3`        | Nur `effect: meteor`. Anzahl gleichzeitig laufender, unabhängiger Meteore. Je Bridge überschreibbar. |
| `meteor_speed`  | float (0.05–20)    | `1.2`      | Nur `effect: meteor`. Mittlere Geschwindigkeit der Meteore in Kanälen/Sekunde (jeder weicht zufällig davon ab). Je Bridge überschreibbar. |
| `firework_interval_ms` | float (200–60000) | `3000` | Nur `effect: firework`. Wie oft (ms) ein neuer Ausbruch von der Kanalmitte losläuft. Je Bridge überschreibbar. |
| `firework_speed` | float (0.5–50)    | `6.0`      | Nur `effect: firework`. Ausbreitungsgeschwindigkeit des Ausbruchs in Kanälen/Sekunde. Je Bridge überschreibbar. |
| `ripple_interval_ms` | float (200–60000) | `3000` | Nur `effect: ripple`. Wie oft (ms) ein neuer Impuls von der Kanalmitte losläuft. Je Bridge überschreibbar. |
| `ripple_speed`  | float (0.5–50)     | `6.0`      | Nur `effect: ripple`. Geschwindigkeit der Wellenfront in Kanälen/Sekunde. Je Bridge überschreibbar. |
| `wave_length`   | float (0.5–50)     | `3.0`      | Nur `effect: wave`. Kanäle pro voller Sinuswelle. Je Bridge überschreibbar. |
| `flicker_interval_ms` | float (20–10000) | `600`   | Nur `effect: flicker`. Mittlerer Abstand (ms) zwischen zwei Helligkeitseinbrüchen über alle Lampen einer Bridge. Je Bridge überschreibbar. |
| `flicker_dip_ms` | float (20–5000)   | `150`      | Nur `effect: flicker`. Erholzeit (ms) einer Lampe nach einem Einbruch. Je Bridge überschreibbar. |
| `restore_state` | bool               | `true`     | Lampenzustand (an/aus, Helligkeit, Farbe) vor dem Effekt sichern und danach wiederherstellen (für alle Bridges gleich). |
| `duration`      | float (0–86400)    | `0`        | Wie lange der Effekt standardmäßig läuft, bevor er von selbst endet (für alle Bridges gemeinsam; im `/start`-Body pro Aufruf übersteuerbar). `0` = **unbegrenzt**, läuft bis `/stop`. |
| `log_level`     | Liste              | `info`     | `trace`,`debug`,`info`,`notice`,`warning`,`error`,`fatal`. |

## REST-API

**Zugang (seit 2.0.0):** Das Add-on veröffentlicht **keinen LAN-Port** mehr.
Die API ist nur noch erreichbar

- über **Ingress** (das Web-UI, relativ zum Panel-Pfad) – ohne Token, und
- über das **interne Docker-Netz von Home Assistant** unter
  `http://<add-on-hostname>:8099` (der Hostname steht auf der Add-on-Seite unter
  *Info*, z. B. `local-redalert` oder `<repo>-redalert`).

Jeder Aufruf, der **nicht** über Ingress kommt (HA-Integration, `rest_command`,
`curl` aus dem HA-Container), braucht den Header
`Authorization: Bearer <api_token>` (ersatzweise `?api_token=<token>` als
Query). Ohne/falsch → `401`. Den Token zeigt die Add-on-Konfiguration bzw. das
Add-on-Log beim ersten Start; die **Home-Assistant-Integration übernimmt ihn
unter Supervisor automatisch** (siehe unten).

| Endpoint  | Methode | Zweck |
|-----------|---------|-------|
| `/`       | GET     | Web-UI (Ingress-Panel). |
| `/health` | GET     | `{status, paired, running, armed, current_preset}` – `paired` ist `true`, sobald mindestens eine Bridge gepaart ist; `running` ist `true`, sobald **irgendeine** Bridge gerade läuft (für den je-Bridge-Status siehe `/config`s `bridges[].running`); `armed` ist `true`, wenn **alle** nicht-`neutral` gepaarten Bridges scharfgeschaltet sind; `current_preset` der Name des zuletzt per `preset` gestarteten Effektsets (`null` bei Ad-hoc-Start ohne `preset`). Auch Ziel des Container-HEALTHCHECK. |
| `/config` | GET     | Effektive Konfiguration inkl. `bridges` (je Bridge zusätzlich `running: bool` und `armed: bool`), `armed` (global) + `armed_bridges` (Liste), `presets` (Namen der gespeicherten Effektsets) und `current_preset` – für das Web-UI und die Home-Assistant-Integration. |
| `/pair`   | POST    | Einmalige Kopplung. Body: `{"bridge_host": "..."}` – Pflicht, sobald mehr als eine Bridge konfiguriert ist (bei genau einer, noch ungepaarten, konfigurierten Bridge optional). |
| `/areas`  | GET     | Entertainment-Bereiche + Kanäle einer Bridge auflisten. Query `?bridge_host=...` – Pflicht, sobald mehr als eine Bridge gepaart ist. |
| `/start`  | POST    | Effekt auf allen konfigurierten (oder im Body übergebenen) Bridges gleichzeitig starten (antwortet sofort; DTLS-Handshakes laufen im Hintergrund, parallel) – oder, mit `bridge_host` im Body, nur auf einer einzelnen Bridge, unabhängig vom Zustand der anderen. Body optional: `duration`, `fps`, `restore_state` gelten für alle Bridges gemeinsam; `effect`, `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`, `glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors`, `gc_direction`, `gc_count`, `gc_length`, `gc_speed`, `gc_background_color`, `gc_chase_glitter`, `gc_background_pulse`, `color2`, `lightning_interval_ms`, `lightning_flash_ms`, `meteor_count`, `meteor_speed`, `firework_interval_ms`, `firework_speed`, `ripple_interval_ms`, `ripple_speed`, `wave_length`, `flicker_interval_ms`, `flicker_dip_ms` sind die **Standardwerte** für Bridges ohne eigene Einstellung. `bridges` (Liste von `{bridge_host, area_id, channel_order, effect?, color?, sweep_seconds?, chase_pause?, attack_ms?, release_ms?, glow_low?, glow_high?, glitter_interval_ms?, glitter_flash_ms?, glitter_colors?, gc_direction?, gc_strip_lengths?, gc_count?, gc_length?, gc_speed?, gc_background_color?, gc_chase_glitter?, gc_background_pulse?, color2?, lightning_interval_ms?, lightning_flash_ms?, meteor_count?, meteor_speed?, firework_interval_ms?, firework_speed?, ripple_interval_ms?, ripple_speed?, wave_length?, flicker_interval_ms?, flicker_dip_ms?}`) übersteuert für diesen Aufruf die Option `bridges` – jede Bridge kann ihre eigenen Effekt-Parameter setzen; `channel_order` als Liste (`[2,3,1,0,5,4]`) oder String (`"2,3,1,0,5,4"`), muss genau die Kanäle des jeweiligen Bereichs enthalten, sonst wird diese eine Bridge übersprungen. `gc_strip_lengths` (nur `chase`, je Bridge, z. B. `[7, 5]` oder `"7,5"`) teilt die Kanäle dieser Bridge in aufeinanderfolgende Gradient-Lightstrips auf; `gc_direction` darf dann ebenfalls eine Liste sein (eine Richtung je Strip). `preset` (Name eines gespeicherten Effektsets) lädt dessen Body als Basis; weitere Body-Felder überschreiben ihn – nicht mit `bridge_host` kombinierbar (`400`). Ein preset-Start übernimmt die `bridges` des Sets (inkl. `area_id`) als neue effektive Konfiguration; ist eine Bridge scharfgeschaltet oder läuft eine Animation, ist er nur erlaubt, wenn das Set pro aktiver Bridge dieselbe `area_id` hat – dann werden laufende Effekte live umgeschaltet (`hotswapped_bridges` in der Antwort, kein Neustart/Handshake), sonst `409`. `bridge_host` (optional): filtert auf genau diese eine Bridge (muss in `bridges`, Option oder Body, enthalten sein); `already_running` gilt dann nur für sie, und ein Solo-Start ändert nie `current_preset`. Ohne `bridge_host` werden bereits laufende Bridges übersprungen statt den ganzen Aufruf abzulehnen (`skipped_bridges` in der Antwort). Antwort enthält `bridges` (tatsächlich neu gestartet, je mit aufgelösten Effekt-Parametern), `failed_bridges` (übersprungen, mit Fehlergrund), `neutral_bridges` und `skipped_bridges` (bereits aktiv); nur wenn **keine** Bridge neu startet und keine fehlgeschlagen ist, antwortet `/start` mit `no_active_bridges`; schlägt mindestens eine fehl und bleibt keine übrig, antwortet `/start` mit `502`. |
| `/stop`   | POST    | Effekt auf allen laufenden Bridges sofort stoppen – oder, mit `bridge_host` im Body, nur auf einer einzelnen Bridge, unabhängig vom Zustand der anderen. |
| `/arm`    | POST    | **Scharfschalten**: DTLS-Stream einer/aller Bridge(s) dauerhaft offen halten, damit ein späteres `/start` den ~3–9 s langen Handshake überspringt und der Effekt praktisch sofort beginnt. Body optional `bridge_host` (sonst alle konfigurierten, nicht-`neutral` Bridges). Solange scharf, belegt die Bridge ihren einzigen Entertainment-Slot und ihre Lampen zeigen ein angenähertes Standbild des vorherigen Zustands. Eine gerade laufende Bridge lässt sich nicht scharfschalten (erst `/stop`); Antwort: `{status, armed:[...], already_armed:[...], busy:[...], failed:[...]}`. |
| `/disarm` | POST    | Scharfschaltung aufheben: Stream(s) schließen und den beim Scharfschalten gesicherten Lichtzustand per CLIP v2 wiederherstellen. Body optional `bridge_host` (sonst alle scharfen Bridges). Ein noch laufender Effekt wird zuvor gestoppt. |
| `/select` | POST    | Ein Effektset **laden**: als `current_preset` merken **und** dessen Bridge-`area_id`s als neue effektive Konfiguration übernehmen (gilt auch für `/arm`, HA-Integration, `rest_command`). Body `{"preset": "<name>"}` (`404`, wenn unbekannt; `400`, wenn die `bridges`-Liste des Sets keinen gültigen Eintrag hat) oder `{"preset": null}` / leer zum Zurücksetzen. Laden geht immer, solange nichts scharfgeschaltet ist und keine Animation läuft; bei scharfer/laufender Bridge nur, wenn das Set pro aktiver Bridge dieselbe `area_id` hat – dann werden laufende Effekte ohne Neustart/Handshake auf das neue Set umgeschaltet (`hotswapped_bridges`), sonst `409`. |
| `/identify` | POST  | Lampen einer Bridge einzeln durchtesten (Zuordnung `channel_id` → Lampe). Body: `bridge_host` (Pflicht, sobald mehr als eine Bridge konfiguriert ist), `area_id` (optional, sonst aus der bridges-Konfiguration), `channel_id` (fehlt = alle Kanäle nacheinander), `seconds` (Standard 3 einzeln / 2 bei „alle“), `color`, `restore_state`. Ein DTLS-Handshake für den ganzen Durchlauf. Belegt denselben Slot wie ein Effekt auf dieser einen Bridge (`already_running`, `/stop` mit passendem `bridge_host` bricht ab) – andere Bridges bleiben unberührt. |
| `/presets` | GET    | Alle gespeicherten Effektsets: `{"presets": {Name: Body, …}, "names": [...]}`. Mit `?name=…` nur dieses eine (`{"name", "config"}`, `404` wenn unbekannt). |
| `/presets` | PUT / POST | Ein Effektset speichern/überschreiben (auch Upload-Ziel). Body `{"name": "...", "config": { <start-Body> }}` – `config` sind die kompletten `/start`-Felder inkl. `bridges` (mit `area_id` pro Bridge); abgelegt unter `/data/presets.json`. |
| `/presets` | DELETE | Effektset löschen. Query `?name=…` (oder Body `{"name": …}`). `404` wenn unbekannt. |

- `duration` (Sekunden, Standard aus der gleichnamigen App-Option, **`0` =
  unbegrenzt**) – wie lange der Effekt läuft, bevor er von selbst endet;
  vorher jederzeit per `/stop` abbrechbar.

## Scharfschalten (schnellerer Start)

Zwischen `/start` und dem sichtbaren Effekt liegt normalerweise der
DTLS-Handshake der Bridge (~1,5–9 s). Wer diese Verzögerung nicht will,
schaltet die Bridge vorab **scharf** (`POST /arm`, im Web-UI der Knopf
„Scharfschalten“ je Bridge-Karte bzw. global unter „2 · Steuerung“, in Home
Assistant der Schalter „Scharfgeschaltet“): der DTLS-Stream bleibt dann
dauerhaft offen, und ein anschließendes `/start` beginnt den Effekt innerhalb
eines einzelnen Frames.

Solange eine Bridge scharf ist:

- belegt sie ihren **einzigen** Entertainment-Slot – andere Entertainment-Apps
  bzw. `/identify` für diese Bridge sind blockiert, bis `/disarm`;
- stehen ihre Lampen unter Stream-Kontrolle und zeigen ein **angenähertes
  Standbild** des Zustands, der beim Scharfschalten geherrscht hat (die exakten
  Farben werden erst bei `/disarm` per CLIP v2 wiederhergestellt). Endet ein
  Effekt, bleibt der letzte Effekt-Frame ~2 s stehen, bevor das Standbild
  zurückkehrt – startet in dieser Zeit ein neuer Effekt (z. B. Effektset-
  Wechsel), ist der Übergang nahtlos, ohne dass das Standbild kurz aufblitzt;
- bleibt sie scharf, bis `/disarm` aufgerufen wird oder die App neu startet
  (beim Herunterfahren entschärft die App automatisch und stellt den
  Lichtzustand wieder her).

Ein `/start` funktioniert unverändert auch ohne Scharfschalten – dann eben mit
dem üblichen Handshake davor.

## Effektsets

Der komplette Satz an Start-Parametern (alle Bridge-Karten aus „1 · Bridges“
**und** die Steuerung) lässt sich unter „2 · Steuerung“ im Web-UI unter einem
Namen speichern (z. B. *Star Trek – Alarmstufe Rot*). Jedes Set speichert die
`area_id` (und alle weiteren Parameter) pro Bridge mit. Ein gespeichertes Set
kann man

- **Laden** – füllt das Formular wieder mit den Werten des Sets **und**
  übernimmt seine `area_id`s als neue effektive Konfiguration (auch für
  Scharfschalten, die HA-Integration und `rest_command`),
- **Herunterladen** – als JSON-Datei (`{"name": …, "config": {…}}`) sichern,
- **Hochladen** – eine solche JSON-Datei wieder einlesen und als Set ablegen,
- **Löschen**.

**Laden geht immer**, solange nichts scharfgeschaltet ist und keine Animation
läuft. Ist eine Bridge scharf bzw. läuft ein Effekt, geht Laden nur, wenn das
Set pro aktiver Bridge dieselbe `area_id` enthält – dann läuft die Animation
**sofort mit dem neuen Set weiter** (die Effekt-Parameter werden im laufenden
Task ausgetauscht, kein Neustart, kein erneuter Handshake). Andernfalls kommt
eine Fehlermeldung (`409`).

Die Sets liegen als `/data/presets.json` im App-Datenordner und überstehen
Neustarts. Per REST: `GET /presets` (alle), `PUT /presets`
(`{"name", "config"}` – speichern/hochladen), `DELETE /presets?name=…`
(löschen), `POST /select {"preset": "<Name>"}` (laden, siehe oben) und
`POST /start {"preset": "<Name>"}` (laden **und** starten; weitere Body-Felder
überschreiben das Set für diesen einen Aufruf).

## Home Assistant einbinden

**Fertige Integration (empfohlen):** im Repo unter
[`custom_components/redalert/`](https://github.com/ringind/redalert/tree/main/custom_components/redalert)
liegt eine eigenständige `custom_component`, die sechs Entities anlegt – zwei
`binary_sensor` (läuft der Effekt gerade? / sind die Bridges scharfgeschaltet?),
drei `switch` (Animation an/aus, je Bridge, Scharfschalten aller Bridges), ein
`select` (gespeichertes Effektset laden – startet nur, wenn gerade eine
Animation läuft) und ein `sensor` (Name des geladenen Sets). Installation über **HACS** (das Repo ist
HACS-fähig – `hacs.json` im Wurzelverzeichnis – aber nicht im Standard-Store
gelistet: HACS → *Benutzerdefinierte Repositories* →
`https://github.com/ringind/redalert`, Kategorie *Integration*) oder manuell
(Ordner nach `config/custom_components/` kopieren). Danach HA neu starten,
dann **Einstellungen → Geräte & Dienste → Integration hinzufügen → „Red Alert
Entertainment App“**. Unter Supervisor werden **Host und API-Token automatisch
erkannt** – nur bestätigen; sonst Host (`<add-on-hostname>`), Port `8099` und
den API-Token aus der Add-on-Konfiguration eintragen. Details: das `README.md`
in diesem Ordner.

**Ohne Zusatzinstallation:** die REST-API (siehe oben) lässt sich auch direkt
über die eingebaute **[`rest_command`](https://www.home-assistant.io/integrations/rest_command/)**-
Integration als ganz normaler HA-Dienst nutzen (`rest_command.<name>`). Jeder
`rest_command`-Eintrag in `configuration.yaml` wird 1:1 zu einem Dienst, den du
aus Automationen, Skripten, Dashboard-Buttons oder **Entwicklerwerkzeuge →
Aktionen** aufrufen kannst.

### Grundlage: Parameter beim Aufruf übergeben

`rest_command` erlaubt beim Dienstaufruf **beliebige zusätzliche Felder** unter
`data:` – die stehen dann als Jinja-Variablen im `payload` (bzw. `url`) dieses
Eintrags zur Verfügung. So lässt sich ein einziger, in `configuration.yaml`
fest definierter Dienst bei jedem Aufruf mit anderen Werten füttern, ohne für
jede Kombination eine eigene `rest_command`-Zeile zu brauchen. Für JSON-Bodys
den Filter `to_json` verwenden (escaped korrekt Anführungszeichen, Sonderzeichen
und Zahlen) statt Werte per Hand in `"…"` einzubetten. `{% if <name> is
defined %}…{% endif %}` lässt ein Feld weg, wenn beim Aufruf keine Variable
dieses Namens mitgegeben wurde – so bleibt z. B. `duration` unangegeben und die
App nimmt ihren eigenen Standard (Effektset- bzw. Options-Wert), statt dass
ein template-seitiger Default (z. B. `0`) das ungewollt überschreibt.

### `configuration.yaml`

`<add-on-hostname>` steht auf der Add-on-Seite unter *Info* (z. B.
`local-redalert` oder `<repo>-redalert`); `<api_token>` in der
Add-on-Konfiguration. Der `Authorization`-Header ist seit App-2.0.0 **Pflicht**
(ohne ihn `401`). Am übersichtlichsten in `secrets.yaml`:
`redalert_token: "…"` und dann `!secret redalert_token`.

```yaml
rest_command:
  # Startet mit den in der App konfigurierten Standardwerten (Options bzw. Web-UI).
  redalert_start:
    url: "http://<add-on-hostname>:8099/start"
    method: POST
    content_type: "application/json"
    headers:
      Authorization: "Bearer <api_token>"
    payload: '{}'   # Dauer ohne Angabe: Standard aus der App-Option duration

  # Startet ein gespeichertes Effektset (Web-UI „2 · Steuerung“ bzw. PUT /presets).
  # Aufruf z. B. mit data: {preset: "Star Trek – Alarmstufe Rot"}
  # optional zusätzlich data: {duration: 30} um die Dauer für diesen einen Aufruf zu übersteuern.
  redalert_start_preset:
    url: "http://<add-on-hostname>:8099/start"
    method: POST
    content_type: "application/json"
    headers:
      Authorization: "Bearer <api_token>"
    payload: >-
      {"preset": {{ preset | to_json }}
      {%- if duration is defined %}, "duration": {{ duration | float }}{% endif -%}
      }

  redalert_stop:
    url: "http://<add-on-hostname>:8099/stop"
    method: POST
    headers:
      Authorization: "Bearer <api_token>"
```

Nach dem Speichern **Entwicklerwerkzeuge → YAML → Alle YAML-Konfigurationen neu
laden** (oder HA neu starten), damit die neuen Dienste erscheinen.

### Ein Effektset aus Home Assistant starten

Den genauen Namen des Sets (Groß-/Kleinschreibung und Leerzeichen zählen) zeigt
entweder das Dropdown unter „2 · Steuerung“ im Web-UI oder `GET /presets` (Feld
`names`).

**Direkt testen** – Entwicklerwerkzeuge → Aktionen → `rest_command.redalert_start_preset`
→ im YAML-Modus:

```yaml
preset: "Star Trek – Alarmstufe Rot"
```

**Fest verdrahteter Dienst pro Set** (bequem für einen Dashboard-Button, der
immer dasselbe Set startet):

```yaml
script:
  redalert_alarmstufe_rot:
    alias: "Red Alert: Alarmstufe Rot"
    sequence:
      - service: rest_command.redalert_start_preset
        data:
          preset: "Star Trek – Alarmstufe Rot"
```

`script.redalert_alarmstufe_rot` erscheint danach wie jede andere Entität und
lässt sich auf einem Dashboard, per Sprachbefehl oder aus einer Automation
auslösen.

**Auswahl per Dropdown** – ein `input_select` mit den Set-Namen plus ein Skript,
das den aktuell gewählten Eintrag startet:

```yaml
input_select:
  redalert_preset:
    name: Red-Alert-Effektset
    options:
      - "Star Trek – Alarmstufe Rot"
      - "Diamant-Funkeln"   # Optionen manuell pflegen, siehe GET /presets

script:
  redalert_start_selected_preset:
    alias: "Red Alert: ausgewähltes Set starten"
    sequence:
      - service: rest_command.redalert_start_preset
        data:
          preset: "{{ states('input_select.redalert_preset') }}"
```

`input_select.redalert_preset` auf ein Dashboard legen, Set auswählen, dann
`script.redalert_start_selected_preset` per Button auslösen.

### Weitere Parameter dynamisch übergeben

Alle Felder aus der `/start`-Zeile der REST-API-Tabelle oben (`effect`, `color`,
`sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`, `glow_low`,
`glow_high`, `glitter_interval_ms`, `glitter_flash_ms`, `glitter_colors`,
`bridges`, `fps`, `restore_state`, …) lassen sich nach demselben Muster wie
`preset`/`duration` oben ergänzen – im `payload` je einen
`{% if <name> is defined %}, "<name>": {{ <name> | to_json }}{% endif %}`-Block
hinzufügen und die Variable beim Dienstaufruf per `data:` mitgeben. Beispiel:
Effekt und Farbe unabhängig vom konfigurierten Standard setzen:

```yaml
rest_command:
  redalert_start_custom:
    url: "http://<add-on-hostname>:8099/start"
    method: POST
    content_type: "application/json"
    headers:
      Authorization: "Bearer <api_token>"
    payload: >-
      {"effect": {{ effect | to_json }}, "color": {{ color | to_json }}
      {%- if duration is defined %}, "duration": {{ duration | float }}{% endif -%}
      }
```

aufgerufen z. B. mit `data: {effect: "glitter", color: "#00FF88", duration: 20}`.

### Automationsbeispiele

Sound + Licht gemeinsam (Standard-Effekt):

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

Ein bestimmtes Effektset auslösen, z. B. beim Türklingeln kurz das gespeicherte
Set „Diamant-Funkeln“ statt des Standards:

```yaml
automation:
  - alias: "Türklingel – Diamant-Funkeln"
    trigger:
      - platform: state
        entity_id: binary_sensor.tuerklingel
        to: "on"
    action:
      - service: rest_command.redalert_start_preset
        data:
          preset: "Diamant-Funkeln"
          duration: 8
      - delay: "00:00:08"
      - service: rest_command.redalert_stop   # optionale Absicherung, falls duration nicht greift
```

## Protokoll

Das App-**Protokoll** (Log-Tab der App) zeigt Konfiguration beim Start,
Pairing-, Start-/Stop-Ereignisse und Fehler. Ausführlichkeit über `log_level`.
(Das Web-UI hat keinen eigenen Protokoll-Bereich mehr; Diagnosemeldungen des
Panels landen in der Browser-Konsole.)

## Fehlerbehebung

| Symptom | Ursache / Lösung |
|---------|------------------|
| `/pair` schlägt fehl | Link-Button nicht rechtzeitig gedrückt (~30 s) oder falsche IP. |
| Aufruf → `401` „Nicht autorisiert" | Seit 2.0.0 braucht jeder Zugriff außerhalb von Ingress den Header `Authorization: Bearer <api_token>`. Token in der Add-on-Konfiguration bzw. im Add-on-Log; in der HA-Integration ins Feld „API-Token" (unter Supervisor meist automatisch vorbelegt). |
| HA-Integration wird nach dem Update auf 2.0.0 „nicht bereit" | Der bestehende Config-Eintrag hat noch keinen Token und zeigt auf die alte LAN-IP. Eintrag entfernen und neu hinzufügen (Host/Token werden unter Supervisor automatisch erkannt). |
| Add-on-Hostname für `rest_command` unbekannt | Add-on-Seite → *Info* (Feld „Hostname", z. B. `local-redalert`); alternativ im Add-on-Log die Startzeile. |
| `/start` → `already_running` | Diese Bridge (bzw. bei einem Aufruf ohne `bridge_host` alle angefragten) läuft schon. Erst `/stop` aufrufen, oder – ohne `bridge_host` – einfach nochmal `/start`: bereits laufende Bridges werden übersprungen (`skipped_bridges`), nur die übrigen neu gestartet. |
| `/start` → 404 `area_id nicht gefunden` | `/areas` prüfen – Bereich evtl. umbenannt/gelöscht. |
| `/start` → 404 `Effektset '…' nicht gefunden` | `preset`-Name stimmt nicht exakt (Groß-/Kleinschreibung, Leerzeichen) mit einem gespeicherten Set überein – `GET /presets` bzw. Web-UI-Dropdown „2 · Steuerung“ prüfen. |
| `rest_command`-Aufruf mit `preset`/`duration`/… ändert nichts | Nach Änderungen an `configuration.yaml` **Entwicklerwerkzeuge → YAML → Alle YAML-Konfigurationen neu laden** (oder HA neu starten); der gesendete Request unter Entwicklerwerkzeuge → Aktionen zeigt den tatsächlich gesendeten `payload`. |
| `/start` → 502 `Bridge nicht erreichbar` | Bridge-IP geändert? Netzwerk/VLAN zwischen HA-Host und Bridge (UDP 2100). Bei mehreren Bridges bedeutet `502` nur, dass **keine** davon erreichbar war – einzelne Ausfälle stehen in `failed_bridges` der `/start`-Antwort, die übrigen Bridges laufen trotzdem. |
| Licht startet erst nach einigen Sekunden | Normaler DTLS-Handshake; bei WLAN-Bridges teils ein `ServerHello timeout`-Retry im Protokoll. `/start` selbst antwortet trotzdem sofort. |
| Lampen reagieren nicht | V1-Bridge (kein Entertainment) oder UDP-Port 2100 zur Bridge blockiert. |
| Streaming bricht ab | Jede Bridge erlaubt nur **einen** aktiven Entertainment-Stream (pro Bridge, nicht global) – Hue-Sync-App/andere Clients auf derselben Bridge schließen. |
| Lauflicht ruckelt | `fps` erhöhen oder Netzlast zur Bridge prüfen. |
| Start bricht ab mit `/bin/sh: can't open '/init': Permission denied` | Behoben ab 1.0.1 (kein eigenes AppArmor-Profil mehr). App aktualisieren; ältere Version deinstallieren und neu installieren, falls das Update nicht greift. |
