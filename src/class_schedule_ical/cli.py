"""Command-line interface for the schedule -> iCal generator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .model import load_yaml, parse_config, parse_holidays, parse_schedule
from .preview import format_preview
from .render import build_calendar
from .validate import (
    validate_against_schema,
    validate_holidays,
    validate_no_overlap,
    validate_schedule,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="class-schedule-ical",
        description="Generate an iCal calendar from YAML school schedules.",
    )
    parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    parser.add_argument("--input-dir", default="schedules", help="directory of schedule YAML files")
    parser.add_argument("--holidays-dir", default="holidays", help="directory of holiday YAML files")
    parser.add_argument("--output-dir", default="output", help="directory for the generated .ics")
    parser.add_argument("--output-file", default="calendar.ics", help="output filename")
    parser.add_argument("--schema", default="schema/schedule.schema.json", help="schedule JSON Schema path")
    parser.add_argument(
        "--holidays-schema", default="schema/holidays.schema.json", help="holidays JSON Schema path"
    )
    parser.add_argument(
        "--check", action="store_true", help="validate only, do not write output"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="print a human-readable schedule preview (no .ics written)",
    )
    args = parser.parse_args(argv)

    root = Path.cwd()
    config_path = root / args.config
    input_dir = root / args.input_dir
    holidays_dir = root / args.holidays_dir
    schema_path = root / args.schema
    holidays_schema_path = root / args.holidays_schema
    output_path = root / args.output_dir / args.output_file

    try:
        config = parse_config(load_yaml(config_path) if config_path.exists() else {})
    except Exception as exc:
        print(f"Error: cannot read config {config_path}: {exc}", file=sys.stderr)
        return 2

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        holidays_schema = json.loads(holidays_schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error: cannot read schema: {exc}", file=sys.stderr)
        return 2

    schedule_paths = sorted(input_dir.glob("*.yaml")) + sorted(input_dir.glob("*.yml"))
    if not schedule_paths:
        print(f"Error: no schedule files found in {input_dir}", file=sys.stderr)
        return 2

    errors: list[str] = []

    schedules = []
    for path in schedule_paths:
        try:
            raw = load_yaml(path)
            errors.extend(
                f"{path.name}: {e}" for e in validate_against_schema(raw, schema)
            )
            schedules.append(parse_schedule(raw, path.stem))
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    holidays = []
    if holidays_dir.exists():
        holiday_paths = sorted(holidays_dir.glob("*.yaml")) + sorted(holidays_dir.glob("*.yml"))
        for path in holiday_paths:
            try:
                raw = load_yaml(path)
                errors.extend(
                    f"{path.name}: {e}" for e in validate_against_schema(raw, holidays_schema)
                )
                holidays.append(parse_holidays(raw, path.stem))
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")

    exceptions = [r for h in holidays for r in h.exceptions]

    for schedule in schedules:
        errors.extend(validate_schedule(schedule))
    for h in holidays:
        errors.extend(validate_holidays(h))
    errors.extend(validate_no_overlap(schedules))

    if errors:
        for e in errors:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.preview:
        print(format_preview(schedules, exceptions))
        return 0

    if args.check:
        print(
            f"OK: {len(schedules)} schedule(s), "
            f"{len(exceptions)} holiday exception(s) valid"
        )
        return 0

    cal = build_calendar(config, schedules, exceptions)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(cal.to_ical())
    print(f"Wrote {output_path} ({len(schedules)} schedule(s), {_event_count(cal)} events)")
    return 0


def _event_count(cal) -> int:
    return sum(1 for c in cal.subcomponents if c.name == "VEVENT")


if __name__ == "__main__":
    sys.exit(main())
