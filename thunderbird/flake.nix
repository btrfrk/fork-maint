{
  description = "Thunderbird (comm-central) artifact build environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { nixpkgs, ... }:
    let
      pkgs = import nixpkgs { system = "x86_64-linux"; };
    in
    {
      devShells.x86_64-linux.default = pkgs.mkShell {
        packages = [
          pkgs.python3
          pkgs.git
          pkgs.nodejs
          pkgs.unzip
        ];

        shellHook = ''
          if [ -n "''${THUNDERBIRD_STATE_DIR:-}" ]; then
            state=$THUNDERBIRD_STATE_DIR
          elif [ -n "''${XDG_STATE_HOME:-}" ]; then
            state=$XDG_STATE_HOME/thunderbird-build
          elif [ -n "''${HOME:-}" ]; then
            state=$HOME/.local/state/thunderbird-build
          else
            echo "flake.nix: set THUNDERBIRD_STATE_DIR or HOME" >&2
            exit 1
          fi
          mkdir -p "$state" || { echo "flake.nix: cannot create $state" >&2; exit 1; }
          export MOZBUILD_STATE_PATH=''${MOZBUILD_STATE_PATH:-$state/mozbuild}
          export MOZCONFIG=''${MOZCONFIG:-${./mozconfig}}
          export MOZ_OBJDIR=''${MOZ_OBJDIR:-$state/obj-artifact}
        '';
      };
    };
}
