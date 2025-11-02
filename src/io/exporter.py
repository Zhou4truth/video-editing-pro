"""Timeline export pipeline using ffmpeg."""

from __future__ import annotations

import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np
import soundfile as sf

from ..core.audio.mixer import AudioClipBuffer, mix_to_bus
from ..core.compositor import Compositor
from ..core.decoder import MediaDecoder
from ..core.project_model import Project


EXPORT_PRESETS = {
    "draft_720p": {
        "width": 1280,
        "height": 720,
        "crf": 28,
        "preset": "veryfast",
        "audio_bitrate": "128k",
    },
    "standard_1080p": {
        "width": 1920,
        "height": 1080,
        "crf": 23,
        "preset": "fast",
        "audio_bitrate": "192k",
    },
}


class Exporter:
    def __init__(self, project: Project, decoder: MediaDecoder, ffmpeg_path: Path) -> None:
        self.project = project
        self.decoder = decoder
        self.ffmpeg_path = ffmpeg_path

    def export(
        self,
        output_path: Path,
        preset: str,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_flag: Optional[Callable[[], bool]] = None,
    ) -> Path:
        if preset not in EXPORT_PRESETS:
            raise ValueError(f"Unknown preset {preset}")

        preset_opts = EXPORT_PRESETS[preset]
        fps = self.project.settings.fps
        duration = self.project.total_length_seconds()
        total_frames = max(int(np.ceil(duration * fps)), 1)
        width = preset_opts["width"]
        height = preset_opts["height"]

        compositor = Compositor(self.project, self.decoder)
        audio_bus = self._render_audio_bus()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            audio_path = temp_dir_path / "mix.wav"
            sf.write(str(audio_path), audio_bus, samplerate=48_000, subtype="PCM_16")

            command = self._build_ffmpeg_command(
                audio_path=audio_path,
                output_path=output_path,
                fps=fps,
                width=width,
                height=height,
                options=preset_opts,
            )

            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if process.stdin is None or process.stderr is None:
                raise RuntimeError("Failed to launch ffmpeg with proper pipes")

            state = {"render": 0.0, "encode": 0.0}
            logs: List[str] = []
            lock = threading.Lock()

            def _publish() -> None:
                if not progress_callback:
                    return
                with lock:
                    progress_callback(max(state["render"], state["encode"]))

            def _read_stderr() -> None:
                while True:
                    raw_line = process.stderr.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    logs.append(line)
                    progress = self._parse_encoder_progress(line, fps, total_frames)
                    if progress is not None:
                        with lock:
                            state["encode"] = max(state["encode"], progress)
                        _publish()

            reader = threading.Thread(target=_read_stderr, daemon=True)
            reader.start()

            try:
                for index in range(total_frames):
                    if cancel_flag and cancel_flag():
                        raise RuntimeError("Export cancelled")
                    seconds = index / fps
                    frame = compositor.render_frame(seconds)
                    resized = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
                    process.stdin.write(resized.tobytes())
                    with lock:
                        state["render"] = max(state["render"], (index + 1) / total_frames)
                    _publish()
            except Exception:
                try:
                    process.stdin.close()
                except Exception:
                    pass
                process.terminate()
                reader.join()
                process.wait()
                raise
            else:
                process.stdin.close()
                return_code = process.wait()
                reader.join()
                if return_code != 0:
                    tail = "\n".join(logs[-10:])
                    raise RuntimeError(f"ffmpeg failed (code {return_code}): {tail}")
                with lock:
                    state["encode"] = 1.0
                    state["render"] = 1.0
                _publish()

        if progress_callback:
            progress_callback(1.0)
        return output_path

    def _build_ffmpeg_command(
        self,
        audio_path: Path,
        output_path: Path,
        fps: int,
        width: int,
        height: int,
        options: Dict,
    ):
        return [
            str(self.ffmpeg_path),
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "-",
            "-i",
            str(audio_path),
            "-c:v",
            "libx264",
            "-preset",
            options["preset"],
            "-crf",
            str(options["crf"]),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-b:a",
            options["audio_bitrate"],
            str(output_path),
        ]

    @staticmethod
    def _parse_encoder_progress(line: str, fps: int, total_frames: int) -> Optional[float]:
        if "frame=" in line:
            try:
                frame_str = line.split("frame=")[1].split()[0]
                frame_index = int(frame_str)
                return min(frame_index / max(total_frames, 1), 1.0)
            except (ValueError, IndexError):
                pass
        if "time=" in line:
            try:
                time_str = line.split("time=")[1].split()[0]
                h, m, s = time_str.split(":")
                seconds = (int(h) * 3600) + (int(m) * 60) + float(s)
                frame_index = seconds * fps
                return min(frame_index / max(total_frames, 1), 1.0)
            except (ValueError, IndexError):
                pass
        return None

    def _render_audio_bus(self) -> np.ndarray:
        sample_rate = 48_000
        buffers = []

        for track in self.project.tracks:
            if track.type != "audio" or track.muted:
                continue
            for clip in track.clips:
                asset = next((a for a in self.project.assets if a.id == clip.asset), None)
                if asset is None:
                    continue
                try:
                    audio_buffer = self.decoder.audio_segment(
                        asset.id, Path(asset.path), clip.in_point, clip.duration()
                    )
                except Exception:
                    continue
                adjusted = AudioClipBuffer(
                    clip=clip,
                    samples=audio_buffer.samples,
                    sample_rate=audio_buffer.rate,
                    start_time=clip.start,
                )
                buffers.append(adjusted)

        if not buffers:
            return np.zeros((1, 2), dtype=np.float32)
        return mix_to_bus(buffers, sample_rate)
