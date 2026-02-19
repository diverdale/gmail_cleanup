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
        result = months_ago_to_cutoff(6)
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_result_is_in_the_past(self):
        result = months_ago_to_cutoff(1)
        assert result < datetime.now(timezone.utc)

    def test_6_months_ago_has_correct_month_offset(self):
        now = datetime.now(timezone.utc)
        result = months_ago_to_cutoff(6)
        expected = now - relativedelta(months=6)
        # Allow 5-second window for test execution time
        assert abs((result - expected).total_seconds()) < 5

    def test_zero_months_returns_approximately_now(self):
        now = datetime.now(timezone.utc)
        result = months_ago_to_cutoff(0)
        assert abs((result - now).total_seconds()) < 5


class TestParseDateToCutoff:
    def test_valid_date_returns_utc_midnight(self):
        result = parse_date_to_cutoff("2024-01-01")
        assert result == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_mid_year_date(self):
        result = parse_date_to_cutoff("2024-06-15")
        assert result == datetime(2024, 6, 15, 0, 0, 0, tzinfo=timezone.utc)

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
    def test_formats_with_slashes_not_hyphens(self):
        cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = build_gmail_query(cutoff)
        assert result == "before:2024/01/01"

    def test_zero_pads_month_and_day(self):
        cutoff = datetime(2023, 6, 5, tzinfo=timezone.utc)
        result = build_gmail_query(cutoff)
        assert result == "before:2023/06/05"

    def test_prefix_is_before(self):
        cutoff = datetime(2020, 12, 31, tzinfo=timezone.utc)
        result = build_gmail_query(cutoff)
        assert result.startswith("before:")
