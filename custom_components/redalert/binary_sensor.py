"""Binary-Sensoren: läuft der Effekt gerade? / sind die Bridges scharfgeschaltet?"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import RedAlertDataUpdateCoordinator
from .entity import RedAlertEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: RedAlertDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        [
            RedAlertRunningSensor(coordinator, entry),
            RedAlertArmedSensor(coordinator, entry),
        ]
    )


class RedAlertRunningSensor(RedAlertEntity, BinarySensorEntity):
    """Spiegelt ``running`` aus GET /config (== /health)."""

    _attr_translation_key = "running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: RedAlertDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "running", domain=BINARY_SENSOR_DOMAIN)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("running"))


class RedAlertArmedSensor(RedAlertEntity, BinarySensorEntity):
    """Spiegelt ``armed`` aus GET /config – sind **alle** nicht-neutralen
    Bridges scharfgeschaltet (DTLS-Stream dauerhaft offen)? Nur-Lese-Anzeige
    neben dem gleichnamigen Schalter; ``armed_bridges`` als Attribut."""

    _attr_translation_key = "armed"
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator: RedAlertDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "armed", domain=BINARY_SENSOR_DOMAIN)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("armed"))

    @property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        return {"armed_bridges": list(self.coordinator.data.get("armed_bridges") or [])}
