#!/usr/bin/env python3
"""Exercise catalog source selection and guard against reintroducing a plugin copy."""
import copy
import json
import os
import importlib.util
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "tests/package-policy.sh"


class CatalogPolicy(unittest.TestCase):
    def check(self, change=None, artifact=None, success=False, symlink=False):
        """Check a temporary catalog without touching the repository under test."""
        manifest = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        if change:
            change(manifest)
        with tempfile.TemporaryDirectory(prefix="gitkb-catalog-policy-") as directory:
            root = Path(directory)
            target = root / ".agents/plugins/marketplace.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(manifest))
            if artifact:
                path = root / artifact
                path.parent.mkdir(parents=True, exist_ok=True)
                if symlink:
                    path.symlink_to("missing-target")
                else:
                    path.write_text("a second maintained copy")
            result = subprocess.run([str(POLICY), str(root)], capture_output=True,
                                    text=True, timeout=10)
            self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)

    def test_catalog_is_valid(self):
        """Accept the maintained immutable canonical source."""
        self.check(success=True)

    def test_source_cannot_switch_authority_or_escape_the_package(self):
        """Reject local copies, alternate repositories, and unsafe subdirectory paths."""
        for field, value in (("source", "local"), ("url", "file:///tmp/plugin"),
                             ("url", "https://github.com/other/plugin.git"),
                             ("path", "../plugin"), ("path", "/tmp/plugin")):
            with self.subTest(field=field, value=value):
                self.check(lambda doc: doc["plugins"][0]["source"].update({field: value}))

    def test_selector_is_an_immutable_commit(self):
        """Reject missing, malformed, mutable, and shell-like selectors."""
        for value in (None, "", "main", "v0.1.2", "a" * 39, "g" * 40, "$(touch sentinel)"):
            with self.subTest(value=value):
                self.check(lambda doc: doc["plugins"][0]["source"].update(sha=value))
        self.check(lambda doc: doc["plugins"][0]["source"].pop("sha"))

    def test_no_ambiguous_or_extra_source_fields(self):
        """Reject a competing mutable ref or embedded environment settings."""
        for field, value in (("ref", "main"), ("env", {"ATC_SESSION_ID": "fixed"})):
            with self.subTest(field=field):
                self.check(lambda doc: doc["plugins"][0]["source"].update({field: value}))

    def test_one_gitkb_entry(self):
        """Reject duplicate entries with the same installation identity."""
        self.check(lambda doc: doc["plugins"].append(copy.deepcopy(doc["plugins"][0])))

    def test_no_local_payload_or_copied_behavior_tests(self):
        """Reject renewed payload and test mirroring even when the source stays correct."""
        for path in ("plugins/gitkb/.mcp.json", "plugin/.mcp.json",
                     "tests/mcp-contract.py", "tests/mcp-startup.py"):
            with self.subTest(path=path):
                self.check(artifact=path)

    def test_broken_payload_symlink_is_rejected(self):
        """Reject dangling aliases that existence checks alone would miss."""
        self.check(artifact="plugin", symlink=True)


