# Red Alert Entertainment – Home-Assistant-Integration

Diese Integration steuert die **Red Alert Entertainment App** (Hue-Entertainment-
Lauflicht, Star Trek „Alarmstufe Rot“) aus Home Assistant heraus – sie spricht
ausschließlich deren REST-API an und enthält keine eigene Licht-/Bridge-Logik.
Einrichtung der App selbst (Hue-Bridge pairen, Entertainment-Bereich, Effekte)
steht in deren eigener Doku, nicht hier:
[App-Dokumentation](https://github.com/ringind/redalert/blob/main/redalert/DOCS.md) ·
[Haupt-README](https://github.com/ringind/redalert#readme).

Legt vier Entities an einem Gerät an: `binary_sensor` (läuft der Effekt
gerade?), `switch` (Animation an/aus), `select` (gespeichertes Effektset
wählen & laden), `sensor` (Name des aktuell geladenen Sets).

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ringind&repository=redalert&category=integration)

1. Obigen Button klicken – **oder** manuell: HACS → **⋮** (oben rechts) →
   **Benutzerdefinierte Repositories** → URL
   `https://github.com/ringind/redalert`, Kategorie **Integration**.
2. „Red Alert Entertainment“ in HACS suchen → **Herunterladen**.
3. Home Assistant neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen** → „Red Alert
   Entertainment App“ suchen, Host + Port der App eingeben (Standard `8099`).

**Voraussetzung:** die App **Red Alert Entertainment** muss bereits
installiert und erreichbar sein – sie ist kein Bestandteil dieser Integration
(siehe oben, „App Store“-Installation im Haupt-README).

Ausführliche Doku zur Integration (Config-Flow-Felder, Entity-Verhalten im
Detail): [`custom_components/redalert/README.md`](https://github.com/ringind/redalert/blob/main/custom_components/redalert/README.md).
