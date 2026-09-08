"""Gemeinsame Basis-Entity: ein HA-Gerät pro App-Instanz (Config-Entry).

Die ``entity_id`` wird hier **explizit** aus einem englischen Schlüssel erzeugt
(``async_generate_entity_id``), statt sie Home Assistant aus dem – je nach
Sprache übersetzten – Anzeigenamen ableiten zu lassen; sonst bekämen z. B.
deutsche Installationen IDs wie ``binary_sensor.…_betriebszustand``. Der
Anzeigename bleibt über ``translation_key`` weiterhin lokalisiert. Das
``unique_id``-Schema trägt seit 1.2.0 ein Plattform-Präfix (``…_<domain>_<key>``)
– Bestandsentitäten älterer Versionen werden dadurch mit den neuen englischen
IDs neu angelegt.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RedAlertDataUpdateCoordinator


class RedAlertEntity(CoordinatorEntity[RedAlertDataUpdateCoordinator]):
    """Basisklasse für alle Entities dieser Integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RedAlertDataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
        *,
        domain: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{domain}_{key}"
        self.entity_id = async_generate_entity_id(
            f"{domain}.{{}}", f"{entry.title} {key}", hass=coordinator.hass
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="redalert (Home Assistant App)",
            model="Red Alert Entertainment",
            configuration_url=coordinator.client.base_url,
        )
