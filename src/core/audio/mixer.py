"""
Audio mixing utilities for Video Editor MVP.

Provides helpers to apply per-clip gain envelopes and mix rendered waveforms
into a single PCM bus suitable for export.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

import numpy as np

from ..project_model import Clip, GainPoint


@dataclass
class AudioClipBuffer:
    clip: Clip
    samples: np.ndarray  # float32 shape=(n, channels)
    sample_rate: int
    start_time: float  # seconds on the timeline


def apply_gain_envelope(samples: np.ndarray, sample_rate: int, envelope: Sequence[GainPoint]) -> np.ndarray:
    if not envelope:
        return samples

    times = np.array([point.t for point in envelope], dtype=np.float32)
    gains = np.array([point.gain for point in envelope], dtype=np.float32)

    duration = samples.shape[0] / sample_rate
    t = np.linspace(0, duration, samples.shape[0], endpoint=False)
    interp = np.interp(t, times, gains, left=gains[0], right=gains[-1])
    if samples.ndim == 1:
        return samples * interp
    else:
        return samples * interp[:, None]


def mix_to_bus(buffers: Iterable[AudioClipBuffer], sample_rate: int, master_gain: float = 1.0) -> np.ndarray:
    buffers = list(buffers)
    if not buffers:
        return np.zeros((0,), dtype=np.float32)

    max_end = 0
    channel_count = 1
    for buf in buffers:
        duration = buf.samples.shape[0] / buf.sample_rate
        end_time = buf.start_time + duration
        max_end = max(max_end, end_time)
        channel_count = max(channel_count, buf.samples.shape[1] if buf.samples.ndim > 1 else 1)

    total_samples = int(np.ceil(max_end * sample_rate))
    bus = np.zeros((total_samples, channel_count), dtype=np.float32)

    for buf in buffers:
        clip_samples = buf.samples
        if buf.samples.ndim == 1:
            clip_samples = buf.samples[:, None]
        gain_applied = apply_gain_envelope(clip_samples, buf.sample_rate, buf.clip.gain_envelope)
        resampled = _resample_if_needed(gain_applied, buf.sample_rate, sample_rate)
        start_idx = int(buf.start_time * sample_rate)
        end_idx = min(start_idx + resampled.shape[0], bus.shape[0])
        segment_len = end_idx - start_idx
        bus[start_idx:end_idx, :resampled.shape[1]] += resampled[:segment_len]

    return np.clip(bus * master_gain, -1.0, 1.0)


def _resample_if_needed(samples: np.ndarray, current_rate: int, target_rate: int) -> np.ndarray:
    if current_rate == target_rate:
        return samples
    ratio = target_rate / current_rate
    target_len = int(round(samples.shape[0] * ratio))
    indices = np.linspace(0, samples.shape[0] - 1, target_len).astype(np.float32)
    if samples.ndim == 1:
        return np.interp(indices, np.arange(samples.shape[0]), samples).astype(np.float32)
    else:
        channels = []
        original_idx = np.arange(samples.shape[0])
        for channel in range(samples.shape[1]):
            channel_samples = np.interp(indices, original_idx, samples[:, channel])
            channels.append(channel_samples)
        return np.stack(channels, axis=1).astype(np.float32)
