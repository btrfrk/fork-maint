# pingvin-share-x

- Built with the fork's Dockerfile by the host's docker daemon, not in the
  box. The daemon must be running, and the user needs access to its socket.
- Two patches split `apk add` out of `backend-builder` and the final stage
  (`backend-builder-base`, `runner-base`), so the downloads sit in stages of
  their own that the fetch step can build. When upstream changes those
  stages, keep the split; a new download step outside the `docker.fetch`
  stages fails the offline build.
- `npm ci` leaves the prisma engines in `/root/.cache/prisma`; upstream's
  backend builder does not copy it, so `prisma generate` downloads them
  again. A patch copies the cache.
- The artifact is a gzipped `docker save` archive of `<image>:<BUILD_NUMBER>`.
  The daemon keeps only the latest tag.
