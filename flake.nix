{
  description = "The systems-engineering spec toolkit: the `spec` command, and a development environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-26.05";
  };

  outputs =
    { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f system);
    in
    {
      # `nix profile install <this repo>` puts `spec` on the PATH; `nix run <this repo> -- check` runs it once.
      packages = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          ps = pkgs.python3Packages;
        in
        rec {
          syseng = ps.buildPythonApplication {
            pname = "syseng";
            version = "0.1.0";
            pyproject = true;
            src = ./.;
            build-system = [ ps.hatchling ];
            dependencies = [ ps.pyyaml ps.pydantic ];
            pythonImportsCheck = [ "syseng" ];
            meta = {
              description = "Systems-engineering spec toolkit";
              mainProgram = "spec";
            };
          };
          default = syseng;
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.withPackages (ps: [
            ps.pyyaml
            ps.pydantic
            ps.pytest
          ]);
        in
        {
          default = pkgs.mkShell {
            name = "syseng-dev";
            packages = [ python ];
            # Run the CLI from source: `spec check`, `spec render`, ...
            shellHook = ''
              export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
              export PATH="$PWD/bin:$PATH"
            '';
          };
          # The skill evals: Node for the runner, in its own shell to keep the default one small.
          evals = pkgs.mkShell {
            name = "syseng-evals";
            packages = [ python pkgs.nodejs_22 ];
            shellHook = ''
              export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
              export PATH="$PWD/bin:$PATH"
            '';
          };
        }
      );
    };
}
