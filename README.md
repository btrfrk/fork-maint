# forks

Patch stacks carried on top of upstream projects, and `fork-maint`, the
script that keeps them current: fetch upstream, rebase the fork branch,
build in a sandbox without network, push, sign and deploy, and write a
report. When a fork is blocked, it can hand the failing step to one
headless agent turn and then rerun the fork to check the result.

The forks here:

| Fork | Upstream | Patch | Ships as |
|---|---|---|---|
| `digikam` | digiKam master | quick filter toolbar, "Open With External Editor" | Arch package on the AUR |
| `fluffychat` | FluffyChat main | personal chat names, a Matrix SDK fix, release build setup | APK in an F-Droid repo |
| `thunderbird` | comm-central main | message zoom pref (bug 1689030) | local Arch package |

## Requirements

- Linux, Python 3.11+ with PyYAML, git, bubblewrap (`bwrap`).
- Nix with flakes, for forks with a `flake`.
- Arch forks: `makepkg`, `bsdtar`, and the PKGBUILD's dependencies
  installed on the host.
- F-Droid forks: `fdroidserver` and an initialized F-Droid repo.
- Agent turns (optional): `aisan` and the `claude` or `codex` CLI.

## Setup

```sh
git clone <this repo> ~/src/forks
mkdir -p ~/.config/fork-maint
cp ~/src/forks/config.example.yaml ~/.config/fork-maint/config.yaml
$EDITOR ~/.config/fork-maint/config.yaml
ln -s ~/src/forks/bin/fork-maint ~/.local/bin/
```

To run it daily:

```sh
systemctl --user link ~/src/forks/systemd/fork-maint.service ~/src/forks/systemd/fork-maint.timer
systemctl --user enable --now fork-maint.timer
```

## Layout

One directory per fork:

| File | Contents |
|---|---|
| `fork.yaml` | the facts: upstream, what to track, fork branch, inputs, verify, build, deploy |
| `NOTES.md` | quirks that do not fit a key: conflict patterns, upstream policy, traps |
| `flake.nix`, `flake.lock` | the build environment as a Nix devShell |
| `arch/` | PKGBUILD and patches for forks installed as Arch packages; sources only. The box copies the whole directory, so build here only through `fork-maint` (`makepkg -g` alone leaves a source mirror that the boxed makepkg then prefers over its `SRCDEST`) |

`agent/prompt.md` is the prompt for agent turns. `tests/` has unit tests
for the parts of `fork-maint` that need no sandbox:

```sh
python3 -m unittest discover tests
```

## Configuration

`fork.yaml` holds what is true on any machine. The host config,
`$XDG_CONFIG_HOME/fork-maint/config.yaml` or the file named by
`FORK_MAINT_CONFIG`, holds what is specific to one: checkouts, remotes,
keys, the deploy target. `forks.<name>` in it is merged over
`<name>/fork.yaml`, mappings key by key. A `null` in `fork.yaml` marks a
value the host config must supply; a fork with one left unset is
reported and skipped. `config.example.yaml` shows every such key.

Keys `fork-maint` reads:

| Key | Meaning |
|---|---|
| `repo`, `fork.branch`, `fork.remote` | the checkout, the patch branch, where to push it (`--force-with-lease`); no push without `fork.remote` |
| `upstream.remote`, `upstream.track` | `branch: <name>` or `tags: <glob>` |
| `rebase.upstream_wins` | files where upstream's side is taken at a conflict (lock files) |
| `inputs` | directories bound read-only at `/inputs/<name>`, exported as `INPUT_<name>` |
| `flake` | the devShell, a path relative to the fork's directory; the host realizes it and passes `nix print-dev-env` into the box |
| `workspace.root_repo`, `root_track`, `subdir` | when the fork repo sits inside another tree (comm inside mozilla): the workspace is a clone of that tree at the host repo's `root_track`, with the fork repo cloned into `subdir` |
| `box.fetch` | shell commands with network: fill caches from lock files and pinned versions |
| `box.prepare`, `box.verify`, `box.build` | shell commands without network, in order in the workspace; `BUILD_NUMBER` is the UTC `yymmddHH`, `BOX_KEYSTORE` a throwaway key, `FORK_DIR` the fork's directory here |
| `box.artifact` | path or glob of the build output in the workspace; a glob keeps the file name |
| `deploy.kind` | `fdroid` or `arch`, below |

`deploy.kind: fdroid` re-signs the APK with `deploy.keystore`,
`key_alias` and `key_pass_file`, checks that `deploy.cert_sha256` is the
only signer and `deploy.app_id` the package, refuses a versionCode not
above the repo's, copies the APK into `deploy.repo_dir`, runs
`fdroid update && fdroid deploy` and keeps `deploy.keep` APKs.

