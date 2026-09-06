# Changelog

## 1.14.0

- **Doku jetzt auch auf Englisch.** Neu: `README.en.md`, `redalert/DOCS.en.md`,
  `custom_components/redalert/README.en.md`, `info.en.md` – jeweils
  eigenständige, vollständige Übersetzung statt zweisprachiger Datei (da HAs
  Dokumentations-Tab keine Sprachumschaltung kennt). Jede Datei verlinkt oben
  auf ihr Pendant in der jeweils anderen Sprache.

## 1.13.0

- **Web-UI jetzt zweisprachig (Deutsch/Englisch).** Umschalter oben rechts
  (DE/EN), Wahl wird pro Browser gespeichert; Vorbelegung anhand der
  Browsersprache. Betrifft alle Beschriftungen, Erklärtexte, Optionsnamen und
  Protokollmeldungen der Bedienoberfläche – die REST-API selbst bleibt
  unverändert (Feldnamen, Fehlermeldungen).

## 1.12.0

- **Breaking: Effekt `sunrise` entfernt.** War zu ähnlich zu `aurora`/`pulse`
  und wurde kaum genutzt. Bestehende Effektsets, gespeicherte `bridges`-
  Optionen und `rest_command`-Aufrufe mit `effect: sunrise` werden nicht mehr
  erkannt und fallen auf `pulse` zurück.
- **Breaking: Option `police_color2` in `color2` umbenannt**, da sie schon
  seit `duel` (v1.11.0) nicht mehr nur für `police` gilt, sondern auch die
  zweite Kometfarbe von `duel` liefert. Bestehende Konfigurationen und
  `/start`-Aufrufe mit `police_color2` müssen auf `color2` angepasst werden.
- **Rechtlicher Hinweis zur Audiodatei entfernt** (README.md §10) – war reine
  Klarstellung ohne rechtliche Bindungswirkung; die App selbst verarbeitet
  keine Audiodateien.

## 1.11.0

- **6 weitere neue Effekte** (jetzt 18 insgesamt):
  - **`ripple`** – wie `firework`, aber die Welle prallt an beiden Enden der
    Kanäle ab und läuft als Echo zurück, bevor sie verblasst. Neue Optionen
    `ripple_interval_ms` (Standard 3000), `ripple_speed` (Standard 6.0).
  - **`wave`** – eine durchgehende Sinuswelle aus Helligkeit läuft über die
    Kanäle, mehrere Wellenberge gleichzeitig sichtbar. Neue Option
    `wave_length` (Kanäle pro voller Welle, Standard 3.0).
  - **`flicker`** – Lampen brechen sporadisch kurz von voller Helligkeit ein,
    wie eine defekte Glühbirne. Neue Optionen `flicker_interval_ms`
    (Standard 600), `flicker_dip_ms` (Standard 150).
  - **`strobe`** – ein hartes, sofortiges Blitzen ohne Überblendung
    (Party-Stroboskop). Nutzt `sweep_seconds` für die Periodendauer, keine
    neuen Optionen.
  - **`duel`** – zwei Kometen starten an entgegengesetzten Enden, treffen
    sich in der Mitte und prallen zurück. Nutzt `sweep_seconds` und die neu
    für mehrere Effekte freigegebene Option `police_color2` als Farbe des
    zweiten Kometen.
  - **`sunrise`** – ein langsamer Farb- und Helligkeitsbogen für alle Lampen
    einer Bridge gemeinsam, wandert zwischen `police_color2` (dunkel/warm)
    und `color` (hell) und zurück. `sweep_seconds` ist jetzt bis 300 (statt
    5) Sekunden einstellbar, damit ein Sonnenaufgang mehrere Minuten dauern
    kann – die anderen Effekte funktionieren mit den bisherigen kurzen
    Werten unverändert weiter.
  - `police_color2` heißt jetzt allgemein „zweite Farbe“, da sie neben
    `police` jetzt auch von `duel` und `sunrise` genutzt wird.
- Web-UI: neue Effekt-Optionen in der Auswahl jeder Bridge-Karte, neue
  Eingabefelder für `ripple`/`wave`/`flicker`, Status zeigt die neuen
  Konfigurationswerte.
- Live gegen die echte Bridge getestet: alle 6 neuen Effekte liefen sauber
  (korrekte Frame-Zahl, keine Tracebacks).

## 1.10.0

