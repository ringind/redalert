"""Switch: Animation an/aus (POST /start bzw. /stop).

Turn-on startet erneut mit dem zuletzt geladenen Effektset
(``current_preset``, siehe select.py), falls eines geladen ist – sonst mit
den App-eigenen Standardwerten (leerer Body), genau wie ein Aufruf ohne
``preset`` im main.py-``/start``.

Zusätzlich gibt es einen ``RedAlertArmSwitch`` (Scharfschalten aller Bridges,
POST /arm bzw. /disarm): hält den DTLS-Stream jeder Bridge dauerhaft offen,
sodass ein anschließender Start den Handshake überspringt. Der Animations-
Switch bleibt davon unberührt – er startet nur schneller, wenn vorher
scharfgeschaltet wurde.

Daneben legt diese Plattform **pro gepaarter Bridge** einen eigenen Switch
an (``RedAlertBridgeAnimationSwitch``), der nur diese eine Bridge über
``bridge_host`` startet/stoppt (main.py seit dem Task-je-Bridge-Umbau) –
unabhängig davon, ob andere Bridges gerade laufen. Die Bridge-Liste kommt
aus ``coordinator.data["bridges"]`` (bereits durch /config geliefert) und
kann sich zur Laufzeit ändern (Bridge in der App-Konfiguration hinzugefügt),
daher die dynamische Nachregistrierung über einen Coordinator-Listener –
ein in dieser Integration bislang einmaliges Muster (alle anderen
Plattformen registrieren einmalig eine feste Entity-Liste). Verschwindet
eine Bridge wieder aus der Konfiguration, wird ihr Switch nicht gelöscht,
sondern nur ``unavailable`` (siehe ``available`` unten) – bewusst einfach
gehalten, siehe README.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import RedAlertApiError
from .coordinator import RedAlertDataUpdateCoordinator
from .entity import RedAlertEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: RedAlertDataUpdateCoordinator = entry.runtime_data
    async_add_entities([
        RedAlertAnimationSwitch(coordinator, entry),
        RedAlertArmSwitch(coordinator, entry),
    ])

    known_hosts: set[str] = set()

    def _add_new_bridge_switches() -> None:
        bridges = coordinator.data.get("bridges") or []
        new_entities = []
        for bridge in bridges:
            host = bridge.get("bridge_host")
            if host and host not in known_hosts:
                known_hosts.add(host)
                new_entities.append(RedAlertBridgeAnimationSwitch(coordinator, entry, host))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_bridge_switches()  # bereits beim Setup konfigurierte Bridges
    entry.async_on_unload(coordinator.async_add_listener(_add_new_bridge_switches))


class RedAlertAnimationSwitch(RedAlertEntity, SwitchEntity):
    """Spiegelt ``running`` und schaltet den Effekt per REST-API."""

    _attr_translation_key = "animation"
    _attr_icon = "mdi:alert-octagram"

    def __init__(self, coordinator: RedAlertDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "animation")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("running"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        preset = self.coordinator.data.get("current_preset")
        try:
            await self.coordinator.client.async_start(preset=preset)
        except RedAlertApiError as exc:
            raise HomeAssistantError(f"Red Alert konnte nicht gestartet werden: {exc}") from exc
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.async_stop()
        except RedAlertApiError as exc:
            raise HomeAssistantError(f"Red Alert konnte nicht gestoppt werden: {exc}") from exc
        await self.coordinator.async_request_refresh()


class RedAlertArmSwitch(RedAlertEntity, SwitchEntity):
    """Scharfschalten aller Bridges: hält den DTLS-Stream jeder Bridge dauerhaft
    offen, sodass ein anschließender Animationsstart den ~3–9 s langen Handshake
    überspringt und praktisch sofort beginnt. Ist eine Bridge noch nicht scharf,
    schaltet ``turn_on`` sie scharf; ist bereits alles scharf, hat der
    Animations-Switch bzw. jeder Start dadurch von selbst den Sofort-Effekt.
    ``is_on`` = alle nicht-neutralen, gepaarten Bridges sind scharf.
    """

    _attr_translation_key = "armed"
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator: RedAlertDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "armed")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("armed"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.async_arm()
        except RedAlertApiError as exc:
            raise HomeAssistantError(f"Red Alert konnte nicht scharfgeschaltet werden: {exc}") from exc
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.async_disarm()
        except RedAlertApiError as exc:
            raise HomeAssistantError(f"Red Alert konnte nicht entschärft werden: {exc}") from exc
        await self.coordinator.async_request_refresh()


class RedAlertBridgeAnimationSwitch(RedAlertEntity, SwitchEntity):
    """Startet/stoppt die Animation nur auf einer einzelnen Bridge."""

    _attr_translation_key = "bridge_animation"
    _attr_icon = "mdi:alert-octagram-outline"

    def __init__(
        self, coordinator: RedAlertDataUpdateCoordinator, entry: ConfigEntry, bridge_host: str
    ) -> None:
        super().__init__(coordinator, entry, f"bridge_animation_{bridge_host}")
        self._bridge_host = bridge_host
        self._attr_translation_placeholders = {"host": bridge_host}

    def _bridge_data(self) -> dict | None:
        return next(
            (b for b in self.coordinator.data.get("bridges", []) if b.get("bridge_host") == self._bridge_host),
            None,
        )

    @property
    def available(self) -> bool:
        return super().available and self._bridge_data() is not None

    @property
    def is_on(self) -> bool:
        bridge = self._bridge_data()
        return bool(bridge and bridge.get("running"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.async_start(bridge_host=self._bridge_host)
        except RedAlertApiError as exc:
            raise HomeAssistantError(
                f"Red Alert ({self._bridge_host}) konnte nicht gestartet werden: {exc}"
            ) from exc
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.async_stop(bridge_host=self._bridge_host)
        except RedAlertApiError as exc:
            raise HomeAssistantError(
                f"Red Alert ({self._bridge_host}) konnte nicht gestoppt werden: {exc}"
            ) from exc
        await self.coordinator.async_request_refresh()
