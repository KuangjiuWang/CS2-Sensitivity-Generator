"""Attribution for offline ProSettings snapshots."""
from dataclasses import dataclass

SNAPSHOT_DATE = "2026-11-21"


@dataclass(frozen=True)
class PlayerSource:
    name: str
    slug: str
    updated: str

    @property
    def source_url(self) -> str:
        return f"https://prosettings.net/players/{self.slug}/"
