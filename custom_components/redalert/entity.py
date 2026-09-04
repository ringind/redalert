"""Gemeinsame Basis-Entity: ein HA-Gerät pro App-Instanz (Config-Entry)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RedAlertDataUpdateCoordinator


class RedAlertEntity(CoordinatorEntity[RedAlertDataUpdateCoordinator]):
    """Basisklasse für alle vier Entities dieser Integration."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: RedAlertDataUpdateCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="redalert (Home Assistant App)",
            model="Red Alert Entertainment",
            configuration_url=coordinator.client.base_url,
        )