- **8 neue Effekte.** Die App ist damit kein reiner Star-Trek-Effekt mehr,
  sondern ein allgemeiner Hue-Entertainment-Lichteffekt-Player:
  - **`police`** – Alarmlicht: jede zweite Lampe bildet eine Gruppe, die
    beiden Gruppen blinken abwechselnd in `color` bzw. der neuen Option
    `police_color2` (Standard Blau).
  - **`lightning`** – Gewitter: alle Lampen einer Bridge blitzen gemeinsam
    auf (statt wie `glitter` unabhängig je Lampe), mit gelegentlichem
    Doppelblitz. Neue Optionen `lightning_interval_ms` (Standard 4000),
    `lightning_flash_ms` (Standard 500).
  - **`heartbeat`** – ein Doppelpuls („lub-dub“) statt eines einzelnen
    Pulses, im Takt von `sweep_seconds`; nutzt dieselben `attack_ms`/
    `release_ms` wie `pulse`.
  - **`aurora`** – Polarlicht: langsame, weiche Farbwellen aus `glitter_colors`
    wandern über die Lampen; eine volle Welle dauert `4 × sweep_seconds`.
  - **`rainbow`** – ein durchgehender, phasenversetzter Regenbogen-Farbumlauf
    über die Lampen; eine volle Umdrehung dauert `4 × sweep_seconds`.
  - **`meteor`** – mehrere unabhängige Kometen mit zufälliger Geschwindigkeit,
    Richtung und Helligkeit. Neue Optionen `meteor_count` (Standard 3),
    `meteor_speed` (Standard 1.2).
  - **`wipe`** – ein Auffüll-Balken läuft einmal über die Kanäle, hält kurz
    voll (`chase_pause`) und beginnt von vorn (Dauer `sweep_seconds`).
  - **`firework`** – wiederkehrende Ausbrüche von der Kanalmitte aus. Neue
    Optionen `firework_interval_ms` (Standard 3000), `firework_speed`
    (Standard 6.0).

  Alle neuen Parameter sind wie gehabt in der App-Konfiguration, im
  `/start`-Body und je Bridge in `bridges` einstellbar. Web-UI: neue
  Effekt-Optionen in der Auswahl jeder Bridge-Karte, neue Eingabefelder
  (inkl. Farbwähler für `police_color2`), Status zeigt die neuen
  Konfigurationswerte.
- **README.md/info.md:** Effekt-Liste und Optionstabellen um die 8 neuen
  Effekte ergänzt.

## 1.9.2

- **Web-UI:** das Feld „chase: Richtung(en)“ (`gc_direction`) beschreibt jetzt
  direkt im Label und per Tooltip die gültigen Werte (`forward`, `backward`,
  `bounce`) statt sie nur im Platzhaltertext anzudeuten.
- **Doku (README.md, info.md):** Einleitung überarbeitet – die App ist ein
  allgemeiner, per Effektset konfigurierbarer Hue-Entertainment-
  Lichteffekt-Player (Puls, Komet, Funkeln, Lauflicht für Gradient-
  Lightstrips, frei wählbare Farben), die Star-Trek-„Alarmstufe Rot“-Szene
  ist nur ein Beispiel-Effektset. `media_player`/Audiodatei als Voraussetzung
  jetzt klar als optional (nur für die Sound+Licht-Automation) markiert.

## 1.9.1

- **Fix: Web-UI reagierte manchmal nicht mehr, erst ein Reload half.**
  Ursache: `fetch()`-Aufrufe im Web-UI hatten kein Zeitlimit – blieb einer
  hängen (z. B. Bridge kurz nicht erreichbar), stauten sich dahinter weitere
  Aufrufe (der 5s-Status-Poll eingeschlossen), bis der Browser sein Limit an
  gleichzeitigen Verbindungen pro Origin erreichte und auch Klicks auf
  Start/Stop/Pairen ins Leere liefen. Jeder Aufruf hat jetzt ein Zeitlimit
  (15 s, `/pair` 35 s – wartet serverseitig bis zu 30 s auf den Link-Button)
  und bricht kontrolliert ab statt unbegrenzt zu hängen; überlappende
  Status-Polls (falls einer doch mal länger braucht) werden jetzt
  übersprungen statt sich zu stauen; beim Zurückkehren zu einem
  zwischenzeitlich inaktiven Browser-Tab (Ingress-Panel im Hintergrund, vom
  Browser gedrosselt) wird sofort neu geladen statt bis zu einer Minute auf
  den nächsten Tick zu warten. Zusätzlich bekommen die App-eigenen
  Hue-CLIP-v2-Aufrufe beim Sichern/Wiederherstellen des Lichtzustands ein
  8s-Zeitlimit (vorher aiohttp-Standard 300 s), damit eine kurz nicht
  erreichbare Bridge `state["task"]` nicht minutenlang fälschlich auf
  „läuft“ hält.
