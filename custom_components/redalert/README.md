# Red Alert Entertainment – Home-Assistant-Integration

🇩🇪 Deutsch (diese Datei) · 🇬🇧 [English](README.en.md)

Eigenständige `custom_component` für die App [`redalert`](../../redalert): spricht
deren REST-API an (siehe [`redalert/DOCS.md`](../../redalert/DOCS.md#rest-api))
und legt sechs Entities an – ohne `rest_command`/Template-Umweg (siehe
[„Home Assistant einbinden“](../../redalert/DOCS.md#home-assistant-einbinden)
für die Variante ganz ohne Zusatzinstallation).

| Entity | Domain | Zeigt / tut |
|---|---|---|
| **Betriebszustand** | `binary_sensor` | `on`, solange die App auf **irgendeiner** Bridge gerade einen Effekt fährt (`running` aus `/config`). |
| **Scharfgeschaltet** | `binary_sensor` | `on`, wenn **alle** nicht-`neutral` Bridges scharfgeschaltet sind (`armed` aus `/config`); `armed_bridges` als Attribut. Nur-Lese-Anzeige neben dem gleichnamigen Schalter. |
| **Animation** | `switch` | Ein = `POST /start` (mit dem aktuell geladenen Effektset, falls eines gewählt ist, sonst App-Standard) – startet **alle** konfigurierten Bridges gemeinsam. Aus = `POST /stop` (stoppt alle laufenden Bridges). |
| **Animation (\<Bridge-IP\>)** | `switch` | Je eine weitere Switch-Entity pro gepaarter Bridge (dynamisch aus `/config`'s `bridges`-Liste angelegt) – startet/stoppt **nur diese eine** Bridge (`bridge_host` im `/start`/`/stop`-Body), unabhängig vom Zustand der anderen. Verschwindet eine Bridge aus der App-Konfiguration, wird ihr Switch nicht gelöscht, sondern nur `unavailable`. |
| **Scharfgeschaltet** | `switch` | Ein = `POST /arm` (hält den DTLS-Stream **aller** nicht-`neutral` Bridges dauerhaft offen, sodass ein anschließender Animationsstart den ~3–9 s langen Handshake überspringt). Aus = `POST /disarm` (schließt die Streams, stellt den Lichtzustand wieder her). `on`, wenn alle diese Bridges scharf sind (`armed` aus `/config`). |
| **Effektset** | `select` | Dropdown mit allen gespeicherten Effektsets (`GET /presets`-Namen). Auswahl ruft `POST /select` auf: die App **lädt** das Set (`current_preset` + Übernahme der Bridge-`area_id`s). Läuft eine Animation bzw. ist eine Bridge scharfgeschaltet, schaltet die App den laufenden Effekt sofort ohne Neustart auf das neue Set um – sofern das Set pro aktiver Bridge dieselbe `area_id` hat; sonst schlägt die Auswahl mit einer Fehlermeldung fehl. |
| **Geladenes Effektset** | `sensor` | Name des geladenen/gestarteten Sets (`current_preset`; leer nach einem Ad-hoc-Start ohne `preset` oder `POST /select {"preset": null}`; ein Solo-Start einer einzelnen Bridge ändert diese Anzeige nie). |

Sechs plus eine Entity je gepaarter Bridge hängen an einem gemeinsamen Gerät
("Red Alert (<Host>)"); ein Config-Entry = eine App-Instanz.

> **Update auf ≥ 1.2.0:** Die Entitäten bekommen ein sprachunabhängiges,
> englisches `entity_id`-Schema (`binary_sensor.red_alert_<host>_running` usw.)
> und werden dafür **neu angelegt** – die alten (auf deutschen HA-Installationen
> z. B. `…_betriebszustand`) verschwinden. Verweise in Automationen und
> Dashboards entsprechend anpassen.

## Installation

### Über HACS (empfohlen)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ringind&repository=redalert&category=integration)

Dieses Repo ist HACS-fähig (`hacs.json` im Wurzelverzeichnis), aber **nicht**
im HACS-Standard-Store gelistet – als **benutzerdefiniertes Repository**
hinzufügen:

1. Obigen Button klicken – öffnet den Dialog direkt in deiner Home-Assistant-
   Instanz. **Oder** manuell: HACS → **⋮** (oben rechts) →
   **Benutzerdefinierte Repositories** → URL
   `https://github.com/ringind/redalert`, Kategorie **Integration**.
2. „Red Alert Entertainment“ in HACS suchen/öffnen → **Herunterladen**.
3. Home Assistant neu starten.

HACS liest dabei denselben Repo-Stand wie der App-Store – ein Release-Tag
(`vX.Y.Z`, siehe [`redalert/CHANGELOG.md`](../../redalert/CHANGELOG.md)) legt
fest, welchen Integrationsstand HACS als installierbare Version anbietet;
ohne Auswahl einer Version installiert HACS den `main`-Branch.

### Manuell (ohne HACS)

Den Ordner `custom_components/redalert/` aus diesem Repo in den
`custom_components/`-Ordner der Home-Assistant-Konfiguration kopieren (Pfad
danach: `config/custom_components/redalert/…`), Home Assistant neu starten.

## Einrichten

**Einstellungen → Geräte & Dienste → Integration hinzufügen → „Red Alert
Entertainment App“.** Abgefragt werden:

- **Host / IP** – z. B. `homeassistant.local` oder die IP des HA-Hosts (**nicht**
  der Ingress-Pfad – der feste REST-Port).
- **Port** – Standard `8099` (App-Tab „Netzwerk“, falls dort umgemappt).
- **SSL** / **SSL-Zertifikat prüfen** – nur relevant, falls die App hinter
  einem eigenen TLS-Reverse-Proxy läuft; im Normalfall beides aus/an lassen
  (kein SSL).

Die Integration prüft beim Einrichten `GET /health`; ist noch keine Bridge
gepaart, wird nur eine Warnung geloggt (kein Abbruch) – Pairing lässt sich
jederzeit nachträglich in der App-Web-UI erledigen.

## Verhalten im Detail

- Poll-Intervall: alle 10 s `GET /config` (ein Aufruf liefert `running`,
  `armed`, `armed_bridges`, `presets` und `current_preset` zusammen).
- „Geladenes Effektset“ kommt von der App selbst (`current_preset` in
  `/health`/`/config`) – gilt also auch, wenn ein Set über das Web-UI, einen
  rohen `/start`-Aufruf mit `preset` oder `POST /select` gesetzt wurde, nicht
  nur über die `select`-Entity.
- Die `select`-Entity ruft immer `POST /select` auf. Läuft nichts und ist
  nichts scharf, wird das Set nur geladen (`current_preset` + `area_id`s); erst
  `switch.…_animation` (bzw. `/start {"preset": …}`) fährt es. Läuft bereits
  eine Animation bzw. ist eine Bridge scharf, schaltet die App den Effekt
  **sofort ohne Neustart/Handshake** auf das neue Set um – nur wenn das Set pro
  aktiver Bridge dieselbe `area_id` hat; sonst schlägt die Auswahl mit
  `HomeAssistantError` fehl (der Server antwortet `409`).
- Ein Ad-hoc-Start ganz ohne `preset` (z. B. der reine „Start“-Button im
  Web-UI ohne Effektset-Auswahl) räumt „Geladenes Effektset“ wieder auf leer.
- `switch.animation` aus schaltet **die gesamte laufende Animation** ab
  (`/stop`) – unabhängig davon, ob sie über das Web-UI, `/start` direkt oder
  diese Integration gestartet wurde.

## Icon/Logo

`custom_components/redalert/brand/{icon,logo}.png` liefern das Marken-Bild
für diese Integration – seit Home Assistant 2026.3 zeigt HA das direkt an
(Geräteseite, „Integration hinzufügen“-Suche), ganz ohne Eintrag im
zentralen [`home-assistant/brands`](https://github.com/home-assistant/brands)-Repo.
In der **HACS-eigenen** Downloads-Übersicht kann statt dessen noch ein
Platzhalter erscheinen – bekannter, offener HACS-Bug bei benutzerdefinierten
(nicht im Standard-Store gelisteten) Repositories mit nur lokalem Marken-Bild
([hacs/integration#5223](https://github.com/hacs/integration/issues/5223),
[#5171](https://github.com/hacs/integration/issues/5171)); liegt an HACS, nicht
an diesem Repo, und behebt sich von selbst, sobald HACS das gefixt hat.
