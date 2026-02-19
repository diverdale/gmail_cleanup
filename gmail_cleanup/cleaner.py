"""Email deletion logic."""
import time

from googleapiclient.errors import HttpError
from rich.progress import track


def batch_delete(service, message_ids: list[str]) -> int:
    """Permanently delete messages in 500-ID chunks. Returns count deleted."""
    if not message_ids:
        return 0

    chunks = [message_ids[i:i + 500] for i in range(0, len(message_ids), 500)]
    deleted = 0

    for chunk in track(chunks, description="Deleting..."):
        delay = 1
        while True:
            try:
                service.users().messages().batchDelete(
                    userId="me", body={"ids": chunk}
                ).execute()
                deleted += len(chunk)
                break
            except HttpError as exc:
                status = int(exc.resp.status)
                if status in {429, 500, 502, 503, 504}:
                    time.sleep(delay)
                    delay = min(delay * 2, 32)
                else:
                    raise

    return deleted
