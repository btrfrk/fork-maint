# thunderbird

- The build is the artifact build: `./mach build` downloads the prebuilt
  compiled parts (libxul and friends) from Mozilla CI for the gecko
  revision of the mozilla checkout (`workspace.root_repo`) and processes
  only the front end. No compiler, minutes instead of hours. A full
  source build, as Arch's PKGBUILD does it, has no advantage for a
  front-end patch and was rejected.
- The installed package will therefore be a nightly-track Thunderbird
  (comm main on mozilla main), not a release. Tracking releases later
  means tracking comm's release branch, where CI also publishes
  artifacts.
- Package: `arch/PKGBUILD` installs the `./mach package` tarball in the
  style of a `-bin` package, as `thunderbird-zoom` with
  `provides=thunderbird` and `conflicts=thunderbird`. With the official
  name, `pacman -Syu` would replace the build as soon as Arch bumps the
  version. Paths, desktop file name and vendor prefs match
  extra/thunderbird, so the profile and launcher pins carry over. The
  in-app updater is disabled by `distribution/policies.json` and its files
  are dropped. `check()` fails the build if `omni.ja` lacks the zoom pref.
  `thunderbird-bin` is kept: in Mozilla's packaged builds it is the real
  binary and `thunderbird` is a launcher stub that execs it, so Arch's
  trick of replacing it with the `/usr/bin` wrapper would loop back.
  Not packaged: the appdata metainfo file (extra/thunderbird takes it from
  the source tree). No langpacks are installed, so their compatibility
  with a nightly-track build has not come up.
- Downgrade protection: Thunderbird refuses a profile last opened by a
  newer version. The packaged build must not be older than what the
  profile last ran, so pull mozilla and comm main before building, and
  compare `pkgver()` with `pacman -Q thunderbird`.
- `fork-maint`: the workspace is a clone of the mozilla checkout at the
  host repo's `origin/main` with comm cloned inside, so the dev checkout is
  only fetched, never moved. `./mach build` is the fetch step: for an
  artifact build it is the download. The test, `./mach package` and
  `makepkg` run without network. The host dev tree still has its own
  objdir and mozconfig.
- Two things are kept current:
  1. The dev branch. `git -C <root_repo> pull --ff-only`, rebase comm
     `main` onto `origin/main`, then `verify`. This keeps the patch
     current for review. Never run `moz-phab submit`; updating the
     revision is the user's job.
  2. The installed package, rebuilt from the same tree.
- The mozilla checkout's own `mozconfig` is the dev copy, with the objdir
  in the tree. The flake's `mozconfig` puts the objdir under
  `$XDG_STATE_HOME/thunderbird-build` and is the one the devShell uses.
- Sandbox gap: the prebuilt binaries load GTK and X11 from `/usr/lib`. In
  a sandbox that needs a read-only `/usr` bind, or Nix libraries plus
  Nix's loader as nixpkgs' `firefox-bin` does.
- Check the built package before deploying: `zipgrep zoom_percent
  .../usr/lib/thunderbird/omni.ja` must match.
- When the patch lands, find the first release that contains it. Once
  extra/thunderbird is at that version, report that the fork can be
  retired. Also report it if review renames the pref; the user sets the
  pref by hand in the config editor.
