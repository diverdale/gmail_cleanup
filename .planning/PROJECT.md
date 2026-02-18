# Gmail Cleanup Tool

## What This Is

A Python CLI tool that connects to Gmail via OAuth and deletes emails older than a user-specified age (X months or a specific date). Built for personal use to solve storage pressure, inbox clutter, and as a routine maintenance utility.

## Core Value

Delete old Gmail messages reliably from the command line — with a dry-run preview before committing to deletion.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] User can delete all emails older than X months
- [ ] User can delete all emails older than a specific date
- [ ] User can run a dry-run that shows what would be deleted before committing
- [ ] Tool shows progress while deleting and a summary count at the end
- [ ] Tool authenticates with Gmail using existing OAuth credentials

### Out of Scope

- Scheduled/automated runs — CLI only for now
- Label/folder filtering — targets all email
- Email exclusions (starred, important) — age filter applies to everything
- Archiving — deletion only

## Context

- Python project (`.python-version` present)
- OAuth credentials already set up: `credentials.json`, `client_id`, `client_secret` files exist in project root
- Gmail API will be used for authentication and email operations
- User needs this for: freeing storage quota, reducing inbox clutter, periodic maintenance

## Constraints

- **Tech stack**: Python (version pinned via `.python-version`)
- **Auth**: Must use existing OAuth credentials — no new auth setup
- **Scope**: CLI only, no web UI or scheduler

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CLI over script | Reusable, parameterizable, easier to invoke regularly | — Pending |
| Dry-run default | Prevents accidental mass deletion, builds user trust | — Pending |

---
*Last updated: 2026-02-18 after initialization*
