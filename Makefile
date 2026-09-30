.PHONY: all test test-integration lint lint-json lint-policy diff-check release-check clean

all: lint test

test:
	@tests/package-policy.sh
	@python3 tests/catalog-policy.py

test-integration:
	@python3 tests/verify-source.py --codex "$(CODEX_TEST_BINARY)" $(if $(CANONICAL_SOURCE_DIR),--source-checkout "$(CANONICAL_SOURCE_DIR)")

lint: lint-json lint-policy
	@echo "All checks passed."

lint-json:
	@echo "Checking marketplace catalog is valid JSON..."
	@jq empty .agents/plugins/marketplace.json

lint-policy:
	@tests/package-policy.sh

diff-check:
	git diff --check

release-check: lint test diff-check

clean:
	@echo "Nothing to clean."
