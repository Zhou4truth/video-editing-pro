"""
High level decoding helpers built on top of PyAV.

The decoder keeps lightweight caches for recently accessed frames so repeated
timeline scrubs avoid hitting the container on every request. For the MVP we
focus on single-threaded decode but allow concurrent calls through a lock.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import av
import numpy as np

TICKS_PER_SECOND = 90_000


def _seconds_to_ticks(seconds: float) -> int:
    return int(round(seconds * TICKS_PER_SECOND))


@dataclass
class VideoFrame:
    pts: float
    image: np.ndarray  # BGR24


@dataclass
class AudioBuffer:
    start: float
    samples: np.ndarray  # float32 mono/stereo
    rate: int


class DecoderError(Exception):
    pass


class FrameCache:
    def __init__(self, capacity: int = 32) -> None:
        self.capacity = capacity
        self._entries: Dict[Tuple[str, int], VideoFrame] = {}
        self._order: Dict[Tuple[str, int], int] = {}
        self._hits = 0
        self._clock = 0

    def get(self, asset_id: str, key_ticks: int) -> Optional[VideoFrame]:
        handle = (asset_id, key_ticks)
        frame = self._entries.get(handle)
        if frame is None:
            return None
        self._clock += 1
        self._order[handle] = self._clock
        return frame

    def put(self, asset_id: str, key_ticks: int, frame: VideoFrame) -> None:
        handle = (asset_id, key_ticks)
        self._entries[handle] = frame
        self._clock += 1
        self._order[handle] = self._clock
        if len(self._entries) > self.capacity:
            lru_handle = min(self._order, key=self._order.get)
            self._entries.pop(lru_handle, None)
            self._order.pop(lru_handle, None)


class MediaDecoder:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._containers: Dict[str, av.container.InputContainer] = {}
        self._video_streams: Dict[str, av.video.stream.VideoStream] = {}
        self._audio_streams: Dict[str, av.audio.stream.AudioStream] = {}
        self._frame_cache = FrameCache()

    # ---------------------------------------------------------- metadata ----------
    def probe(self, path: Path) -> Dict[str, Dict]:
        with av.open(str(path)) as container:
            info = {
                "duration": float(container.duration or 0) / av.time_base if container.duration else 0.0,
                "video": [],
                "audio": [],
            }
            for stream in container.streams:
                if stream.type == "video":
                    info["video"].append(
                        {
                            "index": stream.index,
                            "width": stream.codec_context.width,
                            "height": stream.codec_context.height,
                            "fps": float(stream.average_rate) if stream.average_rate else 0.0,
                        }
                    )
                elif stream.type == "audio":
                    info["audio"].append(
                        {
                            "index": stream.index,
                            "rate": stream.codec_context.rate,
                            "channels": stream.codec_context.channels,
                        }
                    )
        return info

    # ----------------------------------------------------------- frame decode -----
    def video_frame_at(self, asset_id: str, path: Path, seconds: float) -> VideoFrame:
        with self._lock:
            container, stream = self._ensure_video_container(asset_id, path)
            target_ticks = _seconds_to_ticks(seconds)
            cached = self._frame_cache.get(asset_id, target_ticks)
            if cached:
                return cached

            seek_pts = int(seconds / stream.time_base)
            container.seek(seek_pts, stream=stream, any_frame=False, backward=True)

            last_frame: Optional[VideoFrame] = None
            for packet in container.demux(stream):
                for decoded in packet.decode():
                    pts_seconds = float(decoded.pts * decoded.time_base) if decoded.pts is not None else 0.0
                    frame = VideoFrame(
                        pts=pts_seconds,
                        image=decoded.to_ndarray(format="bgr24"),
                    )
                    frame_ticks = _seconds_to_ticks(frame.pts)
                    self._frame_cache.put(asset_id, frame_ticks, frame)
                    last_frame = frame
                    if frame_ticks >= target_ticks:
                        return frame
                if last_frame and _seconds_to_ticks(last_frame.pts) >= target_ticks:
                    break

            if last_frame is None:
                raise DecoderError(f"No frame decoded at {seconds}s for {path}")
            return last_frame

    def audio_segment(
        self,
        asset_id: str,
        path: Path,
        start: float,
        duration: Optional[float],
    ) -> AudioBuffer:
        with self._lock:
            container, stream = self._ensure_audio_container(asset_id, path)
            start_pts = int(start / stream.time_base)
            container.seek(start_pts, stream=stream, any_frame=True, backward=True)

            samples = []
            sample_rate = stream.codec_context.rate
            target_samples = int(duration * sample_rate) if duration and duration > 0 else None
            current_time = 0.0
            for packet in container.demux(stream):
                for frame in packet.decode():
                    frame_time = float(frame.pts * frame.time_base) if frame.pts is not None else current_time
                    current_time = frame_time
                    array = frame.to_ndarray(format="float32")
                    samples.append(array)
                    if target_samples is not None and sum(buf.shape[0] for buf in samples) >= target_samples:
                        break
                if target_samples is not None and sum(buf.shape[0] for buf in samples) >= target_samples:
                    break

            if not samples:
                raise DecoderError(f"No audio decoded from {path}")

            audio = np.concatenate(samples, axis=0)
            if target_samples is not None and audio.shape[0] > target_samples:
                audio = audio[:target_samples]

            return AudioBuffer(start=start, samples=audio, rate=sample_rate)

    # ------------------------------------------------------------- containers -----
    def _ensure_video_container(self, asset_id: str, path: Path):
        container = self._containers.get(asset_id)
        stream = self._video_streams.get(asset_id)
        if container is None or stream is None:
            container = av.open(str(path))
            stream = next((s for s in container.streams if s.type == "video"), None)
            if stream is None:
                raise DecoderError(f"Video stream not found in {path}")
            stream.thread_type = "AUTO"
            self._containers[asset_id] = container
            self._video_streams[asset_id] = stream
        return container, stream

    def _ensure_audio_container(self, asset_id: str, path: Path):
        container = self._containers.get(asset_id)
        stream = self._audio_streams.get(asset_id)
        if container is None or stream is None:
            container = av.open(str(path))
            stream = next((s for s in container.streams if s.type == "audio"), None)
            if stream is None:
                raise DecoderError(f"Audio stream not found in {path}")
            self._containers[asset_id] = container
            self._audio_streams[asset_id] = stream
        return container, stream

    # -------------------------------------------------------------- lifecycle -----
    def close(self) -> None:
        with self._lock:
            for container in self._containers.values():
                container.close()
            self._containers.clear()
            self._video_streams.clear()
            self._audio_streams.clear()
