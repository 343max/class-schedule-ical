"""Cross-field validation that JSON Schema cannot express."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from .model import WEEKDAYS, Holidays, Schedule, slots_for_weekday


def validate_against_schema(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate a schedule's raw YAML mapping against the JSON Schema."""
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    out = []
    for err in errors:
        path = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{path}: {err.message}")
    return out


def validate_schedule(schedule: Schedule) -> list[str]:
    errors: list[str] = []
    p = schedule.filename

    # Dates: end >= start.
    if schedule.end < schedule.start:
        errors.append(f"{p}: end ({schedule.end}) is before start ({schedule.start})")

    # Weekday coverage: each Mon-Fri appears exactly once across all time sections.
    seen: dict[str, int] = {}
    for i, section in enumerate(schedule.times):
        for wd in section.weekdays:
            if wd not in WEEKDAYS:
                errors.append(f"{p}: times[{i}] has invalid weekday {wd!r}")
            else:
                seen[wd] = seen.get(wd, 0) + 1
    for wd in WEEKDAYS:
        count = seen.get(wd, 0)
        if count == 0:
            errors.append(f"{p}: weekday {wd!r} is missing from `times` (must appear exactly once)")
        elif count > 1:
            errors.append(
                f"{p}: weekday {wd!r} is defined {count} times in `times` (must appear exactly once)"
            )

    # `days` keys must match the weekdays exactly.
    day_keys = set(schedule.days)
    for wd in WEEKDAYS:
        if wd not in day_keys:
            errors.append(f"{p}: `days` is missing weekday {wd!r}")
    for wd in sorted(day_keys - set(WEEKDAYS)):
        errors.append(f"{p}: `days` has unknown weekday {wd!r}")

    # Slot validity: start < end, sorted and non-overlapping within each section.
    for i, section in enumerate(schedule.times):
        prev_end = None
        for j, slot in enumerate(section.slots):
            if slot.start >= slot.end:
                errors.append(
                    f"{p}: times[{i}].slots[{j}] start {slot.start} is not before end {slot.end}"
                )
            if prev_end is not None and slot.start < prev_end:
                errors.append(
                    f"{p}: times[{i}].slots[{j}] overlaps the previous slot "
                    f"(starts {slot.start}, previous ends {prev_end})"
                )
            prev_end = slot.end

    # Slot count: classes per weekday must match slots for that weekday.
    for wd in WEEKDAYS:
        if wd not in schedule.days:
            continue
        classes = schedule.days[wd]
        slots = slots_for_weekday(schedule, wd)
        if len(classes) != len(slots):
            errors.append(
                f"{p}: {wd} has {len(classes)} classes but {len(slots)} time slots (must match)"
            )

    return errors


def validate_holidays(holidays: Holidays) -> list[str]:
    errors: list[str] = []
    for i, r in enumerate(holidays.exceptions):
        if r.end < r.start:
            errors.append(
                f"{holidays.filename}: exceptions[{i}] end ({r.end}) is before start ({r.start})"
            )
    return errors


def validate_no_overlap(schedules: list[Schedule]) -> list[str]:
    """Ensure no two schedule date ranges overlap (inclusive)."""
    errors: list[str] = []
    for a in range(len(schedules)):
        for b in range(a + 1, len(schedules)):
            s1, s2 = schedules[a], schedules[b]
            if s1.start <= s2.end and s2.start <= s1.end:
                errors.append(
                    f"schedule date ranges overlap: {s1.filename} ({s1.start}..{s1.end}) "
                    f"and {s2.filename} ({s2.start}..{s2.end})"
                )
    return errors
