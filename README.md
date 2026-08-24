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
extension. The repo's `.vscode/settings.json` maps `schedules/*.yaml` to
`schema/schedule.schema.json` and `holidays/*.yaml` to
`schema/holidays.schema.json`, so you get key autocomplete and inline validation
as you type.

## Usage

```sh
uv run python -m class_schedule_ical            # generate output/calendar.ics
uv run python -m class_schedule_ical --check    # validate only, write nothing
uv run python -m class_schedule_ical --preview  # print the schedule to the terminal
```

(Or `uv run class-schedule-ical` once the console script is installed.)

Validation failures are hard errors with a non-zero exit code.

## Web preview

A small Flask server (`server.py`) parses `output/calendar.ics` with `icalendar`,
expands the weekly recurrences with `dateutil.rrule`, and renders a browser UI:

```sh
uv run python server.py                # then open http://127.0.0.1:8000
uv run python server.py --port 9000    # or a different port
```

- Left column: a scrollable list of weeks (Monday–Friday).
- Right: the selected week as a Mon–Fri grid, with holidays/breaks already
  excluded.

## Directory layout

```
config.yaml                  # calendar name + timezone
schedules/                   # one YAML file per schedule (e.g. per term)
holidays/                    # one YAML file per holiday set (e.g. per school year)
schema/schedule.schema.json  # JSON Schema for schedules
schema/holidays.schema.json  # JSON Schema for holidays
output/calendar.ics          # generated (gitignored)
```

## Schedule format

Each file in `schedules/` describes one time period. When the schedule changes,
add a **new** file with a new date range (ranges must not overlap).

```yaml
start: 2026-08-17               # first school day (inclusive)
end: 2027-01-29                 # last school day (inclusive)

times:                          # every weekday Mon-Fri appears in exactly one section
  - weekdays: [monday, tuesday, wednesday, thursday]
    slots:
      - { start: "08:00", end: "09:30" }
      - { start: "09:55", end: "10:40" }
      - { start: "10:45", end: "12:15" }
  - weekdays: [friday]          # Friday has a different timetable
    slots:
      - { start: "09:55", end: "10:40" }
      - { start: "10:45", end: "12:15" }
      - { start: "12:55", end: "14:25" }

days:                           # classes map to time slots by position (1:1)
  monday:
    - { subject: Enr }
    - { subject: Dalton }
    - { subject: Musik, room: "A301" }
    - { subject: Deutsch, room: "A309" }
  # ... tuesday, wednesday, thursday ...
  friday:
    - { subject: Mathe, room: "A309" }
    - { subject: Dalton }
    - { subject: Sport, room: "TH1" }
    - { subject: Enrichment }
```

### Conventions

- **`subject`** (required) becomes the event title; **`room`** (optional) becomes
  the location.
- **Free periods / no room**: leave `room` empty (or omit it), e.g.
  `- { subject: Dalton }`. The event appears with no location.
- **Breaks between slots are silent** — only the slots themselves become events.
  A gap between `09:30` and `09:55` produces no calendar entry.
- Times are 24h `HH:MM`; slots must not overlap within a section.

## Holidays

Non-school days (breaks, public holidays, study days) live in `holidays/*.yaml`,
separate from the schedules. They apply to every schedule, filtered to each
schedule's date range:

```yaml
exceptions:
  - { start: "2026-10-06", end: "2026-10-06" }   # study day
  - { start: "2026-10-19", end: "2026-10-31" }   # autumn break
  - { start: "2026-12-23", end: "2027-01-02" }   # Christmas break
```

## Validation rules

Enforced on every run (and in-editor via the schema):

- `end >= start`; valid dates and `HH:MM` times.
- Every weekday **Monday–Friday appears exactly once** across `times` sections.
- `days` keys match the time sections; the number of classes per weekday equals
  the number of slots.
- Slots are ordered and non-overlapping (so classes never overlap).
- No two schedule files' date ranges overlap.
- Holiday date ranges are well-formed (`start <= end`).

## How events are generated

- One recurring `VEVENT` per (weekday × slot): `RRULE` weekly on that weekday,
  bounded by the schedule's end date.
- `holidays/` date ranges become `EXDATE` entries (filtered to each schedule's
  date range), so breaks, holidays and study days are skipped.
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
