#!/usr/bin/env python3
"""Run package-owned checks against the exact source selected by this catalog."""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    """Run a bounded command and propagate failures without executing shell text."""
    return subprocess.run(args, check=True, timeout=60, **kwargs)


def git_environment():
    """Keep source verification independent of developer Git configuration and credentials."""
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    return env


def verify(source_dir, source, codex):
    """Verify the checkout identity and reuse its package and real Codex startup tests."""
    env = git_environment()
    actual = subprocess.check_output(["git", "-C", str(source_dir), "rev-parse", "HEAD"],
                                     text=True, timeout=10, env=env).strip()
    if actual != source["sha"]:
        raise RuntimeError(f"Source checkout {actual} does not match catalog {source['sha']}")
    dirty = subprocess.check_output(["git", "-C", str(source_dir), "status", "--porcelain"],
                                    text=True, timeout=10, env=env).strip()
    if dirty:
        raise RuntimeError(f"Canonical source checkout has local changes: {dirty[:4000]}")
    run(["make", "-C", str(source_dir), "release-check"], env=env)
    run(["python3", str(source_dir / "tests/mcp-startup.py"), "--codex", codex,
         "--marketplace", str(ROOT), "--expected-plugin-root", str(source_dir / "plugin")])


def main():
    """Fetch the declared source or verify a provided CI checkout before using its tests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", required=True)
    parser.add_argument("--source-checkout", type=Path)
    args = parser.parse_args()
    if not args.codex:
        parser.error("pass the provider binary via CODEX_TEST_BINARY")
    run([str(ROOT / "tests/package-policy.sh"), str(ROOT)])
    manifest = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    source = next(item["source"] for item in manifest["plugins"] if item["name"] == "gitkb")
    print(f"Verifying {source['url']} at {source['sha']}", flush=True)
    if args.source_checkout:
        verify(args.source_checkout.resolve(), source, args.codex)
        return
    with tempfile.TemporaryDirectory(prefix="gitkb-canonical-source-") as directory:
        source_dir = Path(directory)
        # Public immutable source: avoid developer Git credentials, templates and URL rewrites.
        env = git_environment()
        run(["git", "-c", "init.templateDir=", "init", "--quiet", str(source_dir)], env=env)
        run(["git", "-C", str(source_dir), "fetch", "--quiet", "--depth=1",
             source["url"], source["sha"]], env=env)
        run(["git", "-C", str(source_dir), "checkout", "--quiet", "--detach", "FETCH_HEAD"], env=env)
        verify(source_dir, source, args.codex)


if __name__ == "__main__":
    main()
