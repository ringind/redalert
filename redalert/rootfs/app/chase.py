"""Generates the 'Star Trek Red Alert' running-light pattern.

A bright red comet sweeps back and forth across the entertainment
channels (Larson-scanner style), on top of a dim constant red wash so
the room reads as 'in alert' even between sweeps.
"""

from __future__ import annotations

HUE_16BIT_MAX = 65535


class RedAlertChase:
    def __init__(
        self,
        num_lights: int,
        sweep_seconds: float = 1.4,
        tail_width: float = 1.3,
        base_glow: float = 0.06,
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.sweep_seconds = max(0.1, sweep_seconds)
        self.tail_width = max(0.3, tail_width)
        self.base_glow = min(max(base_glow, 0.0), 1.0)

    def _position(self, t: float) -> float:
        """Triangle wave 0 -> (n-1) -> 0 over one full sweep cycle."""
        if self.num_lights <= 1:
            return 0.0
        period = 2 * self.sweep_seconds
        phase = (t % period) / self.sweep_seconds  # 0..2
        span = self.num_lights - 1
        if phase <= 1:
            return phase * span
        return (2 - phase) * span

    def brightness_for(self, t: float) -> list[float]:
        """Per-light brightness in [0, 1] at time t (seconds since start)."""
        pos = self._position(t)
        levels = []
        for i in range(self.num_lights):
            dist = abs(i - pos)
            comet = max(0.0, 1.0 - dist / self.tail_width)
            levels.append(min(1.0, self.base_glow + comet))
        return levels

    def frame(self, t: float) -> list[dict]:
        """Return per-light 16-bit red-channel commands (green/blue = 0)."""
        return [
            {"red": int(HUE_16BIT_MAX * level), "green": 0, "blue": 0}
            for level in self.brightness_for(t)
        ]
