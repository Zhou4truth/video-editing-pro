"""
Timeline manipulation helpers for the Video Editor MVP.

Mutations operate directly on the shared Project model (see project_model).
The engine keeps the playhead expressed in ticks to simplify precise frame
math while exposing seconds to callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .project_model import Clip, Project, Track

TICKS_PER_SECOND = 90_000


def seconds_to_ticks(seconds: float) -> int:
    return int(round(seconds * TICKS_PER_SECOND))


def ticks_to_seconds(ticks: int) -> float:
    return ticks / TICKS_PER_SECOND


@dataclass
class Playhead:
    position_ticks: int = 0

    @property
    def seconds(self) -> float:
        return ticks_to_seconds(self.position_ticks)

    def set_seconds(self, seconds: float) -> None:
        self.position_ticks = seconds_to_ticks(seconds)


class TimelineEngine:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.playhead = Playhead()
        self.snap_interval_ticks = seconds_to_ticks(1 / max(project.settings.fps, 1))

    # ------------------------------------------------------------------ utils ------
    def snap_time(self, seconds: float) -> float:
        ticks = seconds_to_ticks(seconds)
        interval = max(self.snap_interval_ticks, 1)
        snapped = round(ticks / interval) * interval
        return ticks_to_seconds(snapped)

    def set_snap_resolution(self, frame_multiple: int) -> None:
        interval = max(frame_multiple, 1)
        self.snap_interval_ticks = seconds_to_ticks(interval / max(self.project.settings.fps, 1))

    def find_clip(self, track_id: str, clip_id: str) -> Tuple[Track, Clip, int]:
        track = self.project.get_track(track_id)
        for index, clip in enumerate(track.clips):
            if clip.id == clip_id:
                return track, clip, index
        raise KeyError(f"Clip {clip_id} not found on track {track_id}")

    # --------------------------------------------------------------- edits ---------
    def insert_clip(self, track_id: str, clip: Clip) -> None:
        track = self._ensure_track_for_clip(track_id, clip)
        track.add_clip(clip)

    def split_clip(self, track_id: str, clip_id: str, time_seconds: float) -> Tuple[Clip, Clip]:
        track, clip, index = self.find_clip(track_id, clip_id)
        time_seconds = max(clip.start, min(time_seconds, clip.start + clip.duration()))
        if time_seconds <= clip.start or time_seconds >= clip.start + clip.duration():
            return clip, clip

        offset = time_seconds - clip.start
        new_in = clip.in_point + offset

        left_clip = Clip(
            id=f"{clip.id}_a",
            asset=clip.asset,
            start=clip.start,
            in_point=clip.in_point,
            out_point=new_in,
            muted=clip.muted,
            locked=clip.locked,
            effects=[effect for effect in clip.effects],
            gain_envelope=[point for point in clip.gain_envelope if point.t <= offset],
        )

        right_clip = Clip(
            id=f"{clip.id}_b",
            asset=clip.asset,
            start=time_seconds,
            in_point=new_in,
            out_point=clip.out_point,
            muted=clip.muted,
            locked=clip.locked,
            effects=[effect for effect in clip.effects],
            gain_envelope=[point for point in clip.gain_envelope if point.t >= offset],
        )

        track.clips[index : index + 1] = [left_clip, right_clip]
        return left_clip, right_clip

    def ripple_delete(self, track_id: str, clip_id: str) -> None:
        track, clip, index = self.find_clip(track_id, clip_id)
        duration = clip.duration()
        del track.clips[index]
        for later_clip in track.clips[index:]:
            later_clip.start = max(clip.start, later_clip.start - duration)

    def join_adjacent(self, track_id: str, left_clip_id: str, right_clip_id: str) -> Clip:
        track = self.project.get_track(track_id)
        left_index = self._clip_index(track, left_clip_id)
        right_index = self._clip_index(track, right_clip_id)
        if right_index != left_index + 1:
            raise ValueError("Clips must be adjacent to join")
        left_clip = track.clips[left_index]
        right_clip = track.clips[right_index]
        if left_clip.asset != right_clip.asset:
            raise ValueError("Cannot join clips from different assets")

        merged = Clip(
            id=f"{left_clip.id}_join",
            asset=left_clip.asset,
            start=left_clip.start,
            in_point=min(left_clip.in_point, right_clip.in_point),
            out_point=max(left_clip.out_point, right_clip.out_point),
            muted=left_clip.muted and right_clip.muted,
            locked=left_clip.locked and right_clip.locked,
            effects=left_clip.effects,
            gain_envelope=self._merge_gain_envelopes(left_clip, right_clip),
        )
        track.clips[left_index : right_index + 1] = [merged]
        return merged

    def move_clip(self, track_id: str, clip_id: str, new_start: float) -> None:
        track, clip, _ = self.find_clip(track_id, clip_id)
        clip.start = max(0.0, new_start)
        track.clips.sort(key=lambda c: c.start)

    def trim_clip(self, track_id: str, clip_id: str, new_in: Optional[float], new_out: Optional[float]) -> None:
        _, clip, _ = self.find_clip(track_id, clip_id)
        if new_in is not None:
            clip.in_point = min(max(new_in, 0.0), clip.out_point)
        if new_out is not None:
            clip.out_point = max(new_out, clip.in_point)

    # ------------------------------------------------------------- helpers ---------
    def _merge_gain_envelopes(self, left_clip: Clip, right_clip: Clip) -> List:
        offset = right_clip.start - left_clip.start
        result = list(left_clip.gain_envelope)
        for point in right_clip.gain_envelope:
            adjusted = point.__class__(t=point.t + offset, gain=point.gain)
            result.append(adjusted)
        result.sort(key=lambda p: p.t)
        return result

    def _clip_index(self, track: Track, clip_id: str) -> int:
        for index, clip in enumerate(track.clips):
            if clip.id == clip_id:
                return index
        raise KeyError(clip_id)

    def _ensure_track_for_clip(self, track_id: str, clip: Clip) -> Track:
        for track in self.project.tracks:
            if track.id == track_id:
                return track
        asset = next((a for a in self.project.assets if a.id == clip.asset), None)
        track_type = asset.type if asset else "video"
        new_track = Track(id=track_id, type=track_type)
        self.project.tracks.append(new_track)
        self.project.tracks.sort(key=lambda t: t.id)
        return new_track
