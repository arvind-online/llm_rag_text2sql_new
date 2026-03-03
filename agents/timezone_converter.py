"""LangChain tool for converting UTC timestamps in SQL results to a target timezone."""

import json
import re
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool


# Regex patterns for detecting datetime-like strings
_DATETIME_PATTERNS = [
    re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$'),
    re.compile(r'^\d{4}-\d{2}-\d{2}$'),
]


def _try_parse_datetime(value: str) -> datetime | None:
    """Try to parse a string as a datetime. Returns a datetime or None."""
    formats = [
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
    ]
    # Normalise: strip trailing Z, normalise +00:00
    clean = value.strip()
    if clean.endswith('Z'):
        clean = clean[:-1] + '+00:00'

    # Try fromisoformat first (handles offsets natively in Python 3.11+)
    try:
        return datetime.fromisoformat(clean)
    except ValueError:
        pass

    # Fallback: strip offset and try strptime
    clean_no_offset = re.sub(r'[+-]\d{2}:?\d{2}$', '', clean)
    for fmt in formats:
        try:
            return datetime.strptime(clean_no_offset, fmt)
        except ValueError:
            continue

    return None


def _convert_value(value, target_tz: ZoneInfo):
    """Convert a single value to target timezone if it looks like a datetime."""
    if isinstance(value, str):
        if not any(p.match(value.strip()) for p in _DATETIME_PATTERNS):
            return value
        dt = _try_parse_datetime(value)
        if dt is None:
            return value
        # Treat naive datetimes as UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        converted = dt.astimezone(target_tz)
        return converted.strftime('%Y-%m-%d %H:%M:%S %Z')

    if hasattr(value, 'tzinfo'):
        # Native Python datetime object
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt_timezone.utc)
        return value.astimezone(target_tz).strftime('%Y-%m-%d %H:%M:%S %Z')

    return value


@tool
def convert_utc_to_timezone(records_json: str | list, target_timezone: str) -> str:
    """Convert all UTC datetime/timestamp values in SQL query records to the target timezone.

    Call this tool whenever SQL query results contain datetime, timestamp, or time fields.
    All times stored in the database are in UTC and must be converted before display.

    Args:
        records_json: The query result records — either a JSON array string or a list of dicts
        target_timezone: IANA timezone name from the user's browser (e.g. 'America/New_York', 'Europe/London', 'Asia/Tokyo')

    Returns:
        JSON array string with all datetime values converted to the target timezone
    """
    try:
        target_tz = ZoneInfo(target_timezone)
    except (ZoneInfoNotFoundError, KeyError):
        target_tz = ZoneInfo("UTC")

    # Accept either a JSON string or a raw list/dict passed directly by the LLM
    if isinstance(records_json, (list, dict)):
        records = records_json if isinstance(records_json, list) else [records_json]
    else:
        try:
            records = json.loads(records_json)
        except (json.JSONDecodeError, TypeError):
            return records_json  # Return unchanged if we can't parse

    if not isinstance(records, list):
        records = [records]

    converted = []
    for record in records:
        if isinstance(record, dict):
            converted.append({k: _convert_value(v, target_tz) for k, v in record.items()})
        else:
            converted.append(record)

    return json.dumps(converted)
