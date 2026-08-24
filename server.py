"""Web server to preview the generated .ics calendar.

Parses output/calendar.ics with `icalendar`, expands the weekly recurrences with
`dateutil.rrule`, and serves a small UI: a scrollable week picker on the left and
the Monday-Friday schedule on the right.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
from pathlib import Path

import icalendar
from dateutil.rrule import rrulestr
from flask import Flask, jsonify, request

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Schedule preview</title>
<style>
  * { box-sizing: border-box; }
  body { display: flex; height: 100vh; margin: 0; font-family: -apple-system, system-ui, sans-serif; }
  #sidebar {
    width: 200px; flex: 0 0 200px; overflow-y: auto;
    border-right: 1px solid #ddd; background: #f7f7f8;
  }
  #sidebar h2 { font-size: 13px; margin: 12px; color: #555; }
  .week { padding: 9px 14px; cursor: pointer; border-bottom: 1px solid #ececec; font-size: 13px; }
  .week:hover { background: #e9e9ec; }
  .week.active { background: #cfe3ff; font-weight: 600; }
  #main { flex: 1; overflow-y: auto; padding: 20px; }
  #weekTitle { margin: 0 0 16px; font-size: 18px; }
  .grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
  .day { border: 1px solid #e2e2e2; border-radius: 8px; padding: 10px; min-height: 240px; background: #fff; }
  .day h3 { margin: 0 0 10px; text-align: center; font-size: 14px; color: #333; }
  .event { background: #eef2ff; border-radius: 6px; padding: 7px 9px; margin-bottom: 7px; }
  .event .time { color: #666; font-size: 11px; }
  .event .subject { font-weight: 600; font-size: 13px; }
  .event .room { color: #888; font-size: 12px; }
  .empty { color: #bbb; text-align: center; margin-top: 40px; font-size: 12px; }
</style>
</head>
<body>
  <div id="sidebar"><h2>Weeks</h2></div>
  <div id="main">
    <h1 id="weekTitle"></h1>
    <div class="grid" id="grid"></div>
  </div>
<script>
const DAYS = ['monday','tuesday','wednesday','thursday','friday'];
const sidebar = document.getElementById('sidebar');
const grid = document.getElementById('grid');
const weekTitle = document.getElementById('weekTitle');

async function loadWeeks() {
  const weeks = await (await fetch('/api/weeks')).json();
  if (!weeks.length) return;
  const today = new Date().toISOString().slice(0, 10);
  const current = weeks.find(w => w.start <= today && today <= w.end) || weeks[0];
  weeks.forEach(w => {
    const el = document.createElement('div');
    el.className = 'week';
    el.textContent = w.label;
    el.onclick = () => selectWeek(w, el);
    sidebar.appendChild(el);
  });
  selectWeek(current, sidebar.querySelectorAll('.week')[weeks.indexOf(current)]);
}

async function selectWeek(w, el) {
  document.querySelectorAll('.week').forEach(e => e.classList.remove('active'));
  el.classList.add('active');
  weekTitle.textContent = `Week of ${w.label}`;
  const events = await (await fetch(`/api/events?start=${w.start}&end=${w.end}`)).json();
  render(events);
}

function render(events) {
  grid.innerHTML = '';
  for (const day of DAYS) {
    const col = document.createElement('div');
    col.className = 'day';
    const h = document.createElement('h3');
    h.textContent = day[0].toUpperCase() + day.slice(1);
    col.appendChild(h);
    const evs = events.filter(e => e.day === day).sort((a, b) => a.start.localeCompare(b.start));
    if (!evs.length) {
      const empty = document.createElement('div');
      empty.className = 'empty';
      empty.textContent = 'no classes';
      col.appendChild(empty);
    }
    for (const e of evs) {
      const d = document.createElement('div');
      d.className = 'event';
      d.innerHTML = `<div class="time">${e.start} – ${e.end}</div>` +
                    `<div class="subject">${esc(e.summary)}</div>` +
                    (e.location ? `<div class="room">${esc(e.location)}</div>` : '');
      col.appendChild(d);
    }
    grid.appendChild(col);
  }
}

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

loadWeeks();
</script>
</body>
</html>
"""


def parse_events(ics_path: Path) -> list[dict]:
    cal = icalendar.Calendar.from_ical(ics_path.read_bytes())
    events = []
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue
        dtstart = comp.decoded("dtstart")
        dtend = comp.decoded("dtend")
        exdate = comp.get("exdate")
        exdates: set[date] = set()
        if exdate is not None:
            for item in exdate if isinstance(exdate, list) else [exdate]:
                for dt in item.dts:
                    exdates.add(dt.dt.date())
        events.append(
            {
                "summary": str(comp.get("summary", "")),
                "location": str(comp.get("location", "")),
                "dtstart": dtstart,
                "dtend": dtend,
                "rrule": comp.get("rrule"),
                "exdates": exdates,
            }
        )
    return events


def event_last_date(event: dict) -> date:
    rrule = event["rrule"]
    if rrule is not None:
        until = rrule.get("UNTIL")
        if until:
            return until[0].date()
    return event["dtstart"].date()


def compute_weeks(events: list[dict]) -> list[dict]:
    if not events:
        return []
    first = min(e["dtstart"].date() for e in events)
    last = max(event_last_date(e) for e in events)
    monday = first - timedelta(days=first.weekday())
    weeks = []
    d = monday
    while d <= last:
        friday = d + timedelta(days=4)
        weeks.append(
            {
                "start": d.isoformat(),
                "end": friday.isoformat(),
                "label": f"{d.day:02d}.{d.month:02d}. – {friday.day:02d}.{friday.month:02d}.{friday.year}",
            }
        )
        d += timedelta(days=7)
    return weeks


def events_in_range(events: list[dict], start: date, end: date) -> list[dict]:
    result = []
    for e in events:
        dtstart = e["dtstart"]
        tz = dtstart.tzinfo
        rrule = e["rrule"]
        if rrule is not None:
            rule = rrulestr(rrule.to_ical().decode("utf-8"), dtstart=dtstart)
            after = datetime.combine(start, time.min, tzinfo=tz)
            before = datetime.combine(end, time.max, tzinfo=tz)
            occurrences = rule.between(after, before, inc=True)
        else:
            occurrences = [dtstart] if start <= dtstart.date() <= end else []
        duration = e["dtend"] - e["dtstart"]
        for occ in occurrences:
            if occ.date() in e["exdates"]:
                continue
            result.append(
                {
                    "day": DAYS[occ.weekday()],
                    "date": occ.date().isoformat(),
                    "start": occ.strftime("%H:%M"),
                    "end": (occ + duration).strftime("%H:%M"),
                    "summary": e["summary"],
                    "location": e["location"],
                }
            )
    result.sort(key=lambda x: (x["date"], x["start"]))
    return result


def create_app(ics_path: Path) -> Flask:
    app = Flask(__name__)
    events = parse_events(ics_path)
    weeks = compute_weeks(events)

    @app.route("/")
    def index():
        return INDEX_HTML

    @app.route("/api/weeks")
    def api_weeks():
        return jsonify(weeks)

    @app.route("/api/events")
    def api_events():
        start = date.fromisoformat(request.args["start"])
        end = date.fromisoformat(request.args["end"])
        return jsonify(events_in_range(events, start, end))

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview the generated .ics calendar in a browser.")
    parser.add_argument("--ics", default="output/calendar.ics", help="path to the .ics file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    app = create_app(Path(args.ics))
    print(f"Serving {args.ics} on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
