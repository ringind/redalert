# Changelog

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
