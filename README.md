# class-schedule-ical

Generate a single `.ics` calendar from YAML school schedules, with a JSON Schema
for VSCode autocomplete and strict validation (no overlaps, every weekday defined
exactly once).

You write a school week as YAML, and the tool emits one `output/calendar.ics` you
can subscribe to from Google Calendar or Apple Calendar.

## Setup

```sh
uv sync
```

Requires [uv](https://docs.astral.sh/uv/). Python 3.12+.

### VSCode autocomplete

Install the [redhat.vscode-yaml](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)
extension. The repo's `.vscode/settings.json` already maps `schedules/*.yaml` to
`schema/schedule.schema.json`, so you get key autocomplete and inline validation
as you type.

## Usage

```sh
uv run python -m class_schedule_ical            # generate output/calendar.ics
uv run python -m class_schedule_ical --check    # validate only, write nothing
```

(Or `uv run class-schedule-ical` once the console script is installed.)

Validation failures are hard errors with a non-zero exit code.

## Directory layout

```
config.yaml                 # calendar name + timezone
schedules/                  # one YAML file per schedule (e.g. per term)
schema/schedule.schema.json # JSON Schema for autocomplete + validation
output/calendar.ics         # generated (gitignored)
```

## Schedule format

Each file in `schedules/` describes one time period. When the schedule changes,
add a **new** file with a new date range (ranges must not overlap).

```yaml
start: 2025-09-01               # first school day (inclusive)
end: 2026-01-30                 # last school day (inclusive)

times:                          # every weekday Mon-Fri appears in exactly one section
  - weekdays: [monday, tuesday, wednesday, thursday]
    slots:
      - { start: "08:00", end: "09:30" }
      - { start: "09:45", end: "11:15" }
      - { start: "11:30", end: "13:00" }
  - weekdays: [friday]          # Friday has a different timetable
    slots:
      - { start: "08:30", end: "10:00" }
      - { start: "10:15", end: "11:45" }
      - { start: "12:00", end: "13:00" }

days:                           # classes map to time slots by position (1:1)
  monday:
    - { subject: Mathematics, room: "101" }
    - { subject: English, room: "203" }
    - { subject: German, room: "105" }
  # ... tuesday, wednesday, thursday ...
  friday:
    - { subject: Art, room: "Art Room" }
    - { subject: German, room: "105" }
    - { subject: Physical Education, room: "Gym" }

exceptions:                     # optional full-day non-school ranges (inclusive)
  - { start: "2025-10-13", end: "2025-10-17" }   # autumn break
  - { start: "2025-12-22", end: "2026-01-02" }   # winter break
```

### Conventions

- **`subject`** (required) becomes the event title; **`room`** (optional) becomes
  the location.
- **Free periods**: use a placeholder subject and leave `room` empty, e.g.
  `- { subject: Free }`. The event appears with no location.
- **Breaks between slots are silent** — only the slots themselves become events.
  A gap between `09:30` and `09:45` produces no calendar entry.
- Times are 24h `HH:MM`; slots must not overlap within a section.

## Validation rules

Enforced on every run (and in-editor via the schema):

- `end >= start`; valid dates and `HH:MM` times.
- Every weekday **Monday–Friday appears exactly once** across `time` sections.
- `days` keys match the time sections; the number of classes per weekday equals
  the number of slots.
- Slots are ordered and non-overlapping (so classes never overlap).
- No two schedule files' date ranges overlap.
- Exceptions are well-formed; a warning is printed if one extends outside the
  schedule's date range.

## How events are generated

- One recurring `VEVENT` per (weekday × slot): `RRULE` weekly on that weekday,
  bounded by the schedule's end date.
- `exceptions` become `EXDATE` entries, so breaks and holidays are skipped.
- Events carry a timezone (`Europe/Berlin` by default, see `config.yaml`) with a
  `VTIMEZONE` component so times stay correct across DST.
- **Stable UIDs** (derived from the schedule filename) mean re-generating and
  re-importing/subscribing updates events instead of duplicating them. Deleting a
  schedule file removes its events on the next run.

## Subscribing

Host `output/calendar.ics` on your server and add its URL as a calendar
subscription in Google Calendar ("From URL") or Apple Calendar
("New Calendar Subscription"). Note that URL-based subscriptions refresh on the
provider's own schedule (which can lag by hours), so changes are not instant.