class SourceCheckout(unittest.TestCase):
    def setUp(self):
        """Prepare a real, small source tree without developer Git hooks or configuration."""
        spec = importlib.util.spec_from_file_location("source_checks", ROOT / "tests/verify-source.py")
        self.checks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.checks)
        self.directory = tempfile.TemporaryDirectory(prefix="gitkb-source-policy-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = self.checks.git_environment()
        self.env.update(GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.test",
                        GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.test")
        subprocess.run(["git", "-c", "init.templateDir=", "init", "--quiet", str(self.root)],
                       check=True, env=self.env, timeout=10)
        (self.root / "tracked").write_text("approved")
        self.git("add", "tracked")
        self.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture")
        self.source = {"sha": self.git("rev-parse", "HEAD").strip()}

    def git(self, *args):
        """Use the fixture Git repository without inheriting session-specific Git variables."""
        return subprocess.check_output(["git", "-C", str(self.root), *args],
                                       text=True, env=self.env, timeout=10)

    def reject(self, source=None):
        """Rejection must happen before any package-owned executable is launched."""
        with mock.patch.object(self.checks, "run") as execute:
            with self.assertRaises(RuntimeError):
                self.checks.verify(self.root, source or self.source, "unused")
            execute.assert_not_called()

    def test_wrong_or_dirty_checkout_cannot_run_package_code(self):
        """Reject stale identity and changed bytes before package execution."""
        self.reject({"sha": "0" * 40})
        (self.root / "tracked").write_text("tampered")
        self.reject()

    def test_index_flags_cannot_hide_modified_source(self):
        """Raw committed bytes must win over assume-unchanged and skip-worktree flags."""
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag):
                self.git("update-index", flag, "tracked")
                (self.root / "tracked").write_text("tampered")
                self.reject()
                (self.root / "tracked").write_text("approved")
                self.git("update-index", "--no-assume-unchanged", "--no-skip-worktree", "tracked")

    def test_ignored_shadow_module_is_rejected(self):
        """Ignored Python import shadows cannot execute inside a supposedly clean source tree."""
        (self.root / ".git/info").mkdir(exist_ok=True)
        (self.root / ".git/info/exclude").write_text("sitecustomize.py\n")
        (self.root / "sitecustomize.py").write_text("raise RuntimeError('unreviewed')")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.reject()

    def test_links_special_files_and_modes_are_rejected(self):
        """Reject changes to file type and executable permissions without following links."""
        tracked = self.root / "tracked"
        for kind in ("symlink", "fifo", "executable"):
            with self.subTest(kind=kind):
                tracked.unlink()
                if kind == "symlink":
                    tracked.symlink_to("missing-target")
                elif kind == "fifo":
                    os.mkfifo(tracked)
                else:
                    tracked.write_text("approved")
                    tracked.chmod(0o755)
                self.reject()

    def test_local_fsmonitor_is_never_executed(self):
        """Source validation must not invoke a repository-configured Git status hook."""
        hook = self.root / ".git/fsmonitor"
        marker = self.root / ".git/executed"
        hook.write_text("#!/bin/sh\ntouch " + str(marker) + "\n")
        hook.chmod(0o755)
        self.git("config", "core.fsmonitor", str(hook))
        with mock.patch.object(self.checks, "run"):
            self.checks.verify(self.root, self.source, "unused")
        self.assertFalse(marker.exists(), "verification executed an unreviewed fsmonitor hook")

    def test_replace_refs_cannot_substitute_unapproved_tree(self):
        """A local Git replacement must not change which committed bytes are approved."""
        (self.root / "tracked").write_text("tampered")
        self.git("add", "tracked")
        self.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "unreviewed")
        substitute = self.git("rev-parse", "HEAD").strip()
        self.git("update-ref", "HEAD", self.source["sha"])
        self.git("replace", self.source["sha"], substitute)
        self.reject()

    def test_committed_links_are_not_executable_source(self):
        """Even a tracked symlink may not make package checks read outside the approved tree."""
        (self.root / "alias").symlink_to("tracked")
        self.git("add", "alias")
        self.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "symlink fixture")
        self.source["sha"] = self.git("rev-parse", "HEAD").strip()
        self.reject()

    def test_valid_source_with_unusual_paths(self):
        """NUL-delimited tree parsing preserves tabs, newlines, spaces, and Unicode filenames."""
        path = self.root / "nested" / "quoted ' ü\tline\nfile"
        path.parent.mkdir()
        path.write_text("approved")
        self.git("add", "nested")
        self.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "path fixture")
        self.source["sha"] = self.git("rev-parse", "HEAD").strip()
        with mock.patch.object(self.checks, "run") as execute:
            self.checks.verify(self.root, self.source, "unused")
        self.assertEqual(execute.call_count, 3)

    def test_valid_source_runs_without_parent_credentials_or_hooks(self):
        """Delegate both checks with an owned home and a minimal environment."""
        canaries = {name: "synthetic-canary" for name in
                    ("OPENAI_API_KEY", "SESSION_ACTIVITY_RESOURCE_ID", "ATC_ROOT", "PYTHONPATH", "BASH_ENV")}
        with mock.patch.dict(os.environ, canaries), mock.patch.object(self.checks, "run") as execute:
            self.checks.verify(self.root, self.source, "/provider/codex")
        self.assertEqual(execute.call_count, 3)
        for call in execute.call_args_list:
            env = call.kwargs["env"]
            self.assertTrue(set(canaries).isdisjoint(env))
            self.assertNotEqual(env["HOME"], os.environ["HOME"])
            self.assertEqual(env["CODEX_HOME"], str(Path(env["HOME"]) / "codex"))


if __name__ == "__main__":
    unittest.main()
