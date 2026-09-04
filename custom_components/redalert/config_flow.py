"""Config-Flow: Host/Port der Red-Alert-App abfragen und per /health prüfen."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RedAlertApiClient, RedAlertApiError
from .const import (
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

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Required(CONF_SSL, default=DEFAULT_SSL): bool,
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


class RedAlertConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ein Config-Entry pro App-Instanz (Host+Port als eindeutige ID)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            scheme = "https" if user_input[CONF_SSL] else "http"
            base_url = f"{scheme}://{host}:{port}"
            session = async_get_clientsession(self.hass, verify_ssl=user_input[CONF_VERIFY_SSL])
            client = RedAlertApiClient(session, base_url)

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
                        CONF_SSL: user_input[CONF_SSL],
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
