"""Date plumbing between the two platforms.

Salesforce returns date-times as  2026-10-14T00:00:00.000+0000
m3ter wants                       2026-10-14T00:00:00.000Z   (ISO-8601, UTC, 'Z')

Revenue Cloud ends a lifecycle at 23:59:59 of the last day (inclusive);
m3ter dates are exclusive, so the matching m3ter end is one second later —
midnight of the next day. m3sh does the same: dateAdd(LifecycleEndDate, 1, "SECONDS").
"""
from datetime import UTC, datetime, timedelta

SF_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'
M3_FORMAT = '%Y-%m-%dT%H:%M:%S.000Z'


def parse_sf(value: str) -> datetime:
    return datetime.strptime(value, SF_FORMAT).astimezone(UTC)


def to_m3ter(value: str, plus_seconds: int = 0) -> str:
    """Salesforce date-time string -> m3ter date-time string, optionally shifted."""
    return (parse_sf(value) + timedelta(seconds=plus_seconds)).strftime(M3_FORMAT)


def exclusive_end(value: str) -> str:
    """Salesforce inclusive 23:59:59 end -> m3ter exclusive midnight end."""
    return to_m3ter(value, plus_seconds=1)


# ---- the other direction: m3ter -> Salesforce (used by the bill sync) --------
#
# An m3ter service period ends at midnight EXCLUSIVE (2026-11-01T00:00:00.000Z);
# Revenue Cloud usage records end at the last second INCLUSIVE. m3sh did
# DateTime.dateSub(String.left(EndDateTime, 22) + "Z", 1, "SECONDS") —
# 2026-10-31T23:59:59Z. inclusive_end() is that. SOQL date-time literals are
# unquoted and carry no millis: 2026-10-14T00:00:00Z.

def parse_m3ter(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(UTC)


def sf_datetime(value: str, plus_seconds: int = 0) -> str:
    """m3ter date-time -> the form Salesforce accepts in both SOQL and payloads."""
    return (parse_m3ter(value) + timedelta(seconds=plus_seconds)).strftime('%Y-%m-%dT%H:%M:%SZ')


def inclusive_end(value: str) -> str:
    """m3ter exclusive midnight end -> Revenue Cloud inclusive 23:59:59 end."""
    return sf_datetime(value, plus_seconds=-1)
