---
description: List and triage open GitHub issues for a repository
argument-hint: "[owner/repo] [label]"
---

Use the `github` MCP server tools to fetch open issues for the repository `$1`
(if no repository is given, infer it from the current git remote, or ask).
If a label `$2` is provided, filter by it.

Then produce a triage table with columns: number, title, labels, age, and a
suggested priority (P0–P3) with a one-line reason. Group stale issues (no
activity in 30+ days) at the end. Do not modify any issue unless I ask.
