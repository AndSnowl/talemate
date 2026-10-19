import pytest

from talemate.world.dates import Precision, WorldDate


def test_of_sets_precision():
    assert WorldDate.of(304).precision is Precision.YEAR
    assert WorldDate.of(304, 2, 3).precision is Precision.DAY


def test_of_month_only_precision():
    assert WorldDate.of(304, 2).precision is Precision.MONTH


def test_of_hour_or_minute_is_exact():
    assert WorldDate.of(304, 2, 3, hour=14).precision is Precision.EXACT
    assert WorldDate.of(304, 2, 3, minute=5).precision is Precision.EXACT


def test_plus_month_is_calendar_month():
    result = WorldDate.of(312, 1, 31).plus("P1M")
    assert result.to_datetime().month == 2


def test_plus_keeps_original_precision_without_time_part():
    result = WorldDate.of(312, 1).plus("P1M")
    assert result.precision is Precision.MONTH


def test_plus_with_time_part_becomes_exact():
    result = WorldDate.of(312, 1).plus("PT1H")
    assert result.precision is Precision.EXACT


def test_plus_rejects_past_9999_day_based():
    with pytest.raises(ValueError, match="past year 9999"):
        WorldDate.of(9999, 12, 31).plus("P1D")


def test_plus_rejects_past_9999_month_based():
    with pytest.raises(ValueError, match="past year 9999"):
        WorldDate.of(9999, 12, 31).plus("P1M")


def test_plus_rejects_negative_result_day_based():
    with pytest.raises(ValueError, match="before year 1"):
        WorldDate.of(1).plus("-P1D")


def test_plus_rejects_negative_result_month_based():
    with pytest.raises(ValueError, match="before year 1"):
        WorldDate.of(1, 1, 1).plus("-P1M")


def test_dates_order_by_instant():
    early = WorldDate.of(100)
    late = WorldDate.of(200)
    assert early < late
    assert sorted([late, early]) == [early, late]
