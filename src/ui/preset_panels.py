"""Independent selectors for professional sensitivity and appearance presets."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.player_crosshairs import CROSSHAIR_PRESETS
from core.player_sensitivity import SENSITIVITY_PRESETS
from ui.crosshair import CrosshairPreview


def player_picker(name, presets):
    picker = QComboBox()
    picker.setAccessibleName(name)
    for preset in presets:
        picker.addItem(preset.name, preset)
    return picker


def source_label():
    label = QLabel()
    label.setOpenExternalLinks(True)
    label.setWordWrap(True)
    label.setObjectName("muted")
    return label


def source_text(preset):
    return (f'<a href="{preset.source_url}" style="color:#62DCE6">ProSettings</a>'
            f"  ·  {preset.updated}")


class PlayerSensitivityPanel(QWidget):
    apply_requested = Signal(object, bool)

    def __init__(self):
        super().__init__()
        self.dpi = 800
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        layout.addLayout(row)
        self.players = player_picker("灵敏度选手", SENSITIVITY_PRESETS)
        row.addWidget(self.players, 1)
        self.mode = QComboBox()
        self.mode.addItems(("保持我的 DPI", "用选手 DPI"))
        self.mode.setAccessibleName("灵敏度应用方式")
        row.addWidget(self.mode, 1)
        self.details = QLabel()
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        self.source = source_label()
        layout.addWidget(self.source)
        self.apply_button = QPushButton("应用灵敏度")
        self.apply_button.setObjectName("primary")
        self.apply_button.clicked.connect(self.apply_preset)
        layout.addWidget(self.apply_button)
        self.players.currentIndexChanged.connect(self.refresh)
        self.mode.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def set_dpi(self, dpi: int) -> None:
        if dpi != self.dpi:
            self.dpi = dpi
            self.refresh()

    def refresh(self) -> None:
        preset = self.players.currentData()
        reference = f"{preset.dpi} DPI × {preset.sensitivity:g}  ·  {preset.effective_dpi:g} eDPI"
        application = (f"按 {self.dpi} DPI 应用 {preset.sensitivity_at(self.dpi):.3f}"
                       if self.mode.currentIndex() == 0 else f"请把鼠标硬件设为 {preset.dpi} DPI")
        self.details.setText(f"{reference}\n{application}")
        self.source.setText(source_text(preset))

    def apply_preset(self) -> None:
        self.apply_requested.emit(self.players.currentData(), self.mode.currentIndex() == 0)


class PlayerCrosshairPanel(QWidget):
    apply_requested = Signal(object)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        layout.addLayout(row)
        self.players = player_picker("准星选手", CROSSHAIR_PRESETS)
        row.addWidget(self.players, 1)
        self.apply_button = QPushButton("应用准星")
        self.apply_button.setObjectName("primary")
        self.apply_button.clicked.connect(self.apply_preset)
        row.addWidget(self.apply_button)
        self.preview = CrosshairPreview(lambda: self.players.currentData().crosshair)
        self.preview.setMinimumHeight(48)
        layout.addWidget(self.preview)
        self.source = source_label()
        layout.addWidget(self.source)
        self.players.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def apply_preset(self) -> None:
        self.apply_requested.emit(self.players.currentData())

    def refresh(self) -> None:
        preset = self.players.currentData()
        note = "  ·  旧版准星近似换算" if preset.legacy else ""
        self.source.setText(source_text(preset) + note)
        self.preview.update()
