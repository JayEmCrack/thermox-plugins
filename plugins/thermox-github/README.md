# thermox-github

A Claude Code plugin that bundles a GitHub connector and adds GitHub workflow commands.

## Contents

| Path | Purpose |
|---|---|
| `.claude-plugin/plugin.json` | Plugin manifest |
| `.mcp.json` | GitHub's official remote MCP server (`github`) |
| `commands/gh-issues.md` | `/gh-issues [owner/repo] [label]`: triage open issues |
| `commands/gh-pr-review.md` | `/gh-pr-review <owner/repo> <pr>`: review a PR |
| `skills/github-workflow/` | Conventions: confirm before writing to GitHub, etc. |

## Setup

1. Create a GitHub personal access token (fine-grained recommended) with the
   repo permissions you need (e.g. Contents, Issues, Pull requests: read/write).
2. Set it as a user environment variable (PowerShell):

   ```powershell
   [Environment]::SetEnvironmentVariable("GITHUB_PERSONAL_ACCESS_TOKEN", "<your token>", "User")
   ```

   Restart Claude Code afterwards so it picks up the variable.
3. Install from the marketplace (in an interactive `claude` session):

   ```
   /plugin marketplace add JayEmCrack/thermox-plugins
   /plugin install thermox-github@thermox
   ```
