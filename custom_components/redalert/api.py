"""Dünner HTTP-Client für die Red-Alert-App-REST-API (main.py).

Kein State hier – nur GET/POST-Wrapper um die in main.py dokumentierten
Endpunkte (/health, /config, /start, /stop). Fehler werden als
RedAlertApiError durchgereicht, damit Coordinator/Entities einheitlich
reagieren können.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class RedAlertApiError(Exception):
    """Die App war nicht erreichbar oder hat einen Fehler gemeldet."""


class RedAlertApiClient:
    """Spricht mit einer laufenden Red-Alert-App-Instanz."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _request(self, method: str, path: str, json: dict | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.request(method, url, json=json) as resp:
                    # Die App antwortet auch bei Fehlern (400/404/502) mit
                    # einem JSON-Body ({"error": "..."}) – trotzdem einlesen,
                    # damit die Fehlermeldung im Log/UI landet.
                    try:
                        data = await resp.json()
                    except (aiohttp.ContentTypeError, ValueError):
                        data = {}
                    if resp.status >= 400:
                        raise RedAlertApiError(
                            data.get("error") or f"{method} {path} → HTTP {resp.status}"
                        )
                    return data
        except TimeoutError as exc:
            raise RedAlertApiError(f"Zeitüberschreitung bei {method} {path}") from exc
        except aiohttp.ClientError as exc:
            raise RedAlertApiError(f"{method} {path} nicht erreichbar: {exc}") from exc

    async def async_get_health(self) -> dict[str, Any]:
        """GET /health – {status, paired, running, current_preset}."""
        return await self._request("GET", "/health")

    async def async_get_config(self) -> dict[str, Any]:
        """GET /config – effektive Konfiguration inkl. presets/current_preset."""
        return await self._request("GET", "/config")

    async def async_start(
        self, preset: str | None = None, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """POST /start – optional ein gespeichertes Effektset laden."""
        payload = dict(body or {})
        if preset is not None:
            payload["preset"] = preset
        return await self._request("POST", "/start", json=payload)

    async def async_stop(self) -> dict[str, Any]:
        """POST /stop."""
        return await self._request("POST", "/stop")
