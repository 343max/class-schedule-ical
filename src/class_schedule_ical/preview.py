"""Human-readable schedule preview (terminal)."""

from __future__ import annotations

from .model import WEEKDAYS, Schedule, slots_for_weekday


def format_preview(schedules: list[Schedule]) -> str:
    max_subject = max(
        (len(c.subject) for s in schedules for classes in s.days.values() for c in classes),
        default=0,
    )

    out: list[str] = []
    for s in schedules:
        out.append(f"=== {s.filename}  ({s.start} – {s.end}) ===")
        for weekday in WEEKDAYS:
            classes = s.days.get(weekday, ())
            slots = slots_for_weekday(s, weekday)
            if not classes:
                continue
            out.append("")
            out.append(weekday.capitalize())
            for cls, slot in zip(classes, slots):
                room = cls.room or ""
                out.append(
                    f"  {slot.start:%H:%M}–{slot.end:%H:%M}   "
                    f"{cls.subject:<{max_subject}}  {room}"
                )
        if s.exceptions:
            out.append("")
            out.append("No school:")
            for r in s.exceptions:
                out.append(f"  {r.start} – {r.end}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
