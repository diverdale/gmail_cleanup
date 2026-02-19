"""Unit tests for batch_delete in gmail_cleanup.cleaner."""
import pytest
from unittest.mock import MagicMock, patch
from googleapiclient.errors import HttpError

from gmail_cleanup.cleaner import batch_delete


def make_http_error(status: int) -> HttpError:
    resp = MagicMock()
    resp.status = str(status)  # httplib2 returns string
    return HttpError(resp=resp, content=b"error")


class TestBatchDelete:

    def test_empty_list(self):
        """Empty list returns 0; batchDelete never called."""
        mock_service = MagicMock()
        result = batch_delete(mock_service, [])
        assert result == 0
        mock_service.users().messages().batchDelete.assert_not_called()

    def test_chunking(self):
        """501 IDs causes batchDelete to be called exactly twice (500 + 1 split)."""
        mock_service = MagicMock()
        ids = [str(i) for i in range(501)]
        result = batch_delete(mock_service, ids)
        assert mock_service.users().messages().batchDelete.call_count == 2

    def test_success_returns_count(self):
        """3 IDs, success path returns 3."""
        mock_service = MagicMock()
        ids = ["a", "b", "c"]
        result = batch_delete(mock_service, ids)
        assert result == 3

    def test_retry_on_429(self):
        """First call raises HttpError(429), second succeeds; sleep called once; returns count."""
        mock_service = MagicMock()
        ids = ["x", "y"]
        mock_service.users().messages().batchDelete().execute.side_effect = [
            make_http_error(429),
            None,
        ]
        with patch("time.sleep") as mock_sleep:
            result = batch_delete(mock_service, ids)
        assert result == 2
        mock_sleep.assert_called_once()

    def test_no_retry_on_403(self):
        """HttpError(403) raises immediately; batchDelete called once; sleep not called."""
        mock_service = MagicMock()
        ids = ["z"]
        mock_service.users().messages().batchDelete().execute.side_effect = make_http_error(403)
        with patch("time.sleep") as mock_sleep:
            with pytest.raises(HttpError):
                batch_delete(mock_service, ids)
        mock_sleep.assert_not_called()

    def test_retry_twice_then_success(self):
        """HttpError(500) twice, then success; sleep called twice; returns count."""
        mock_service = MagicMock()
        ids = ["m", "n", "o"]
        mock_service.users().messages().batchDelete().execute.side_effect = [
            make_http_error(500),
            make_http_error(500),
            None,
        ]
        with patch("time.sleep") as mock_sleep:
            result = batch_delete(mock_service, ids)
        assert result == 3
        assert mock_sleep.call_count == 2
