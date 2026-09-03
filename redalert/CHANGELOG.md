# Changelog

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
