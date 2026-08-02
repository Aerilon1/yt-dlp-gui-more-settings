from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubtitleSpec:
    """
    Which subtitles to fetch, baked onto a DownloadItem at Add/creation time from that
    item's own URL's scan result. Never shared window-level state -- that was the root
    cause of the pre-rewrite cross-item contamination bug (scanning video B would silently
    change which languages video A's retry requested).
    """

    mode: str = "none"  # "none" | "all_tracks" | "all" | "lang" | "auto_lang"
    lang: str = ""
    langs: list[str] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return self.mode != "none"

    def to_dict(self) -> dict:
        return {"mode": self.mode, "lang": self.lang, "langs": list(self.langs)}

    @classmethod
    def from_dict(cls, data: dict) -> "SubtitleSpec":
        return cls(
            mode=data.get("mode", "none"),
            lang=data.get("lang", ""),
            langs=list(data.get("langs") or []),
        )

    @classmethod
    def none(cls) -> "SubtitleSpec":
        return cls()
