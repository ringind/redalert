"""Red-Alert light patterns.

Effects, selected by the ``effect`` option / ``/start`` body:

- ``pulse`` (default): every channel rises and falls **together** – bright on
  sound, dim in the pauses. Driven by the audio cue envelope (or a periodic
  cosine when no cue is active), with an asymmetric attack/release so the
  transitions read as fades rather than steps.
- ``comet``: a comet running **continuously in one direction** around the
  channels (wraps at the end, constant speed). Each lamp on its own runs a
  **pulse**: a very short rise as the head arrives, then a long exponential
  fade back to the resting glow. Consecutive lamps peak one after another, so
  together they read as a comet dragging a tail. See ``RedAlertComet``.
- ``glitter``: each lamp sparkles on its own – at random moments it snaps to
  full brightness in a colour picked from a palette and then fades out fast,
  like light glinting off diamonds. Several lamps can be lit at once.
- ``chase``: one or more soft-edged two-colour bands sliding along the
  channels – built for Hue Gradient Lightstrips, where each channel is a
  coloured segment rather than a separate lamp. See ``RedAlertChase``.
- ``police``: two lamp groups (even/odd position) alternately strobe two
  colours, like emergency lights. See ``RedAlertPolice``.
- ``lightning``: the whole array flashes bright together at random moments
  (occasionally a quick double-strike), then fades – a distant storm rather
  than glitter's continuous per-lamp sparkle. See ``RedAlertLightning``.
- ``heartbeat``: a ``pulse`` variant driven by a two-beat "lub-dub" input
  instead of a single cosine hump. See ``RedAlertPulse.heartbeat``.
- ``aurora``: slow, soft colour waves blending through a palette, drifting
  across the lamps – a calm ambient look. See ``RedAlertAurora``.
- ``rainbow``: a continuous hue-cycle, phase-offset per lamp so a spectrum
  visibly sweeps across the array. See ``RedAlertRainbow``.
- ``meteor``: several independent comets crossing at randomised speeds and
  brightness – a busier, less orderly cousin of ``comet``. See
  ``RedAlertMeteor``.
- ``wipe``: a sequential fill across the channels that holds once full, then
  resets and fills again – a one-shot motif repeated on a loop. See
  ``RedAlertWipe``.
- ``firework``: one-shot bursts radiating outward from the centre channel,
  then fading, repeating every interval. See ``RedAlertFirework``.
- ``ripple``: a brightness pulse radiates from the centre channel, reflects
  off both ends of the strip and echoes back inward before fading, then
  repeats – unlike ``firework``, which only radiates outward once per burst.
  See ``RedAlertRipple``.
- ``wave``: a continuous spatial sine wave of brightness scrolling across the
  channels, with several crests/troughs visible at once – unlike ``comet``'s
  single localised head. See ``RedAlertWave``.
- ``flicker``: lamps sporadically dip and glitch from full brightness, like a
  failing bulb – the opposite mood of ``glitter`` (which brightens) or
  ``lightning`` (a single shared flash). See ``RedAlertFlicker``.
- ``strobe``: a hard, instant on/off flash, no fade at all – unlike
  ``pulse``'s smooth attack/release. See ``RedAlertStrobe``.
- ``duel``: two comets launched from opposite ends in two colours, meeting in
  the middle and bouncing back off each other – unlike ``meteor``
  (independent, random) or ``comet`` (a single deterministic loop). See
  ``RedAlertDuel``.

``RedAlertComet`` / ``RedAlertPulse`` / ``RedAlertMeteor`` / ``RedAlertWipe`` /
``RedAlertFirework`` / ``RedAlertPolice`` / ``RedAlertRipple`` /
``RedAlertWave`` / ``RedAlertStrobe`` only compute a **0..1 shape**;
``main.py`` maps it onto the configured ``glow_low`` / ``glow_high`` levels
and applies the colour + 16-bit scaling (``RedAlertPolice`` additionally
picks colour A/B per lamp from its ``group_a`` list). ``RedAlertGlitter``,
``RedAlertLightning`` and ``RedAlertFlicker`` are stateful and time-stepped
(``step(dt)``) rather than pure functions of ``t``; glitter additionally
picks a per-lamp colour (main.py still does the level mapping and 16-bit
scaling). ``RedAlertChase`` computes a per-segment **blend** between two
colours instead (main.py interpolates and layers glow/pulse/glitter on top);
``RedAlertAurora`` / ``RedAlertRainbow`` instead compute a per-lamp
**colour** directly (0..255 float RGB) with no separate brightness shape –
main.py applies glow scaling on top of that colour. ``RedAlertDuel`` returns
**two** brightness shapes (one per comet); main.py blends ``color``/
``color2`` accordingly.
"""

