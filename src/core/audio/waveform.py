"""
Waveform generation utilities.

The waveform is stored as RMS values per fixed size window, enabling low-cost
timeline waveform rendering.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np


@dataclass
class WaveformData:
    window_size: int
    rms: List[float]

    def to_dict(self) -> dict:
        return {"window_size": self.window_size, "rms": self.rms}

    @staticmethod
    def from_dict(data: dict) -> "WaveformData":
        return WaveformData(window_size=int(data["window_size"]), rms=list(map(float, data["rms"])))


def compute_waveform(samples: np.ndarray, window_size: int = 512) -> WaveformData:
    if samples.ndim > 1:
        mono = np.mean(samples, axis=1)
    else:
        mono = samples
    windows = len(mono) // window_size
    if windows == 0:
        rms_values = [float(np.sqrt(np.mean(np.square(mono))))] if mono.size else [0.0]
        return WaveformData(window_size=window_size, rms=rms_values)

    rms_values = []
    for i in range(windows):
        window = mono[i * window_size : (i + 1) * window_size]
        rms = float(np.sqrt(np.mean(np.square(window)))) if window.size else 0.0
        rms_values.append(rms)
    return WaveformData(window_size=window_size, rms=rms_values)


def save_waveform(path: Path, data: WaveformData) -> None:
    path.write_text(json.dumps(data.to_dict()))


def load_waveform(path: Path) -> WaveformData:
    return WaveformData.from_dict(json.loads(path.read_text()))
