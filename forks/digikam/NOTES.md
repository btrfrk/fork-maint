# digikam

- `fork-maint` builds the package in the box from a mirror of the
  workspace (`makepkg --holdver` with the mirror in `SRCDEST`), so the
  build does not depend on the push and needs no network. It pushes the
  branch to `fork.remote` only after the build succeeded; AUR users build
  from the branch that `source=` in `arch/PKGBUILD` names. A full build
  each time upstream moves: about an hour.
- By hand, the package builds from that pushed branch: push the rebased
  branch before `makepkg`, or the build picks up the old branch.
- Never push the branch to GitHub. GitHub rejects the history: old
  bundled DNN weights exceed its 100 MB blob limit.
- Leave the other local branches alone (`split/*`, `filterbar*`,
  `ext-editor`, `master`) and the tag `filterbar-preupstream-backup`.
  They are older working branches from a past upstreaming attempt.
- `prepare()` lifts the configure-time cap on OpenCV 5.x with a sed on
  `OPENCV_MAX_VERSION` and a grep behind it. Upstream carries the port
  (bug 522887) but still refuses 5.x. Once upstream drops the cap the grep
  fails; then drop the sed. It was a patch until 2026-10-31, when a
  comment change next to the line broke it.
- OpenCV 5.1 has no `cv::dnn::readNetFromTensorflow`, which the aesthetic
  detector (`core/libs/imgqsort/detectors/aesthetic_detector.cpp`) and
  `core/tests/imgqsort/NIMA_inference_cli.cpp` call. The commit "Guard
  readNetFromTensorflow for OpenCV 5" puts those calls behind
  `CV_VERSION_MAJOR < 5`: on OpenCV 5 the model does not load and
  aesthetic scoring is off, failing the way a missing model file does.
  Keep it as its own commit on top of the stack, apart from the quick
  filter patches, and drop it once upstream loads the model another way.
- `fork-maint` publishes `arch/` to the AUR (`deploy.aur`) after a build,
  when the PKGBUILD or a patch changed; `git add` new files, untracked
  ones are not copied. A change goes out with the next run that builds:
  when upstream moves, or `fork-maint --force digikam`. A failed AUR push
  is retried the same way.
- `pkgrel` in `arch/PKGBUILD` has no effect while `pkgver` there is
  stale: `makepkg` resets it to 1 whenever `pkgver()` yields a new
  version.
- Compare `depends` against `extra/digikam` now and then:
  `https://gitlab.archlinux.org/archlinux/packaging/packages/digikam/-/raw/main/PKGBUILD`.
  Report meaningful drift.
- Every automated push of the branch reaches AUR users.
