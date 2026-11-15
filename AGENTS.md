# AGENTS.md

## No local paths or identity

This repo is public. Nothing tracked may name a particular machine or
person: no home-directory paths, no checkout locations, no key or
keystore paths, no remote names, no account names, email addresses,
domains, application IDs or certificate digests.

- Such values belong in the host config
  (`$XDG_CONFIG_HOME/fork-maint/config.yaml`), which is not tracked. In
  `fork.yaml`, a value the host must supply is `null`; add a matching
  placeholder to `config.example.yaml`.
- In `NOTES.md`, the README and comments, refer to a value by its config
  key (`deploy.app_id`, `workspace.root_repo`), not by its value.
- Paths inside this repo are relative to the fork's directory (`flake: .`).
- Generic defaults are fine: `~/.config`, `~/.local/state`, example
  locations such as `~/src/<fork>` in setup instructions.
- Exception: the `Maintainer:` line and `source=` in an `arch/PKGBUILD`.
  makepkg reads them verbatim, and the AUR publishes them anyway.
- Run logs and the merged config written next to them hold host values.
  They live under `$XDG_STATE_HOME`, never in this repo.

Before committing, check the diff for host values, including untracked
files you are about to add.
