"""Original low-contrast rooms rendered from the same view as the targets."""
from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPolygonF

from core.cs2_math import dot


@dataclass(frozen=True)
class Room:
    half_width: float
    depth: float
    height: float
    sky_top: str
    sky_bottom: str
    front: str
    left: str
    right: str
    floor: str
    detail: str = ""


ROOMS = {
    "linear": Room(1.55, 1.36, .40, "#040507", "#111017", "#2C2929", "#19191F", "#242125", "#16141E", "relief"),
    "micro": Room(.26, 1.55, .34, "#53678B", "#90A6BE", "#151C24", "#262D34", "#222A33", "#272F39"),
    "six": Room(1.75, 1.36, .43, "#050608", "#100F16", "#2C282A", "#201D24", "#241F24", "#17151F", "relief"),
    "wall": Room(2.05, 1.3, .51, "#7B9C91", "#C0A476", "#242B32", "#1B232B", "#252F3A", "#373C43"),
    "phase": Room(1.45, 1.26, .42, "#071A21", "#193F43", "#1B222B", "#171C27", "#202832", "#253143", "seams"),
    "moving": Room(.84, 1.35, .58, "#303337", "#3D4042", "#525353", "#393B3D", "#434546", "#4D5153", "ceiling"),
}


def clip_near(points, near=.06):
    """Clip a convex camera-space polygon before the perspective divide."""
    result = []
    previous = points[-1]
    for point in points:
        if (previous[2] >= near) != (point[2] >= near):
            t = (near - previous[2]) / (point[2] - previous[2])
            result.append((previous[0] + (point[0] - previous[0]) * t,
                           previous[1] + (point[1] - previous[1]) * t, near))
        if point[2] >= near:
            result.append(point)
        previous = point
    return result


def draw_room(painter, viewport, camera, sx: float, sy: float, room: Room) -> None:
    sky = QLinearGradient(0, viewport.top(), 0, viewport.bottom())
    sky.setColorAt(0, QColor(room.sky_top))
    sky.setColorAt(1, QColor(room.sky_bottom))
    painter.fillRect(viewport, sky)
    painter.setPen(Qt.PenStyle.NoPen)
    far = room.depth
    near = -max(.7, far / 2)
    x, top, bottom = room.half_width, -room.height, .48
    left_front = (-x, top, far), (-x, bottom, far)
    right_front = (x, top, far), (x, bottom, far)
    left_back = (-x, top, near), (-x, bottom, near)
    right_back = (x, top, near), (x, bottom, near)
    faces = [
        (room.front, (left_front[0], right_front[0], right_front[1], left_front[1])),
        (room.left, (left_back[0], left_front[0], left_front[1], left_back[1])),
        (room.right, (right_front[0], right_back[0], right_back[1], right_front[1])),
        (room.front, (right_back[0], left_back[0], left_back[1], right_back[1])),
        (room.floor, (left_front[1], right_front[1], right_back[1], left_back[1])),
    ]
    if room.detail == "relief":
        z = far - .015
        faces.extend((
            ("#201D25", ((-x, top, z), (-x * .67, bottom, z), (-x, bottom, z))),
            ("#18171D", ((x * .69, top, z), (x, top, z), (x, bottom, z),
                         (x * .88, bottom, z), (x * .88, 0, z), (x * .69, 0, z))),
        ))
    elif room.detail == "seams":
        z = far - .015
        for edge in (-x + .02, x - .045):
            faces.append(("#293052", ((edge, top, z), (edge + .025, top, z),
                                      (edge + .025, bottom, z), (edge, bottom, z))))
    elif room.detail == "ceiling":
        faces.append(("#25282C", (left_front[0], right_front[0], right_back[0], left_back[0])))
        z = far - .012
        faces.append(("#79545F", ((-.28, top, z), (.28, top, z),
                                  (.28, top + .013, z), (-.28, top + .013, z))))
    center = viewport.center()
    forward, right, down = camera.basis()
    for color, face in faces:
        points = [(dot(p, right), dot(p, down), dot(p, forward)) for p in face]
        clipped = clip_near(points)
        if len(clipped) >= 3:
            path = QPolygonF([QPointF(center.x() + sx * a / z, center.y() + sy * b / z)
                              for a, b, z in clipped])
            base = QColor(color)
            shading = QLinearGradient(0, viewport.top() + viewport.height() * .18, 0, viewport.bottom())
            shading.setColorAt(0, base.lighter(112))
            shading.setColorAt(1, base.darker(125))
            painter.setBrush(shading)
            painter.drawPolygon(path)