- **Effekt-Bezeichnungen im Web-UI korrigiert:** `chase` (Gradient-Lightstrip-
  Bänder) heißt jetzt „Lauflicht“ (vorher fälschlich „Gradient-Strip“),
  `comet` heißt jetzt „Komet“ (vorher fälschlich „Lauflicht“).
- **Web-UI, „2 · Steuerung“:** Start/Stop stehen jetzt oben am Anfang des
  Abschnitts statt nach den Parameter-Erklärungen.
- **Home-Assistant-Integration:** Der `binary_sensor` heißt auf Deutsch jetzt
  „Betriebszustand“ (vorher „Läuft“); außerdem stand die deutsche
  Quell-Übersetzung (`strings.json`) versehentlich in der Datei, aus der Home
  Assistant beim ersten Einrichten die technischen Entity-IDs ableitet – die
  ist jetzt (wie bei HA-Integrationen vorgesehen) Englisch, sodass neu
  angelegte Entities englische technische Namen bekommen (z. B.
  `binary_sensor.<gerät>_running`), unabhängig von der UI-Sprache.

## 1.9.0

- **Breaking: Effekt-Namen umbenannt.** Der bisherige Komet-Effekt heißt jetzt
  `comet` (vorher `chase`), der Gradient-Lightstrip-Effekt jetzt `chase`
  (vorher `gradient_chase`). Bestehende Effektsets (`/data/presets.json`),
  gespeicherte `bridges`-Optionen und `rest_command`-Aufrufe, die `effect:
  chase` oder `effect: gradient_chase` verwenden, müssen auf `comet` bzw.
  `chase` angepasst werden – alte Werte werden nicht mehr erkannt (fallen auf
  `pulse` zurück). Alle sonstigen Parameter (`gc_*`, `chase_pause`, …) heißen
  unverändert weiter.
- **Web-UI: Farbwähler statt Hex-Text für alle Farbparameter.** Jede
  Bridge-Karte bietet für `color` und `gc_background_color` jetzt einen
  Farbwähler mit „eigene Farbe verwenden“-Häkchen statt eines Hex-Textfelds;
  `glitter_colors` (je Bridge) besteht jetzt aus drei Farbwählern statt einem
  Freitextfeld.
- **Fix: Effekt-Auswahl „wie Konfiguration“ sprang zurück.** Der periodische
  Konfigurations-Sync (alle 5 s) konnte eine bewusst gewählte Bridge-Einstellung
  (z. B. „wie Konfiguration“ im Effekt-Feld) wieder überschreiben, sobald das
  Feld leer war. Alle Bridge-Karten-Felder merken sich jetzt, ob der Nutzer sie
  angefasst hat, und werden danach vom Sync nicht mehr angetastet.
