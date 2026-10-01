#!/usr/bin/env python3
"""Run package-owned checks against the exact source selected by this catalog."""
import argparse
import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args, *, timeout=60, **kwargs):
    """Run a bounded command and propagate failures without executing shell text."""
    return subprocess.run(args, check=True, timeout=timeout, **kwargs)


def git_environment():
    """Keep source verification independent of developer Git configuration and credentials."""
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    return env


def check_tree(source_dir, source, env):
    """Compare bytes and modes to the committed tree, bypassing index flags and status hooks."""
    git = ["git", "--no-replace-objects", "-c", "core.fsmonitor=false", "-C", str(source_dir)]
    actual = subprocess.check_output([*git, "rev-parse", "HEAD"],
                                     text=True, timeout=10, env=env).strip()
    if actual != source["sha"]:
        raise RuntimeError(f"Source checkout {actual} does not match catalog {source['sha']}")
    tree = subprocess.check_output([*git, "ls-tree", "-rzl", "--full-tree", source["sha"]],
                                   timeout=10, env=env)
    expected = {}
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, digest, size = metadata.decode("ascii").split()
        if kind != "blob" or mode not in ("100644", "100755"):
            raise RuntimeError(f"Canonical source must contain regular files: {os.fsdecode(name)}")
        expected[os.fsdecode(name)] = (mode == "100755", digest, int(size))
    seen = {}
    directories = {str(parent) for name in expected for parent in Path(name).parents}
    for parent, dirs, files in os.walk(source_dir, followlinks=False):
        if Path(parent) == source_dir:
            dirs[:] = [name for name in dirs if name != ".git"]
            files = [name for name in files if name != ".git"]
        for name in dirs + files:
            path = Path(parent) / name
            relative = str(path.relative_to(source_dir))
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                if relative not in directories:
                    raise RuntimeError(f"Canonical source has unexpected directory: {relative}")
                continue
            if not stat.S_ISREG(mode):
                raise RuntimeError(f"Canonical source has non-regular file: {relative}")
            if relative not in expected or path.stat().st_size != expected[relative][2]:
                raise RuntimeError(f"Canonical source checkout has local changes: {relative}")
            # Git's blob identity includes its header; do not apply repository clean filters.
            with path.open("rb") as stream:
                size = os.fstat(stream.fileno()).st_size
                digest = hashlib.sha1(b"blob " + str(size).encode() + b"\0", usedforsecurity=False)
                while chunk := stream.read(65536):
                    digest.update(chunk)
            seen[relative] = (bool(mode & 0o111), digest.hexdigest(), size)
    changed = sorted(name for name in seen.keys() | expected.keys()
                     if seen.get(name) != expected.get(name))
    if changed:
        raise RuntimeError(f"Canonical source checkout has local changes: {changed[:20]}")


def verify(source_dir, source, codex):
    """Validate the entire checkout before delegating checks without parent credentials."""
    check_tree(source_dir, source, git_environment())
    with tempfile.TemporaryDirectory(prefix="gitkb-source-check-home-") as directory:
        (Path(directory) / "codex").mkdir()
        env = {"HOME": directory, "CODEX_HOME": str(Path(directory) / "codex"),
               "XDG_CONFIG_HOME": str(Path(directory) / "config"), "TMPDIR": directory,
               "PATH": os.environ.get("PATH", os.defpath), "CODEX_TEST_BINARY": codex,
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "1",
               "GIT_CONFIG_KEY_0": "core.fsmonitor", "GIT_CONFIG_VALUE_0": "false"}
        run(["make", "-C", str(source_dir), "release-check"], env=env)
        # Allow the shared driver's bounded installs, three launches, and cleanup to finish.
        for mode in ([], ["--legacy-first"]):
            run(["python3", "-B", str(source_dir / "tests/mcp-startup.py"), "--codex", codex,
                 "--marketplace", str(ROOT), "--expected-plugin-root", str(source_dir / "plugin"), *mode],
                env=env, timeout=300)


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
