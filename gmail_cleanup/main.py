"""Gmail Cleanup CLI — delete old Gmail messages from the command line."""

from typing import Optional

import typer
from googleapiclient.errors import HttpError

from gmail_cleanup.auth import build_gmail_service
from gmail_cleanup.date_utils import (
    build_gmail_query,
    months_ago_to_cutoff,
    parse_date_to_cutoff,
)
from gmail_cleanup.gmail_client import count_messages

app = typer.Typer(
    name="gmail-clean",
    help="Delete old Gmail messages from the command line.",
    add_completion=False,
)


def validate_date(value: Optional[str]) -> Optional[str]:
    """Validate --before argument is YYYY-MM-DD format."""
    if value is None:
        return None
    try:
        parse_date_to_cutoff(value)
    except ValueError:
        raise typer.BadParameter(f"Date must be YYYY-MM-DD, got: {value}")
    return value


@app.command()
def main(
    older_than: Optional[int] = typer.Option(
        None,
        "--older-than",
        help="Target emails older than N months.",
        min=1,
    ),
    before: Optional[str] = typer.Option(
        None,
        "--before",
        help="Target emails before YYYY-MM-DD.",
        callback=validate_date,
        is_eager=False,
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Perform live deletion. Dry-run is the default.",
    ),
) -> None:
    """Delete old Gmail messages. Runs in dry-run mode by default.

    Exactly one of --older-than or --before must be provided.
    Pass --execute to perform live deletion after confirmation.
    """
    # Mutual exclusion: require exactly one targeting argument
    if older_than is None and before is None:
        typer.echo(
            "Error: Provide --older-than N (months) or --before YYYY-MM-DD.",
            err=True,
        )
        raise typer.Exit(code=1)
    if older_than is not None and before is not None:
        typer.echo(
            "Error: Use --older-than or --before, not both.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Build Gmail query from CLI argument
    if older_than is not None:
        cutoff = months_ago_to_cutoff(older_than)
    else:
        cutoff = parse_date_to_cutoff(before)  # type: ignore[arg-type]

    query = build_gmail_query(cutoff)

    # Authenticate and count matching messages
    try:
        service = build_gmail_service()
    except FileNotFoundError as exc:
        typer.echo(f"Error: credentials.json not found — {exc}", err=True)
        raise typer.Exit(code=1)

    try:
        count = count_messages(service, query)
    except HttpError as exc:
        typer.echo(f"Gmail API error: {exc}", err=True)
        raise typer.Exit(code=1)

    if not execute:
        # Dry-run: show count and exit — zero write/delete API calls made
        typer.echo(
            f"[DRY RUN] Found ~{count} emails matching '{query}' "
            f"(approximate, up to 500 shown)."
        )
        typer.echo("Run with --execute to delete permanently.")
        raise typer.Exit(code=0)

    # --execute path: show count and require explicit confirmation
    # typer.confirm() appends " [y/N]: " automatically — do not include in message
    typer.echo(f"Found ~{count} emails matching '{query}' (approximate, up to 500 shown).")
    try:
        confirmed = typer.confirm("Delete permanently")
    except (KeyboardInterrupt, typer.Abort):
        typer.echo("\nCancelled.")
        raise typer.Exit(code=0)

    if not confirmed:
        typer.echo("Deletion cancelled.")
        raise typer.Exit(code=0)

    # Deletion stub — Phase 4 implements batch_delete
    typer.echo("Deletion not yet implemented. (Phase 4)")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
