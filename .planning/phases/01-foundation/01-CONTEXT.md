# Phase 1: Foundation - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Secure project skeleton with credential file protection (.gitignore), working OAuth 2.0 authentication with token caching, and a verified Gmail API connection. No CLI flags, no email operations — just auth that downstream phases can depend on.

</domain>

<decisions>
## Implementation Decisions

### Token file location
- Claude's discretion — user deferred to implementation judgment
- Recommended: store token.json in `~/.config/gmail-clean/token.json` (standard XDG config dir convention for CLI tools, works from any invocation directory regardless of working directory)

### credentials.json location
- Claude's discretion — user deferred to implementation judgment
- Recommended: look up credentials.json relative to the script/package location (not CWD), so the tool works from any directory

### Claude's Discretion
- Token and credential file path resolution strategy (use ~/.config/gmail-clean/ for token, script-relative for credentials.json)
- Module structure: 4-module layout (main.py, auth.py, gmail_client.py, cleaner.py) vs single file — choose what is cleanest for v1
- First-run messaging: what to print before/after browser opens for OAuth

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for a personal CLI tool.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-02-18*
