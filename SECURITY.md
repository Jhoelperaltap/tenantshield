# Security Policy

## Supported Versions

| Version | Supported                                              |
|---------|--------------------------------------------------------|
| 0.5.x   | ⚠ Alpha pre-release — security fixes on best-effort basis |
| < 0.5   | ❌ No support                                          |

This table will be revised when `v1.0.0` is released.

## Reporting a Vulnerability

Report security issues by email to `security@ejsupportit.com`.

- Initial acknowledgement within 72 hours of receipt.
- Do not report vulnerabilities through public GitHub issues, pull requests, discussions, or any other public channel.
- Coordinated disclosure: the timing of public disclosure is agreed between the reporter and the maintainers. The reporter receives public credit after the fix ships, if they wish.

## Scope

In scope:

- Any code path that allows a principal acting in tenant A to read, write, or infer the existence of data belonging to tenant B from within TenantShield-enforced models, queries, or workers.
- Any way to bypass the deny-by-default policy without going through the documented escape hatches (explicit `unscoped()` calls and configured `AllowList` policies).
- Any failure of tenant context propagation across async, threaded, or task-queue boundaries that results in queries running with the wrong tenant context, no tenant context, or a stale tenant context.

Out of scope:

- Bugs in documentation, examples, or non-runtime artifacts.
- Denial-of-service caused by user code that bypasses TenantShield's filtering — that is the calling application's responsibility.
- Issues in third-party dependencies. Report those upstream; we will track and update.
- Issues that require the attacker to already have administrative access to the host, the database, or the application's secrets.
