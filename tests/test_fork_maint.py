import argparse
import importlib.machinery
import importlib.util
import subprocess
import tempfile
import textwrap
import unittest
import unittest.mock
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
        path = Path("out/digikam-btrfrk-9.2.0-1-x86_64.pkg.tar.zst")
        self.assertEqual(fm.artifact_name("out/digikam-*.pkg.tar.zst", path, "digikam", "26111505"),
                         path.name)

    def test_fixed_name_gets_fork_and_build_number(self):
        path = Path("build/app-release.apk")
        self.assertEqual(fm.artifact_name(str(path), path, "fluffychat", "26111505"),
                         "fluffychat-26111505.apk")

    def test_earlier_artifacts_are_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "out").mkdir()
            old = ws / "out/thunderbird-btrfrk-162.0a1.1-1-x86_64.pkg.tar.zst"
            other = ws / "out/notes.txt"
            old.touch()
            other.touch()
            fm.remove_artifacts(ws, "out/thunderbird-btrfrk-*.pkg.tar.zst")
            self.assertFalse(old.exists())
            self.assertTrue(other.exists())

    def test_pkginfo_version(self):
        info ="pkgname = x\npkgver = 2:9.2.0.r1.abc-3\narch = x86_64\n"
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


class SrcinfoTest(unittest.TestCase):
    SRCINFO = textwrap.dedent("""\
        pkgbase = demo
        \tpkgver = 1
        \tmakedepends = cmake
        \tmakedepends = qt6-tools>=6.5
        \tcheckdepends = python
        \tdepends = qt6-base
        \tdepends = cmake
        \tdepends_x86_64 = lib32-demo
        \tdepends_aarch64 = arm-demo
        \toptdepends = ffmpeg: video

        pkgname = demo
        """)

    def test_names_without_constraints_or_duplicates(self):
        self.assertEqual(fm.srcinfo_deps(self.SRCINFO, "x86_64"),
                         ["cmake", "qt6-tools", "python", "qt6-base", "lib32-demo"])

    def test_other_machines_entries_are_skipped(self):
        self.assertIn("arm-demo", fm.srcinfo_deps(self.SRCINFO, "aarch64"))
        self.assertNotIn("lib32-demo", fm.srcinfo_deps(self.SRCINFO, "aarch64"))


class RootfsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in ("STATE_ROOT", "LOG_DIR", "FORKS"):
            self.addCleanup(setattr, fm, name, getattr(fm, name))
        fm.STATE_ROOT, fm.LOG_DIR, fm.FORKS = root / "state", root / "logs", root / "forks"
        (fm.FORKS / "demo").mkdir(parents=True)

    def fork(self, **cfg):
        fork = fm.Fork("demo", {"repo": "/nonexistent", "fork": {"branch": "main"}, **cfg},
                       argparse.Namespace())
        (fork.state / "env.sh").write_text("")
        fork.shell = "/usr/bin/bash"
        return fork

    def binds(self, fork):
        with unittest.mock.patch.object(fm, "run") as run:
            fork.box("true", fork.log("test"))
        argv = run.call_args.args[0]
        return {argv[i + 2]: argv[i + 1] for i, a in enumerate(argv) if a == "--ro-bind"}

    def test_box_binds_the_host_system_without_rootfs(self):
        binds = self.binds(self.fork())
        self.assertEqual(binds["/usr"], "/usr")
        self.assertEqual(binds["/etc"], "/etc")

    def test_box_binds_the_root_with_rootfs(self):
        fork = self.fork(rootfs="arch")
        (fork.root / "var/lib/pacman").mkdir(parents=True)
        binds = self.binds(fork)
        self.assertEqual(binds["/usr"], str(fork.root / "usr"))
        self.assertEqual(binds["/etc"], str(fork.root / "etc"))
        self.assertEqual(binds["/var/lib/pacman"], str(fork.root / "var/lib/pacman"))
        self.assertEqual(binds["/etc/passwd"], "/etc/passwd")
        self.assertEqual(binds["/etc/makepkg.conf"], "/etc/makepkg.conf")

    def test_rootfs_outside_the_fork_is_rejected(self):
        (fm.FORKS / "demo/fork.yaml").write_text("rootfs: ../other\n")
        with self.assertRaisesRegex(fm.ForkError, "not inside the fork's directory"):
            fm.load_fork("demo", {})

    def test_root_too_deep_for_the_agent_socket(self):
        fm.STATE_ROOT = fm.STATE_ROOT / ("d" * 60)
        fork = self.fork(rootfs="arch")
        with unittest.mock.patch.object(fm, "run") as run:
            with self.assertRaisesRegex(fm.ForkError, "too deep for gpg-agent"):
                fork.prepare_root()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class AurTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = root = Path(tmp.name)
        for name in ("STATE_ROOT", "LOG_DIR", "FORKS"):
            self.addCleanup(setattr, fm, name, getattr(fm, name))
        fm.STATE_ROOT, fm.LOG_DIR, fm.FORKS = root / "state", root / "logs", root / "forks"
        arch = fm.FORKS / "demo/arch"
        arch.mkdir(parents=True)
        (arch / "PKGBUILD").write_text(textwrap.dedent("""\
            pkgname=demo
            pkgver=0
            pkgrel=1
            arch=(any)
            package() { :; }
            """))
        subprocess.run(["git", "init", "-q", str(fm.FORKS)], check=True)
        subprocess.run(["git", "-C", str(fm.FORKS), "add", "."], check=True)
        (root / ".PKGINFO").write_text("pkgname = demo\npkgver = 1.0-1\n")
        self.artifact = root / "demo-1.0-1-any.pkg.tar"
        subprocess.run(["bsdtar", "-cf", str(self.artifact), "-C", str(root), ".PKGINFO"],
                       check=True)

    def bare(self, name):
        path = self.root / f"{name}.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(path)], check=True)
        return str(path)

    def deploy(self, url):
        fork = fm.Fork("demo", {"repo": str(self.root), "fork": {"branch": "main"},
                                "deploy": {"aur": url}},
                       argparse.Namespace(no_deploy=False, no_push=False))
        fork.artifact = self.artifact
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        with unittest.mock.patch.dict("os.environ", env):
            fork.deploy_aur()

    def files(self, url):
        return subprocess.run(["git", "-C", url, "ls-tree", "--name-only", "master"],
                              capture_output=True, text=True, check=True).stdout.split()

    def test_new_package(self):
        url = self.bare("new")
        self.deploy(url)
        self.assertEqual(self.files(url), [".SRCINFO", "PKGBUILD"])

    def test_renamed_package_goes_to_the_new_url(self):
        old, new = self.bare("old"), self.bare("new")
        self.deploy(old)
        self.deploy(new)
        self.assertEqual(self.files(new), [".SRCINFO", "PKGBUILD"])
        log = subprocess.run(["git", "-C", new, "log", "--oneline", "master"],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(len(log.splitlines()), 1)
