# fluffychat

- Upstream forbids LLM-written changes in its repository. The `Update
  policy` commit removes `AGENTS.md`. Keep it first in the stack; if
  upstream edits the file, keep the removal. Anything for upstream (a PR,
  a comment on #2120) is written by the user. Don't draft it, and don't
  present fork commits as ready to upstream.
- The fork branch is `working`. `private_chat_names` is an older copy of
  the stack and is not maintained.
- `pubspec.lock`: upstream's version wins at a conflict
  (`rebase.upstream_wins` in `fork.yaml`, a `merge=ours` attribute that
  `fork-maint` configures in the repo). `flutter pub get` in the box
  re-resolves the lock from `pubspec_overrides.yaml`; the committed lock
  does not need the fork's path sources. After a rebase, look at the SDK
  commit upstream's lock resolves to (`git show origin/main:pubspec.lock`,
  `resolved-ref` under `matrix`). If it differs from `base=` in
  `scripts/prepare-matrix-sdk.sh`:
  1. Fetch `inputs.matrix_sdk` and rebase the patch onto the new commit
     there (`build/matrix-sdk-dev` is the scratch clone for patch work).
  2. Regenerate `patches/matrix-sdk-token-refresh.patch`. Update `base=`
     in the script and the commit and version named in `patches/README.md`.
  3. Move `build/matrix-sdk` aside, rerun `prepare`.
  4. Run the SDK tests from `patches/README.md`. Fold the changes into the
     token-refresh commit.
- `scripts/prepare-pub-packages.sh` pins two pub.dev archives by version
  and sha256 and patches them for `compileSdk 37`. When upstream bumps
  `flutter_vodozemac` or `flutter_shortcuts_new`, update version and hash
  in the script and check that the patches still apply. If a new version
  no longer needs a patch, drop it from the script and from
  `pubspec_overrides.yaml`.
- `flutter build` does not re-resolve after a `pubspec_overrides.yaml`
  change. Run `flutter pub get`.
- versionCode: `fork-maint` passes `--build-number=<UTC yymmddHH>` to
  `flutter build`, so every build is newer than the one before and the
  stack does not need a `version:` bump in `pubspec.yaml`. Take upstream's
  version line at a conflict. The deploy step refuses a versionCode that is
  not above the repo's.
- Signing: the box builds with a throwaway key in its home, the host
  re-signs with `apksigner` and checks that the only signer is the release
  key (`deploy.cert_sha256`) before the APK enters the F-Droid repo.
- If upstream needs a newer Flutter than the flake pins
  (`flutterPackages.v3_47`), check `environment:` in `pubspec.yaml` and
  the version in `.github/workflows`. Report it and stop. Don't change the
  flake during a run.
- Flake: nixpkgs' Flutter is read-only and Gradle refuses read-only plugin
  project directories, so the shellHook keeps a writable directory tree
  with files linked into the store, one per SDK store path. Rust is
  unpinned: cargokit runs `rustup` itself and requests `stable`.
- `android/app/src/main/res/raw/keep.xml` keeps `notifications_icon`
  from resource shrinking. Dart names it only as a string, so without the
  keep rule the release APK lacks it and flutter_local_notifications
  fails to initialize: no notifications. The last `box.build` command
  checks the APK for it.
- The installed app is `deploy.app_id`, signed with the release key. A
  debug-key build, `chat.fluffy.fluffychat.dev`, may be installed next to
  it.
