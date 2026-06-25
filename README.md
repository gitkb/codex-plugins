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
