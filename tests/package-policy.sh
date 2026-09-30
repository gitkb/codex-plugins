#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

repo_root=${1:-.}
manifest="$repo_root/.agents/plugins/marketplace.json"
test -f "$manifest" || fail "missing marketplace"

jq -e '
  .name == "gitkb" and
  ([.plugins[] | select(.name == "gitkb")] | length == 1) and
  ([.plugins[] | select(.name == "gitkb")][0] |
    .policy == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"} and
    .category == "Productivity" and
    (.source |
      keys == ["path", "sha", "source", "url"] and
      .source == "git-subdir" and
      .url == "https://github.com/gitkb/gitkb-codex-plugin.git" and
      .path == "./plugin" and
      (.sha | type == "string" and test("^[0-9a-f]{40}$"))))
' "$manifest" >/dev/null || fail "gitkb must select exactly one canonical package by immutable SHA"

for path in plugins/gitkb plugin tests/mcp-contract.py tests/mcp-startup.py; do
  if [ -e "$repo_root/$path" ] || [ -L "$repo_root/$path" ]; then
    fail "catalog must not vendor the canonical payload or behavior tests: $path"
  fi
done

echo "Catalog policy checks passed."
