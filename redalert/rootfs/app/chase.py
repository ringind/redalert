"""Red-Alert light patterns.

Two effects, selected by the ``effect`` option / ``/start`` body:

- ``pulse`` (default): every channel rises and falls **together** – bright on
  sound, dim in the pauses. Driven by the audio cue envelope (or a periodic
  cosine when no cue is active), with an asymmetric attack/release so the
  transitions read as fades rather than steps.
- ``chase``: a comet running **continuously in one direction** around the
  channels (wraps at the end, constant speed), with a bright head, a short glow
  ahead of it and a long exponential tail trailing behind, over a dim wash.

Both classes only compute brightness in ``[0, 1]``; ``main.py`` applies the
colour and 16-bit scaling.
"""

from __future__ import annotations

import math

HUE_16BIT_MAX = 65535


class RedAlertChase:
    """Comet running continuously around the channels, dragging a tail.

    ``sweep_seconds`` is the time for **one full loop** past every channel. The
    head position advances at constant speed and wraps, so the motion is even
    with no turn-around dwell. Brightness for a channel depends on its signed
    circular distance ``d`` from the head:

    - ``d < 0`` (channel is behind the head): ``exp(d / tail_len)`` – the long
      trailing comet tail;
    - ``d > 0`` (ahead of the head): ``exp(-d / head_len)`` – a short glow so the
      leading edge is soft, not a hard on/off.
    """

    def __init__(
        self,
        num_lights: int,
        sweep_seconds: float = 1.4,
        tail_len: float = 1.7,
        head_len: float = 0.45,
        base_glow: float = 0.05,
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.sweep_seconds = max(0.1, sweep_seconds)
        self.tail_len = max(0.1, tail_len)
        self.head_len = max(0.05, head_len)
        self.base_glow = min(max(base_glow, 0.0), 1.0)

    def _head(self, t: float) -> float:
        """Continuous head position 0..n, one full loop per ``sweep_seconds``."""
        n = self.num_lights
        return (t / self.sweep_seconds) * n % n

    def brightness_for(self, t: float) -> list[float]:
        """Per-light brightness in [0, 1] at time t (seconds since start)."""
        n = self.num_lights
        if n == 1:
            return [1.0]
        head = self._head(t)
        levels = []
        for i in range(n):
            # signed distance head->channel, wrapped to (-n/2, n/2]
            d = (i - head + n / 2) % n - n / 2
            glow = math.exp(d / self.tail_len) if d <= 0 else math.exp(-d / self.head_len)
            levels.append(min(1.0, self.base_glow + (1.0 - self.base_glow) * glow))
        return levels

    def frame(self, t: float) -> list[dict]:
        """Return per-light 16-bit red-channel commands (green/blue = 0)."""
        return [
            {"red": int(HUE_16BIT_MAX * level), "green": 0, "blue": 0}
            for level in self.brightness_for(t)
        ]


class RedAlertPulse:
    """All channels together: dark → full → dark, in time with the music.

    Each frame, :meth:`step` takes the raw level (the cue gain, or
    :meth:`periodic` when there is no cue) and the time since the last call.

    The raw cue envelope is noisy on the way up – it wobbles across a single
    threshold several times per beat – so a plain threshold produces visible
    steps. Instead a **Schmitt-style gate with off-debounce** turns the beat into
    a clean 0/1 signal:

    - off → on when the level rises above ``hi``;
    - on → off only after the level has stayed below ``lo`` for ``hold_s``
      continuously (short dips inside a beat don't drop it).

    A **linear slew** then drives the level toward that stable target: up at
    ``1 / attack_s`` per second, down at ``1 / release_s`` per second. Because the
    target only changes once per beat, the ramp is strictly monotonic – no jumps
    – and reaches **exactly** 1.0 ``attack_s`` after the gate opens and **exactly**
    0.0 ``release_s`` after it closes. Keep ``release_s`` < ``attack_s`` for the
    intended look: swell up to full, then drop back down faster.
    """

    def __init__(
        self,
        num_lights: int,
        attack_s: float = 0.14,
        release_s: float = 0.07,
        lo: float = 0.16,
        hi: float = 0.30,
        hold_s: float = 0.12,
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.attack_s = max(1e-3, attack_s)
        self.release_s = max(1e-3, release_s)
        self.lo = min(max(lo, 0.0), 0.95)
        self.hi = max(self.lo + 1e-3, min(hi, 1.0))
        self.hold_s = max(0.0, hold_s)
        self._current = 0.0
        self._on = False
        self._below_for = 0.0

    def reset(self, value: float = 0.0) -> None:
        self._current = min(1.0, max(0.0, value))
        self._on = self._current > 0.5
        self._below_for = 0.0

    def step(self, level: float, dt: float) -> list[float]:
        """Advance the gate + slew by ``dt`` seconds; return per-channel levels."""
        g = min(1.0, max(0.0, level))
        dt = max(0.0, dt)
        if self._on:
            self._below_for = self._below_for + dt if g < self.lo else 0.0
            if self._below_for >= self.hold_s:
                self._on = False
        elif g >= self.hi:
            self._on = True
            self._below_for = 0.0

        target = 1.0 if self._on else 0.0
        span = (1.0 / self.attack_s if target > self._current else 1.0 / self.release_s) * dt
        if target > self._current:
            self._current = min(target, self._current + span)
        else:
            self._current = max(target, self._current - span)
        return [self._current] * self.num_lights

    @staticmethod
    def periodic(t: float, period_s: float) -> float:
        """Cosine 0..1 pulse, one full up/down cycle per ``period_s`` (no-cue fallback)."""
        if period_s <= 0:
            return 1.0
        return 0.5 - 0.5 * math.cos(2.0 * math.pi * (t % period_s) / period_s)
