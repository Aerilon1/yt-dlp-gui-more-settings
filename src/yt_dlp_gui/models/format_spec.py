from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FormatSpec:
    """Which format/quality to download, baked to a concrete yt-dlp argv at Add time."""

    mode: str = "manual"  # "manual" | "preset"
    preset_key: str = ""
    file_type: str = "video"  # "video" | "audio"
    container: str = "mp4"
    quality_mode: str = "best"  # "best" | "height_cap"
    max_height: int | None = None
    resolved_argv: list[str] = field(default_factory=list)

    def label(self) -> str:
        if self.mode == "preset":
            return self.preset_key
        if self.file_type == "audio":
            quality = "Best"  # extract-audio has no height concept
        else:
            quality = f"{self.max_height}p (max)" if self.quality_mode == "height_cap" and self.max_height else "Best"
        suffix = " (audio)" if self.file_type == "audio" else ""
        return f"Manual: {quality} {self.container}{suffix}"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "preset_key": self.preset_key,
            "file_type": self.file_type,
            "container": self.container,
            "quality_mode": self.quality_mode,
            "max_height": self.max_height,
            "resolved_argv": list(self.resolved_argv),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FormatSpec":
        return cls(
            mode=data.get("mode", "manual"),
            preset_key=data.get("preset_key", ""),
            file_type=data.get("file_type", "video"),
            container=data.get("container", "mp4"),
            quality_mode=data.get("quality_mode", "best"),
            max_height=data.get("max_height"),
            resolved_argv=list(data.get("resolved_argv") or []),
        )
