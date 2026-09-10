"""Konstanten der Red-Alert-Entertainment-Integration."""

from datetime import timedelta

DOMAIN = "redalert"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SSL = "ssl"
CONF_VERIFY_SSL = "verify_ssl"
CONF_API_TOKEN = "api_token"

DEFAULT_PORT = 8099
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

# Interner Container-Port der App (immer 8099, unabhängig von einem – seit
# App-2.0.0 nicht mehr existierenden – LAN-Port-Mapping). Für die
# Supervisor-Autoerkennung, die das Add-on über seinen internen Hostnamen
# anspricht.
ADDON_INTERNAL_PORT = 8099
# Slug-Endung des Add-ons (Store-Repo-Präfix variabel: "<repo>_redalert").
ADDON_SLUG_SUFFIX = "redalert"

# Wie oft /health + /config abgefragt werden (Web-UI der App pollt alle 5 s,
# siehe CLAUDE.md – hier bewusst etwas entspannter, das ist kein Live-Panel).
UPDATE_INTERVAL = timedelta(seconds=10)

# Netzwerk-Timeout je Aufruf an die App (großzügig: /start antwortet zwar
# sofort, aber der Supervisor-Host kann unter Last kurz hängen).
REQUEST_TIMEOUT = 10