- **Web-UI, „2 · Steuerung“: Eingabefelder entfernt.** Effekt/Farbe/Timing/
  Dauer/fps ließen sich hier nie wirksam setzen, weil jede Bridge entweder
  eigene Werte hat oder „wie Konfiguration“ nutzt – der Standard kommt jetzt
  ausschließlich aus der App-Konfiguration. Übrig bleiben die
  Parameter-Erklärungen sowie **Start**/**Stop**.
- **„wie oben“ → „wie Konfiguration“** in der Effekt-Auswahl jeder Bridge-Karte
  (Bezug auf die App-Konfiguration statt der jetzt entfernten Felder unter
  „2 · Steuerung“).
- **Status zeigt jetzt alle Konfigurationsparameter**, inklusive
  `restore_state` und `log_level` (vorher nicht angezeigt); `/config` liefert
  `log_level` neu mit.

## 1.8.0

- **Neuer Effekt `gradient_chase`** – nur für Hue Gradient Lightstrips (jeder
  Kanal ein Farb-Segment statt einer eigenen Lampe): ein oder mehrere weich
  überblendete Zwei-Farben-Bänder laufen über die Segmente. Neue Parameter
  (Option, `/start`-Body **und** je Bridge in `bridges` überschreibbar, außer
  `gc_strip_lengths`, das nur je Bridge existiert): `gc_direction`
  (`forward`/`backward`/`bounce`), `gc_count`, `gc_length`, `gc_speed`,
  `gc_background_color`, `gc_chase_glitter` (Bänder funkeln zusätzlich wie
  `glitter`), `gc_background_pulse` (Hintergrund pulsiert zusätzlich wie
  `pulse`). Mehrere kombinierte Gradient Lightstrips (eine Entertainment Area
  mit mehreren Geräten) lassen sich über `gc_strip_lengths` wieder in ihre
  einzelnen physischen Strips aufteilen, jeder mit eigener `gc_direction` (als
  Liste, eine Richtung je Strip).
- Web-UI: Effekt-Auswahl (Standard **und** je Bridge) sowie Steuerungsfelder
  für alle neuen `gc_*`-Parameter, inkl. Strip-Längen je Bridge.

## 1.7.0

- **Neue Home-Assistant-Integration** (`custom_components/redalert/`, siehe
  README darin): vier Entities – `binary_sensor` (läuft der Effekt?),
  `switch` (Animation an/aus), `select` (gespeichertes Effektset auswählen &
  laden), `sensor` (Name des aktuell geladenen Sets). Eigenständige
  `custom_component`, kein Bestandteil des App-Containers.
- **`/health` und `/config` liefern jetzt `current_preset`** (Name des
  zuletzt per `POST /start {"preset": ...}` geladenen Effektsets, `null` bei
  Ad-hoc-Start ohne `preset`) – Grundlage für die neue Integration, auch per
  REST direkt nutzbar.
- **HACS-fähig:** `hacs.json` im Repo-Wurzelverzeichnis plus
  `.github/workflows/hacs.yaml` (`hacs/action` + `hassfest`) machen
  `custom_components/redalert/` als benutzerdefiniertes HACS-Repository
  (Kategorie *Integration*) installierbar.
- **Terminologie an Home Assistant 2026.2 angepasst:** „Add-on“ heißt dort
  jetzt „App“ (rein UI-/Dokutext, technisch unverändert – weiterhin
  Docker-Container über den Supervisor, `repository.yaml`/`config.yaml`
  unangetastet). Alle Doku (`README.md`, `DOCS.md`, Integrations-README,
  Config-Flow-Texte) sowie `repository.yaml`s Anzeigename entsprechend
  aktualisiert.

## 1.6.1

- **Web-UI, „2 · Steuerung“: `attack_ms`/`release_ms` jetzt auch als
  gemeinsamer Standard einstellbar.** Bisher gab es die beiden `pulse`-Timing-
  Felder nur je Bridge-Karte („Effekt für diese Bridge anpassen“) – der
  Standardwert für Bridges ohne eigene Einstellung ließ sich im Web-UI nicht
  setzen (nur über die Add-on-Option bzw. direkt per `/start`-Body). Neue
  Felder **Attack (ms)** / **Release (ms)** neben `sweep_seconds`/`chase-
  Pause`.
- **Web-UI: sichtbarer Klickeffekt auf allen Buttons.** Bisher hatten nur
  Start/Stop eine gedrückte Optik (an den laufenden Zustand gekoppelt); jetzt
  gibt jeder Button (Pairen, Bereiche laden, Lampen zuordnen, Effektsets,
  Protokoll, Aktualisieren, …) beim Anklicken/Antippen kurz sichtbar nach.

## 1.6.0

- **Neuer Effekt-Wert `neutral`.** `effect: neutral` (in der Regel je Bridge in
  `bridges[]` gesetzt) lässt die betreffende Bridge komplett unangetastet – kein
  DTLS-Stream, kein Sichern/Wiederherstellen. So kann ein Effektset auf einer
  Bridge einen Effekt fahren und eine andere Bridge auslassen. Eine
  `neutral`-Bridge braucht keine `area_id`. Sind **alle** Start-Bridges
  `neutral`, antwortet `/start` mit `{"status": "no_active_bridges"}` (kein
  Fehler, kein laufender Effekt). Auswählbar in der Add-on-Konfiguration, im
  Web-UI („2 · Steuerung“ und je Bridge-Karte) und im `/start`-Body; `effect`
  akzeptiert jetzt `pulse` | `chase` | `glitter` | `neutral`.

## 1.5.0

- **Effektsets (Presets).** Der komplette Satz an Start-Parametern (alle
  Bridge-Karten aus „1 · Bridges“ **und** die Steuerung aus „2 · Steuerung“)
  lässt sich unter „3 · Effektsets“ im Web-UI unter einem Namen speichern
  (z. B. *Star Trek – Alarmstufe Rot*), wieder laden, direkt starten, als
  JSON-Datei herunter- und wieder hochladen und löschen. Die Sets liegen als
  `/data/presets.json` im Add-on-Datenordner. Neue REST-Endpunkte
  `GET /presets` (alle bzw. `?name=…` eines), `PUT`/`POST /presets`
  (`{"name","config"}` – speichern/hochladen), `DELETE /presets?name=…`; und
  `POST /start {"preset": "<Name>"}` startet ein Set direkt (weitere
  Body-Felder überschreiben es für diesen Aufruf). `/config` liefert die
  Set-Namen unter `presets` mit.
- **Neuer Effekt `glitter` (Diamant-Gefunkel).** Jede Lampe funkelt für sich:
  in zufälligen Momenten – im Mittel alle `glitter_interval_ms` ms über alle
  Lampen einer Bridge – springt eine Lampe auf `glow_high` in einer zufällig
  aus `glitter_colors` gezogenen Farbe und klingt mit der Zeitkonstante
  `glitter_flash_ms` wieder auf `glow_low` ab; ist `glitter_flash_ms` größer
  als `glitter_interval_ms`, funkeln mehrere Lampen gleichzeitig. Neue Optionen
  `glitter_interval_ms` (Standard 90), `glitter_flash_ms` (Standard 260) und
  `glitter_colors` (Standard `#FFFFFF #CFE8FF #FFF1D0`; leer = Bridge-Farbe) –
  in der Add-on-Konfiguration, im Web-UI („2 · Steuerung“ und je Bridge-Karte)
  und im `/start`-Body, wie die übrigen Effekt-Parameter je Bridge
  überschreibbar. `effect` akzeptiert jetzt `pulse` | `chase` | `glitter`.

## 1.4.0

- **Neue Option `duration`.** Die Standard-Effektdauer (Sekunden, für alle
  Bridges gemeinsam) ist jetzt in der Add-on-Konfiguration einstellbar, statt
  fest auf 30 s codiert zu sein. **`0` (Vorgabe im Auslieferungszustand) =
  unbegrenzt** – der Effekt läuft dann bis `POST /stop`, statt nach 30 s von
  selbst zu enden. Im `/start`-Body bleibt `duration` weiterhin pro Aufruf
  übersteuerbar (ebenfalls `0` = unbegrenzt für diesen einen Aufruf).
  **Achtung:** Bestehende Automationen, die sich auf das automatische Ende
  nach 30 s verlassen haben, laufen ab dieser Version unbegrenzt weiter, bis
  entweder `duration` gesetzt oder explizit `/stop` aufgerufen wird.

## 1.3.0

- **Effekt je Bridge einzeln konfigurierbar.** Jede Zeile der Option
  `bridges` (und jeder Eintrag im `/start`-Body `bridges`) kann jetzt
  zusätzlich zu `bridge_host`/`area_id`/`channel_order` optional `effect`,
  `color`, `sweep_seconds`, `chase_pause`, `attack_ms`, `release_ms`,
  `glow_low`, `glow_high` setzen – **inklusive der Effekt-Art** (`pulse` oder
  `chase`). Nicht gesetzte Werte fallen weiter auf die gleichnamige Option
  bzw. den `/start`-Body-Wert zurück, der damit zum **Standard für Bridges
  ohne eigene Einstellung** wird. `duration`, `fps` und `restore_state`
  bleiben für alle Bridges gemeinsam (nicht pro Bridge). Alle Bridges starten
  weiterhin gleichzeitig (parallele DTLS-Handshakes, gemeinsame Start-Uhr) –
  auch wenn sie unterschiedliche Effekte zeigen.
- **Web-UI:** jede Bridge-Karte hat jetzt einen aufklappbaren Abschnitt
  „Effekt für diese Bridge anpassen“ (Effekt, Farbe, sweep_seconds,
  chase_pause, Attack/Release, glow_low/glow_high) – leer gelassen gilt der
  Standard aus „2 · Steuerung“.

## 1.2.0

- **Bis zu 3 Hue Bridges gleichzeitig.** Die Optionen `bridge_host`/`area_id`/
  `channel_order` sind zur Liste **`bridges`** zusammengefasst (max. 3 Zeilen,
  je `bridge_host` + `area_id` + optional `channel_order`) – bestehende
  Einzel-Bridge-Konfigurationen müssen in die neue Liste umgezogen werden.
  `/start` fährt alle konfigurierten (oder im Body per `bridges` übergebenen)
  Bridges mit **denselben** Effekt-Parametern (Farbe, Dauer, Timing) **synchron**
  ab: alle DTLS-Handshakes starten parallel, die Effekt-Uhr beginnt erst, wenn
  alle fertig sind. Ist eine Bridge nicht erreichbar/gepaart, starten die
  übrigen trotzdem („best effort“, siehe `failed_bridges` in der Antwort);
  `/start` schlägt nur fehl, wenn **keine** Bridge startet.
  `credentials.json` ist jetzt nach `bridge_host` verschlüsselt (alte
  Einzel-Bridge-Dateien werden beim Laden automatisch migriert, kein
  Re-Pairing nötig). `/pair` (Body `bridge_host`) und `/areas`
  (Query `bridge_host`) brauchen die Bridge jetzt explizit, sobald mehr als
  eine Bridge konfiguriert bzw. gepaart ist; `/identify` genauso (Body
  `bridge_host`).
- **Web-UI:** Abschnitt „1 · Bridges“ zeigt 3 Bridge-Karten (Pairing, Bereich,
  `channel_order`, „Lampen zuordnen“) – leere Karten werden beim Start
  ignoriert. „2 · Steuerung“ bleibt ein gemeinsames Formular für alle Bridges.

## 1.1.9

- **Cue-Funktion entfernt.** Kein Audio-Beat-Sync mehr über eine mitgelieferte
  `redalert_cue.json`: die Option `cue_file`, der `use_cue`-Schalter, `cue_offset`
  und der `/sync`-Endpunkt (Feinsynchronisation zur Musik) sind komplett
  entfallen, ebenso `tools/generate_cue.py`. `pulse` läuft jetzt immer nach der
  periodischen `sweep_seconds`-Uhr.
- **`duration` bestimmt jetzt allein die Laufzeit.** Ohne Angabe im `/start`-Body
  läuft der Effekt **30 Sekunden** (statt bisher bis zum Ende der Cue-Datei bzw.
  bis `/stop`), danach endet er von selbst.
- **Web-UI, „3 · Steuerung“:** das Farbfeld zeigt die gewählte Farbe jetzt
  deutlich größer an; **Start** und **Stop** zeigen per gedrücktem Zustand an,
  welcher der beiden gerade aktiv ist.
- **Web-UI, „Protokoll“:** neue Checkbox „Anfragen einblenden“ zeigt zusätzlich
  die gesendeten Request-Bodys; neue Knöpfe **Löschen** und **Herunterladen**
  (als Textdatei).

## 1.1.8

- **Neue Option `chase_pause` (Sekunden).** Steuert die Pause zwischen zwei
  `chase`-Durchläufen – in der Add-on-Konfiguration, im Web-UI („3 · Steuerung“)
  und per `/start`-Body. `0` (Standard) = nahtlos umlaufender Komet wie bisher.
  `> 0` = der Komet macht **einen** vollständigen Durchlauf (jede Lampe pulst
  einmal, die letzte glüht sauber aus), dann ruhen alle Lampen `chase_pause`
  Sekunden auf `glow_low`, dann der nächste Durchlauf.

## 1.1.7

- **`chase` nutzt die Cue standardmäßig nicht mehr.** Bisher war `use_cue` für
  beide Effekte per Default an – im Add-on (Cue immer geladen) wurde der
  `chase`-Komet dadurch im Klaxon-Takt auf ~12–19 % gedimmt und blitzte nur auf
  den unregelmäßigen Beats hell auf, also ganz anders als der ruhige Komet in
  den Tests. Jetzt: `use_cue` Default **`pulse` an, `chase` aus** (im `/start`-
  Body bzw. per Checkbox „Cue nutzen" übersteuerbar; die Checkbox folgt jetzt
  automatisch dem Effekt).
- **`duration` ohne Wert nimmt weiter die Cue-Länge**, auch wenn die Cue den
  Effekt nicht moduliert (`use_cue: false`) – so endet auch der cue-lose
  `chase` von selbst, statt bis `/stop` zu laufen.

## 1.1.6

- **Fix `chase`: Spitze flackerte unregelmäßig.** Das Puls-Maximum war nur ein
  einzelner Punkt (raised-cosine-Scheitel) – bei 25 fps traf ihn je nach
  Frame-Zeitpunkt mal 100 %, mal ~90 %, sodass jeder Sweep anders hell war. Die
  Spitze wird jetzt **flach auf 100 % gehalten** (`peak_frac`, Standard 0.08 des
  Zyklus); bei jeder Framerate landen mehrere Frames exakt auf dem Maximum.
- **`chase`: weicher Übergang zwischen den Lampen.** Der 100-%-Kopf ist jetzt
  etwas breiter als der Lampenabstand (`1/n + overlap_frac`, `overlap_frac`
  Standard 0.10 ≈ 140 ms). Dadurch stehen zwei benachbarte Lampen kurz gemeinsam
  auf 100 % und glühen dann nacheinander aus – es gibt keine Lücke mehr, in der
  keine Lampe voll leuchtet. `fade_frac`-Standard 0.60 → 0.62.

## 1.1.5

- **`glow_low` / `glow_high` – neue Optionen für beide Effekte.** Zwischen den
  Pulsen ruhen die Lampen jetzt auf `glow_low` (Standard `0.08`) statt auf `0`,
  im Puls-Maximum auf `glow_high` (Standard `1.0`). Gilt für `pulse` **und**
  `chase`, einstellbar in der Add-on-Konfiguration und im Web-UI (Abschnitt 3)
  sowie per `/start`-Body. `glow_low: 0` = wie bisher ganz aus.
- **`channel_order` als kommagetrennte Liste.** Die Option ist jetzt ein String
  (`"2,3,1,0,5,4"`) statt einer int-Liste – so lässt sie sich in der
  HA-Add-on-Konfiguration direkt eintippen. Alte Listen-Werte werden weiter
  akzeptiert; ungültige Eingaben werden ignoriert (Warnung im Log).

## 1.1.4

- **Fix `chase`: Flackern und ungleichmäßige Helligkeit.** Drei Ursachen:
  1. Die Helligkeit wurde aus der räumlichen `exp`-Distanz zum Kometenkopf
     berechnet; deren scharfe Spitze bei `d=0` wurde je nach Frame-Zeitpunkt mal
     getroffen, mal knapp verfehlt, sodass jeder Durchlauf einer Lampe anders
     hell war. Jetzt ist die Helligkeit ein reines **zeitliches Puls-Profil pro
     Lampe**: kurzer Raised-Cosine-Anstieg beim Eintreffen des Kopfes, dann
     langes `exp`-Ausblenden – jeder Durchlauf peakt exakt auf `1.0`. Eine
     einzelne Lampe pulst damit genauso (vorher: konstant `1.0`).
     `tail_len` / `head_len` ersetzt durch `attack_frac` / `decay_frac` /
     `fade_frac` (Bruchteile von `sweep_seconds`).
  2. Jede Lampe geht zwischen den Pulsen jetzt **ganz auf 0** und bleibt ein
     Stück des Zyklus dunkel (`fade_frac`, Standard 0.6), statt über ein
     `base_glow`-Grundleuchten nie ganz auszugehen (`base_glow` Standard jetzt
     `0`).
  3. Bei aktiver Cue wurde der Komet Frame für Frame mit dem **rohen**
     Cue-Gain multipliziert, der mehrfach pro Beat über einen weiten Bereich
     zappelt – sichtbares Flackern. Der Gain läuft jetzt durch dasselbe
     Beat-Gate + Slew wie `pulse` und dimmt den Kometen sauber zwischen 12 %
     (Beat aus) und 100 % (Beat an).
- **`channel_order` im Web-UI konfigurierbar.** Neues Feld unter „3 · Steuerung“
  (kommagetrennt, z. B. `2,3,1,0,5,4`); `/start` nimmt `channel_order` jetzt auch
  im Body an (Liste oder String). Ungültige Reihenfolge → `400` mit Hinweis.
- **Neu: „4 · Lampen zuordnen“ im Web-UI** + Endpoint `POST /identify`. Leuchtet
  Kanäle einzeln auf – einen bestimmten (`channel_id`) oder alle nacheinander –,
  um herauszufinden, welche `channel_id` welche physische Lampe ist. Ein
  DTLS-Handshake pro Durchlauf, danach Lampen-Wiederherstellung.

## 1.1.3

- **`chase` überarbeitet:** Der Komet läuft jetzt **gleichmäßig in eine
  Richtung** um alle Kanäle (wraparound, konstante Geschwindigkeit, kein
  Umkehr-Stocken) und zieht einen **exponentiell auslaufenden Schweif** hinter
  sich her – heller Kopf, kurzer Vorglanz, langer Nachlauf. `sweep_seconds` ist
  jetzt die Dauer **einer vollen Umrundung** (vorher: ein Durchlauf hin).
  Neue Feinparameter in `chase.py`: `tail_len`, `head_len`.
- **Lichtzustand sichern/wiederherstellen:** vor dem Effekt werden an/aus,
  Helligkeit und Farbe aller Bereichs-Lampen per Hue CLIP v2 gesichert und nach
  dem Effekt zurückgeschrieben. Option/Body `restore_state` (Standard `true`).

## 1.1.2

- **Fix `pulse`: der anschwellende Puls hatte Helligkeitssprünge.** Die rohe
  Cue-Hüllkurve zappelt beim Beat-Einsatz mehrfach über die Schwelle, wodurch
  der schnelle Release den Anstieg immer wieder zurückriss. Jetzt formt ein
  Schmitt-Trigger mit Off-Entprellung (`hi` ein, `lo` + `hold_s` aus) den Beat
  zu einem sauberen 0/1-Signal; der lineare Slew läuft dadurch **monoton** hoch
  und wieder runter – keine Sprünge mehr.

## 1.1.1

- **`pulse` geht jetzt voll von 0 auf 100 % und wieder auf 0.** Kein
  Grundglühen mehr (`base_glow` = 0). Eine Kontrastkurve (`lo`/`hi`) drückt
  Pausen auf echte 0 und laute Beats auf echte 100 %; ein Snap überbrückt die
  letzten Prozente.
- Standard-Fades umgestellt, sodass das **Abfallen schneller ist als das
  Aufblenden**: `attack_ms` 60 → **140**, `release_ms` 300 → **70**.

## 1.1.0

- **Neuer Effekt `pulse` (jetzt Standard):** alle Lampen blenden gemeinsam im
  Takt der Musik auf und in der Pause wieder ab. Der Verlauf kommt aus der
  Cue-Hüllkurve; `attack_ms` / `release_ms` steuern die Fade-Geschwindigkeit.
  Das bisherige Lauflicht bleibt als `effect: chase` erhalten.
- **`POST /sync`** – laufende Feinsynchronisation an die echte
  Wiedergabeposition des media_player (`{"position": <s>}`), Nachführung
  begrenzt auf ±0,5 s pro Aufruf.
- **`cue_offset`** (Option/Body) – Startposition in der Cue, um das Licht auf
  die bereits laufende Musik auszurichten.
- Effekt-Loop plant Frames gegen eine absolute Uhr → keine Drift der
  Licht-Zeitachse mehr.
- `/config` zeigt `effect`, `attack_ms`, `release_ms`, `sync_correction_s`;
  Web-UI bekommt Effekt-Auswahl und `cue_offset`-Feld.
- DOCS: neuer Abschnitt „Synchronisation zur Musik“ mit Regelschleifen-Automation.

## 1.0.1

- **Fix:** Start bricht ab mit `/bin/sh: can't open '/init': Permission denied`.
  Das mitgelieferte AppArmor-Profil (`apparmor.txt`) hat den s6-overlay-Entrypoint
  `/init` der HA-Basis nicht zugelassen. Profil entfernt – Home Assistant erzeugt
  automatisch ein passendes Standard-Profil.

## 1.0.0

Erstes vollständiges Add-on-Release.

- **Ingress-Web-UI** zur Steuerung (Pairing, Bereiche laden, Start/Stop, Farbe,
  Dauer, fps, sweep) – erreichbar über den Seitenleisten-Eintrag „Red Alert“.
- **s6-Overlay-Supervision** auf Basis der offiziellen `home-assistant/base-python`-Images
  inkl. bashio-Logging.
- **Container-HEALTHCHECK** auf `/health` – Supervisor startet den Dienst bei Hängern neu.
- `POST /start` antwortet sofort; der DTLS-Handshake (mehrere Sekunden) läuft
  im Hintergrund-Task – vermeidet Timeouts bei HA-`rest_command`.
- `REDALERT_DATA_DIR` überschreibt den Datenordner (`/data`) für lokale Tests.
- Neue Optionen `color` (Effektfarbe) und `log_level` (Protokoll-Ausführlichkeit).
- Neuer Endpoint `GET /config` (effektive Konfiguration für das Web-UI).
- `/start` akzeptiert zusätzlich `color` im Request-Body.
- Übersetzte Konfigurations-Oberfläche (DE/EN).
- Aufteilung in ein Add-on-Store-Repository (`repository.yaml` + `redalert/`).

## 0.1.0

- Interner Prototyp: REST-API (`/pair`, `/areas`, `/start`, `/stop`), Comet-Sweep,
  Audio-Sync per Cue-Datei.
