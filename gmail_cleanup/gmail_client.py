"""Gmail API operations — message discovery in Phase 3, deletion in Phase 4."""

from googleapiclient.errors import HttpError  # noqa: F401 — re-exported for callers


def list_message_ids(service, query: str) -> list[str]:
    """Return all message IDs matching query via paginated API calls.

    Uses nextPageToken loop with maxResults=500 per page. Returns every
    matching message ID — no silent truncation. Raises HttpError on API failure.

    Args:
        service: Authenticated Gmail API service object from build_gmail_service().
        query: Gmail search query string (e.g. "before:2024/01/01").

    Returns:
        Flat list of all matching message ID strings.
    """
    ids: list[str] = []
    page_token = None
    while True:
        kwargs: dict = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token
        result = service.users().messages().list(**kwargs).execute()
        ids.extend(m["id"] for m in result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return ids
