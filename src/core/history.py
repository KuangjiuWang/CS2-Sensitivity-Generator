"""Versioned local records with atomic updates."""
from dataclasses import asdict, fields
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from core.telemetry import FlickStats, TrackingStats


def flick_report(stats: FlickStats | None) -> dict | None:
    if stats is None:
        return None
    return {
        "attempts": stats.attempts, "hits": stats.hits,
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
           *, name: str = "", score: float | None = None, conclusion: str = "") -> dict:
    return {"kind": kind, "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "settings": settings, "flick": flick_report(flick), "tracking": track_report(tracking),
            "name": name, "score": score, "conclusion": conclusion}


class HistoryStore:
    def __init__(self, path: Path):
        self.path = path
        self.settings = {}
        self.records = []
        self.error = ""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("version") != 1
                    or not isinstance(data.get("settings"), dict) or not isinstance(data.get("records"), list)):
                raise ValueError("无法识别本地历史文件格式")
            self.settings = data["settings"]
            self.records = data["records"]
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            self.error = str(error)

    def save(self, settings: dict) -> None:
        if settings != self.settings:
            self._write(settings, self.records)

    def append(self, *records: dict, settings: dict) -> None:
        self._write(settings, [*self.records, *records])

    def clear(self) -> None:
        self._write(self.settings, [], recover=True)

    def _write(self, settings: dict, records: list[dict], *, recover: bool = False) -> None:
        if self.error and not recover:
            raise OSError(self.error)
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
