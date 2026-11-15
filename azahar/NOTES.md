# azahar

- The package builds with the bundled libraries (all submodules), like
  upstream's Linux builds, so the host needs no AUR packages. `fetch`
  initializes the submodules in the workspace; every later phase is
  offline.
- `arch/PKGBUILD` builds out of tree from `AZAHAR_SRC`, which `fork.yaml`
  sets to the workspace clone. It has no `source=`; nothing is pushed.
- The box home keeps makepkg's `src/build`, so a run after a small upstream
  move rebuilds incrementally. Delete `home/pkg/azahar` in the fork's state
  directory to force a clean build.
- The package provides and conflicts `azahar`, replacing the AUR package.
- The fork branch is the checkout's working branch. A run rebases it in
  place; commit or stash before a run.
