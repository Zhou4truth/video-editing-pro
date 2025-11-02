"""Import helpers for media assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List
import itertools

import numpy as np

from ..core.project_model import Asset, Project
from ..core.decoder import MediaDecoder
from ..core.audio.waveform import compute_waveform, save_waveform


VIDEO_EXT = {".mp4", ".mov", ".mkv"}
AUDIO_EXT = {".mp3", ".wav", ".aac"}


@dataclass
class ImportResult:
    assets: List[Asset]
    thumbnails: List[np.ndarray]


class MediaImporter:
    def __init__(self, project: Project, decoder: MediaDecoder, waveform_dir: Path) -> None:
        self.project = project
        self.decoder = decoder
        self.waveform_dir = waveform_dir
        self._id_counter = itertools.count(1)

    def import_paths(self, paths: Iterable[Path]) -> ImportResult:
        assets: List[Asset] = []
        thumbnails: List[np.ndarray] = []

        for path in paths:
            asset_type = self._asset_type(path)
            if asset_type is None:
                continue
            asset_id = self._generate_id(asset_type)
            asset = Asset(id=asset_id, path=str(path), type=asset_type, metadata={})
            self.project.add_asset(asset)
            assets.append(asset)

            thumbnail = self._create_thumbnail(asset)
            thumbnails.append(thumbnail)

            if asset_type == "audio":
                self._generate_waveform(asset)

        return ImportResult(assets=assets, thumbnails=thumbnails)

    def _asset_type(self, path: Path) -> str | None:
        suffix = path.suffix.lower()
        if suffix in VIDEO_EXT:
            return "video"
        if suffix in AUDIO_EXT:
            return "audio"
        return None

    def _generate_id(self, asset_type: str) -> str:
        prefix = "v" if asset_type == "video" else "a"
        return f"{prefix}{next(self._id_counter)}"

    def _create_thumbnail(self, asset: Asset) -> np.ndarray:
        try:
            frame = self.decoder.video_frame_at(asset.id, Path(asset.path), 0.0)
            image = frame.image
        except Exception:
            image = np.zeros((180, 320, 3), dtype=np.uint8)
        return image

    def _generate_waveform(self, asset: Asset) -> None:
        try:
            audio = self.decoder.audio_segment(asset.id, Path(asset.path), 0.0, 5.0)
            waveform = compute_waveform(audio.samples)
            target = self.waveform_dir / f"{asset.id}.waveform"
            target.parent.mkdir(parents=True, exist_ok=True)
            save_waveform(target, waveform)
        except Exception:
            pass
