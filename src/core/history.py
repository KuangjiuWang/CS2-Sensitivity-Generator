"""Versioned local records with atomic updates."""
from dataclasses import asdict, fields
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QLockFile

from core.telemetry import ClickStats, FlickStats, TrackingStats


def flick_report(stats: FlickStats | None) -> dict | None:
    if stats is None:
        return None
    return {
        "method": "scenario" if isinstance(stats, ClickStats) else "click", "attempts": stats.attempts, "hits": stats.hits,
        **({"points": stats.points, "elapsed": stats.elapsed} if isinstance(stats, ClickStats) else {}),
        "mean_latency": stats.mean_latency if stats.hits else None,
        "mean_overshoot": stats.mean_overshoot if stats.completed_overshoots else None,
        "timings": stats.timings(),
        "sectors": [
            {item.name: getattr(sector, item.name) for item in fields(sector) if item.name != "traces"}
            for sector in stats.sectors
        ],
    }


def track_report(stats: TrackingStats | None) -> dict | None:
    if stats is None:
        return None
    return {**asdict(stats), "accuracy": stats.accuracy, "centering": stats.centering, "lag_rate": stats.lag_rate,
            "lead_rate": stats.lead_rate, "timings": stats.timings()}


def record(kind: str, settings: dict, flick: FlickStats | None, tracking: TrackingStats | None,
           *, name: str = "", score: float | None = None, conclusion: str = "", input_mode: str = "") -> dict:
    return {"kind": kind, "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "settings": settings, "flick": flick_report(flick), "tracking": track_report(tracking),
            "name": name, "score": score, "conclusion": conclusion,
            "input_mode": flick.input_mode if isinstance(flick, ClickStats) else input_mode}


class HistoryStore:
    def __init__(self, path: Path):
        self.path = path
        self.settings = {}
        self.records = []
        self.error = ""
        self.reload()

    def _read(self) -> tuple[dict, list]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}, []
        if (not isinstance(data, dict) or data.get("version") != 1
                or not isinstance(data.get("settings"), dict) or not isinstance(data.get("records"), list)):
            raise ValueError("无法识别本地历史文件格式")
        return data["settings"], data["records"]

    def reload(self) -> None:
        try:
            self.settings, self.records = self._read()
        except (OSError, ValueError) as error:
            self.error = str(error)
        else:
            self.error = ""

    def save(self, settings: dict) -> None:
        if settings != self.settings:
            self._update(settings)

    def append(self, *records: dict, settings: dict) -> None:
        self._update(settings, records)

    def clear(self) -> None:
        self._update(clear=True)

    def _update(self, settings: dict | None = None, additions: tuple = (), *, clear=False) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(self.path.with_name(self.path.name + ".lock")))
        if not lock.tryLock(500):
            raise OSError("暂时无法锁定历史文件，请稍后重试。")
        try:
            try:
                saved_settings, records = self._read()
            except ValueError as error:
                if not clear:
                    raise OSError(str(error)) from error
                saved_settings, records = self.settings, []
            self._write(saved_settings if settings is None else settings,
                        [] if clear else [*records, *additions])
        finally:
            lock.unlock()

    def _write(self, settings: dict, records: list) -> None:
        temp_path = self.path.parent / f".{uuid4().hex}.tmp"
        stream = temp_path.open("x", encoding="utf-8")
        try:
            with stream:
                json.dump({"version": 1, "settings": settings, "records": records}, stream, ensure_ascii=False)
            temp_path.replace(self.path)
        finally:
            temp_path.unlink(missing_ok=True)
        self.settings, self.records = settings, records
        self.error = ""