from __future__ import annotations

import colorsys
import math
import random

HUE_16BIT_MAX = 65535


class RedAlertComet:
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

    @staticmethod
    def heartbeat(t: float, period_s: float) -> float:
        """"Lub-dub" 0..1 input for :meth:`step`: a bigger beat then a smaller
        one per ``period_s``, then rest – like a resting heart rate. Feeding
        this through the same gate + slew as :meth:`periodic` turns each bump
        into a clean double flash instead of a single smooth pulse.
        """
        if period_s <= 0:
            return 1.0
        phase = (t % period_s) / period_s

        def _bump(center: float, width: float, amp: float) -> float:
            d = abs(phase - center)
            d = min(d, 1.0 - d)  # wrap-around distance
            if d >= width:
                return 0.0
            return amp * math.cos((d / width) * (math.pi / 2)) ** 2

        return max(_bump(0.08, 0.10, 1.0), _bump(0.24, 0.08, 0.6))


class RedAlertGlitter:
    """Independent sparkle per lamp – short bright flashes in random colours.

    Diamond-twinkle look: sparkles ignite at random moments (on average one
    every ``interval_s`` **across the whole strip**); each ignition snaps one
    lamp to full brightness in a colour picked at random from ``palette`` and
    then fades exponentially with time constant ``flash_s``. Whenever
    ``flash_s`` is longer than ``interval_s`` several lamps glint at once.

    Unlike the other effects this one is stateful and time-stepped rather than
    a pure function of ``t``: :meth:`step` advances by ``dt`` seconds and
    returns one ``(level, (r, g, b))`` pair per lamp – ``level`` is the 0..1
    shape (mapped onto ``glow_low`` / ``glow_high`` by ``main.py``),
    ``(r, g, b)`` the 8-bit sparkle colour that lamp is currently showing.
    Randomness is intentionally unseeded, so two ``glitter`` bridges next to
    each other twinkle differently.
    """

    def __init__(
        self,
        num_lights: int,
        interval_s: float = 0.09,
        flash_s: float = 0.26,
        palette: list[tuple[int, int, int]] | None = None,
        seed: int | None = None,
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.interval_s = max(1e-3, interval_s)
        self.flash_s = max(1e-3, flash_s)
        self.palette = [tuple(c) for c in palette] if palette else [(255, 255, 255)]
        self._rng = random.Random(seed)
        self._level = [0.0] * self.num_lights
        self._color = [self.palette[0]] * self.num_lights
        self._carry = 0.0  # fractional ignitions carried between frames

    def step(self, dt: float) -> list[tuple[float, tuple[int, int, int]]]:
        """Advance by ``dt`` s; return per-lamp ``(level, (r, g, b))``."""
        dt = max(0.0, dt)
        if dt > 0.0:
            decay = math.exp(-dt / self.flash_s)
            for i in range(self.num_lights):
                lv = self._level[i] * decay
                self._level[i] = lv if lv > 1e-3 else 0.0
            # Expected number of ignitions this frame; keep the fraction for next.
            self._carry += dt / self.interval_s
            ignitions = int(self._carry)
            self._carry -= ignitions
            for _ in range(min(ignitions, self.num_lights * 4)):
                i = self._rng.randrange(self.num_lights)
                self._level[i] = 1.0
                self._color[i] = self.palette[self._rng.randrange(len(self.palette))]
        return list(zip(self._level, self._color))


class RedAlertChase:
    """One or more soft-edged two-colour bands sliding along the channels.

    Built for Hue **Gradient Lightstrips**, where each Entertainment channel
    is one coloured segment of a continuous strip rather than a separate
    lamp (several gradient lightstrips can be combined into one longer
    logical strip simply by putting all their segments in one Entertainment
    area – ``channel_order`` picks the physical sequence, ``num_lights`` here
    is just the resulting channel count).

    :meth:`blend_for` returns, per segment, a **0..1 blend** – ``1`` = fully
    the chase colour, ``0`` = fully the background colour – with a soft
    raised-cosine edge instead of a hard cut (the "gradient" in the name).
    ``main.py`` linearly interpolates ``color``/``gc_background_color`` per
    segment using this blend, and separately layers the optional background
    pulse (dims/brightens wherever ``blend`` isn't 1) and chase glitter
    (sparkles wherever ``blend`` is high) on top – this class only computes
    the geometry, no colour or I/O.

    ``count`` bands run at once, evenly spaced. ``direction``:

    - ``forward`` / ``backward``: the strip is a **loop** – bands wrap
      seamlessly from the last segment back to the first, like ``comet``.
    - ``bounce``: the strip is a **line** – bands reflect off both ends
      instead of wrapping, like a Larson scanner.

    ``length_segments`` is the width of the flat ``1.0`` core of a band, in
    segments; ``speed_segments_per_s`` is how many segments a band's head
    crosses per second. ``fps`` (the app's configured frame rate) is used two
    ways, both purely anti-aliasing: it widens the soft edge's minimum width
    (``smooth`` in ``__init__``) and it sets the per-frame cap of the
    **temporal slew** in :meth:`blend_for` (see there). Neither changes the
    band geometry, only how fast a single segment's blend is allowed to move
    between two frames.
    """

    def __init__(
        self,
        num_lights: int,
        direction: str = "forward",
        count: int = 1,
        length_segments: float = 2.0,
        speed_segments_per_s: float = 4.0,
        fps: float = 25.0,
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.direction = direction if direction in ("forward", "backward", "bounce") else "forward"
        self.count = max(1, int(count))
        self.half_width = min(max(length_segments, 0.2), float(self.num_lights)) / 2.0
        self.speed = max(0.01, speed_segments_per_s)
        self.fps = max(1.0, float(fps))
        # Edge softness in segments: about one segment (never narrower than a
        # third of the band, nor wider than it), *and* – like RedAlertComet's
        # peak_frac – never narrower than a couple of frames' worth of travel
        # at this speed/fps.
        base_smooth = min(max(self.half_width, 0.3), 1.0)
        min_smooth = 6.25 * self.speed / self.fps
        # Cap at the whole strip length (was num_lights/2, which on short
        # strips at high speed clamped 'smooth' back below the anti-alias
        # floor and let the flicker return – 1.16.1).
        self.smooth = min(max(base_smooth, min_smooth), max(2.0, float(self.num_lights)))
        # Temporal slew: cap how far any single segment's blend may move per
        # frame. blend_for() is otherwise a pure function of t sampled once
        # per frame, so a fast-moving raised-cosine edge still steps ~0.25 per
        # frame at its midpoint even after the smooth widening above – visible
        # as an occasional flicker "beim Auf-/Abblenden". Clamping the
        # frame-to-frame change makes the transition read as a fade at any
        # speed/fps/geometry (same idea as RedAlertPulse's attack/release
        # slew). 3.0 blend/s ⇒ a full 0→1 takes ≥ ~0.33 s.
        self._max_blend_rate = 3.0
        self._prev_blend: list[float] | None = None

    def _band(self, dist: float) -> float:
        """0..1 falloff: flat 1.0 within ``half_width``, 0.0 beyond the soft edge."""
        if dist <= self.half_width:
            return 1.0
        if dist >= self.half_width + self.smooth:
            return 0.0
        x = (dist - self.half_width) / self.smooth
        return 0.5 + 0.5 * math.cos(math.pi * x)  # 1 -> 0, raised cosine

    def _geom_blend(self, t: float) -> list[float]:
        """Per-segment 0..1 band geometry at time t – no temporal smoothing."""
        n = self.num_lights
        if self.direction == "bounce":
            span = max(1, n - 1)  # line length in segments
            period = 2.0 * span
            heads = [
                (t * self.speed + i * period / self.count) % period for i in range(self.count)
            ]
            heads = [h if h <= span else period - h for h in heads]
            return [max(self._band(abs(j - h)) for h in heads) for j in range(n)]
        sign = -1.0 if self.direction == "backward" else 1.0
        heads = [(sign * t * self.speed + i * n / self.count) % n for i in range(self.count)]
        return [
            max(self._band(min(abs(j - h), n - abs(j - h))) for h in heads) for j in range(n)
        ]

    def blend_for(self, t: float, dt: float | None = None) -> list[float]:
        """Per-segment 0..1 chase blend at time ``t`` (seconds since start).

        ``dt`` (seconds since the previous frame) enables the temporal slew –
        each segment's blend may move at most ``_max_blend_rate * dt`` toward
        the current geometry, so no single frame shows a hard jump. The first
        call, or a call without ``dt``, returns the raw geometry unchanged.
        """
        raw = self._geom_blend(t)
        if dt is None or dt <= 0 or self._prev_blend is None or len(self._prev_blend) != len(raw):
            self._prev_blend = list(raw)
            return raw
        step = self._max_blend_rate * dt
        out: list[float] = []
        for r, p in zip(raw, self._prev_blend):
            d = r - p
            if d > step:
                p += step
            elif d < -step:
                p -= step
            else:
                p = r
            out.append(p)
        self._prev_blend = out
        return out


class RedAlertPolice:
    """Two lamp groups alternately flash two colours (emergency-lights strobe).

    Lamps at even positions (``group_a``) show colour A for the first half of
    ``period_s``, lamps at odd positions show colour B for that same half
    (i.e. are dark), then it flips for the second half – so the two groups
    strobe back and forth rather than both lamps cycling through both
    colours. This class only computes the shared 0/1 on/off shape;
    ``main.py`` looks up ``group_a`` to pick colour A or B per lamp and maps
    the shape onto ``[glow_low, glow_high]`` like the other effects.
    """

    def __init__(self, num_lights: int, period_s: float = 0.6) -> None:
        self.num_lights = max(1, num_lights)
        self.period_s = max(0.05, period_s)
        self.group_a = [i % 2 == 0 for i in range(self.num_lights)]

    def brightness_for(self, t: float) -> list[float]:
        """Per-light 0/1 shape at time ``t`` – 1.0 while that lamp's group is lit."""
        on_a = (t % self.period_s) < (self.period_s / 2.0)
        return [1.0 if (on_a == is_a) else 0.0 for is_a in self.group_a]


class RedAlertLightning:
    """A distant storm: the whole array flashes bright together at random
    moments, then fades – unlike :class:`RedAlertGlitter`'s continuous,
    independent per-lamp sparkle, a lightning flash lights every lamp at
    once, like the sky briefly lighting up. Occasionally followed by a quick
    second flash (a double-strike), as real lightning often does.

    Stateful and time-stepped like :class:`RedAlertGlitter`: :meth:`step`
    advances by ``dt`` seconds and returns the single shared 0..1 level for
    every lamp – ``main.py`` maps it onto ``[glow_low, glow_high]`` and
    applies the configured colour.
    """

    _DOUBLE_STRIKE_CHANCE = 0.35
    _DOUBLE_STRIKE_GAP_S = 0.09

    def __init__(
        self, interval_s: float = 4.0, flash_s: float = 0.5, seed: int | None = None
    ) -> None:
        self.interval_s = max(1e-3, interval_s)
        self.flash_s = max(1e-3, flash_s)
        self._rng = random.Random(seed)
        self._level = 0.0
        self._carry = 0.0
        self._next_echo_s: float | None = None

    def step(self, dt: float) -> float:
        """Advance by ``dt`` s; return the shared 0..1 level for this frame."""
        dt = max(0.0, dt)
        if dt > 0.0:
            decay = math.exp(-dt / self.flash_s)
            self._level = self._level * decay if self._level > 1e-3 else 0.0
            if self._next_echo_s is not None:
                self._next_echo_s -= dt
                if self._next_echo_s <= 0:
                    self._level = 1.0
                    self._next_echo_s = None
            # Expected number of strikes this frame; keep the fraction for next.
            self._carry += dt / self.interval_s
            ignitions = int(self._carry)
            self._carry -= ignitions
            for _ in range(ignitions):
                self._level = 1.0
                if self._next_echo_s is None and self._rng.random() < self._DOUBLE_STRIKE_CHANCE:
                    self._next_echo_s = self._DOUBLE_STRIKE_GAP_S
        return self._level


class RedAlertAurora:
    """Slow, soft colour waves drifting across the lamps – a calm ambient
    look, unlike ``glitter``'s fast per-lamp sparkle or ``chase``'s hard
    two-colour bands. Continuously blends through a palette of colours, each
    lamp offset in phase (by its position) so the blend visibly drifts along
    the array instead of every lamp changing colour in lockstep.

    Computes a per-lamp **colour** directly, not a brightness shape;
    ``main.py`` layers its own slow brightness breathing
    (:meth:`RedAlertPulse.periodic`) and the ``[glow_low, glow_high]`` mapping
    on top.
    """

    def __init__(
        self,
        num_lights: int,
        palette: list[tuple[int, int, int]] | None = None,
        period_s: float = 6.0,
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.palette = [tuple(c) for c in palette] if palette else [(0, 200, 120)]
        self.period_s = max(0.5, period_s)

    def colors_for(self, t: float) -> list[tuple[float, float, float]]:
        """Per-lamp ``(r, g, b)`` in 0..255 (float), blended from the palette."""
        n = len(self.palette)
        out: list[tuple[float, float, float]] = []
        for i in range(self.num_lights):
            phase = (t / self.period_s + i / self.num_lights) % 1.0
            pos = phase * n
            idx = int(pos) % n
            nxt = (idx + 1) % n
            frac = pos - int(pos)
            c0, c1 = self.palette[idx], self.palette[nxt]
            out.append(tuple(c0[k] + (c1[k] - c0[k]) * frac for k in range(3)))
        return out


class RedAlertRainbow:
    """Continuous rainbow hue-cycle, phase-offset per lamp so a spectrum
    visibly sweeps across the array – a colour-loop that stays phase-locked
    across lamps, unlike each Hue lamp cycling through colours independently.

    Computes a per-lamp **colour** directly (full saturation/value), not a
    brightness shape; ``main.py`` maps a constant level through
    ``[glow_low, glow_high]`` on top (usually ``glow_high``, i.e. full colour).
    """

    def __init__(self, num_lights: int, period_s: float = 6.0) -> None:
        self.num_lights = max(1, num_lights)
        self.period_s = max(0.2, period_s)

    def colors_for(self, t: float) -> list[tuple[float, float, float]]:
        """Per-lamp ``(r, g, b)`` in 0..255 (float), full saturation/value."""
        n = self.num_lights
        out: list[tuple[float, float, float]] = []
        for i in range(n):
            hue = ((t / self.period_s) + i / n) % 1.0
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            out.append((r * 255.0, g * 255.0, b * 255.0))
        return out


class RedAlertMeteor:
    """Several independent comets crossing the channels at randomised speeds,
    directions and peak brightness – a busier, less orderly cousin of
    :class:`RedAlertComet`, which runs a single deterministic sweep.

    Each meteor's start position/speed/brightness is randomised once at
    construction (like :class:`RedAlertGlitter`'s palette/seed), then
    :meth:`brightness_for` is a pure function of ``t`` – no per-frame state.
    """

    _TAIL_FRAC = 0.35

    def __init__(
        self,
        num_lights: int,
        count: int = 3,
        speed: float = 1.2,
        seed: int | None = None,
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.count = max(1, count)
        rng = random.Random(seed)
        speed = max(0.05, speed)
        self._meteors = [
            {
                "offset": rng.uniform(0, self.num_lights),
                "speed": rng.uniform(speed * 0.6, speed * 1.6) * rng.choice((1.0, -1.0)),
                "peak": rng.uniform(0.55, 1.0),
            }
            for _ in range(self.count)
        ]
        self._tail = max(0.3, self._TAIL_FRAC * self.num_lights)

    def brightness_for(self, t: float) -> list[float]:
        """Per-light 0..1 shape at time ``t`` – the brightest overlapping meteor wins."""
        n = self.num_lights
        levels = [0.0] * n
        for m in self._meteors:
            head = (m["offset"] + m["speed"] * t) % n
            for i in range(n):
                d = (head - i) % n  # distance behind the head, wrapping
                if d < self._tail:
                    lvl = m["peak"] * math.exp(-d / (self._tail / 3.0))
                    if lvl > levels[i]:
                        levels[i] = lvl
        return [min(1.0, v) for v in levels]


class RedAlertWipe:
    """Sequential fill across the channels (like a loading bar) that holds
    once full, then resets and fills again – a one-shot motif repeated on a
    loop, unlike ``chase``'s continuously moving band.

    ``sweep_seconds`` is the fill duration (channel 0 to the last channel);
    ``pause_seconds`` is how long it holds fully lit before resetting to
    empty and filling again.
    """

    def __init__(
        self, num_lights: int, sweep_seconds: float = 1.4, pause_seconds: float = 0.6
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.sweep_seconds = max(0.1, sweep_seconds)
        self.pause_seconds = max(0.0, pause_seconds)

    def brightness_for(self, t: float) -> list[float]:
        """Per-light 0..1 shape at time ``t`` – how far the fill has reached."""
        cycle = self.sweep_seconds + self.pause_seconds
        u = t % cycle
        n = self.num_lights
        if u >= self.sweep_seconds:
            return [1.0] * n
        filled = (u / self.sweep_seconds) * n
        return [min(1.0, max(0.0, filled - i)) for i in range(n)]


class RedAlertFirework:
    """One-shot bursts radiating outward from the centre channel, then
    fading – repeats every ``interval_s``. Good for a celebratory trigger
    (countdown, doorbell) rather than a continuous ambient loop.
    """

    _DECAY_FRAC = 0.5

    def __init__(self, num_lights: int, interval_s: float = 3.0, speed: float = 6.0) -> None:
        self.num_lights = max(1, num_lights)
        self.center = (self.num_lights - 1) / 2.0
        self.interval_s = max(0.2, interval_s)
        self.speed = max(0.5, speed)

    def brightness_for(self, t: float) -> list[float]:
        """Per-light 0..1 shape at time ``t`` – the burst ring's current radius/decay."""
        age = t % self.interval_s
        radius = age * self.speed
        decay = math.exp(-age / self._DECAY_FRAC)
        return [decay if abs(i - self.center) <= radius else 0.0 for i in range(self.num_lights)]


class RedAlertRipple:
    """A brightness pulse radiates from the centre channel, reflects off both
    ends of the strip and echoes back inward before fading, then repeats –
    unlike :class:`RedAlertFirework`, which only radiates outward once per
    burst and never bounces back.

    The wavefront's distance from the centre follows a folded (triangle-wave)
    ramp, so it travels out to the nearest end, back through the centre,
    out to the other end, and so on, while the shared ``decay`` envelope
    (reset every ``interval_s``) fades the whole thing out between echoes.
    """

    _DECAY_FRAC = 0.7
    _WIDTH = 1.0  # width of the travelling wavefront, in channels

    def __init__(self, num_lights: int, interval_s: float = 3.0, speed: float = 6.0) -> None:
        self.num_lights = max(1, num_lights)
        self.center = (self.num_lights - 1) / 2.0
        self.max_dist = max(self.center, self.num_lights - 1 - self.center, 1e-6)
        self.interval_s = max(0.2, interval_s)
        self.speed = max(0.5, speed)

    def brightness_for(self, t: float) -> list[float]:
        """Per-light 0..1 shape at time ``t`` – position of the echoing wavefront."""
        age = t % self.interval_s
        period = 2.0 * self.max_dist
        folded = (age * self.speed) % period
        radius = folded if folded <= self.max_dist else period - folded
        decay = math.exp(-age / self._DECAY_FRAC)
        return [
            decay * max(0.0, 1.0 - abs(abs(i - self.center) - radius) / self._WIDTH)
            for i in range(self.num_lights)
        ]


class RedAlertWave:
    """A continuous spatial sine wave of brightness scrolling across the
    channels, with several crests/troughs visible at once – unlike
    :class:`RedAlertComet`'s single localised head looping around.

    ``wavelength`` is the number of channels per full sine cycle (small =
    more, tighter crests visible at once); ``period_s`` is how long the
    pattern takes to scroll past a fixed point.
    """

    def __init__(self, num_lights: int, period_s: float = 2.0, wavelength: float = 3.0) -> None:
        self.num_lights = max(1, num_lights)
        self.period_s = max(0.1, period_s)
        self.wavelength = max(0.5, wavelength)

    def brightness_for(self, t: float) -> list[float]:
        """Per-light 0..1 shape at time ``t`` – a scrolling sine wave."""
        k = 2.0 * math.pi / self.wavelength
        w = 2.0 * math.pi / self.period_s
        return [0.5 - 0.5 * math.cos(k * i - w * t) for i in range(self.num_lights)]


class RedAlertFlicker:
    """Lamps sporadically dip and glitch from full brightness, like a failing
    bulb – the opposite mood of :class:`RedAlertGlitter` (which brightens) or
    :class:`RedAlertLightning` (a single shared flash).

    Stateful and time-stepped like :class:`RedAlertGlitter`: each lamp rests
    at full brightness (``1.0``) and recovers there exponentially after a
    dip; at random moments (on average one every ``interval_s`` **across the
    whole strip**) a lamp suddenly dips to a low, random level. ``main.py``
    maps the returned ``1.0``-resting shape onto ``[glow_low, glow_high]``
    like the other effects, so the resting state is the bridge's normal
    "on" glow and a dip is the glitch.
    """

    def __init__(
        self,
        num_lights: int,
        interval_s: float = 0.6,
        dip_s: float = 0.15,
        seed: int | None = None,
    ) -> None:
        self.num_lights = max(1, num_lights)
        self.interval_s = max(1e-3, interval_s)
        self.dip_s = max(1e-3, dip_s)
        self._rng = random.Random(seed)
        self._level = [1.0] * self.num_lights
        self._carry = 0.0

    def step(self, dt: float) -> list[float]:
        """Advance by ``dt`` s; return per-lamp ``1.0``-resting 0..1 level."""
        dt = max(0.0, dt)
        if dt > 0.0:
            recover = math.exp(-dt / self.dip_s)
            for i in range(self.num_lights):
                lv = 1.0 - (1.0 - self._level[i]) * recover
                self._level[i] = 1.0 if lv > 1.0 - 1e-3 else lv
            # Expected number of dips this frame; keep the fraction for next.
            self._carry += dt / self.interval_s
            dips = int(self._carry)
            self._carry -= dips
            for _ in range(min(dips, self.num_lights * 4)):
                i = self._rng.randrange(self.num_lights)
                self._level[i] = self._rng.uniform(0.0, 0.35)
        return list(self._level)


class RedAlertStrobe:
    """A hard, instant on/off flash – no fade at all, unlike ``pulse``'s
    smooth attack/release. Classic rave/party strobe look.

    ``period_s`` is the time between the start of one flash and the next;
    the on-time within each period (the duty cycle) is a fixed, short
    fraction so the flash always reads as a sharp strobe rather than a
    square-wave blink.
    """

    _DUTY = 0.15

    def __init__(self, num_lights: int, period_s: float = 0.5) -> None:
        self.num_lights = max(1, num_lights)
        self.period_s = max(0.02, period_s)

    def brightness_for(self, t: float) -> list[float]:
        """Per-light 0/1 shape at time ``t`` – on for the first ``_DUTY`` of each period."""
        on = (t % self.period_s) < (self.period_s * self._DUTY)
        return [1.0 if on else 0.0] * self.num_lights


class RedAlertDuel:
    """Two comets launched from opposite ends in two colours, meeting in the
    middle and bouncing back off each other – unlike :class:`RedAlertMeteor`
    (independent, random) or :class:`RedAlertComet` (a single deterministic
    loop).

    Each comet's position follows a triangle wave between the two ends of
    the strip, exactly out of phase with the other, so they meet in the
    middle, "collide", and head back the way they came. Returns **two**
    brightness shapes (one per comet); ``main.py`` colours comet A with the
    bridge colour and comet B with ``color2``, blending the two where
    their tails overlap.
    """

    _TAIL_FRAC = 0.35

    def __init__(self, num_lights: int, period_s: float = 2.0) -> None:
        self.num_lights = max(1, num_lights)
        self.span = max(1, self.num_lights - 1)
        self.period_s = max(0.2, period_s)
        self.tail = max(0.3, self._TAIL_FRAC * self.num_lights)

    def brightness_for(self, t: float) -> tuple[list[float], list[float]]:
        """Per-light 0..1 shapes ``(comet_a, comet_b)`` at time ``t``."""
        phase = (t % self.period_s) / self.period_s
        tri = 1.0 - abs(2.0 * phase - 1.0)  # 0 -> 1 -> 0
        pos_a = tri * self.span
        pos_b = self.span - pos_a
        levels_a = [max(0.0, 1.0 - abs(i - pos_a) / self.tail) for i in range(self.num_lights)]
        levels_b = [max(0.0, 1.0 - abs(i - pos_b) / self.tail) for i in range(self.num_lights)]
        return levels_a, levels_b
