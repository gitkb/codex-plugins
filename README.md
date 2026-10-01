# GitKB Codex Plugins

The Codex plugin marketplace by GitKB.

## Available Plugins

| Plugin | Authoritative source |
|--------|----------------------|
| gitkb | [gitkb/gitkb-codex-plugin](https://github.com/gitkb/gitkb-codex-plugin) — knowledge base and code intelligence |

This repository owns the catalog, installation policies and approved source
selectors. The standalone repository owns the plugin payload, hooks, skills,
MCP configuration, package version and behavior tests. Changes to those components
belong there; there is no bundled GitKB payload or sync workflow here.

The GitKB entry uses Codex's supported `git-subdir` source, selecting `./plugin`
from the standalone repository by a full immutable commit SHA. See the
[OpenAI packaging documentation](https://developers.openai.com/plugins/build/plugins).

The Claude marketplace also includes [`meta`](https://github.com/gitkb/meta).
Add a Codex entry here once its authoritative repository has a supported payload.

## Usage

```bash
codex plugin marketplace add gitkb/codex-plugins
codex plugin add gitkb@gitkb
```

The installation identity remains `gitkb@gitkb`. Codex fetches the declared
Git source and installs its package; a Harmony meta checkout is not required.
The reference is pinned rather than rolling with `main`, so changes upstream
only reach this catalog after a reviewed pin update.

For an existing Git-backed marketplace installation:

```bash
codex plugin marketplace upgrade gitkb
codex plugin add gitkb@gitkb
```

Then start a new Codex session, or resume through the ATC shim, to launch a new
MCP process. Refreshing a marketplace or installing binaries alone does not
change an already running MCP child's environment. Missing historical activity
is not backfilled.

## Development and Release Promotion

```bash
make release-check
make test-integration CODEX_TEST_BINARY=/absolute/path/to/provider/codex
```

Catalog tests reject duplicate GitKB entries, unexpected sources, mutable or
malformed selectors, escaping package paths, and a reintroduced local payload
or copy of the MCP behavior tests.

The integration command fetches the exact catalog commit into a temporary
checkout and runs its package-owned policy, MCP contract and startup tests. The
startup test installs this catalog's actual Git-backed entry with Codex, compares
every installed package file against the referenced source, and verifies session
and credential isolation. It uses an isolated Codex home and synthetic context,
without model turns or real activity sinks. Pass the provider binary, not an ATC
shim. Source fetches need network access to the public standalone repository;
`make release-check` remains offline.

CI checks out the same source selector and passes it as `CANONICAL_SOURCE_DIR`
to avoid fetching that verification checkout again. Codex still resolves and
fetches the actual Git-backed plugin entry. CI uses Codex `0.159.2`.

To promote a new plugin release:

1. Implement and test the change in `gitkb/gitkb-codex-plugin`, bumping its plugin
   version when the installed payload changes.
2. Update only the GitKB entry's `source.sha` to the approved full commit SHA.
3. Run the catalog and delegated source checks, then review and merge the pin PR.

The initial selector contains the tested `0.1.2` payload from standalone
[PR #7](https://github.com/gitkb/gitkb-codex-plugin/pull/7), matching the payload
previously bundled by marketplace PR #5. It is immutable and published, so the
catalog cannot fall back to the pre-fix standalone `main` while that PR is open.

## License

MIT

Source verification compares every file's bytes and executable mode with the
pinned Git tree, independently of the index, ignore rules, replacement refs,
and fsmonitor hooks. Unexpected files (including ignored import shadows),
symlinks, and special files fail before package tests execute. Provided checkouts
must be pristine; use the default temporary checkout when a developer checkout
contains generated files. Delegated checks use a temporary home and omit parent
credentials, Python/shell startup overrides, and ATC session settings. The shared
canonical driver covers both fresh installation and upgrade from a bundled
`0.1.0` fixture. These checks validate catalog selection and the MCP launch
boundary; they are not a sandbox for arbitrary package code or a live ATC
registry acceptance test. Python 3.11 or newer is required.
