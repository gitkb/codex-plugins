#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

test -f .agents/plugins/marketplace.json || fail "missing marketplace"
test -f plugins/gitkb/.codex-plugin/plugin.json || fail "missing bundled gitkb plugin"

marketplace_name=$(jq -r '.name' .agents/plugins/marketplace.json)
test "$marketplace_name" = "gitkb" || fail "marketplace name must be gitkb"

source_kind=$(jq -r '.plugins[] | select(.name == "gitkb") | .source.source' .agents/plugins/marketplace.json)
source_path=$(jq -r '.plugins[] | select(.name == "gitkb") | .source.path' .agents/plugins/marketplace.json)
test "$source_kind" = "local" || fail "Codex marketplace plugin source must be local"
test "$source_path" = "./plugins/gitkb" || fail "gitkb source path must be ./plugins/gitkb"

plugin_name=$(jq -r '.name' plugins/gitkb/.codex-plugin/plugin.json)
test "$plugin_name" = "gitkb" || fail "bundled plugin name must be gitkb"

if jq -e 'has("hooks")' plugins/gitkb/.codex-plugin/plugin.json >/dev/null; then
  fail "plugin manifest must not use unsupported hooks field"
fi

hook_commands=$(jq -r '.. | objects | select(.type? == "command") | .command' plugins/gitkb/hooks/hooks.json)
test -n "$hook_commands" || fail "expected command hooks"
if echo "$hook_commands" | grep -v '^git-kb hook codex$' >/dev/null; then
  fail "all hooks must delegate to git-kb hook codex"
fi

if grep -R "gitkb-atc\\|@personal" . \
  --exclude-dir=.git \
  --exclude=package-policy.sh >/dev/null; then
  fail "marketplace must not contain old ATC or personal-marketplace identity"
fi

echo "Marketplace policy checks passed."
