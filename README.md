# GitKB Codex Plugins

A private Codex plugin marketplace by GitKB.

## Available Plugins

| Plugin | Description |
|--------|-------------|
| [gitkb](https://github.com/gitkb/gitkb-codex-plugin) | Knowledge base and code intelligence for AI-native development. |

The Claude marketplace also includes [`meta`](https://github.com/gitkb/meta). Add the Codex `meta` plugin here after `gitkb/meta` has a `codex-plugin` payload that mirrors its Claude plugin.

## Repository Layout

```text
.agents/plugins/marketplace.json # Codex marketplace manifest
plugins/gitkb/                   # Installable GitKB Codex plugin payload
```

Codex marketplace entries resolve plugin paths relative to this marketplace repo. The `plugins/gitkb` payload mirrors the private `gitkb-codex-plugin` package while both are under review.

## Usage

```bash
# Add this private marketplace when you have repository access
codex plugin marketplace add gitkb/codex-plugins

# Install a plugin
codex plugin add gitkb@gitkb
```

## License

MIT

## MCP Launch Regression Tests

`make test` checks the packaged environment allowlist and cache version. The
installation test exercises the actual Codex MCP launch boundary with synthetic
sessions, custom registry settings, paths with spaces and Unicode, and credential
canaries. It reuses an isolated plugin installation across two sessions and a
launch without activity context. It does not start a model turn or run an activity
sink, and it does not use your Codex home or credentials.

```bash
make test-integration CODEX_TEST_BINARY=/absolute/path/to/provider/codex
```

Pass the provider binary, rather than an ATC shim. CI runs this test with Codex
`0.159.2`, in addition to the release checks.
