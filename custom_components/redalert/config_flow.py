"""Config-Flow: Host/Port/API-Token der Red-Alert-App abfragen und per /health prüfen.

Läuft Home Assistant unter Supervisor, versucht der Flow, das Add-on und seinen
API-Token automatisch über die Supervisor-API zu finden und das Formular
vorzubelegen (der Nutzer bestätigt nur noch). Andernfalls – oder wenn die
Erkennung scheitert – werden die Felder manuell ausgefüllt (Token steht im
Add-on-Log und im Add-on-Konfigurationsdialog).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RedAlertApiClient, RedAlertApiError

if TYPE_CHECKING:
    from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from .const import (
    ADDON_INTERNAL_PORT,
    ADDON_SLUG_SUFFIX,
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_SUPERVISOR_API = "http://supervisor"


async def _discover_addon(hass: Any) -> dict[str, Any] | None:
    """Add-on-Host + API-Token über die Supervisor-API ermitteln.

    Gibt ``{host, port, api_token}`` zurück oder ``None`` (kein Supervisor,
    Add-on nicht installiert, keine Rechte)."""
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        return None
    session = async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {supervisor_token}"}
    try:
        async with session.get(f"{_SUPERVISOR_API}/addons", headers=headers) as resp:
            if resp.status != 200:
                return None
            addons = ((await resp.json()).get("data") or {}).get("addons") or []
        slug = next(
            (
                a["slug"]
                for a in addons
                if a.get("installed", True)
                and str(a.get("slug", "")).split("_", 1)[-1].split("-", 1)[-1] == ADDON_SLUG_SUFFIX
            ),
            None,
        )
        if not slug:
            return None
        async with session.get(f"{_SUPERVISOR_API}/addons/{slug}/info", headers=headers) as resp:
            if resp.status != 200:
                return None
            info = (await resp.json()).get("data") or {}
    except Exception as exc:  # noqa: BLE001 – Erkennung ist rein optional
        _LOGGER.debug("Supervisor-Autoerkennung fehlgeschlagen: %s", exc)
        return None

    host = info.get("hostname")
    if not host:
        return None
    return {
        CONF_HOST: host,
        CONF_PORT: ADDON_INTERNAL_PORT,
        CONF_API_TOKEN: str((info.get("options") or {}).get(CONF_API_TOKEN) or ""),
    }


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.Coerce(int),
            vol.Optional(CONF_API_TOKEN, default=defaults.get(CONF_API_TOKEN, "")): str,
            vol.Required(CONF_SSL, default=defaults.get(CONF_SSL, DEFAULT_SSL)): bool,
            vol.Required(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
            ): bool,
        }
    )


class RedAlertConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ein Config-Entry pro App-Instanz (Host+Port als eindeutige ID)."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] = {}

    async def async_step_hassio(
        self, discovery_info: "HassioServiceInfo"
    ) -> ConfigFlowResult:
        """Von Supervisor angestoßene Erkennung – auf den normalen Schritt leiten."""
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            token = user_input.get(CONF_API_TOKEN, "").strip()

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            scheme = "https" if user_input[CONF_SSL] else "http"
            base_url = f"{scheme}://{host}:{port}"
            session = async_get_clientsession(self.hass, verify_ssl=user_input[CONF_VERIFY_SSL])
            client = RedAlertApiClient(session, base_url, token)

            try:
                health = await client.async_get_health()
            except RedAlertApiError:
                _LOGGER.exception("Red Alert App unter %s nicht erreichbar", base_url)
                errors["base"] = "cannot_connect"
            else:
                if not health.get("paired"):
                    # Kein hartes Abbruchkriterium – Pairing lässt sich auch
                    # später über die App-Web-UI nachholen.
                    _LOGGER.warning(
                        "Red Alert App unter %s antwortet, aber keine Bridge gepaart", base_url
                    )
                return self.async_create_entry(
                    title=f"Red Alert ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_API_TOKEN: token,
                        CONF_SSL: user_input[CONF_SSL],
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )

            defaults = user_input
        else:
            if not self._discovered:
                self._discovered = await _discover_addon(self.hass) or {}
            defaults = self._discovered

        return self.async_show_form(
            step_id="user", data_schema=_schema(defaults), errors=errors
        )
