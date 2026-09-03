"""Red-Alert light patterns.

Two effects, selected by the ``effect`` option / ``/start`` body:

- ``pulse`` (default): every channel rises and falls **together** – bright on
  sound, dim in the pauses. Driven by the audio cue envelope (or a periodic
  cosine when no cue is active), with an asymmetric attack/release so the
  transitions read as fades rather than steps.
- ``chase``: a comet running **continuously in one direction** around the
  channels (wraps at the end, constant speed). Each lamp on its own runs a
  **pulse**: a very short rise as the head arrives, then a long exponential
  fade back to the resting glow. Consecutive lamps peak one after another, so
  together they read as a comet dragging a tail.

Both classes only compute a **0..1 shape**; ``main.py`` maps it onto the
configured ``glow_low`` / ``glow_high`` levels and applies the colour + 16-bit
scaling.
"""

from __future__ import annotations

import math

HUE_16BIT_MAX = 65535


class RedAlertChase:
    """Comet running continuously around the channels, dragging a tail.

    ``sweep_seconds`` is the time for **one full loop** past every channel, so a
    given lamp is passed by the head once every ``sweep_seconds``. Its brightness
    is a pure function of ``phase`` – the fraction of that cycle elapsed since the
    head last sat on it (``0`` = head on the lamp, rising toward ``1`` = about to
    be hit again):

    Over one cycle a lamp does, in ``phase`` order:

    - ``0 .. top``: held flat at **1.0** – the comet head. ``top`` is at least
      ``peak_frac`` (so a couple of frames always land on the full value and the
      peak doesn't shimmer between sweeps) and, for >= 2 lamps, at least
      ``1/n + overlap_frac`` – wider than the lamp-to-lamp spacing, so the next
      lamp reaches 1.0 while this one is still there and **two lamps sit at 100 %
      together** for ``overlap_frac`` of a sweep before fading one after another;
    - ``top .. fade_frac``: an ``exp(-·/decay_frac)`` fall, shifted to reach
      **exactly 0** at ``fade_frac`` – the long afterglow;
    - ``fade_frac .. 1 - attack_frac``: held at **0** – the resting glow;
    - last ``attack_frac``: a raised-cosine rise back to 1.0 – the head arriving.

    Fractions are of ``sweep_seconds``. The ``0 .. 1`` shape is mapped onto the
    real ``glow_low`` / ``glow_high`` levels by ``main.py``, so "0" here means
    "return to the resting glow", not necessarily black.
    """

    def __init__(
        self,
        num_lights: int,
        sweep_seconds: float = 1.4,
        pause_seconds: float = 0.0,
        decay_frac: float = 0.22,
        attack_frac: float = 0.07,
        peak_frac: float = 0.08,
        overlap_frac: float = 0.10,
        fade_frac: float = 0.62,
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.sweep_seconds = max(0.1, sweep_seconds)
        self.pause_seconds = max(0.0, pause_seconds)
        self.decay_frac = max(0.02, decay_frac)
        self.attack_frac = min(max(attack_frac, 0.01), 0.5)
        peak_frac = min(max(peak_frac, 0.01), 0.3)
        overlap_frac = min(max(overlap_frac, 0.0), 0.3)
        # Width of the flat 1.0 top. For >= 2 lamps make it a touch wider than the
        # lamp-to-lamp spacing so adjacent heads overlap at full brightness.
        top = peak_frac
        if self.num_lights >= 2:
            top = max(top, 1.0 / self.num_lights + overlap_frac)
        self.top = min(top, 0.5)
        self.fade_frac = min(
            max(fade_frac, self.top + 0.08), 1.0 - self.attack_frac - 1e-3
        )

    def _envelope(self, phase: float) -> float:
        """Pulse over one lamp cycle: flat 1.0 across ``top``, flat 0.0 between."""
        rise_start = 1.0 - self.attack_frac
        if phase >= rise_start:
            x = (phase - rise_start) / self.attack_frac  # 0 -> 1 over the attack
            return 0.5 - 0.5 * math.cos(math.pi * x)  # 0 -> 1, raised cosine
        if phase < self.top:
            return 1.0  # flat head
        if phase >= self.fade_frac:
            return 0.0  # resting glow
        # exp decay from the end of the flat top, shifted to hit 0.0 at fade_frac
        p = phase - self.top
        floor = math.exp(-(self.fade_frac - self.top) / self.decay_frac)
        return (math.exp(-p / self.decay_frac) - floor) / (1.0 - floor)

    def _pulse_s(self, s: float, attack_s: float) -> float:
        """One lamp's 0..1 pulse, ``s`` seconds after its rise began (< 0 = idle)."""
        if s < 0.0:
            return 0.0
        if s < attack_s:
            # rise: reuse the envelope's raised-cosine attack band
            return self._envelope((1.0 - self.attack_frac) + s / self.sweep_seconds)
        phase = (s - attack_s) / self.sweep_seconds  # 0 at the flat top
        if phase >= self.fade_frac:
            return 0.0  # faded out – stays here through the pause
        return self._envelope(phase)

    def brightness_for(self, t: float) -> list[float]:
        """Per-light 0..1 pulse shape at time t (seconds since start).

        ``main.py`` maps this onto ``[glow_low, glow_high]``. With
        ``pause_seconds == 0`` the comet loops seamlessly; with a pause it makes
        **one** full traversal (every lamp pulses once, last one fades out), then
        all lamps sit at 0 for ``pause_seconds`` before the next traversal.
        """
        n = self.num_lights
        if self.pause_seconds <= 0.0:
            turns = t / self.sweep_seconds
            return [
                min(1.0, max(0.0, self._envelope((turns - i / n) % 1.0)))
                for i in range(n)
            ]
        sweep = self.sweep_seconds
        attack_s = self.attack_frac * sweep
        head_step = sweep / n  # time between one lamp's rise and the next
        active_s = attack_s + (n - 1) * head_step + self.fade_frac * sweep
        u = t % (active_s + self.pause_seconds)
        return [
            min(1.0, max(0.0, self._pulse_s(u - i * head_step, attack_s)))
            for i in range(n)
        ]

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
