"""Gaussian blur effect for rectangular regions."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


def apply_blur(frame_bgr: np.ndarray, roi: Tuple[int, int, int, int], radius: int = 11) -> np.ndarray:
    """
    Apply a separable Gaussian blur inside the ROI.
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

    radius = max(1, radius)
    kernel = (radius // 2) * 2 + 1  # ensure odd kernel size
    blurred = cv2.GaussianBlur(region, (kernel, kernel), 0, borderType=cv2.BORDER_REFLECT)
    frame_copy[y : y + h, x : x + w] = blurred
    return frame_copy
