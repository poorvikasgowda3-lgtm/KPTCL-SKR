from __future__ import annotations

import re
from datetime import datetime
from typing import Any


TIME_PATTERN = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")
DURATION_PATTERN = re.compile(r"^\d{1,3}:[0-5]\d$")
DATE_PATTERNS = (re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"), re.compile(r"^\d{4}-\d{2}-\d{2}$"))


def _minutes(value: str) -> int:
    hours, minutes = (int(part) for part in value.split(":"))
    return hours * 60 + minutes


def calculated_duration(start: str, end: str, overnight: bool = False) -> int | None:
    if not TIME_PATTERN.fullmatch(start) or not TIME_PATTERN.fullmatch(end):
        return None
    start_minutes, end_minutes = _minutes(start), _minutes(end)
    if end_minutes < start_minutes:
        if not overnight:
            return None
        end_minutes += 24 * 60
    return end_minutes - start_minutes


def _duration_minutes(value: str) -> int | None:
    if not DURATION_PATTERN.fullmatch(value):
        return None
    return _minutes(value)


def validate_report(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(level: str, message: str) -> None:
        issues.append({"level": level, "message": message})

    report = data.get("report", {})
    required = {
        "Station name": report.get("station_name"),
        "Report date": report.get("date"),
        "Station peak load": report.get("peak_load"),
        "Peak load time": report.get("peak_load_time"),
        "AE(M) station signature": report.get("signature"),
    }
    for label, value in required.items():
        if not str(value or "").strip():
            add("error", f"Missing required value: {label}.")
    report_date = str(report.get("date", "")).strip()
    if report_date:
        date_is_valid = False
        for pattern, date_format in zip(DATE_PATTERNS, ("%d/%m/%Y", "%Y-%m-%d")):
            if pattern.fullmatch(report_date):
                try:
                    datetime.strptime(report_date, date_format)
                    date_is_valid = True
                except ValueError:
                    pass
        if not date_is_valid:
            add("error", "Report date must be a valid date in DD/MM/YYYY or YYYY-MM-DD format.")
    for label, value in (
        ("Peak load time", report.get("peak_load_time")),
    ):
        if value and not TIME_PATTERN.fullmatch(str(value).strip()):
            add("error", f"{label} must use 24-hour HH:MM format.")

    transformers = data.get("transformers", [])
    complete_transformer = False
    for index, transformer in enumerate(transformers, 1):
        fields = [str(transformer.get(key, "") or "").strip() for key in ("rating", "load", "time")]
        if not any(fields):
            continue
        if not all(fields):
            add("error", f"Transformer {index}: enter rating, load, and reading time, or remove the row.")
        else:
            complete_transformer = True
            if not TIME_PATTERN.fullmatch(fields[2]):
                add("error", f"Transformer {index}: reading time must use 24-hour HH:MM format.")
            for label, value in (("rating", fields[0]), ("load", fields[1])):
                try:
                    float(value)
                except ValueError:
                    add("warning", f"Transformer {index} {label} is not numeric; verify it.")
    if not complete_transformer:
        add("error", "Enter at least one complete transformer rating, load, and reading time.")

    for label, key in (
        ("Maximum voltage", ("max_high_voltage", "max_low_voltage")),
        ("Minimum voltage", ("min_high_voltage", "min_low_voltage")),
    ):
        values = [str(report.get(field, "") or "").strip() for field in key]
        if any(values) and not all(values):
            add("warning", f"{label}: enter both high-side and low-side values, or leave both blank.")
        for value in values:
            if value:
                try:
                    float(value)
                except ValueError:
                    add("warning", f"{label} contains a non-numeric value ({value}); verify the notebook.")
    try:
        max_high = float(str(report.get("max_high_voltage", "")).strip())
        min_high = float(str(report.get("min_high_voltage", "")).strip())
        if max_high < min_high:
            add("warning", "Maximum high-side voltage is below the minimum value; verify the readings.")
    except (TypeError, ValueError):
        pass
    try:
        max_low = float(str(report.get("max_low_voltage", "")).strip())
        min_low = float(str(report.get("min_low_voltage", "")).strip())
        if max_low < min_low:
            add("warning", "Maximum low-side voltage is below the minimum value; verify the readings.")
    except (TypeError, ValueError):
        pass

    for voltage in ("66", "11"):
        rows = data.get(f"interruptions_{voltage}", [])
        is_nil = bool(data.get(f"nil_{voltage}", False))
        if is_nil:
            continue
        if not rows:
            add("error", f"Mark {voltage}KV interruptions as Nil or add at least one entry.")
        for index, row in enumerate(rows, 1):
            prefix = f"{voltage}KV interruption {index}"
            feeder = str(row.get("feeder", "")).strip()
            start = str(row.get("start", "")).strip()
            end = str(row.get("end", "")).strip()
            duration = str(row.get("reported_duration", "")).strip()
            relay = str(row.get("relay", "")).strip()
            for label, value in (
                ("feeder number", feeder), ("start time", start), ("end time", end),
                ("reported duration", duration), ("protection/relay type", relay),
            ):
                if not value:
                    add("error", f"{prefix}: enter the {label}.")
            for label, value in (("start time", start), ("end time", end)):
                if value and not TIME_PATTERN.fullmatch(value):
                    add("error", f"{prefix}: {label} must use 24-hour HH:MM format.")
            if duration and not DURATION_PATTERN.fullmatch(duration):
                add("error", f"{prefix}: duration must use HH:MM format, as reported in the notebook.")
            if TIME_PATTERN.fullmatch(start) and TIME_PATTERN.fullmatch(end):
                start_min, end_min = _minutes(start), _minutes(end)
                overnight = bool(row.get("overnight"))
                if end_min < start_min and not overnight:
                    add("error", f"{prefix}: end time is earlier than start time. Confirm overnight if applicable.")
                elif end_min < start_min:
                    end_min += 24 * 60
                reported_min = _duration_minutes(duration)
                if reported_min is not None:
                    elapsed = end_min - start_min
                    if reported_min != elapsed:
                        add(
                            "warning",
                            f"{prefix}: notebook duration {duration} differs from calculated elapsed "
                            f"{elapsed // 60:02d}:{elapsed % 60:02d}. Verify and retain or correct the reported value.",
                        )

    for field in data.get("uncertain_fields", []):
        add("warning", f"OCR marked this field uncertain: {field}. Check against the notebook.")

    for field in ("peak_load",):
        value = str(report.get(field, "") or "").strip()
        if value:
            try:
                float(value)
            except ValueError:
                add("warning", "Station peak load is not numeric; verify the notebook.")
    return issues
