# Red Alert Entertainment

Star-Trek-„Alarmstufe Rot“-Effekt über Philips-Hue-Lampen via **Hue
Entertainment API** (DTLS-Streaming), mit Ingress-Web-UI und Audio-Sync per
Cue-Datei. Effekte: `pulse` (alle Lampen gemeinsam im Takt, Standard) und
`chase` (Larson-Lauflicht).

Vollständige Anleitung: siehe **[DOCS.md](DOCS.md)** (wird in HA als Tab
„Dokumentation“ angezeigt), inkl. Abschnitt
[„Synchronisation zur Musik“](DOCS.md#synchronisation-zur-musik).

## Auf einen Blick

- **Info / Konfiguration / Dokumentation / Protokoll**: Standard-Tabs des Add-ons.
- **Steuerung**: Seitenleisten-Panel „Red Alert“ (Ingress) – Pairing, Bereiche
  laden, Effekt, Start/Stop, Farbe/Dauer/`cue_offset`/fps.
- **REST-API** auf Port `8099`: `/health`, `/config`, `/pair`, `/areas`,
  `/start`, `/stop`, `/sync` – für `rest_command`-Automationen.
- Container-HEALTHCHECK auf `/health`, s6-Supervision, DE/EN-Übersetzung.

## Dateien

| Datei | Zweck |
|-------|-------|
| `config.yaml` | Add-on-Manifest (Optionen, Ingress, Ports). |
| `build.yaml` | Basis-Images (`home-assistant/base-python`). |
| `Dockerfile` | Image-Build. |
| `translations/` | Beschriftung der Konfigurationsoberfläche (de/en). |
| `rootfs/etc/s6-overlay/…` | Service-Definition (Start/Logging). |
| `rootfs/app/main.py` | REST-Server, Effekt-Loop, `/sync`, Ingress-Panel. |
| `rootfs/app/chase.py` | Effekt-Berechnung: `RedAlertPulse` (Takt) + `RedAlertChase` (Larson). |
| `rootfs/app/panel.html` | Web-UI. |
| `rootfs/app/redalert_cue.json` | Vorgefertigte Helligkeits-Hüllkurve (kein Audio). |
