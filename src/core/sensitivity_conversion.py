"""Match PC mouse hip-fire by horizontal turn distance at the same DPI."""
from math import floor, log10

from core.cs2_math import M_YAW, positive

PUBG_FOV_MIN = 80
PUBG_FOV_MAX = 103
PUBG_FOV_DEFAULT = 90


def menu_value(value: float, minimum: float, maximum: float, decimals: int) -> float | None:
    if not minimum <= value <= maximum:
        return None
    scale = 10 ** decimals
    return floor(value * scale + 0.5) / scale


def hipfire_values(cs2_sensitivity: float, pubg_fov: int = PUBG_FOV_DEFAULT) -> dict[str, float | None]:
    if not PUBG_FOV_MIN <= pubg_fov <= PUBG_FOV_MAX:
        raise ValueError("PUBG FPP FOV must be between 80 and 103 degrees")
    yaw = positive(cs2_sensitivity) * M_YAW
    battlefield = (yaw - 0.00231498) / 0.00173623
    pubg = 50 * log10(yaw / (0.00005555 * pubg_fov))
    return {
        "valorant": menu_value(yaw / 0.07, .01, 10, 3),
        "battlefield": menu_value(battlefield, 0, 200, 0),
        "pubg": menu_value(pubg, 0, 100, 0),
        "apex": menu_value(cs2_sensitivity, .2, 20, 2),
    }
