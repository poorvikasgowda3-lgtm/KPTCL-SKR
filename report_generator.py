from __future__ import annotations

from collections import OrderedDict
from typing import Any


def _value(value: Any) -> str:
    if value is None:
        return ""
    result = str(value).strip()
    return "" if result.lower() in {"none", "null"} else result


def _format_interruptions(rows: list[dict[str, Any]], is_nil: bool) -> str:
    if is_nil:
        return "Nil"
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for row in rows:
        feeder = _value(row.get("feeder"))
        start = _value(row.get("start"))
        end = _value(row.get("end"))
        duration = _value(row.get("reported_duration"))
        relay = _value(row.get("relay"))
        if not all((feeder, start, end, duration, relay)):
            continue
        grouped.setdefault(feeder, []).append(row)
    groups = []
    for feeder, entries in grouped.items():
        formatted = [f"{_value(row['start'])} to {_value(row['end'])} = {_value(row['reported_duration'])}({_value(row['relay'])})" for row in entries]
        remarks = [_value(row.get("remarks")) for row in entries]
        if any(remarks):
            formatted = [
                line + (f" - {remark}" if remark else "")
                for line, remark in zip(formatted, remarks)
            ]
        groups.append(f"{feeder} -\n" + "\n".join(formatted))
    return "\n\n".join(groups)


def generate_report(data: dict[str, Any]) -> str:
    report = data.get("report", {})
    lines = ["Good morning Madam ,", ""]
    station = _value(report.get("station_name"))
    report_date = _value(report.get("date"))
    peak_load = _value(report.get("peak_load"))
    peak_time = _value(report.get("peak_load_time"))
    if station and report_date and peak_load and peak_time:
        lines.extend(
            [
                f"Station peak load of  {station} on {report_date} is {peak_load}MW at {peak_time}Hrs.",
                "",
            ]
        )
    else:
        peak_line = "Station peak load"
        if station:
            peak_line += f" of  {station}"
        if report_date:
            peak_line += f" on {report_date}"
        if peak_load:
            peak_line += f" is {peak_load}MW"
        if peak_time:
            peak_line += f" at {peak_time}Hrs"
        lines.extend([peak_line + ".", ""])

    transformers = data.get("transformers", [])
    for index, transformer in enumerate(transformers):
        rating = _value(transformer.get("rating"))
        load = _value(transformer.get("load"))
        time = _value(transformer.get("time"))
        if not all((rating, load, time)):
            continue
        if index == 0:
            lines.append(f"1){rating}MVA Tr1- {load}MW at {time} Hrs.")
        elif index == 1:
            lines.append(f"2){rating}MVA Tr2 -  {load}MW at {time}hrs")
        elif index == 2:
            lines.append(f"3){rating}MVA Tr3 - {load}MW at {time}Hrs.")
        else:
            lines.append(f"{index + 1}){rating}MVA Tr{index + 1} - {load}MW at {time}Hrs.")

    if len(lines) > 2:
        lines.append("")
    lines.append("Voltages")
    for label, high_key, low_key in (
        ("Max", "max_high_voltage", "max_low_voltage"),
        ("Min", "min_high_voltage", "min_low_voltage"),
    ):
        high = _value(report.get(high_key))
        low = _value(report.get(low_key))
        if high and low:
            lines.append(f"{label} -{high}/{low}kV")
    lines.append("")
    condition = _value(report.get("station_condition"))
    if condition:
        lines.extend([f"Station Condition : {condition}.", ""])
    interruptions_66 = _format_interruptions(data.get("interruptions_66", []), data.get("nil_66", False))
    if interruptions_66:
        lines.append(f"66KV Interruptions: {interruptions_66}")
    interruptions_11 = _format_interruptions(data.get("interruptions_11", []), data.get("nil_11", False))
    if interruptions_11:
        lines.extend(["", "11kv Interruptions :", "", interruptions_11])
    lines.extend(["", "Regards,", "AE(M)"])
    signature = _value(report.get("signature"))
    if signature:
        lines.append(f"{signature}.")
    return "\n".join(lines).strip()
