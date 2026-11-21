{
  description = "pingvin-share-x image";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # prisma-engines 6.6.0, the version in backend/package-lock.json. The
    # client accepts only engines built from its own commit.
    nixpkgs-prisma.url = "github:NixOS/nixpkgs/76bbc62a9c80d7fc9be22bbba264b8d7a32eda6e";
    # The source tree; fork-maint overrides it with the workspace clone.
    src = {
      url = "github:smp46/pingvin-share-x";
      flake = false;
    };
  };

  outputs =
    {
      nixpkgs,
      nixpkgs-prisma,
      src,
      ...
    }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      lib = pkgs.lib;
      engines = nixpkgs-prisma.legacyPackages.${system}.prisma-engines;
      nodejs = pkgs.nodejs_24;
      version = (lib.importJSON "${src}/package.json").version;

      prismaEnv = {
        PRISMA_QUERY_ENGINE_LIBRARY = "${engines}/lib/libquery_engine.node";
        PRISMA_SCHEMA_ENGINE_BINARY = "${engines}/bin/schema-engine";
      };

      # importNpmLock replaces the direct dependencies' version ranges with
      # store paths, and npm rejects an override that differs from the direct
      # dependency's spec. "$name" refers to that spec.
      packageJSON =
        dir:
        let
          package = lib.importJSON "${src}/${dir}/package.json";
          direct = (package.dependencies or { }) // (package.devDependencies or { });
        in
        package
        // lib.optionalAttrs (package ? overrides) {
          overrides = lib.mapAttrs (
            name: value: if lib.isString value && direct ? ${name} then "\$${name}" else value
          ) package.overrides;
        };

      npmPackage =
        dir: args:
        pkgs.buildNpmPackage (
          {
            pname = "pingvin-share-x-${dir}";
            inherit version nodejs;
            src = "${src}/${dir}";
            npmDeps = pkgs.importNpmLock {
              npmRoot = "${src}/${dir}";
              package = packageJSON dir;
            };
            npmConfigHook = pkgs.importNpmLock.npmConfigHook;
            NEXT_TELEMETRY_DISABLED = "1";
            SCARF_ANALYTICS = "false";
            dontNpmPrune = true;
          }
          // args
        );

      frontend = npmPackage "frontend" {
        installPhase = ''
          mkdir -p $out
          cp -r .next/standalone/. $out/
          cp -r .next/static $out/.next/static
          cp -r public $out/public
        '';
      };

      backend = npmPackage "backend" (
        prismaEnv
        // {
          buildPhase = ''
            runHook preBuild
            npx prisma generate
            npm run build
            npx tsc prisma/seed/config.seed.ts --outDir dist/prisma/seed --rootDir prisma/seed
            npm prune --omit=dev --offline
            runHook postBuild
          '';
          # Build-only packages that npm prune keeps, as upstream's Dockerfile
          # removes them, and sharp's musl builds.
          installPhase = ''
            rm -rf node_modules/typescript node_modules/esbuild node_modules/@esbuild \
              node_modules/@img/*linuxmusl*
            find node_modules/.bin -xtype l -delete
            mkdir -p $out
            cp -r node_modules dist prisma package.json tsconfig.json $out/
          '';
        }
      );

      image = pkgs.dockerTools.buildLayeredImage {
        name = "pingvin-share-x";
        tag = "latest";
        contents = [
          nodejs
          pkgs.busybox
          pkgs.getent
          pkgs.su-exec
          pkgs.caddy
          pkgs.curl
          pkgs.dockerTools.caCertificates
        ];
        # The layout of upstream's image. Copied rather than linked: the
        # entrypoint chowns the data and public directories.
        extraCommands = ''
          mkdir -p opt/app/scripts tmp home root
          chmod 1777 tmp
          cp -r ${frontend} opt/app/frontend
          cp -r ${backend} opt/app/backend
          cp -r ${src}/reverse-proxy opt/app/reverse-proxy
          cp -r ${src}/scripts/docker opt/app/scripts/docker
          cp -r ${frontend}/public/img tmp/img
          chmod -R u+w opt tmp/img
          echo 'root:x:0:0:root:/root:/bin/sh' > etc/passwd
          echo 'root:x:0:' > etc/group
          echo 'root:!::0:::::' > etc/shadow
        '';
        config = {
          Entrypoint = [
            "sh"
            "./scripts/docker/create-user.sh"
          ];
          Cmd = [
            "sh"
            "./scripts/docker/entrypoint.sh"
          ];
          WorkingDir = "/opt/app";
          ExposedPorts."3000/tcp" = { };
          Env = [
            "PATH=/bin"
            "NODE_ENV=docker"
            "SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt"
          ]
          ++ lib.mapAttrsToList (k: v: "${k}=${v}") prismaEnv;
          Healthcheck = {
            Test = [
              "CMD-SHELL"
              ''(if [ "$CADDY_DISABLED" = "true" ]; then curl -fs http://localhost:''${BACKEND_PORT:-8080}/api/health; else curl -fs http://localhost:3000/api/health; fi) || exit 1''
            ];
            Interval = 10 * 1000000000;
            Timeout = 3 * 1000000000;
            StartPeriod = 90 * 1000000000;
          };
        };
      };
    in
    {
      packages.${system} = {
        inherit frontend backend image;
        default = image;
      };
    };
}
