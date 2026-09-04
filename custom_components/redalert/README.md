# Red Alert Entertainment – Home-Assistant-Integration

Eigenständige `custom_component` für die App [`redalert`](../../redalert): spricht
deren REST-API an (siehe [`redalert/DOCS.md`](../../redalert/DOCS.md#rest-api))
und legt vier Entities an – ohne `rest_command`/Template-Umweg (siehe
[„Home Assistant einbinden“](../../redalert/DOCS.md#home-assistant-einbinden)
für die Variante ganz ohne Zusatzinstallation).

| Entity | Domain | Zeigt / tut |
|---|---|---|
| **Läuft** | `binary_sensor` | `on`, solange die App gerade einen Effekt fährt (`running` aus `/config`). |
| **Animation** | `switch` | Ein = `POST /start` (mit dem aktuell geladenen Effektset, falls eines gewählt ist, sonst App-Standard). Aus = `POST /stop`. |
| **Effektset** | `select` | Dropdown mit allen gespeicherten Effektsets (`GET /presets`-Namen); Auswahl lädt **und startet** das Set sofort (`POST /start {"preset": …}`). |
| **Geladenes Effektset** | `sensor` | Name des zuletzt geladenen Sets (leer bei einem Ad-hoc-Start ohne `preset`, z. B. über die App-Web-UI oder direkten `/start`-Aufruf ohne `preset`). |

Alle vier hängen an einem gemeinsamen Gerät ("Red Alert (<Host>)"); ein
Config-Entry = eine App-Instanz.

## Installation

### Über HACS (empfohlen)

Dieses Repo ist HACS-fähig (`hacs.json` im Wurzelverzeichnis), aber **nicht**
im HACS-Standard-Store gelistet – als **benutzerdefiniertes Repository**
hinzufügen:

1. HACS → **⋮** (oben rechts) → **Benutzerdefinierte Repositories**.
2. URL `https://github.com/ringind/redalert`, Kategorie **Integration**.
3. „Red Alert Entertainment“ in HACS suchen/öffnen → **Herunterladen**.
4. Home Assistant neu starten.

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
  `presets` und `current_preset` zusammen).
- „Geladenes Effektset“ kommt von der App selbst (`current_preset` in
  `/health`/`/config`) – gilt also auch, wenn ein Set über das Web-UI oder
  einen rohen `/start`-Aufruf mit `preset` gestartet wurde, nicht nur über
  diese Integration.
- Ein Ad-hoc-Start ganz ohne `preset` (z. B. der reine „Start“-Button im
  Web-UI ohne Effektset-Auswahl) räumt „Geladenes Effektset“ wieder auf leer.
- `switch.animation` aus schaltet **die gesamte laufende Animation** ab
  (`/stop`) – unabhängig davon, ob sie über das Web-UI, `/start` direkt oder
  diese Integration gestartet wurde.
