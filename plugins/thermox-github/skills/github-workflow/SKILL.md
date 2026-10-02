---
name: github-workflow
description: Conventions for working with GitHub through the bundled `github` MCP connector — reading repos, issues, PRs, and Actions runs. Use whenever a task involves GitHub data or actions.
---

# GitHub workflow

- Prefer the `github` MCP server tools over shelling out to `gh` or calling
  the REST API with curl.
- Reads (repos, issues, PRs, diffs, Actions runs) are fine to do freely.
- Writes are outward-facing: creating/closing issues, commenting, reviewing,
  merging, pushing, or editing labels require explicit user confirmation
  first. Show exactly what will be posted before doing it.
- When a repo isn't specified, infer `owner/repo` from `git remote get-url
  origin`; if that fails, ask.
- If the connector returns 401/403, tell the user that
  `GITHUB_PERSONAL_ACCESS_TOKEN` is missing or lacks scopes — never ask them
  to paste the token into chat.
