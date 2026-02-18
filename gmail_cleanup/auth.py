"""Gmail OAuth authentication with token caching."""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# https://mail.google.com/ is required for batchDelete.
# Do NOT use gmail.modify — it returns HTTP 403 on batchDelete.
# Source: googleapis/google-api-python-client#2710
SCOPES = ["https://mail.google.com/"]

# Token stored in XDG config dir — works regardless of invocation directory.
# Do NOT use a CWD-relative path; this tool is invoked from many directories.
TOKEN_PATH = Path.home() / ".config" / "gmail-clean" / "token.json"

# credentials.json lives at the project root, one level above this package file.
# auth.py is at: <root>/gmail_cleanup/auth.py
# credentials.json is at: <root>/credentials.json
# Do NOT use os.getcwd() — it breaks when tool is invoked from another directory.
CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials.json"


def get_credentials() -> Credentials:
    """Load cached credentials or trigger OAuth browser flow.

    First run: opens browser, user grants consent, token saved to TOKEN_PATH.
    Subsequent runs: loads token from TOKEN_PATH, refreshes silently if expired.

    NOTE: If SCOPES is ever changed, delete TOKEN_PATH and re-authenticate.
    The cached token scope is not re-validated at load time.
    """
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Silent refresh — no browser needed
            creds.refresh(Request())
        else:
            # First run: open browser for user consent
            print("Opening browser for Gmail authentication...")
            print("If the browser does not open automatically, visit the URL shown below.")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(
                port=0,
                open_browser=True,
                authorization_prompt_message="",  # suppress duplicate URL print
                success_message="Authentication complete. You can close this tab.",
            )
            print("Authentication successful.")

        # Persist token for next run.
        # Create directory first — ~/.config/gmail-clean/ may not exist.
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def build_gmail_service():
    """Return authenticated Gmail API service object."""
    return build("gmail", "v1", credentials=get_credentials())
