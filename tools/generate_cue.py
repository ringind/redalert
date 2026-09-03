#!/usr/bin/env python3
"""Erzeugt aus einer lokalen Audiodatei eine Lichtsteuerungs-Kurve (redalert_cue.json).

Es wird NUR eine numerische Lautstaerke-Huellkurve extrahiert (Zahlen pro
Zeitpunkt) - keine Audiodaten selbst werden gespeichert oder weitergegeben.
Die Eingabedatei bleibt vollstaendig unangetastet auf deinem Rechner.

Benoetigt: ffmpeg (im PATH) sowie die Python-Pakete numpy (Pflicht) und
scipy (optional, nur fuer die Ausgabe des erkannten Wiederholzyklus).

Aufruf:
    python3 generate_cue.py eingabe.mp3 ausgabe_cue.json [--fps 25]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np


def decode_to_mono_wav(input_path: Path, sample_rate: int) -> Path:
    tmp = Path(tempfile.mkstemp(suffix=".wav")[1])
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(input_path),
            "-ac", "1", "-ar", str(sample_rate),
            "-f", "wav", str(tmp),
        ],
        check=True,
    )
    return tmp


def rms_envelope(wav_path: Path, window_s: float = 0.02, hop_s: float = 0.01):
    with wave.open(str(wav_path), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        data = w.readframes(n)
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float64) / 32768.0

    win = max(1, int(sr * window_s))
    hop = max(1, int(sr * hop_s))
    env = []
    for start in range(0, max(1, len(samples) - win), hop):
        seg = samples[start:start + win]
        env.append(float(np.sqrt(np.mean(seg ** 2))))
    env = np.array(env)
    env_norm = env / (env.max() + 1e-9)
    times = np.arange(len(env)) * hop / sr
    duration = len(samples) / sr
    return times, env_norm, duration


def report_cycle_period(times: np.ndarray, env_norm: np.ndarray) -> None:
    try:
        from scipy.signal import find_peaks
    except ImportError:
        return
    peaks, _ = find_peaks(env_norm, height=0.35, distance=15)
    if len(peaks) < 2:
        return
    intervals = np.diff(times[peaks])
    print(f"Erkannte Pulse: {len(peaks)}, mittlerer Abstand: {np.median(intervals):.3f} s",
          file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Audiodatei (mp3/wav/...)")
    parser.add_argument("output", type=Path, help="Ziel-JSON, z.B. redalert_cue.json")
    parser.add_argument("--fps", type=int, default=25, help="Frames/Sekunde des Lichtprogramms")
    parser.add_argument("--gamma", type=float, default=1.4, help="Kontrast der Huellkurve")
    parser.add_argument("--noise-floor", type=float, default=0.05,
                         help="Werte darunter werden als Stille (0) behandelt")
    args = parser.parse_args()

    wav_path = decode_to_mono_wav(args.input, sample_rate=11025)
    try:
        times, env_norm, duration = rms_envelope(wav_path)
    finally:
        wav_path.unlink(missing_ok=True)

    report_cycle_period(times, env_norm)

    n_frames = int(duration * args.fps)
    frame_times = np.arange(n_frames) / args.fps
    gain = np.interp(frame_times, times, env_norm)
    gain = np.clip((gain - args.noise_floor) / (1 - args.noise_floor), 0, 1) ** args.gamma

    cue = {
        "fps": args.fps,
        "duration_s": round(duration, 3),
        "gain": [round(float(g), 3) for g in gain],
    }
    args.output.write_text(json.dumps(cue))
    print(f"Geschrieben: {args.output} ({n_frames} Frames, {duration:.1f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()
