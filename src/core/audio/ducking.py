"""Simple side-chain audio ducking processor."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class DuckingParams:
    threshold: float = -30.0  # dBFS threshold for voice detection
    base_gain_db: float = 0.0  # dB applied when voice below threshold
    slope: float = 1.0  # dB attenuation per dB above threshold
    min_gain_db: float = -12.0  # Clamp lower bound
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
    frame_duration = frame_size / sample_rate

    def _time_coeff(time_constant: float) -> float:
        if time_constant <= 0:
            return 0.0
        return float(np.exp(-frame_duration / time_constant))

    attack_coeff = _time_coeff(params.attack)
    release_coeff = _time_coeff(params.release)
    gain_db = params.base_gain_db
    output = np.zeros_like(music)

    for start in range(0, len(music), frame_size):
        end = start + frame_size
        window_voice = voice[start:end]
        window_music = music[start:end]
        level = rms_db(window_voice) if window_voice.size else -120.0
        level_over = max(0.0, level - params.threshold)
        target_gain_db = params.base_gain_db - params.slope * level_over
        target_gain_db = max(params.min_gain_db, target_gain_db)

        if target_gain_db < gain_db:
            gain_db = attack_coeff * (gain_db - target_gain_db) + target_gain_db
        else:
            gain_db = release_coeff * (gain_db - target_gain_db) + target_gain_db

        gain_linear = 10 ** (gain_db / 20)
        output[start:end] = window_music * gain_linear

    return output
