import pytest

from talemate.world.calendar import Calendar, Era, Holiday
from talemate.world.dates import WorldDate


def _thawmonth_calendar() -> Calendar:
    names = Calendar().month_names.copy()
    names[2] = "Thawmonth"
    return Calendar(month_names=names)


def test_format_each_precision():
    calendar = _thawmonth_calendar()
    assert calendar.format(WorldDate.of(312)) == "312"
    assert calendar.format(WorldDate.of(312, 3)) == "Thawmonth 312"
    assert calendar.format(WorldDate.of(312, 3, 3)) == "3 Thawmonth 312"


def test_format_exact_appends_time():
    calendar = _thawmonth_calendar()
    date = WorldDate.of(312, 3, 3, hour=14, minute=5)
    assert calendar.format(date) == "3 Thawmonth 312 14:05"


def test_format_uses_latest_era():
    calendar = Calendar(
        eras=[
            Era(name="First Age", start_year=1),
            Era(name="Age of Ruin", abbreviation="AR", start_year=300),
        ]
    )
    assert calendar.format(WorldDate.of(312)) == "13 AR"


def test_format_without_era_abbreviation():
    calendar = Calendar(eras=[Era(name="First Age", start_year=1)])
    assert calendar.format(WorldDate.of(312)) == "312"


def test_calendar_rejects_wrong_month_count():
    with pytest.raises(ValueError):
        Calendar(month_names=["Jan"] * 11)


def test_calendar_rejects_wrong_weekday_count():
    with pytest.raises(ValueError):
        Calendar(weekday_names=["Mon"] * 6)


def test_holidays_on():
    calendar = Calendar(holidays=[Holiday(name="Thaw Day", month=3, day=3)])
    assert [h.name for h in calendar.holidays_on(WorldDate.of(312, 3, 3))] == [
        "Thaw Day"
    ]
    assert calendar.holidays_on(WorldDate.of(312, 3, 4)) == []
