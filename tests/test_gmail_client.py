"""Tests for gmail_cleanup.gmail_client — paginated message ID fetching."""
from unittest.mock import MagicMock, call

import pytest
from googleapiclient.errors import HttpError

from gmail_cleanup.gmail_client import list_message_ids


def make_mock_service(pages):
    """Create a mock Gmail API service returning the given sequence of pages.

    Args:
        pages: list of dicts, each like {"messages": [...], "nextPageToken": "tok"}
               or {"messages": [...]} (no token = last page).
    """
    mock_service = MagicMock()
    execute_mock = MagicMock(side_effect=[page for page in pages])
    mock_service.users.return_value.messages.return_value.list.return_value.execute = execute_mock
    return mock_service


class TestListMessageIds:
    def test_single_page_returns_all_ids(self):
        """1 page, 3 messages -> list of 3 IDs."""
        pages = [{"messages": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}]
        service = make_mock_service(pages)
        result = list_message_ids(service, "before:2024/01/01")
        assert result == ["a", "b", "c"]

    def test_two_pages_returns_all_ids(self):
        """page1 has nextPageToken, page2 does not -> combined list of all IDs."""
        pages = [
            {"messages": [{"id": f"p1_{i}"} for i in range(3)], "nextPageToken": "tok1"},
            {"messages": [{"id": f"p2_{i}"} for i in range(2)]},
        ]
        service = make_mock_service(pages)
        result = list_message_ids(service, "before:2024/01/01")
        assert result == ["p1_0", "p1_1", "p1_2", "p2_0", "p2_1"]

    def test_empty_result_returns_empty_list(self):
        """Response has no 'messages' key and no nextPageToken -> returns []."""
        pages = [{}]
        service = make_mock_service(pages)
        result = list_message_ids(service, "before:2024/01/01")
        assert result == []

    def test_last_page_has_no_messages_key(self):
        """page1 has messages+nextPageToken, page2 has no 'messages' key -> IDs from page1 only."""
        pages = [
            {"messages": [{"id": "x"}, {"id": "y"}], "nextPageToken": "tok2"},
            {"nextPageToken": None},  # no messages key, loop should end
        ]
        # Note: {"nextPageToken": None} — None is falsy, so loop ends after page2
        service = make_mock_service(pages)
        result = list_message_ids(service, "before:2024/01/01")
        assert result == ["x", "y"]

    def test_http_error_propagates(self):
        """Service raises HttpError on execute() -> HttpError raised from list_message_ids."""
        mock_service = MagicMock()
        http_error = HttpError(resp=MagicMock(status=500), content=b"Internal Server Error")
        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = http_error
        with pytest.raises(HttpError):
            list_message_ids(mock_service, "before:2024/01/01")

    def test_pagetoken_passed_on_second_call(self):
        """Verify list() is called with pageToken= argument on second call."""
        pages = [
            {"messages": [{"id": "a"}], "nextPageToken": "my_token"},
            {"messages": [{"id": "b"}]},
        ]
        service = make_mock_service(pages)
        list_message_ids(service, "q=test")
        list_calls = service.users.return_value.messages.return_value.list.call_args_list
        assert len(list_calls) == 2
        # First call should NOT have pageToken
        assert "pageToken" not in list_calls[0].kwargs
        # Second call MUST have pageToken="my_token"
        assert list_calls[1].kwargs.get("pageToken") == "my_token"

    def test_maxresults_is_500(self):
        """Verify list() is called with maxResults=500 on every page."""
        pages = [
            {"messages": [{"id": "a"}], "nextPageToken": "tok"},
            {"messages": [{"id": "b"}]},
        ]
        service = make_mock_service(pages)
        list_message_ids(service, "q=test")
        list_calls = service.users.return_value.messages.return_value.list.call_args_list
        for c in list_calls:
            assert c.kwargs.get("maxResults") == 500
