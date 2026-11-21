"""Offline player crosshair presets, independent of sensitivity."""
from dataclasses import dataclass
from math import ceil, trunc

from core.crosshair import Crosshair, RGBA
from core.player_source import PlayerSource


@dataclass(frozen=True)
class CrosshairPreset(PlayerSource):
    crosshair: Crosshair
    legacy: bool = False


def static_cross(length: int, thickness: int, gap: int, height: int, color: RGBA,
                 *, outline_mode: int = 0, **options) -> Crosshair:
    return Crosshair(length=length, thickness=thickness, gap=gap, reference_height=height,
                     color=color, dot=False, outline_mode=outline_mode, **options)


def legacy_static(size: float, width: float, gap: float, height: int, color: RGBA, **options) -> Crosshair:
    """Approximate classic static geometry at the player's published render height."""
    scale = height / 480
    thickness = max(1, round(width * scale))
    pixel_gap = max(0, trunc(4 + gap) + ceil(thickness / 2))
    return static_cross(round(size * scale), thickness, pixel_gap, height, color, **options)


GREEN = (0, 255, 0, 255)
YELLOW = (255, 255, 0, 255)
CYAN = (0, 255, 255, 255)

CROSSHAIR_PRESETS = (
    CrosshairPreset("donk", "donk", "2026-11-15",
                    static_cross(2, 2, 1, 960, GREEN, spread_limit=227, inner_alpha=.10)),
    CrosshairPreset("m0NESY", "m0nesy", "2026-11-19",
                    static_cross(4, 1, 2, 960, YELLOW, spread_limit=227)),
    CrosshairPreset("ZywOo", "zywoo", "2026-11-14",
                    static_cross(3, 2, 2, 960, (0, 255, 223, 255), spread_limit=226)),
    CrosshairPreset("s1mple", "s1mple", "2026-10-31",
                    static_cross(2, 2, 1, 960, YELLOW, spread_limit=227,
                              split_distance=7, inner_alpha=1, outer_alpha=.50, split_ratio=.30)),
    CrosshairPreset("ropz", "ropz", "2026-11-12",
                    static_cross(4, 1, 2, 1080, GREEN)),
    CrosshairPreset("NiKo", "niko", "2026-11-15",
                    static_cross(3, 1, 1, 960, (0, 255, 145, 255), spread_limit=228)),
    CrosshairPreset("flameZ", "flamez", "2026-11-12",
                    Crosshair(
        style=5, length=3, thickness=1, gap=2, reference_height=960, color=(0, 229, 255, 255),
        dot=True, outline_mode=0, spread_limit=227, split_distance=6,
        inner_alpha=1, outer_alpha=.45, split_ratio=.30,
    )),
    CrosshairPreset("Twistzz", "twistzz", "2026-11-15",
                    static_cross(8, 3, 3, 1080, (0, 255, 135, 255))),
    CrosshairPreset("coldzera", "coldzera", "2026-04-25",
                    legacy_static(2, 0, -3, 960, YELLOW, outline_mode=1, inner_alpha=.10), legacy=True),
    CrosshairPreset("GeT_RiGhT", "get_right", "2026-08-21",
                    legacy_static(5, 1.1, -10, 1050, GREEN, outline_mode=1,
                               split_distance=7, inner_alpha=1, outer_alpha=.50, split_ratio=.30), legacy=True),
    CrosshairPreset("f0rest", "f0rest", "2026-10-25",
                    static_cross(2, 2, 3, 1080, (255, 255, 255, 252), outline_mode=1,
                              spread_limit=191, split_distance=7, inner_alpha=1,
                              outer_alpha=.35, split_ratio=.30)),
    CrosshairPreset("olofmeister", "olofmeister", "2026-06-19",
                    legacy_static(1, 0, -1, 1080, GREEN), legacy=True),
    CrosshairPreset("device", "dev1ce", "2026-11-17",
                    static_cross(2, 2, 1, 960, CYAN, spread_limit=227,
                              split_distance=8, inner_alpha=1, outer_alpha=.45, split_ratio=.30)),
    CrosshairPreset("NEO", "neo", "2026-07-19",
                    legacy_static(1.7, 0, -2.5, 1080, GREEN, split_distance=7,
                               inner_alpha=1, outer_alpha=.50), legacy=True),
)
