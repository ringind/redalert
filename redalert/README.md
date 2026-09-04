# Red Alert Entertainment

Star-Trek-„Alarmstufe Rot“-Effekt über Philips-Hue-Lampen via **Hue
Entertainment API** (DTLS-Streaming), mit Ingress-Web-UI, auf **bis zu 3
Bridges gleichzeitig** – jede mit eigenem Effekt/Farbe/Timing möglich.
Effekte: `pulse` (alle Lampen gemeinsam im Takt, Standard) und `chase`
(umlaufender Komet mit Schweif).

Vollständige Anleitung: siehe **[DOCS.md](DOCS.md)** (wird in HA als Tab
„Dokumentation“ angezeigt).

## Auf einen Blick

- **Info / Konfiguration / Dokumentation / Protokoll**: Standard-Tabs des Add-ons.
- **Steuerung**: Seitenleisten-Panel „Red Alert“ (Ingress) – Pairing/Bereiche
  je Bridge (bis zu 3), optional eigener Effekt/Farbe/Timing je Bridge;
  Dauer/fps und Start/Stop gemeinsam für alle Bridges.
- **REST-API** auf Port `8099`: `/health`, `/config`, `/pair`, `/areas`,
  `/start`, `/stop` – für `rest_command`-Automationen.
- Container-HEALTHCHECK auf `/health`, s6-Supervision, DE/EN-Übersetzung.

## Dateien

| Datei | Zweck |
|-------|-------|
| `config.yaml` | Add-on-Manifest (Optionen, Ingress, Ports). |
| `build.yaml` | Basis-Images (`home-assistant/base-python`). |
| `Dockerfile` | Image-Build. |
| `translations/` | Beschriftung der Konfigurationsoberfläche (de/en). |
| `rootfs/etc/s6-overlay/…` | Service-Definition (Start/Logging). |
| `rootfs/app/main.py` | REST-Server, Effekt-Loop, Ingress-Panel. |
| `rootfs/app/chase.py` | Effekt-Berechnung: `RedAlertPulse` (Takt) + `RedAlertChase` (Komet+Schweif). |
| `rootfs/app/panel.html` | Web-UI. |
