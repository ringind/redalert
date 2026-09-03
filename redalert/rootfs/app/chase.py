"""Red-Alert light patterns.

Two effects, selected by the ``effect`` option / ``/start`` body:

- ``pulse`` (default): every channel rises and falls **together** – bright on
  sound, dim in the pauses. Driven by the audio cue envelope (or a periodic
  cosine when no cue is active), with an asymmetric attack/release so the
  transitions read as fades rather than steps.
- ``chase``: the original Larson-scanner comet sweeping across the channels on
  top of a dim constant wash.

Both classes only compute brightness in ``[0, 1]``; ``main.py`` applies the
colour and 16-bit scaling.
"""

from __future__ import annotations

import math

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


class RedAlertPulse:
    """All channels together: fade up on sound, fade down on silence.

    Call :meth:`step` once per frame with the raw target level (the cue gain, or
    :meth:`periodic` when there is no cue) and the elapsed time since the last
    call. An exponential follower with separate attack/release time constants
    smooths the target so quick beats still ramp instead of snapping.
    """

    def __init__(
        self,
        num_lights: int,
        base_glow: float = 0.06,
        attack_s: float = 0.06,
        release_s: float = 0.30,
        gamma: float = 1.0,
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.base_glow = min(max(base_glow, 0.0), 1.0)
        self.attack_s = max(1e-3, attack_s)
        self.release_s = max(1e-3, release_s)
        self.gamma = max(0.1, gamma)
        self._current = 0.0

    def reset(self, value: float = 0.0) -> None:
        self._current = min(1.0, max(0.0, value))

    def step(self, target: float, dt: float) -> list[float]:
        """Advance ``dt`` seconds toward ``target`` (0..1); return per-channel levels."""
        target = min(1.0, max(0.0, target)) ** self.gamma
        tau = self.attack_s if target > self._current else self.release_s
        alpha = 1.0 - math.exp(-max(0.0, dt) / tau)
        self._current += (target - self._current) * alpha
        level = self.base_glow + (1.0 - self.base_glow) * self._current
        return [level] * self.num_lights

    @staticmethod
    def periodic(t: float, period_s: float) -> float:
        """Cosine 0..1 pulse, one full up/down cycle per ``period_s`` (no-cue fallback)."""
        if period_s <= 0:
            return 1.0
        return 0.5 - 0.5 * math.cos(2.0 * math.pi * (t % period_s) / period_s)
