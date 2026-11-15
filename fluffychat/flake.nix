{
  description = "FluffyChat build environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { nixpkgs, ... }:
    let
      pkgs = import nixpkgs {
        system = "x86_64-linux";
        config = {
          allowUnfree = true;
          android_sdk.accept_license = true;
        };
      };

      buildToolsVersion = "36.0.0";
      android = pkgs.androidenv.composeAndroidPackages {
        # compileSdk of the app and of its Android plugins.
        platformVersions = [
          "34"
          "35"
          "36"
          "37.0"
        ];
        buildToolsVersions = [ buildToolsVersion ];
        includeNDK = true;
        ndkVersions = [ "28.2.13676358" ];
        cmakeVersions = [ "3.22.1" ];
      };
      sdk = "${android.androidsdk}/libexec/android-sdk";
      flutter = pkgs.flutterPackages.v3_47;
    in
    {
      devShells.x86_64-linux.default = pkgs.mkShell {
        packages = [
          flutter
          pkgs.jdk17
          android.androidsdk
          # cargokit (flutter_vodozemac) drives rustup itself and requests the
          # unpinned "stable" toolchain.
          pkgs.rustup
          pkgs.cmake
          pkgs.ninja
          pkgs.python3
          pkgs.git
          pkgs.curl
          # scripts/prepare_vodozemac.sh reads the pinned version from pubspec.lock
          pkgs.yq-go
          # golden_screenshot:download_apple_fonts unpacks a dmg; p7zip
          # cannot read the cpio payload inside.
          pkgs._7zz
        ];

        ANDROID_HOME = sdk;
        ANDROID_SDK_ROOT = sdk;
        JAVA_HOME = pkgs.jdk17.home;
        # Gradle's aapt2 from Maven is an unpatched dynamic binary.
        GRADLE_OPTS = "-Dorg.gradle.project.android.aapt2FromMavenOverride=${sdk}/build-tools/${buildToolsVersion}/aapt2";

        # Gradle refuses read-only project directories, and Flutter includes
        # plugin projects from its SDK (packages/integration_test/android). Use
        # a writable tree of directories whose files link into the store.
        shellHook = ''
          if [ -n "''${FLUFFYCHAT_STATE_DIR:-}" ]; then
            state=$FLUFFYCHAT_STATE_DIR
          elif [ -n "''${XDG_STATE_HOME:-}" ]; then
            state=$XDG_STATE_HOME/fluffychat
          elif [ -n "''${HOME:-}" ]; then
            state=$HOME/.local/state/fluffychat
          else
            echo "flake.nix: set FLUFFYCHAT_STATE_DIR or HOME" >&2
            exit 1
          fi
          flutter_sdk=${flutter.sdk}
          flutter_root=$state/flutter-sdk/$(basename "$flutter_sdk")
          if [ ! -d "$flutter_root" ]; then
            mkdir -p "$state/flutter-sdk" &&
              tmp=$(mktemp -d "$state/flutter-sdk/tmp.XXXXXX") &&
              cp -r --no-dereference "$flutter_sdk/." "$tmp" &&
              chmod -R u+w "$tmp" &&
              mv "$tmp" "$flutter_root" ||
              { echo "flake.nix: cannot create $flutter_root" >&2; exit 1; }
          fi
          export FLUTTER_ROOT=$flutter_root
          export PATH=$flutter_root/bin:$PATH
          export RUSTUP_HOME=''${RUSTUP_HOME:-$state/rustup}
          export CARGO_HOME=''${CARGO_HOME:-$state/cargo}
        '';
      };
    };
}
