"""
Core project data model for Video Editor MVP.

All public time values remain in seconds for readability while the timeline
engine converts to integer ticks internally for precise math.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Callable
import json
import threading
import time


def _now_millis() -> int:
    return int(time.time() * 1000)


@dataclass
class Keyframe:
    t: float
    x: float
    y: float
    w: float
    h: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Keyframe":
        return Keyframe(
            t=float(data.get("t", 0.0)),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            w=float(data.get("w", 0.0)),
            h=float(data.get("h", 0.0)),
        )


@dataclass
class Effect:
    type: str
    params: Dict[str, Any] = field(default_factory=dict)
    keyframes: List[Keyframe] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "params": dict(self.params),
            "keyframes": [kf.to_dict() for kf in self.keyframes],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Effect":
        return Effect(
            type=data["type"],
            params=dict(data.get("params", {})),
            keyframes=[Keyframe.from_dict(kf) for kf in data.get("keyframes", [])],
        )


@dataclass
class GainPoint:
    t: float
    gain: float

    def to_dict(self) -> Dict[str, Any]:
        return {"t": float(self.t), "gain": float(self.gain)}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "GainPoint":
        return GainPoint(
            t=float(data.get("t", 0.0)),
            gain=float(data.get("gain", 1.0)),
        )


@dataclass
class Clip:
    id: str
    asset: str
    start: float  # timeline start in seconds
    in_point: float
    out_point: float
    muted: bool = False
    locked: bool = False
    effects: List[Effect] = field(default_factory=list)
    gain_envelope: List[GainPoint] = field(default_factory=list)

    def duration(self) -> float:
        return max(0.0, self.out_point - self.in_point)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "asset": self.asset,
            "start": float(self.start),
            "in": float(self.in_point),
            "out": float(self.out_point),
            "muted": bool(self.muted),
            "locked": bool(self.locked),
            "effects": [effect.to_dict() for effect in self.effects],
            "gain_envelope": [point.to_dict() for point in self.gain_envelope],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Clip":
        return Clip(
            id=data["id"],
            asset=data["asset"],
            start=float(data.get("start", 0.0)),
            in_point=float(data.get("in", 0.0)),
            out_point=float(data.get("out", 0.0)),
            muted=bool(data.get("muted", False)),
            locked=bool(data.get("locked", False)),
            effects=[Effect.from_dict(e) for e in data.get("effects", [])],
            gain_envelope=[GainPoint.from_dict(g) for g in data.get("gain_envelope", [])],
        )


@dataclass
class Track:
    id: str
    type: str  # "video" or "audio"
    clips: List[Clip] = field(default_factory=list)
    muted: bool = False
    locked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "muted": bool(self.muted),
            "locked": bool(self.locked),
            "clips": [clip.to_dict() for clip in self.clips],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Track":
        return Track(
            id=data["id"],
            type=data["type"],
            muted=bool(data.get("muted", False)),
            locked=bool(data.get("locked", False)),
            clips=[Clip.from_dict(c) for c in data.get("clips", [])],
        )

    def length_seconds(self) -> float:
        if not self.clips:
            return 0.0
        return max(clip.start + clip.duration() for clip in self.clips)

    def add_clip(self, clip: Clip) -> None:
        self.clips.append(clip)
        self.clips.sort(key=lambda c: c.start)


@dataclass
class Asset:
    id: str
    path: str
    type: str  # "video" or "audio"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "type": self.type,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Asset":
        return Asset(
            id=data["id"],
            path=data["path"],
            type=data.get("type", "video"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ProjectSettings:
    fps: int = 30
    width: int = 1920
    height: int = 1080
    autosave_interval_sec: int = 120
    ui_scale: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fps": self.fps,
            "resolution": [self.width, self.height],
            "autosave_interval_sec": self.autosave_interval_sec,
            "ui_scale": self.ui_scale,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ProjectSettings":
        resolution = data.get("resolution", [1920, 1080])
        width = int(resolution[0]) if resolution else 1920
        height = int(resolution[1]) if len(resolution) > 1 else 1080
        return ProjectSettings(
            fps=int(data.get("fps", 30)),
            width=width,
            height=height,
            autosave_interval_sec=int(data.get("autosave_interval_sec", 120)),
            ui_scale=float(data.get("ui_scale", 1.0)),
        )


@dataclass
class Project:
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    assets: List[Asset] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    last_saved_millis: int = field(default_factory=_now_millis)
    autosave_token: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": self.settings.to_dict(),
            "assets": [asset.to_dict() for asset in self.assets],
            "tracks": [track.to_dict() for track in self.tracks],
            "metadata": dict(self.metadata),
            "version": self.version,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Project":
        project = Project()
        project.settings = ProjectSettings.from_dict(data.get("project", {}))
        project.assets = [Asset.from_dict(a) for a in data.get("assets", [])]
        project.tracks = [Track.from_dict(t) for t in data.get("tracks", [])]
        project.metadata = dict(data.get("metadata", {}))
        project.version = data.get("version", "1.0.0")
        project.last_saved_millis = _now_millis()
        return project

    def add_asset(self, asset: Asset) -> None:
        if any(existing.id == asset.id for existing in self.assets):
            raise ValueError(f"Asset {asset.id} already exists")
        self.assets.append(asset)

    def remove_asset(self, asset_id: str) -> None:
        self.assets = [asset for asset in self.assets if asset.id != asset_id]
        for track in self.tracks:
            track.clips = [clip for clip in track.clips if clip.asset != asset_id]

    def ensure_track(self, track_id: str, track_type: str) -> Track:
        for track in self.tracks:
            if track.id == track_id:
                return track
        track = Track(id=track_id, type=track_type)
        self.tracks.append(track)
        self.tracks.sort(key=lambda t: t.id)
        return track

    def get_track(self, track_id: str) -> Track:
        for track in self.tracks:
            if track.id == track_id:
                return track
        raise KeyError(track_id)

    def all_clips(self) -> Iterable[Clip]:
        for track in self.tracks:
            for clip in track.clips:
                yield clip

    def total_length_seconds(self) -> float:
        return max((track.length_seconds() for track in self.tracks), default=0.0)

    def save(self, path: Path) -> None:
        data = self.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
        self.last_saved_millis = _now_millis()

    @staticmethod
    def load(path: Path) -> "Project":
        data = json.loads(path.read_text())
        project = Project.from_dict(data)
        project.last_saved_millis = _now_millis()
        return project

    def autosave(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        autosave_path = directory / f"{self.autosave_token or 'autosave'}.vegproj.autosave"
        autosave_path.write_text(json.dumps(self.to_dict()))
        return autosave_path


class ProjectStore:
    """Thread-safe in-memory store for project updates."""

    def __init__(self, project: Optional[Project] = None) -> None:
        self._lock = threading.RLock()
        self._project = project or Project()
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []

    @property
    def project(self) -> Project:
        with self._lock:
            return self._project

    def update(self, fn: Callable[[Project], None]) -> None:
        with self._lock:
            fn(self._project)
            snapshot = self._project.to_dict()
        for listener in list(self._listeners):
            listener(snapshot)

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)
