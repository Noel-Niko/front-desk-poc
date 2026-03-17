"""Tests for the date offset system — written FIRST per TDD."""

from datetime import date, datetime, timedelta

import pytest

from backend.app.services.date_utils import (
    format_date_natural,
    format_time_natural,
    is_future,
    is_weekday,
    resolve_date,
    resolve_datetime,
    resolve_payment_due_date,
    temporal_hint,
)


class TestResolveDate:
    def test_today(self) -> None:
        assert resolve_date(0) == date.today()

    def test_yesterday(self) -> None:
        assert resolve_date(1) == date.today() - timedelta(days=1)

    def test_five_days_ago(self) -> None:
        assert resolve_date(5) == date.today() - timedelta(days=5)


class TestResolveDatetime:
    def test_today_morning(self) -> None:
        result = resolve_datetime(0, "08:15")
        assert result.date() == date.today()
        assert result.hour == 8
        assert result.minute == 15

    def test_yesterday_afternoon(self) -> None:
        result = resolve_datetime(1, "14:30")
        assert result.date() == date.today() - timedelta(days=1)
        assert result.hour == 14
        assert result.minute == 30


class TestIsFuture:
    def test_past_event_yesterday(self) -> None:
        # Yesterday is always past
        assert is_future(1, "12:00") is False

    def test_late_night_today_is_future(self) -> None:
        # 23:59 today should be future (unless test runs at 11:59 PM)
        assert is_future(0, "23:59") is True

    def test_early_morning_today_is_past(self) -> None:
        # 00:01 today should be past (unless test runs at midnight)
        assert is_future(0, "00:01") is False


class TestResolvePaymentDueDate:
    def test_due_today(self) -> None:
        assert resolve_payment_due_date(0) == date.today()

    def test_due_in_four_days(self) -> None:
        assert resolve_payment_due_date(4) == date.today() + timedelta(days=4)


class TestIsWeekday:
    def test_known_weekday(self) -> None:
        # Find the offset for a known weekday
        for offset in range(7):
            d = date.today() - timedelta(days=offset)
            expected = d.weekday() < 5
            assert is_weekday(offset) == expected, f"offset={offset}, date={d}"


class TestFormatDateNatural:
    def test_today(self) -> None:
        result = format_date_natural(0)
        assert "today" in result

    def test_yesterday(self) -> None:
        result = format_date_natural(1)
        assert "yesterday" in result

    def test_older_date(self) -> None:
        result = format_date_natural(5)
        # Should contain year for older dates
        assert str(date.today().year) in result or str(date.today().year - 1) in result


class TestFormatTimeNatural:
    def test_morning(self) -> None:
        assert format_time_natural("08:15") == "8:15 AM"

    def test_afternoon(self) -> None:
        assert format_time_natural("14:30") == "2:30 PM"

    def test_noon(self) -> None:
        assert format_time_natural("12:00") == "12:00 PM"


class TestTemporalHint:
    def test_past_day(self) -> None:
        assert temporal_hint(1, "12:00") == "past"

    def test_future_event_today(self) -> None:
        assert temporal_hint(0, "23:59") == "future"

    def test_past_event_today(self) -> None:
        assert temporal_hint(0, "00:01") == "past"