`deploy.kind: arch` puts the `pacman -U` command in the report. With
`deploy.aur`, the URL of the package's AUR repo, the tracked files of
`arch/` are pushed there when they differ from the AUR's, with the built
version in the PKGBUILD and a regenerated `.SRCINFO`. Where `pkgver()`
computes the version, a new version alone is not a change.

`patches`, `package`, `deployed_check` and `upstreaming` are notes for
whoever maintains the fork by hand; the script ignores them.

The host config's `agent` section configures agent turns, below.

## A run

`fork-maint [--force] [--no-push] [--no-deploy] [--no-agent] [fork ...]`
processes the named forks, or every fork with a `box:` section, one at a
time. A failure in one never stops the others. `--force` runs a fork
even when nothing moved, `--no-push` skips pushing the branch and the
AUR, `--no-deploy` stops after signing.

Per fork: fetch upstream and inputs; stop if the base did not move and
the branch tip is built (and deployed, for `fdroid`); back the branch up
as `backup/<branch>-<date>`; rebase it; realize the devShell; run the
box phases in a clone of the fork repo; push; sign and deploy on the
host.

The box is bwrap with its own namespaces: `/usr`, `/etc` and
`/nix/store` read-only, a persistent box home under
`$XDG_STATE_HOME/fork-maint/<fork>/home` mounted over the real home, the
workspace clone read-write, declared inputs read-only under `/inputs/`,
the fork's directory of this repo read-only at `/work/fork`. No keys and
no deploy target inside; those are host-side steps that run only after
the box succeeded.

Network: only the `fetch` phase has a route. It fills the caches in the
box home and the workspace from lock files and pinned versions and, for
Gradle, resolves every configuration through an init script.
`prepare`, `verify` and `build` run with the network namespace closed,
so a build that needs something fetch did not provide fails instead of
downloading.

Without `flake`, the box runs the system toolchain (makepkg). The box
sees `/var/lib/pacman` read-only for makepkg's dependency check; the
packages themselves, `makedepends` included, must be installed on the
host. fakeroot works in the box because `FAKEROOTDONTTRYCHOWN` is set:
with one uid mapped, a real chown fails with EINVAL, not EPERM.

To build by hand, use the devShell with the host environment cleared,
from the fork's source tree:

```sh
nix develop ~/src/forks/<fork> -i --keep HOME -c <command>
```

Plain `nix develop` prepends to the host `PATH`, so a missing tool would
come from `/usr/bin` unnoticed.

Output goes to `$XDG_STATE_HOME/fork-maintenance/<date>/`: one log per
step, `report.md`, and per fork `<fork>.json` (status, failing step,
paths) and `<fork>-config.yaml` (the merged config). Tags in the fork
repo: `fork-built` after a successful build, `fork-deployed` after an
automatic deploy. A rebase conflict is aborted and reported; the branch
is left as it was. A fork without `box:` is reported as not automated.

## The agent on failure

With `agent.harness` set to `claude` or `codex` in the host config, a
fork blocked at rebase, verify or build gets one headless agent turn,
then one more pass of that fork, which is the judge. `agent.max_turns`
(claude only) and `agent.timeout_minutes` bound the turn; `agent.model`
is passed to codex. The prompt is `agent/prompt.md`, with the fork's
merged config and `NOTES.md` as its facts and rules.

The turn runs inside aisan: `aisan claude <repo> --binds ... -- -p
<prompt> --permission-mode bypassPermissions --max-turns N`, or `aisan
codex <repo> --binds ... -- exec <prompt>`. The sandbox roots at the
fork's checkout, read-write, and sees this repo and the day's log
directory read-only. No keys, no SSH, no network, model calls through
aisan's proxy. The agent can commit on the fork branch and nothing
else; pushing, signing and deploying stay with the script and happen
only after its rerun passed. `--no-agent` skips the turn;
`<fork>-agent.log` holds the transcript and `<fork>.json` the outcome.

## Rules

- Flakes pin toolchains only. Paths, keys and credentials come from the
  host config, as environment variables or Gradle properties.
- No secrets in this repo, and no host paths.
- Arch forks are plain PKGBUILDs installed with `pacman -U`. There is no
  package repository.
- Android forks ship through an F-Droid repo, signed with a release key
  the host holds, under the fork's own application ID, so they install
  next to upstream's app.

## Cadence

`upstream.track` says which upstream revisions a fork follows, and so
when it is rebuilt:

- `branch: <name>`: every upstream commit past the deployed one. The
  current setting for all forks.
- `tags: <glob>`: release tags matching the glob. The target for apps used
  daily, where main's breakage is not wanted.

Switching a fork is a one-line change in its `fork.yaml`.

## Adding a fork

Copy the shape of an existing directory, and add its host values under
`forks.<name>` in the host config. Find the fork branch and its base with
`git log --oneline <upstream>..<branch>`. Record where the artifacts land
and how the current installation was deployed; do not guess from the
upstream README.

## License

MIT, see `LICENSE`. The patches themselves live in the fork repositories,
under the upstream projects' licenses.
