"""Data model and parsing for school schedules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Any

import yaml


class _NoDatesSafeLoader(yaml.SafeLoader):
    """SafeLoader that keeps ISO dates/times as strings instead of auto-converting."""


_NoDatesSafeLoader.yaml_implicit_resolvers = {
    key: [r for r in resolvers if r[0] != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


WEEKDAYS: tuple[str, ...] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
)

# RFC 5545 BYDAY tokens for each school day.
WEEKDAY_TO_RFC: dict[str, str] = {
    "monday": "MO",
    "tuesday": "TU",
    "wednesday": "WE",
    "thursday": "TH",
    "friday": "FR",
}

# Python weekday() (Mon=0 .. Sun=6) -> RFC BYDAY token.
PY_WEEKDAY_TO_RFC: dict[int, str] = {
    0: "MO",
    1: "TU",
    2: "WE",
    3: "TH",
    4: "FR",
}

DEFAULT_NAME = "School Schedule"
DEFAULT_TIMEZONE = "Europe/Berlin"


@dataclass(frozen=True)
class Slot:
    start: time
    end: time


@dataclass(frozen=True)
class TimeSection:
    weekdays: tuple[str, ...]
    slots: tuple[Slot, ...]


@dataclass(frozen=True)
class ClassBlock:
    subject: str
    room: str | None = None


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date


@dataclass(frozen=True)
class Schedule:
    filename: str  # file stem, used in UIDs
    start: date
    end: date
    times: tuple[TimeSection, ...]
    days: dict[str, tuple[ClassBlock, ...]]


@dataclass(frozen=True)
class Holidays:
    filename: str
    exceptions: tuple[DateRange, ...]


@dataclass(frozen=True)
class Config:
    name: str = DEFAULT_NAME
    timezone: str = DEFAULT_TIMEZONE


def load_yaml(path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.load(fh, Loader=_NoDatesSafeLoader)
    if not isinstance(data, dict):
        raise ValueError(f"expected a mapping at the top level, got {type(data).__name__}")
    return data


def parse_config(data: dict[str, Any]) -> Config:
    return Config(
        name=str(data.get("name", DEFAULT_NAME)),
        timezone=str(data.get("timezone", DEFAULT_TIMEZONE)),
    )


def parse_schedule(data: dict[str, Any], filename: str) -> Schedule:
    times = tuple(
        TimeSection(
            weekdays=tuple(raw["weekdays"]),
            slots=tuple(
                Slot(start=time.fromisoformat(s["start"]), end=time.fromisoformat(s["end"]))
                for s in raw["slots"]
            ),
        )
        for raw in data["times"]
    )
    days = {
        weekday: tuple(
            ClassBlock(subject=c["subject"], room=c.get("room"))
            for c in classes
        )
        for weekday, classes in data["days"].items()
    }
    return Schedule(
        filename=filename,
        start=date.fromisoformat(data["start"]),
        end=date.fromisoformat(data["end"]),
        times=times,
        days=days,
    )


def parse_holidays(data: dict[str, Any], filename: str) -> Holidays:
    exceptions = tuple(
        DateRange(
            start=date.fromisoformat(r["start"]),
            end=date.fromisoformat(r["end"]),
        )
        for r in data.get("exceptions", [])
    )
    return Holidays(filename=filename, exceptions=exceptions)


def slots_for_weekday(schedule: Schedule, weekday: str) -> list[Slot]:
    """Return the time slots that apply to ``weekday`` (empty if none)."""
    for section in schedule.times:
        if weekday in section.weekdays:
            return list(section.slots)
    return []
