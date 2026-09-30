.PHONY: all test test-integration lint lint-json lint-policy diff-check release-check clean

all: lint test

test:
	@tests/package-policy.sh
	@python3 tests/mcp-contract.py plugins/gitkb

test-integration:
	@python3 tests/mcp-startup.py --codex "$(CODEX_TEST_BINARY)"

lint: lint-json lint-policy
	@echo "All checks passed."

lint-json:
	@echo "Checking marketplace.json is valid JSON..."
	@jq empty .agents/plugins/marketplace.json
	@echo "Checking bundled plugin manifest is valid JSON..."
	@jq empty plugins/gitkb/.codex-plugin/plugin.json
	@echo "Checking bundled hooks config is valid JSON..."
	@jq empty plugins/gitkb/hooks/hooks.json
	@echo "Checking bundled MCP config is valid JSON..."
	@jq empty plugins/gitkb/.mcp.json

lint-policy:
	@tests/package-policy.sh

diff-check:
	git diff --check

release-check: lint test diff-check

clean:
	@echo "Nothing to clean."
