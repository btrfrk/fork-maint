# pingvin-share-x

- `flake.nix` builds the image with `dockerTools`, from the workspace clone
  as input `src`; upstream's Dockerfile is not used. The image has the
  layout of upstream's (`/opt/app`, the same entrypoint scripts), on nix's
  glibc instead of Alpine.
- The image follows upstream's `Dockerfile` and `scripts/docker/` by hand.
  `reviewedRecipe` holds their sha256 sums; when upstream changes one, the
  flake refuses to evaluate and names the file. Port the change (new
  packages, files, environment), then update the sums the error prints.
- `nixpkgs-prisma` pins the nixpkgs revision with `prisma-engines` at the
  version in `backend/package-lock.json`. The client accepts only engines
  built from its own commit: when upstream bumps prisma, move the pin to a
  nixpkgs revision with that version (search nixpkgs for
  `prisma-engines: <old> -> <new>`).
- `importNpmLock` fetches each package by the integrity hash in the lock
  file, so a lock change needs no hash update here. It replaces the direct
  dependencies' ranges with store paths; the flake rewrites `overrides`
  entries for direct dependencies to `$<name>`, or npm rejects them.
- npm runs no install scripts (not in `allowScripts`). argon2 and sharp load
  their prebuilt glibc modules, and prisma takes the engines from
  `PRISMA_QUERY_ENGINE_LIBRARY` and `PRISMA_SCHEMA_ENGINE_BINARY`.
- Prisma warns at startup that it cannot detect the libssl version. The
  engines come from the environment, so the warning has no effect.
- The image is tagged `pingvin-share-x:latest`.
