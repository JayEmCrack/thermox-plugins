# thermox-plugins

A Claude Code plugin marketplace.

| Plugin | Description |
|---|---|
| [thermox-github](plugins/thermox-github) | GitHub connector (official GitHub MCP server) plus issue and PR workflow commands |

## Install

In an interactive `claude` session:

```
/plugin marketplace add JayEmCrack/thermox-plugins
/plugin install thermox-github@thermox
```

Then set `GITHUB_PERSONAL_ACCESS_TOKEN` in your environment and restart Claude Code. See the [plugin README](plugins/thermox-github/README.md) for details.
