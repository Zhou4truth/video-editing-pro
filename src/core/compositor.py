"""
Frame compositor for Video Editor MVP.

For every frame request we composite clips that overlap the target time,
apply effects in sequence, and return a BGR frame ready for preview/export.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from pathlib import Path

from .project_model import Clip, Effect, Keyframe, Project, Track
from .decoder import MediaDecoder, VideoFrame
from .effects.mosaic import apply_mosaic
from .effects.blur import apply_blur


@dataclass
class CompositorConfig:
    background_color: Tuple[int, int, int] = (0, 0, 0)


def _interpolate_keyframes(keyframes: List[Keyframe], t: float) -> Tuple[float, float, float, float]:
    if not keyframes:
        return 0.0, 0.0, 1.0, 1.0
    if t <= keyframes[0].t:
        first = keyframes[0]
        return first.x, first.y, first.w, first.h
    if t >= keyframes[-1].t:
        last = keyframes[-1]
        return last.x, last.y, last.w, last.h
    for left, right in zip(keyframes, keyframes[1:]):
        if left.t <= t <= right.t:
            span = right.t - left.t
            factor = (t - left.t) / span if span else 0.0
            x = left.x + (right.x - left.x) * factor
            y = left.y + (right.y - left.y) * factor
            w = left.w + (right.w - left.w) * factor
            h = left.h + (right.h - left.h) * factor
            return x, y, w, h
    last = keyframes[-1]
    return last.x, last.y, last.w, last.h


class Compositor:
    def __init__(self, project: Project, decoder: MediaDecoder, config: Optional[CompositorConfig] = None) -> None:
        self.project = project
        self.decoder = decoder
        self.config = config or CompositorConfig()

    def render_frame(self, seconds: float) -> np.ndarray:
        settings = self.project.settings
        width, height = settings.width, settings.height
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = self.config.background_color

        for track in self._iter_tracks(order="video"):
            for clip in track.clips:
                if clip.start <= seconds < clip.start + clip.duration():
                    local_time = seconds - clip.start + clip.in_point
                    frame = self._composite_clip(frame, clip, local_time, settings)
        return frame

    def _composite_clip(self, base_frame: np.ndarray, clip: Clip, local_time: float, settings) -> np.ndarray:
        width, height = settings.width, settings.height
        asset = next((a for a in self.project.assets if a.id == clip.asset), None)
        if asset is None:
            return base_frame
        decoded = self.decoder.video_frame_at(clip.asset, Path(asset.path), local_time)
        clip_frame = self._apply_effects(decoded, clip, local_time, width, height)
        blended = base_frame.copy()
        np.copyto(blended, clip_frame)
        return blended

    def _apply_effects(self, video_frame: VideoFrame, clip: Clip, local_time: float, width: int, height: int) -> np.ndarray:
        frame = video_frame.image.copy()
        for effect in clip.effects:
            if effect.type == "mosaic":
                blocks = int(effect.params.get("blocks", 24))
                roi = self._keyframe_roi(effect, local_time, width, height)
                frame = apply_mosaic(frame, roi, blocks)
            elif effect.type == "blur":
                radius = int(effect.params.get("radius", 11))
                roi = self._keyframe_roi(effect, local_time, width, height)
                frame = apply_blur(frame, roi, radius)
        return frame

    def _keyframe_roi(self, effect: Effect, local_time: float, width: int, height: int) -> Tuple[int, int, int, int]:
        x, y, w, h = _interpolate_keyframes(effect.keyframes, local_time)
        return (
            int(x * width),
            int(y * height),
            int(w * width),
            int(h * height),
        )

    def _iter_tracks(self, order: str) -> List[Track]:
        if order == "video":
            return [track for track in self.project.tracks if track.type == "video" and not track.muted]
        return [track for track in self.project.tracks if track.type == "audio" and not track.muted]
