"""Current CS2 crosshair settings and share-code import."""
from dataclasses import dataclass
from math import floor

STYLES = (
    "动态十字", "动态圆形", "经典动态十字", "静态圆形", "静态十字",
    "十字（射击反馈）", "仅中心点", "动态象限", "静态方形", "静态象限",
)
LENGTH_STYLES = (0, 2, 4, 5, 7)
GAP_STYLES = (0, 2, 3, 4, 5, 7, 8, 9)
SPREAD_STYLES = (0, 1, 7)
ANIMATED_STYLES = (*SPREAD_STYLES, 2, 5)
ALPHABET = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789"
RGBA = tuple[int, int, int, int]


@dataclass(frozen=True)
class Crosshair:
    style: int = 4
    length: int = 8
    gap: int = 4
    thickness: int = 2
    dot: bool = True
    t_style: bool = False
    color: RGBA = (231, 253, 139, 255)
    outline_mode: int = 1
    outline_color: RGBA = (0, 0, 0, 255)
    reference_height: int = 1080
    spread_limit: int = 255
    split_distance: int = 3
    inner_alpha: float = 0
    outer_alpha: float = 1
    split_ratio: float = 1
    follow_recoil: bool = False
    scope_scale: float = 1
    scope_color: bool = False

    def dimensions(self, height_px: float) -> tuple[int, int, int]:
        scale = height_px / self.reference_height
        gap = self.gap if self.style == 2 else max(0, self.gap)
        signed_gap = floor(abs(gap) * scale + .5) * (-1 if gap < 0 else 1)
        return floor(self.length * scale + .5), signed_gap, max(1, floor(self.thickness * scale + .5))


def decode_share_code(code: str) -> Crosshair:
    """Decode the modern CS container using its documented cs2-v1 byte layout."""
    code = code.strip()
    if code.startswith("CSGO-"):
        raise ValueError("这是旧版 CSGO- 分享码。请在当前 CS2 中重新复制。")
    if len(code) != 46 or not code.startswith("CS") or any(c not in ALPHABET for c in code[2:]):
        raise ValueError("请粘贴完整的新版 CS2 准星分享码（CS 开头，共 46 个字符）。")
    value = 0
    for character in reversed(code[2:]):
        value = value * len(ALPHABET) + ALPHABET.index(character)
    if value.bit_length() > 256:
        raise ValueError("准星分享码无效。")
    data = value.to_bytes(32, "big")
    if data[0] != sum(data[1:]) % 256:
        raise ValueError("准星分享码校验失败，请重新从游戏复制。")
    if data[1] != 1:
        raise ValueError("当前软件不支持此准星分享码版本。")
    flags = data[4]
    style = flags & 31
    thickness, outline_mode = data[13] & 63, data[13] >> 6
    if style >= len(STYLES) or outline_mode > 2:
        raise ValueError("分享码中的准星样式或描边模式无效。")
    split = int.from_bytes(data[18:22], "little")
    return Crosshair(
        style=style, length=data[16], gap=max(-3840, min(3840, int.from_bytes(data[14:16], "little", signed=True))),
        thickness=min(32, thickness), dot=bool(flags & 64), t_style=bool(flags & 128),
        color=tuple(data[5:9]), outline_mode=outline_mode, outline_color=tuple(data[9:13]),
        reference_height=max(240, int.from_bytes(data[2:4], "little")), spread_limit=data[17],
        split_distance=split & 127, inner_alpha=min(100, (split >> 7) & 127) / 100,
        outer_alpha=min(100, 30 + ((split >> 14) & 127)) / 100, split_ratio=min(100, (split >> 21) & 127) / 100,
        follow_recoil=bool(flags & 32), scope_scale=min(200, 10 + data[22]) / 100,
        scope_color=bool(split & (1 << 28)),
    )
