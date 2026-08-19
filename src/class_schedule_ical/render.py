"""Build the combined VCALENDAR from validated schedules."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, Timezone, vRecur

from .model import PY_WEEKDAY_TO_RFC, WEEKDAY_TO_RFC, Config, Schedule, slots_for_weekday

PRODID = "-//class-schedule-ical//EN"
UID_DOMAIN = "class-schedule-ical"


def build_calendar(config: Config, schedules: list[Schedule]) -> Calendar:
    tz = ZoneInfo(config.timezone)

    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add("x-wr-calname", config.name)
    cal.add_component(Timezone.from_tzinfo(tz))

    for schedule in schedules:
        _add_schedule(cal, schedule, tz)

    return cal


def _add_schedule(cal: Calendar, schedule: Schedule, tz) -> None:
    for weekday, classes in schedule.days.items():
        slots = slots_for_weekday(schedule, weekday)
        rfc_day = WEEKDAY_TO_RFC[weekday]
        for idx, (cls, slot) in enumerate(zip(classes, slots)):
            ev = Event()
            ev.add("uid", f"{schedule.filename}-{weekday}-{idx}@{UID_DOMAIN}")
            ev.add("summary", cls.subject)
            if cls.room:
                ev.add("location", cls.room)

            dtstart, dtend = _first_occurrence(schedule.start, weekday, slot, tz)
            ev.add("dtstart", dtstart)
            ev.add("dtend", dtend)

            until = _rrule_until(schedule.end, tz)
            ev.add("rrule", vRecur.from_ical(f"FREQ=WEEKLY;BYDAY={rfc_day};UNTIL={until}"))

            for exc in _exception_dates(schedule, weekday, slot.start, tz):
                ev.add("exdate", exc)

            cal.add_component(ev)


RFC_TO_PY_WEEKDAY = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4}


def _first_occurrence(start: date, weekday: str, slot, tz):
    """Return (DTSTART, DTEND) for the first ``weekday`` on or after ``start``."""
    target = RFC_TO_PY_WEEKDAY[WEEKDAY_TO_RFC[weekday]]
    d = start
    while d.weekday() != target:
        d += timedelta(days=1)
    return (
        datetime.combine(d, slot.start, tzinfo=tz),
        datetime.combine(d, slot.end, tzinfo=tz),
    )


def _rrule_until(end: date, tz) -> str:
    """RFC 5545 requires UNTIL in UTC when DTSTART carries a TZID."""
    end_of_day = datetime.combine(end, time(23, 59, 59), tzinfo=tz)
    return end_of_day.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _exception_dates(schedule: Schedule, weekday: str, start_time: time, tz):
    """Yield EXDATE datetimes for exception days that fall on ``weekday``."""
    rfc_day = WEEKDAY_TO_RFC[weekday]
    for r in schedule.exceptions:
        d = r.start
        while d <= r.end:
            if PY_WEEKDAY_TO_RFC.get(d.weekday()) == rfc_day:
                yield datetime.combine(d, start_time, tzinfo=tz)
            d += timedelta(days=1)
