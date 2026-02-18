"""Gmail Cleanup CLI — Phase 1 entry point (auth verification only)."""

import typer
from googleapiclient.errors import HttpError

from gmail_cleanup.auth import build_gmail_service

app = typer.Typer(
    name="gmail-clean",
    help="Delete old Gmail messages from the command line.",
    add_completion=False,
)


@app.command()
def main() -> None:
    """Verify Gmail authentication and API connection."""
    try:
        service = build_gmail_service()
    except FileNotFoundError as exc:
        typer.echo(f"Error: credentials.json not found — {exc}", err=True)
        raise typer.Exit(code=1)

    # Verify connection by fetching user profile (read-only, no messages accessed)
    try:
        profile = service.users().getProfile(userId="me").execute()
        email = profile["emailAddress"]
        typer.echo(f"Connected to Gmail as: {email}")
    except HttpError as exc:
        typer.echo(f"Gmail API error: {exc}", err=True)
        raise typer.Exit(code=1)

    # Verify list access by fetching one message ID (proves the scope works)
    try:
        result = service.users().messages().list(userId="me", maxResults=1).execute()
        messages = result.get("messages", [])
        if messages:
            typer.echo(f"API access confirmed. First message ID: {messages[0]['id']}")
        else:
            typer.echo("API access confirmed (no messages in mailbox).")
    except HttpError as exc:
        typer.echo(f"Gmail list error: {exc}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
