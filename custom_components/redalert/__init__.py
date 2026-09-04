"""Home-Assistant-Integration für die Red Alert Entertainment App.

Spricht ausschließlich die REST-API der App an (main.py: /health, /config,
/start, /stop – siehe redalert/DOCS.md), keine eigene Logik. Ein Config-Entry
= eine App-Instanz (Host+Port).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RedAlertApiClient, RedAlertApiError
from .const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL, DOMAIN
from .coordinator import RedAlertDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
]


def _base_url(entry: ConfigEntry) -> str:
    scheme = "https" if entry.data.get(CONF_SSL) else "http"
    return f"{scheme}://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = RedAlertApiClient(session, _base_url(entry))
    coordinator = RedAlertDataUpdateCoordinator(hass, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except RedAlertApiError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
