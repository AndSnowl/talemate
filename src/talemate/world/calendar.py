"""In-world calendars.

A `Calendar` names a world's months and weekdays, and formats a `WorldDate`
for display at that date's precision. Eras rename years in a date range
(e.g. the 312th Gregorian year rendered as "13 AR"); holidays mark fixed
month/day occasions.
"""

import structlog
from pydantic import BaseModel, Field, field_validator

from .dates import Precision, WorldDate

log = structlog.get_logger("talemate.world.calendar")

DEFAULT_MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

DEFAULT_WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


class Era(BaseModel):
    name: str
    abbreviation: str = ""
    start_year: int


class Holiday(BaseModel):
    name: str
    month: int
    day: int


class Calendar(BaseModel):
    month_names: list[str] = Field(default_factory=lambda: list(DEFAULT_MONTH_NAMES))
    weekday_names: list[str] = Field(
        default_factory=lambda: list(DEFAULT_WEEKDAY_NAMES)
    )
    eras: list[Era] = Field(default_factory=list)
    holidays: list[Holiday] = Field(default_factory=list)

    @field_validator("month_names")
    @classmethod
    def _validate_month_names(cls, value: list[str]) -> list[str]:
        if len(value) != 12:
            raise ValueError("month_names must have exactly 12 entries")
        return value

    @field_validator("weekday_names")
    @classmethod
    def _validate_weekday_names(cls, value: list[str]) -> list[str]:
        if len(value) != 7:
            raise ValueError("weekday_names must have exactly 7 entries")
        return value

    def _era_for(self, year: int) -> Era | None:
        in_force = [era for era in self.eras if era.start_year <= year]
        if not in_force:
            return None
        return max(in_force, key=lambda era: era.start_year)

    def _year_label(self, year: int) -> str:
        era = self._era_for(year)
        if era is None:
            return str(year)

        displayed_year = year - era.start_year + 1
        if era.abbreviation:
            return f"{displayed_year} {era.abbreviation}"
        return str(displayed_year)

    def format(self, date: WorldDate) -> str:
        """Render a `WorldDate` at its own precision, honoring the era in force."""

        dt = date.to_datetime()
        year_label = self._year_label(dt.year)

        if date.precision is Precision.YEAR:
            return year_label

        month_name = self.month_names[dt.month - 1]
        if date.precision is Precision.MONTH:
            return f"{month_name} {year_label}"

        text = f"{dt.day} {month_name} {year_label}"
        if date.precision is Precision.EXACT:
            text += f" {dt.hour:02d}:{dt.minute:02d}"
        return text

    def holidays_on(self, date: WorldDate) -> list[Holiday]:
        dt = date.to_datetime()
        return [
            holiday
            for holiday in self.holidays
            if holiday.month == dt.month and holiday.day == dt.day
        ]
