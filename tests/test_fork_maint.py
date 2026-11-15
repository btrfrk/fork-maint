import argparse
import importlib.machinery
import importlib.util
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "bin/fork-maint"


def load_script():
    loader = importlib.machinery.SourceFileLoader("fork_maint", str(SCRIPT))
    spec = importlib.util.spec_from_loader("fork_maint", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


fm = load_script()


class MergeTest(unittest.TestCase):
    def test_mappings_merge_by_key(self):
        base = {"fork": {"branch": "main"}, "deploy": {"kind": "fdroid", "keep": 3}}
        over = {"fork": {"remote": "mine"}, "deploy": {"keep": 5}}
        self.assertEqual(fm.merge(base, over), {
            "fork": {"branch": "main", "remote": "mine"},
            "deploy": {"kind": "fdroid", "keep": 5},
        })

    def test_lists_and_scalars_are_replaced(self):
        self.assertEqual(fm.merge({"a": [1, 2], "b": None}, {"a": [3], "b": "x"}),
                         {"a": [3], "b": "x"})

    def test_base_is_not_modified(self):
        base = {"fork": {"branch": "main"}}
        fm.merge(base, {"fork": {"remote": "mine"}})
        self.assertEqual(base, {"fork": {"branch": "main"}})

    def test_null_keys(self):
        cfg = {"repo": None, "deploy": {"kind": "arch", "app_id": None}, "box": {"fetch": [None]}}
        self.assertEqual(list(fm.null_keys(cfg)), ["repo", "deploy.app_id"])


class LoadForkTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.forks = Path(tmp.name)
        (self.forks / "demo").mkdir()
        (self.forks / "demo/fork.yaml").write_text(textwrap.dedent("""\
            repo: null
            fork:
              branch: main
            flake: .
            box:
              build: [make]
            """))
        self.saved = fm.FORKS
        fm.FORKS = self.forks
        self.addCleanup(setattr, fm, "FORKS", self.saved)

    def test_host_values_fill_nulls(self):
        cfg = fm.load_fork("demo", {"forks": {"demo": {"repo": "~/src/demo",
                                                       "fork": {"remote": "mine"}}}})
        self.assertEqual(cfg["repo"], str(Path.home() / "src/demo"))
        self.assertEqual(cfg["fork"], {"branch": "main", "remote": "mine"})
        self.assertEqual(cfg["flake"], str(self.forks / "demo"))

    def test_unset_null_is_an_error(self):
        with self.assertRaisesRegex(fm.ForkError, r"not set: repo; add under forks\.demo"):
            fm.load_fork("demo", {})

    def test_has_box(self):
        self.assertTrue(fm.has_box(self.forks / "demo/fork.yaml"))
        (self.forks / "demo/fork.yaml").write_text("repo: null\n# box: in a comment\n")
        self.assertFalse(fm.has_box(self.forks / "demo/fork.yaml"))


class ArtifactTest(unittest.TestCase):
    def test_glob_keeps_the_name(self):
        path = Path("out/digikam-quickfilter-git-9.2.0-1-x86_64.pkg.tar.zst")
        self.assertEqual(fm.artifact_name("out/digikam-*.pkg.tar.zst", path, "digikam", "26111505"),
                         path.name)

    def test_fixed_name_gets_fork_and_build_number(self):
        path = Path("build/app-release.apk")
        self.assertEqual(fm.artifact_name(str(path), path, "fluffychat", "26111505"),
                         "fluffychat-26111505.apk")

    def test_pkginfo_version(self):
        info = "pkgname = x\npkgver = 2:9.2.0.r1.abc-3\narch = x86_64\n"
        self.assertEqual(fm.pkginfo_version(info), ("2:9.2.0.r1.abc-3", "9.2.0.r1.abc", "3"))
        self.assertEqual(fm.pkginfo_version("pkgver = 1.0-1\n"), ("1.0-1", "1.0", "1"))


class NewBaseTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in ("STATE_ROOT", "LOG_DIR"):
            self.addCleanup(setattr, fm, name, getattr(fm, name))
        fm.STATE_ROOT, fm.LOG_DIR = root / "state", root / "logs"
        self.repo = root / "repo"
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        for tag in ("v1.2", "v1.10", "v1.9"):
            subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", tag], check=True)
            subprocess.run([*git, "tag", tag], check=True)
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "tip"], check=True)

    def fork(self, track):
        cfg = {"repo": str(self.repo), "fork": {"branch": "main"},
               "upstream": {"remote": "origin", "track": track}}
        return fm.Fork("demo", cfg, argparse.Namespace())

    def rev(self, ref):
        return subprocess.run(["git", "-C", str(self.repo), "rev-parse", ref],
                              capture_output=True, text=True, check=True).stdout.strip()

    def test_tags_pick_the_highest_version(self):
        self.assertEqual(self.fork({"tags": "v1.*"}).new_base(), ("v1.10", self.rev("v1.10")))

    def test_no_matching_tag(self):
        with self.assertRaisesRegex(fm.ForkError, "no tag matches v2"):
            self.fork({"tags": "v2.*"}).new_base()

    def test_track_needs_branch_or_tags(self):
        with self.assertRaisesRegex(fm.ForkError, "needs `branch` or `tags`"):
            self.fork({}).new_base()


if __name__ == "__main__":
    unittest.main()
