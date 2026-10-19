"""In-world dates.

A `WorldDate` is a seconds-resolution instant anchored at year 1, paired with
a display precision (year / month / day / exact). Dates are proleptic
Gregorian, so world years run 1-9999. Durations are added with
`datetime + isodate.parse_duration(...)` so that, for example, adding one
month moves the calendar month rather than approximating it as 30 days.
"""

import datetime
import re
from enum import Enum
from functools import total_ordering

import isodate
import structlog
from pydantic import BaseModel, ConfigDict

log = structlog.get_logger("talemate.world.dates")

# the epoch against which `instant` (seconds) is measured
EPOCH = datetime.datetime(1, 1, 1)

# matches a duration's time designator ("T") followed by an hour/minute/
# second component, e.g. the "T1H" in "P1DT1H"
_TIME_PART_RE = re.compile(r"T\d")


class Precision(str, Enum):
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    EXACT = "exact"


@total_ordering
class WorldDate(BaseModel):
    model_config = ConfigDict(frozen=True)

    instant: int
    precision: Precision

    @classmethod
    def of(
        cls,
        year: int,
        month: int | None = None,
        day: int | None = None,
        hour: int = 0,
        minute: int = 0,
    ) -> "WorldDate":
        """Build a `WorldDate`, inferring precision from the most specific part given."""

        if month is None:
            precision = Precision.YEAR
            month = 1
            day = 1
        elif day is None:
            precision = Precision.MONTH
            day = 1
        else:
            precision = Precision.DAY

        if hour or minute:
            precision = Precision.EXACT

        dt = datetime.datetime(year, month, day, hour, minute)
        instant = int((dt - EPOCH).total_seconds())
        return cls(instant=instant, precision=precision)

    def to_datetime(self) -> datetime.datetime:
        return EPOCH + datetime.timedelta(seconds=self.instant)

    def plus(self, duration: str) -> "WorldDate":
        """Add an ISO-8601 duration, keeping EXACT precision if the duration
        carries a time part, otherwise keeping this date's precision."""

        # parsed separately from the addition below, so a malformed duration
        # string (also a ValueError, from isodate) isn't mistaken for a
        # year-range overflow
        parsed = isodate.parse_duration(duration)
        is_negative = duration.strip().startswith("-")

        try:
            dt = self.to_datetime() + parsed
        except (OverflowError, ValueError) as exc:
            direction = "before year 1" if is_negative else "past year 9999"
            raise ValueError(f"result is {direction}") from exc

        instant = int((dt - EPOCH).total_seconds())
        precision = (
            Precision.EXACT if _TIME_PART_RE.search(duration) else self.precision
        )
        return WorldDate(instant=instant, precision=precision)

    def __lt__(self, other: "WorldDate") -> bool:
        if not isinstance(other, WorldDate):
            return NotImplemented
        return self.instant < other.instant
