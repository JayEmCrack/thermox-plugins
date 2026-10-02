---
description: Review a GitHub pull request using the GitHub connector
argument-hint: "<owner/repo> <pr-number>"
---

Use the `github` MCP server tools to fetch pull request #$2 in `$1`: its
description, changed files, diff, and CI status.

Review it for correctness bugs, missing tests, and risky changes. Report
findings ranked by severity, each with file and line. Summarize CI status.

Do NOT post comments, approve, or request changes on GitHub unless I
explicitly confirm after seeing your findings.
