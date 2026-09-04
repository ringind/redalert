"""Konstanten der Red-Alert-Entertainment-Integration."""

from datetime import timedelta

DOMAIN = "redalert"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SSL = "ssl"
CONF_VERIFY_SSL = "verify_ssl"

DEFAULT_PORT = 8099
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

# Wie oft /health + /config abgefragt werden (Web-UI der App pollt alle 5 s,
# siehe CLAUDE.md – hier bewusst etwas entspannter, das ist kein Live-Panel).
UPDATE_INTERVAL = timedelta(seconds=10)

# Netzwerk-Timeout je Aufruf an die App (großzügig: /start antwortet zwar
# sofort, aber der Supervisor-Host kann unter Last kurz hängen).
REQUEST_TIMEOUT = 10
