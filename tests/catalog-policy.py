#!/usr/bin/env python3
"""Exercise catalog source selection and guard against reintroducing a plugin copy."""
import copy
import json
import importlib.util
import subprocess
import tempfile
import unittest
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
    def test_wrong_or_dirty_checkout_cannot_run_package_code(self):
        """Use real Git state to reject stale or modified checkouts before executing their tests."""
        spec = importlib.util.spec_from_file_location("source_checks", ROOT / "tests/verify-source.py")
        checks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checks)
        with tempfile.TemporaryDirectory(prefix="gitkb-source-policy-") as directory:
            root = Path(directory)
            env = checks.git_environment()
            env.update(GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.test",
                       GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.test")
            subprocess.run(["git", "-c", "init.templateDir=", "init", "--quiet", str(root)],
                           check=True, env=env, timeout=10)
            (root / "tracked").write_text("approved")
            subprocess.run(["git", "-C", str(root), "add", "tracked"], check=True, env=env, timeout=10)
            subprocess.run(["git", "-C", str(root), "-c", "commit.gpgsign=false",
                            "commit", "--quiet", "-m", "fixture"], check=True, env=env, timeout=10)
            sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                          text=True, env=env, timeout=10).strip()
            with self.assertRaisesRegex(RuntimeError, "does not match catalog"):
                checks.verify(root, {"sha": "0" * 40}, "unused")
            (root / "tracked").write_text("unreviewed")
            with self.assertRaisesRegex(RuntimeError, "local changes"):
                checks.verify(root, {"sha": sha}, "unused")


if __name__ == "__main__":
    unittest.main()
