"""Offline player sensitivity presets, independent of appearance."""
from dataclasses import dataclass

from core.cs2_math import edpi, positive
from core.player_source import PlayerSource


@dataclass(frozen=True)
class SensitivityPreset(PlayerSource):
    dpi: int
    sensitivity: float

    @property
    def effective_dpi(self) -> float:
        return edpi(self.dpi, self.sensitivity)

    def sensitivity_at(self, dpi: int) -> float:
        return round(self.effective_dpi / positive(dpi), 3)


SENSITIVITY_PRESETS = (
    SensitivityPreset("donk", "donk", "2026-11-15", 800, 1.25),
    SensitivityPreset("m0NESY", "m0nesy", "2026-11-19", 400, 2.3),
    SensitivityPreset("ZywOo", "zywoo", "2026-11-14", 400, 1.9),
    SensitivityPreset("s1mple", "s1mple", "2026-10-31", 400, 3.09),
    SensitivityPreset("ropz", "ropz", "2026-11-12", 400, 1.77),
    SensitivityPreset("NiKo", "niko", "2026-11-15", 800, .8),
    SensitivityPreset("flameZ", "flamez", "2026-11-12", 400, 3),
    SensitivityPreset("Twistzz", "twistzz", "2026-11-15", 400, 1.59),
    SensitivityPreset("coldzera", "coldzera", "2026-04-25", 800, 1.10),
    SensitivityPreset("GeT_RiGhT", "get_right", "2026-08-21", 400, 3),
    SensitivityPreset("f0rest", "f0rest", "2026-10-25", 400, 3.5),
    SensitivityPreset("olofmeister", "olofmeister", "2026-06-19", 800, 1.25),
    SensitivityPreset("device", "dev1ce", "2026-11-17", 800, .95),
    SensitivityPreset("NEO", "neo", "2026-07-19", 800, 1.05),
)
