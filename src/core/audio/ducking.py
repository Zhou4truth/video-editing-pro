"""Simple side-chain audio ducking processor."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class DuckingParams:
    threshold: float = -30.0  # dBFS
    reduction: float = -12.0  # dB change when voice is loud
    attack: float = 0.05  # seconds
    release: float = 0.3  # seconds


def rms_db(samples: np.ndarray, eps: float = 1e-12) -> float:
    rms = np.sqrt(np.mean(np.square(samples)))
    return 20 * np.log10(max(rms, eps))


def apply_ducking(voice: np.ndarray, music: np.ndarray, sample_rate: int, params: DuckingParams) -> np.ndarray:
    """
    Apply gain reduction to music whenever voice exceeds threshold.
    """
    if voice.shape != music.shape:
        raise ValueError("Voice and music buffers must match")

    frame_size = max(int(sample_rate * 0.01), 1)  # 10ms windows
    attack_coeff = np.exp(-1.0 / (params.attack * sample_rate)) if params.attack > 0 else 0.0
    release_coeff = np.exp(-1.0 / (params.release * sample_rate)) if params.release > 0 else 0.0
    gain = 1.0
    output = np.zeros_like(music)

    for i in range(0, len(music), frame_size):
        window_voice = voice[i : i + frame_size]
        window_music = music[i : i + frame_size]
        level = rms_db(window_voice) if window_voice.size else -120.0
        target_gain_db = 0.0
        if level > params.threshold:
            target_gain_db = params.reduction * ((level - params.threshold) / abs(params.reduction))
            target_gain_db = max(params.reduction, target_gain_db)

        target_gain = 10 ** (target_gain_db / 20)
        if target_gain < gain:
            gain = attack_coeff * (gain - target_gain) + target_gain
        else:
            gain = release_coeff * (gain - target_gain) + target_gain
        output[i : i + frame_size] = window_music * gain

    return output
