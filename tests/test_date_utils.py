"""Tests for gmail_cleanup.date_utils."""
from datetime import datetime, timezone

import pytest
from dateutil.relativedelta import relativedelta

from gmail_cleanup.date_utils import (
    build_gmail_query,
    months_ago_to_cutoff,
    parse_date_to_cutoff,
)


class TestMonthsAgeToCutoff:
    def test_returns_utc_aware_datetime(self):
        """Result must be tz-aware (local tz, not necessarily UTC)."""
        result = months_ago_to_cutoff(6)
        assert result.tzinfo is not None

    def test_result_is_in_the_past(self):
        result = months_ago_to_cutoff(1)
        assert result < datetime.now().astimezone()

    def test_6_months_ago_has_correct_month_offset(self):
        now = datetime.now().astimezone()
        result = months_ago_to_cutoff(6)
        expected = now - relativedelta(months=6)
        # Allow 5-second window for test execution time
        assert abs((result - expected).total_seconds()) < 5

    def test_zero_months_returns_approximately_now(self):
        now = datetime.now().astimezone()
        result = months_ago_to_cutoff(0)
        assert abs((result - now).total_seconds()) < 5


class TestParseDateToCutoff:
    def test_valid_date_returns_end_of_day_local(self):
        """parse_date_to_cutoff returns end-of-day (23:59:59) in local timezone."""
        result = parse_date_to_cutoff("2024-01-01")
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59
        assert result.tzinfo is not None

    def test_mid_year_date(self):
        result = parse_date_to_cutoff("2024-06-15")
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59
        assert result.tzinfo is not None

    def test_before_end_of_day(self):
        """Convenience: verify 2024-01-01 resolves to 23:59:59 in local tz."""
        result = parse_date_to_cutoff("2024-01-01")
        assert result.hour == 23 and result.minute == 59 and result.second == 59

    def test_invalid_format_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_date_to_cutoff("not-a-date")

    def test_invalid_month_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_date_to_cutoff("2024-13-01")

    def test_wrong_format_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_date_to_cutoff("01/01/2024")


class TestBuildGmailQuery:
    def test_prefix_is_before(self):
        cutoff = datetime(2020, 12, 31, tzinfo=timezone.utc)
        result = build_gmail_query(cutoff)
        assert result.startswith("before:")

    def test_epoch_integer_not_formatted_date(self):
        """build_gmail_query must return 'before:EPOCH' not 'before:YYYY/MM/DD'."""
        cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = build_gmail_query(cutoff)
        assert result.startswith("before:")
        epoch_part = result[len("before:"):]
        assert epoch_part.isdigit(), f"Expected digit-only epoch, got: {epoch_part!r}"

    def test_epoch_is_integer_string(self):
        """Epoch part must be a pure integer string (no decimal point)."""
        cutoff = datetime(2024, 6, 15, 23, 59, 59, tzinfo=timezone.utc)
        result = build_gmail_query(cutoff)
        epoch_part = result[7:]
        assert epoch_part.isdigit()
