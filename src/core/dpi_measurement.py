"""Estimate effective horizontal DPI from Raw Input over a measured distance."""
from dataclasses import dataclass

from core.cs2_math import positive

MIN_DPI = 100
MAX_DPI = 64000


@dataclass
class DpiMeasurement:
    distance_cm: float
    net_x: int = 0
    travel_x: int = 0
    travel_y: int = 0

    def add(self, dx: int, dy: int) -> None:
        self.net_x += dx
        self.travel_x += abs(dx)
        self.travel_y += abs(dy)

    def estimate(self) -> int:
        counts = abs(self.net_x)
        if not self.travel_x:
            raise ValueError("没有收到水平移动。请移动鼠标后重试。")
        if self.travel_y > .20 * counts or counts < .80 * self.travel_x:
            raise ValueError("这次移动偏离水平或折返过多。请沿尺子直线滑动一次。")
        dpi = round(counts * 2.54 / positive(self.distance_cm))
        if not MIN_DPI <= dpi <= MAX_DPI:
            raise ValueError("检测值超出 100–64000 DPI。请核对距离并重新测量。")
        return dpi
