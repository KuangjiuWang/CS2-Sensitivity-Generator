"""Allowlist of current CS2 crosshair commands."""
from core.crosshair import Crosshair


def crosshair_cfg_text(settings: Crosshair) -> str:
    values = {
        "cl_crosshairstyle": settings.style,
        "cl_crosshair_length": settings.length,
        "cl_crosshair_gap": settings.gap,
        "cl_crosshair_thickness": settings.thickness,
        "cl_crosshairdot": int(settings.dot),
        "cl_crosshair_t": int(settings.t_style),
        "cl_crosshair_drawoutline": settings.outline_mode,
        "cl_crosshair_screen_height": settings.reference_height,
        "cl_crosshair_dynamic_spread_limit": settings.spread_limit,
        "cl_crosshair_dynamic_splitdist": settings.split_distance,
        "cl_crosshair_dynamic_splitalpha_innermod": settings.inner_alpha,
        "cl_crosshair_dynamic_splitalpha_outermod": settings.outer_alpha,
        "cl_crosshair_dynamic_maxdist_splitratio": settings.split_ratio,
        "cl_crosshair_recoil": int(settings.follow_recoil),
        "cl_ironsight_dot_scale": settings.scope_scale,
        "cl_ironsight_usecrosshaircolor": int(settings.scope_color),
    }
    for prefix, channels in (("cl_crosshaircolor", settings.color), ("cl_crosshairoutline", settings.outline_color)):
        values.update((f"{prefix}_{channel}", value) for channel, value in zip("rgba", channels))
    return "".join(f'{command} "{value:g}"\n' for command, value in values.items())
