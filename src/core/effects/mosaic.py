"""Pixelation effect for rectangular regions."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


def apply_mosaic(frame_bgr: np.ndarray, roi: Tuple[int, int, int, int], blocks: int = 24) -> np.ndarray:
    """
    Apply a pixelation effect inside the ROI (x, y, w, h) on a copy of frame_bgr.
    """
    x, y, w, h = roi
    x = max(0, x)
    y = max(0, y)
    w = max(1, w)
    h = max(1, h)
    frame_copy = frame_bgr.copy()
    region = frame_copy[y : y + h, x : x + w]
    if region.size == 0:
        return frame_copy

    blocks = max(1, blocks)
    downscale_w = max(1, w // blocks)
    downscale_h = max(1, h // blocks)
    small = cv2.resize(region, (downscale_w, downscale_h), interpolation=cv2.INTER_LINEAR)
    pixelated = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    frame_copy[y : y + h, x : x + w] = pixelated
    return frame_copy
